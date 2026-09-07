"""Versioned sequence operations; immutable source and execution snapshots."""
import copy
import json
import math
import secrets
import shutil
import threading
import time
import uuid
from pathlib import Path
from ..studio_store import Conflict
from ..studio_plan import geometry
from ..studio_recipes import defaults
from ..comfy import ComfyCancelled, ComfyError
from . import compiler, media, track, source_parameters
from .references import References

ACTIVE = {'preparing','submitting','running','unknown'}


def uid(): return uuid.uuid4().hex


def number(value, low, high, label):
    if isinstance(value,bool): raise ValueError(label+'须为数字')
    n=float(value)
    if not math.isfinite(n) or not low<=n<=high: raise ValueError(f'{label}须为{low}～{high}')
    return n


def dump(path, value):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


class Assembly(References):
    def __init__(self, studio, library, recover=False):
        self.st,self.lib,self.store=studio,library,studio.store
        self.lock=threading.RLock();self.controls={}
        self.st.jobs.gpu_guards.append(self.gpu_guard)
        if recover:
            for p in self.projects():
                changed=False
                for r in p['assembly']['runs']:
                    if r['state'] in ACTIVE and r['state']!='unknown':
                        r['state']='unknown' if r['kind']=='generate' else 'cancelled'
                        r['error']='网站重启，请核对原提交后恢复；不会自动重试' if r['kind']=='generate' else '网站重启，本地处理已中断，原件保留'
                        if r['state']=='cancelled': r['finished']=time.time()
                        changed=True
                if changed:
                    p['status']='interrupted';self.store.save(p,p['revision'])

    def projects(self):
        return [p for p in self.store.list()+self.store.list(trash=True) if p['mode']=='video_assembly']

    def gpu_guard(self,kind,pid):
        return not any(p['id']!=pid and any(r['kind']=='generate' and r['state'] in ACTIVE for r in p['assembly']['runs']) for p in self.projects())

    def get(self,pid):
        p=self.store.get(pid)
        if p['mode']!='video_assembly': raise ValueError('不是视频接续项目')
        return p

    def checked(self,pid,revision,idle=True):
        p=self.get(pid)
        if p['revision']!=revision: raise Conflict('项目已更新，请刷新后重试；原草稿保留')
        if idle and (self.st.jobs.is_busy(pid) or any(r['state'] in ACTIVE for r in p['assembly']['runs'])):
            raise Conflict('该项目有运行或待确认任务，请先处理后再修改')
        return p

    def create(self,name):
        return self.store.create(dict(name=str(name or '视频接续')[:120],mode='video_assembly',kind='assembly',
            status='draft',duration=0,segments=[],settings={},export=None,changes=[],error=None,
            assembly=dict(version=1,draft_revision=1,clips=[],runs=[],output=dict(width=1280,height=720,fps=24,fit='contain'),canvas_set=False)))

    def snapshot(self,pid):
        p=self.get(pid);p['assembly_contract_version']=1;p['busy']=self.st.jobs.is_busy(pid)
        for c in p['assembly']['clips']:
            c['url']=self.st.url(pid,c['file'])
            if c.get('cover'): c['cover_url']=self.st.url(pid,c['cover'])
            c['source_parameters']=source_parameters.for_clip(self.lib,c)
        for r in p['assembly']['runs']:
            if r.get('file'): r['url']=self.st.url(pid,r['file'])
            r['source_parameters']=source_parameters.parameter_records(r)
        p['duration']=self.duration(p)
        self.reference_snapshot(p)
        p['assembly_reference_version']=1
        p['assembly_track_version']=1
        p['assembly_source_parameters_version']=1
        p['assembly_tail_preparation_version']=2
        p['assembly']['track_order']=track.order(p)
        return p

    def duration(self,p):
        total=0
        for c in p['assembly']['clips']:
            if c.get('removed_at'): continue
            total+=c['end']-c['start']
            for e in c['extensions']:
                if not e.get('removed_at'):
                    r=self.find_run(p,e.get('selected'),required=False)
                    total+=r['report']['duration'] if r and r.get('report') else float(e['seconds'])
        return total

    def find_clip(self,p,cid):
        c=next((c for c in p['assembly']['clips'] if c['id']==cid),None)
        if not c: raise ValueError('片段不属于本项目')
        return c

    def find_extension(self,p,eid):
        for c in p['assembly']['clips']:
            for e in c['extensions']:
                if e['id']==eid:
                    if c.get('removed_at') or e.get('removed_at'): raise ValueError('请先恢复所属片段或续写段')
                    return c,e
        raise ValueError('续写段不属于本项目')

    def find_run(self,p,rid,required=True):
        r=next((r for r in p['assembly']['runs'] if r['id']==rid),None)
        if not r and required: raise ValueError('记录不属于本项目')
        return r

    def path(self,pid,value):
        path=Path(value).resolve()
        if self.store.directory(pid).resolve() not in path.parents or not path.is_file():
            raise ValueError('项目媒体缺失或不属于当前项目')
        return path

    def import_video(self,pid,revision,upload=None,reference=None):
        with self.lock:
            p=self.checked(pid,revision);cid=uid();rid=uid()
            directory=self.store.directory(pid)/'assembly'/'sources';directory.mkdir(parents=True,exist_ok=True)
            if reference:
                item=self.lib.store.get(reference['asset'],reference['version'])
                if item.get('deleted'): raise ValueError('请先恢复资产')
                entry=next((m for m in item['snapshot']['media'] if m['id']==reference['media']),None)
                if not entry: raise ValueError('视频不属于所选固定资产版本')
                obj=self.lib.store.object(entry['hash'])
                if obj['kind']!='video': raise ValueError('这里只能导入视频')
                source=self.lib.store.path(obj['path']);name=item['name'];suffix=obj['extension']
                provenance=dict(type='library',asset=item['id'],version=item['snapshot']['id'],media=entry['id'],hash=entry['hash'])
            else:
                if upload is None: raise ValueError('请选择视频文件')
                name=Path(upload.filename.replace(chr(92),'/')).name;suffix=Path(name).suffix.lower()
                provenance=dict(type='local',name=name)
            source_records=source_parameters.from_library(self.lib,provenance)
            if suffix.lower() not in ('.mp4','.mov','.mkv','.webm','.avi','.m4v','.mpeg','.mpg'):
                raise ValueError('请选择MP4、MOV、MKV、WebM等视频文件')
            destination=directory/(cid+suffix);event=threading.Event();self.controls[rid]=event
            p['assembly']['runs'].append(dict(id=rid,kind='import',state='preparing',created=time.time(),started=time.time(),finished=None,
                                              seed=None,tasks=[],snapshot=dict(source=provenance),note='导入视频与读取媒体信息',error=None))
            p['status']='preparing';self.store.save(p,revision)
        def prepare():
            stream=Path(source).open('rb') if reference else upload.stream
            try:
                with destination.open('wb') as target:
                    while True:
                        if event.is_set(): raise media.Cancelled('已取消导入，原视频保留')
                        block=stream.read(1024*1024)
                        if not block: break
                        target.write(block)
            finally:
                if reference: stream.close()
            meta=media.inspect(destination,event);provenance['sha256']=media.digest(destination)
            cover=directory/(cid+'.jpg')
            media.command(['ffmpeg','-nostdin','-y','-v','error','-i',destination,'-frames:v','1','-vf','scale=240:-2',cover],event)
            with self.lock:
                if event.is_set(): raise media.Cancelled('已取消导入，原视频保留')
                current=self.get(pid)
                current['assembly']['clips'].append(dict(id=cid,name=name,file=str(destination),cover=str(cover),start=0.,end=meta['duration'],meta=meta,provenance=provenance,source_parameters=source_records,extensions=[]))
                if not current['assembly']['canvas_set']:
                    current['assembly']['output'].update(width=math.ceil(meta['width']/2)*2,height=math.ceil(meta['height']/2)*2)
                    current['assembly']['canvas_set']=True
                self.find_run(current,rid).update(state='success',finished=time.time(),note='视频已导入')
                current.update(status='draft',duration=self.duration(current));self.store.save(current,current['revision'])
        try:
            self.st.jobs.run_inline('assembly_import',pid,prepare)
        except Exception as error:
            self.update_run(pid,rid,state='cancelled' if isinstance(error,media.Cancelled) else 'failed',error=str(error),finished=time.time())
            raise
        finally: self.controls.pop(rid,None)
        return self.snapshot(pid)

    def invalidate(self,clip,after=-1):
        for e in clip['extensions'][after+1:]: e['selected']=None

    def save(self,pid,data):
        with self.lock,self.store.lock:
            p=self.get(pid);a=p['assembly'];items=data['clips']
            track_order=track.validate(data['track_order'],track.order(p)) if 'track_order' in data else None
            if 'draft_revision' in data:
                if data['draft_revision']!=a.get('draft_revision',1):raise Conflict('制作草稿已被其他页面修改，请核对后重新保存')
            elif p['revision']!=data['revision']:raise Conflict('项目已更新，请刷新后重试')
            active=[c for c in a['clips'] if not c.get('removed_at')]
            if len(items)!=len(active) or {c['id'] for c in items}!={c['id'] for c in active}:
                raise Conflict('保存不能增删或恢复片段，请使用对应操作')
            order=[]
            for item in items:
                c=self.find_clip(p,item['id']);start=number(item['start'],0,c['meta']['duration'],'起点')
                end=number(item['end'],0,c['meta']['duration'],'终点')
                if end<=start: raise ValueError('终点须大于起点')
                if (start,end)!=(c['start'],c['end']): self.invalidate(c)
                c.update(start=start,end=end,name=str(item.get('name',c['name']))[:160])
                drafts=item.get('extensions',[])
                existing=[e for e in c['extensions'] if not e.get('removed_at')]
                if [e['id'] for e in drafts]!=[e['id'] for e in existing]: raise Conflict('续写段顺序已变化，请刷新')
                for draft,e in zip(drafts,existing):
                    recipe=draft['recipe']
                    configs={k:compiler.settings(self.st.recipes,v) for k,v in draft['configurations'].items()}
                    if set(configs)!=set(compiler.RECIPES) or any(v['recipe']!=k for k,v in configs.items()) or recipe not in configs:
                        raise ValueError('续接配方草稿不完整')
                    seconds=number(draft['seconds'],1,3600,'新增时长');compiler.plan(seconds,configs[recipe]['render_cap'])
                    seed=str(draft.get('seed','0'))
                    if not seed.isascii() or not seed.isdigit() or int(seed)>9007199254740991: raise ValueError('种子须为0～9007199254740991的整数')
                    if draft['seed_mode'] not in ('fixed','random'): raise ValueError('种子模式无效')
                    if draft.get('sound','native') not in ('native','mute'): raise ValueError('声音选项无效')
                    e['references']=self.reference_bindings(p,draft.get('references',e.get('references',[])))
                    e.update(recipe=recipe,configurations=configs,prompt=str(draft['prompt'])[:50000],seconds=seconds,
                             seed_mode=draft['seed_mode'],seed=seed,sound=draft.get('sound','native'))
                    self.reference_assets(p,e)
                order.append(c)
            output=copy.deepcopy(data['output'])
            for key in ('width','height'):
                value=number(output[key],2,8192,'输出尺寸')
                if value%2: raise ValueError('输出宽高须为偶数')
                output[key]=int(value)
            if output['fps'] not in (24,25,30,50,60) or output['fit'] not in ('contain','cover'): raise ValueError('导出规格无效')
            a.update(output=output,clips=order+[c for c in a['clips'] if c.get('removed_at')])
            if track_order is not None:
                # A range edit may invalidate selected descendants in this save.
                available=set(track.order(p))
                a['track_order']=[key for key in track_order if key in available]
            p.update(name=str(data.get('name',p['name']))[:120],duration=self.duration(p))
            a['draft_revision']=a.get('draft_revision',1)+1
            self.store.save(p,p['revision']);return self.snapshot(pid)

    def add_extension(self,pid,data):
        with self.lock:
            p=self.checked(pid,data['revision']);c=self.find_clip(p,data['clip'])
            if c.get('removed_at'): raise ValueError('请先恢复片段')
            c['extensions'].append(dict(id=uid(),prompt='',seconds=5,recipe='dance_split',seed_mode='random',seed='0',sound='native',selected=None,
                                        configurations={k:defaults(k) for k in compiler.RECIPES}))
            self.store.save(p,data['revision']);return self.snapshot(pid)

    def visibility(self,pid,data):
        with self.lock:
            p=self.checked(pid,data['revision']);removed=data.get('removed',True)
            if not isinstance(removed,bool): raise ValueError('移除状态必须是布尔值')
            kind=data['kind']
            if kind=='clip':
                target=self.find_clip(p,data['id']);self.invalidate(target)
            elif kind=='extension':
                c=next((c for c in p['assembly']['clips'] if any(e['id']==data['id'] for e in c['extensions'])),None)
                if not c or c.get('removed_at'): raise ValueError('请先恢复所属片段')
                target=next(e for e in c['extensions'] if e['id']==data['id'])
                target['selected']=None;self.invalidate(c,c['extensions'].index(target))
            elif kind=='run':
                target=self.find_run(p,data['id'])
                if target['kind']=='generate': self.find_extension(p,target['extension'])
                if removed and (target['state'] in ACTIVE or any(e.get('selected')==target['id'] for c in p['assembly']['clips'] for e in c['extensions']) or any(r['state'] in ACTIVE and target['id'] in json.dumps(r.get('snapshot',{})) for r in p['assembly']['runs'])):
                    raise Conflict('当前选用或运行中的结果不能移除')
            else: raise ValueError('记录类型无效')
            if removed: target['removed_at']=time.time()
            else: target.pop('removed_at',None)
            self.store.save(p,data['revision']);return self.snapshot(pid)

    def source(self,p,eid):
        c,e=self.find_extension(p,eid);source=dict(file=c['file'],start=c['start'],end=c['end'],origin=copy.deepcopy(c['provenance']))
        for previous in c['extensions']:
            if previous['id']==eid: break
            if previous.get('removed_at'): continue
            r=self.find_run(p,previous.get('selected'),False)
            if not r or r['state']!='success' or r.get('removed_at'): raise ValueError('请先选用前一续写段结果')
            source=dict(file=r['file'],start=0,end=r['report']['duration'],origin=dict(candidate=r['id']))
        self.path(p['id'],source['file'])
        source['sha256']=media.digest(source['file'])
        return source

    def select(self,pid,data):
        with self.lock:
            p=self.checked(pid,data['revision']);c,e=self.find_extension(p,data['extension']);r=self.find_run(p,data['run'])
            if r.get('extension')!=e['id'] or r['state']!='success' or r.get('removed_at'): raise ValueError('请选择当前续写段的可用候选')
            if r['snapshot']['source']!=self.source(p,e['id']): raise Conflict('候选的前置视频已变化，请重生成或恢复原输入')
            order=track.order(p)
            if e['selected']!=r['id']:
                self.invalidate(c,c['extensions'].index(e))
                p['assembly']['draft_revision']=p['assembly'].get('draft_revision',1)+1
            e['selected']=r['id']
            p['assembly']['track_order']=order
            p['assembly']['track_order']=track.order(p)
            self.store.save(p,data['revision']);return self.snapshot(pid)

    def parts(self,p):
        parts={}
        for c in p['assembly']['clips']:
            if c.get('removed_at'): continue
            parts['clip:'+c['id']]=dict(file=str(self.path(p['id'],c['file'])),start=c['start'],end=c['end'],origin=c['provenance'])
            for e in c['extensions']:
                if e.get('removed_at'): continue
                r=self.find_run(p,e.get('selected'),False)
                if not r or r['state']!='success' or r.get('removed_at'): raise ValueError('还有续写段未选用，请先选用或移除该续写段')
                if r['snapshot']['source']!=self.source(p,e['id']): raise Conflict('续写段前置来源已变化，请重新选用')
                parts['extension:'+e['id']]=dict(file=str(self.path(p['id'],r['file'])),start=0,end=r['report']['duration'],candidate=r['id'])
        if not parts: raise ValueError('请先导入视频')
        parts=[parts[key] for key in track.order(p)]
        for part in parts:part['sha256']=media.digest(part['file'])
        return parts

    def preflight(self,pid,eid):
        p=self.get(pid);c,e=self.find_extension(p,eid);source=self.source(p,eid)
        if source['end']-source['start']<1-.001: raise ValueError('AI续接需要至少1秒有效片尾')
        s=e['configurations'][e['recipe']];parts=compiler.plan(e['seconds'],s['render_cap'])
        result=compiler.compile_tail(self.st.recipes,pid,eid,s,parts[0],int(e['seed']),e['prompt'],
                 dict(kind='external_decoded_av',frame_count=22,video='__prepared_tail__.mkv',audio='__prepared_tail__.wav'),'preview',assets=self.reference_assets(p,e))
        return dict(input_inventory=result['input_inventory'],parts=parts,added_seconds=sum(x['deliver'] for x in parts)/24,issues=result['issues'],
                    bindings=result['bindings'],adapter_revision=1,validation='离线编译；未提交生成')

    def start(self,pid,data,kind):
        with self.lock:
            p=self.checked(pid,data['revision']);rid=uid()
            if kind=='generate':
                if self.st.ctx['cfg'].get('studio_disable_generation'): raise ValueError('该隔离环境禁止真实生成')
                _,e=self.find_extension(p,data['extension']);self.preflight(pid,e['id'])
                snapshot=dict(extension=copy.deepcopy(e),source=self.source(p,e['id']),assets=self.reference_assets(p,e),tail_preparation=media.TAIL_PREPARATION)
                seed=int(e['seed']) if e['seed_mode']=='fixed' else secrets.randbelow(9007199254740992)
            else: snapshot=dict(parts=self.parts(p),output=copy.deepcopy(p['assembly']['output']));seed=None
            run=dict(id=rid,kind=kind,state='preparing',created=time.time(),started=time.time(),finished=None,
                     extension=data.get('extension'),seed=seed,snapshot=snapshot,tasks=[],note='准备续接' if kind=='generate' else '准备拼接',error=None)
            p['assembly']['runs'].append(run);p['status']='generating' if kind=='generate' else 'assembling'
            self.store.save(p,data['revision'])
            event=threading.Event();self.controls[rid]=event
            if not self.st.jobs.start('assembly_'+kind,pid,lambda:self.worker(pid,rid,event),lane='gpu' if kind=='generate' else 'media'):
                self.controls.pop(rid,None);self.update_run(pid,rid,state='failed',error='处理通道忙碌，请稍后重试',finished=time.time())
                raise Conflict('处理通道忙碌，请稍后重试')
            return self.snapshot(pid)

    def update_run(self,pid,rid,**values):
        def change(p):
            self.find_run(p,rid).update(values)
            p['status']='interrupted' if values.get('state')=='unknown' else 'failed' if values.get('state')=='failed' else 'complete' if values.get('state')=='success' else 'draft' if values.get('state')=='cancelled' else p['status']
        self.store.mutate(pid,change)

    def worker(self,pid,rid,cancel):
        try:
            r=copy.deepcopy(self.find_run(self.get(pid),rid));directory=self.store.directory(pid)/'assembly'/'runs'/rid
            directory.mkdir(parents=True,exist_ok=True);dump(directory/'manifest.json',r)
            progress=lambda note:self.update_run(pid,rid,note=note)
            if r['kind']=='export':
                file,report=media.assemble(r['snapshot']['parts'],directory,r['snapshot']['output'],cancel,progress)
            else: file,report=self.generate(pid,r,directory,cancel,progress)
            if cancel.is_set(): raise media.Cancelled('已停止，未发布未完成结果')
            self.update_run(pid,rid,state='success',file=file,report=report,finished=time.time(),note='已完成',error=None)
        except (media.Cancelled,ComfyCancelled) as error:
            self.update_run(pid,rid,state='cancelled',error=str(error),finished=time.time())
        except Exception as error:
            latest=self.find_run(self.get(pid),rid)
            uncertain=latest['state'] in ('submitting','running') and latest['kind']=='generate'
            self.update_run(pid,rid,state='unknown' if uncertain else 'failed',error=str(error),
                            error_kind='engine' if isinstance(error,ComfyError) else 'compile' if str(error).startswith('工作流检查失败') else 'website',
                            finished=None if uncertain else time.time())
        finally: self.controls.pop(rid,None)

    def generate(self,pid,run,directory,cancel,progress):
        # Explicit user action only. Never call the engine launcher/start process.
        r=run;rid=r['id'];e=r['snapshot']['extension'];s=e['configurations'][e['recipe']]
        assets=copy.deepcopy(r['snapshot'].get('assets',[]))
        for asset in assets:
            self.path(pid,asset['path'])
            if media.digest(asset['path'])!=asset['sha256']: raise ValueError('参考素材与运行快照不一致')
        self.st.prepare_execution_inputs(pid,{},assets)
        self.st.recipes.connect()
        source=copy.deepcopy(r['snapshot']['source']);plans=compiler.plan(e['seconds'],s['render_cap']);parts=[]
        tasks=copy.deepcopy(r['tasks'])
        for index,part in enumerate(plans):
            if cancel.is_set(): raise media.Cancelled('已停止后续续接')
            if index<len(tasks) and tasks[index].get('file'):
                task=tasks[index];parts.append(dict(file=task['file'],start=0,end=part['deliver']/24))
                source=dict(file=task['file'],start=0,end=part['deliver']/24);continue
            progress(f'准备声画尾部 · 内部任务 {index+1}/{len(plans)}')
            if media.digest(source['file'])!=r['snapshot']['source']['sha256'] and index==0: raise ValueError('原输入文件已改变，拒绝用新文件替代运行快照')
            size=geometry(s);input_dir=self.st.input/'time_forest_assembly'/pid/rid/str(index)
            context=media.tail(source['file'],source['start'],source['end'],input_dir,size['width'],size['height'],self.st.input,cancel,
                               preparation=r['snapshot'].get('tail_preparation','legacy_contain_v1'))
            compiled=compiler.compile_tail(self.st.recipes,pid,e['id'],s,part,r['seed'],e['prompt'],context,rid+'/'+str(index),assets=assets)
            if compiled['issues']: raise ValueError('工作流检查失败：'+'；'.join(compiled['issues']))
            dump(directory/f'workflow-{index}.json',compiled)
            task=tasks[index] if index<len(tasks) else dict(index=index)
            if index==len(tasks): tasks.append(task)
            if not task.get('prompt_id'):
                queue=self.st.comfy._get('/queue')
                if queue.get('queue_running') or queue.get('queue_pending'): raise Conflict('ComfyUI已有任务，未提交本次续接')
                task['client_id']='time-forest-'+rid+'-'+str(index)
                with self.lock:
                    if cancel.is_set():raise media.Cancelled('已停止，未提交新的续接任务')
                    self.update_run(pid,rid,state='submitting',tasks=tasks,note=f'提交续接 {index+1}/{len(plans)}')
                task['prompt_id']=self.st.comfy.submit(compiled['workflow'],task['client_id'])
                self.update_run(pid,rid,state='running',tasks=tasks,prompt_id=task['prompt_id'],client_id=task['client_id'],note=f'生成续接 {index+1}/{len(plans)}')
            self.update_run(pid,rid,state='running',tasks=tasks,prompt_id=task['prompt_id'],client_id=task['client_id'])
            history=self.st.comfy.wait(task['prompt_id']);dump(directory/f'history-{index}.json',history)
            self.update_run(pid,rid,state='preparing',note='回收声画结果')
            raw=self.st.comfy.first_video(history,task['prompt_id'],compiled['output_node'],self.st.output)
            meta=media.inspect(raw,cancel)
            if not meta['audio'] or meta['duration']+.02<(part['head']+part['deliver'])/24: raise ValueError('生成结果缺少原生声音或有效帧，未发布候选')
            self.update_run(pid,rid,state='preparing',note='裁除上下文，保留新增声画')
            part_file,report=media.assemble([dict(file=str(raw),start=22/24,end=(22+part['deliver'])/24,mute=e['sound']=='mute')],
                directory/f'part-{index}',dict(width=meta['width'],height=meta['height'],fps=24,fit='contain'),cancel)
            task.update(file=part_file,report=report);self.update_run(pid,rid,tasks=tasks)
            parts.append(dict(file=part_file,start=0,end=report['duration']))
            source=dict(file=part_file,start=0,end=report['duration'])
        meta=media.inspect(parts[0]['file'],cancel)
        return media.assemble(parts,directory/'delivery',dict(width=meta['width'],height=meta['height'],fps=24,fit='contain'),cancel,progress)

    def control(self,pid,rid,action):
        with self.lock:
            p=self.get(pid);r=self.find_run(p,rid)
            if r['state'] not in ACTIVE: raise Conflict('任务已结束，请刷新')
            if action=='stop':
                event=self.controls.get(rid)
                if not event: raise Conflict('原执行状态待确认，请先查询恢复')
                if r['state']=='submitting': raise Conflict('正在提交，等待引擎编号后再停止')
                if r['kind']=='generate' and r['state']=='running':
                    queue=self.st.comfy._get('/queue');owned=[v for v in queue.get('queue_running',[])+queue.get('queue_pending',[]) if len(v)>1 and v[1]==r.get('prompt_id')]
                    if not owned or any(len(v)<4 or v[3].get('client_id')!=r.get('client_id') for v in owned): raise Conflict('无法核对当前引擎任务归属，未中断其他任务')
                    if not self.st.comfy.cancel_job(r['prompt_id']): raise Conflict('任务已离开队列，请等待结果回收')
                event.set();self.update_run(pid,rid,note='停止已请求，保留已完成结果');return
            if self.st.jobs.is_busy(pid): raise Conflict('执行线程仍在处理，请稍后')
            if r['state']!='unknown': raise Conflict('没有待确认提交')
            queue=self.st.comfy._get('/queue');queued=queue.get('queue_running',[])+queue.get('queue_pending',[])
            tasks=r['tasks'];task=tasks[-1] if tasks else None
            if task and not task.get('prompt_id'):
                found=[v for v in queued if len(v)>3 and v[3].get('client_id')==task.get('client_id')]
                if found: task['prompt_id']=found[0][1];self.update_run(pid,rid,tasks=tasks)
            prompt=task.get('prompt_id') if task else None
            history=self.st.comfy._get('/history/'+prompt) if prompt else {}
            if action=='close':
                if prompt and (history.get(prompt) or any(len(v)>1 and v[1]==prompt for v in queued)): raise Conflict('找到原提交，请查询恢复，不要结束等待')
                self.update_run(pid,rid,state='cancelled',finished=time.time(),note='用户结束等待；原提交结果未确认，快照保留');return
            if action!='recover' or not prompt: raise Conflict('缺少可追踪的原提交编号；核对后可结束等待，系统不会自动重试')
            record=history.get(prompt)
            if record and record.get('status',{}).get('status_str')=='error':
                self.update_run(pid,rid,state='failed',finished=time.time(),error=json.dumps(record['status'],ensure_ascii=False));return
            if not record and not any(len(v)>1 and v[1]==prompt for v in queued): raise Conflict('尚未找到原提交，未重新生成')
            if self.st.ctx['cfg'].get('studio_disable_generation'): raise ValueError('隔离环境禁止恢复生成执行')
            self.update_run(pid,rid,state='running',prompt_id=prompt,client_id=task['client_id'],tasks=tasks)
            event=threading.Event();self.controls[rid]=event
            if not self.st.jobs.start('assembly_generate',pid,lambda:self.worker(pid,rid,event),lane='gpu'):
                self.controls.pop(rid,None);self.update_run(pid,rid,state='unknown');raise Conflict('生成通道忙碌')

    def ingest(self,pid,data):
        with self.lock:
            p=self.checked(pid,data['revision']);r=self.find_run(p,data['run'])
            if r['state']!='success' or r.get('removed_at') or r['kind'] not in ('generate','export'): raise ValueError('请选择未移除的成功结果')
            if r['kind']=='generate': self.find_extension(p,r['extension'])
            path=self.path(pid,r['file'])
            result=self.lib.ingest(path,p['name']+(' · 续接' if r['kind']=='generate' else ' · 成片'),
                provenance=dict(type='generated',project=pid,candidate=r['id'],mode='video_assembly',seed=r['seed'],snapshot=r['snapshot'],tasks=r['tasks']),
                key='assembly-output:'+pid+':'+r['id'])
            r['asset']=result['id'];self.store.save(p,p['revision']);return dict(asset=result['id'],project=self.snapshot(pid))
