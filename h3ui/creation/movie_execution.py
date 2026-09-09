"""One prepared movie segment per H3 submission; fake terminal is injectable."""
import copy
import math
import secrets
import threading
import time
import shutil
from pathlib import Path
from .contracts import digest,request_contract,read,validate
from .service import uid
from .providers import ProviderError
from . import plans
from ..studio_store import Conflict
from ..studio_plan import aligned,geometry
from ..studio_recipes import RECIPES,SOURCES
from ..studio_inputs import validate_tags,inventory,validate as validate_inputs
from ..studio_media import digest as file_digest
from ..video_assembly import media,compiler

ACTIVE={'queued','preparing','submitting','running','cancel_requested','submission_unknown'}


class Execution:
    def __init__(self,movie):
        self.m=movie;self.c=movie.c;self.st=self.c.st;self.store=self.c.store
        self.controls={};self.backend=None;self.tail=media.tail;self.assemble=media.assemble

    def path(self,p,take):
        record=p.get('movie_media',{}).get(take['media']['media_id'])
        if not record:raise ValueError('生成媒体记录缺失')
        path=(self.store.directory(p['id'])/record['relative_path']).resolve()
        if not path.is_relative_to(self.store.directory(p['id']).resolve()) or not path.is_file() or file_digest(path)!=take['media']['content_hash']:raise ValueError('生成原件缺失或已改变')
        return path

    def preflight(self,pid,data):
        request_contract('GenerationPreflight',data);p=self.m.checked(pid,data);sid=data['segment_id'];bundle,source=self.m.frozen(p,sid);draft=self.m.draft(p,sid)
        from .movie import PROFILE_RECIPES
        profile=PROFILE_RECIPES[draft['profile_id']];settings=self.st.recipes.normalize(dict(draft['parameter_overrides'],recipe=profile['recipe']),'image_story')
        issues=[];segment=source['segment'];tail=segment.get('dependency',{}).get('kind')=='upstream_tail'
        if tail!=(profile['context_kind']=='external_decoded_av'):issues.append('工作流输入类型与剧本的续接关系不一致，请回剧本页核对')
        if bundle['ready_state']!='ready':issues.append('正式 Prompt 尚未确认，请回剧本第五页确认')
        if source['prompt'].get('prompt_mode')!=profile['prompt_mode']:issues.append('正式 Prompt 格式与工作流不一致，请回剧本页转换并确认')
        prompt_value=source['prompt'].get('payload',{});prompt=prompt_value.get('prompt_text','') if profile['prompt_mode']=='full' else prompt_value.get('fields',{}).get('prompt','')
        if not prompt.strip():issues.append('缺少正式片段 Prompt')
        seconds=segment.get('planned_seconds');head=22 if tail else 0;deliver=round(float(seconds or 0)*24)
        raw=max(124,aligned(deliver+head));cap=min(360,int(float(settings['render_cap'])*24))
        if deliver<=0 or raw>cap:issues.append('计划时长超出一次 H3 生成范围，请回剧本页调整或拆分片段；电影页不会暗中拆分')
        frame_plan=dict(fps_num=24,fps_den=1,raw=raw,head=head,deliver=deliver,tail=max(0,raw-head-deliver))
        assets=[]
        for r in source['references']:
            if r['id'] not in draft['reference_ids']:continue
            fixed=r['library_reference']
            _,m,obj=self.c.references.fixed(fixed['asset'],fixed['version'],fixed['media']);path=self.c.library.store.path(obj['path'])
            if file_digest(path)!=fixed['hash']:raise ValueError('参考原件已改变')
            assets.append(dict(id=r['id'],name=r['name'],kind=r['kind'],purpose=r['purpose'],subject=r.get('subject',''),path=str(path),sha256=fixed['hash'],library_reference=fixed,input_name='time_forest_movie/'+pid+'/refs/'+fixed['hash']+obj['extension'],duration=obj.get('duration',0)))
        for b in source['bindings']:
            if b['state']=='pending':issues.append('仍有待落实的剧本资产')
            if b['state']=='bound' and not any(r['library_reference']['asset']==b['asset_ref'] and r['library_reference']['version']==b['asset_version'] for r in assets):issues.append('已绑定的剧本资产未进入本次输入')
        projection=dict(id=pid,mode='image_story',settings=settings)
        validate_inputs(projection,{},assets)
        if profile['prompt_mode']=='structured' and prompt.strip():
            from ..studio_prompts import build
            prompt=build(projection,dict(prompt_value.get('fields',{}),**{k:frame_plan[k] for k in ('raw','head','deliver','tail')},asset_mode='custom' if assets else 'none'),assets)
        validate_tags(prompt,inventory(projection,{},assets))
        upstream=None
        if tail:
            tid=draft['upstream_take_id']
            if not tid:issues.append('请明确选择上游片段的生成结果及尾部范围')
            else:
                take=self.m.take(p,tid)
                if take['movie_segment_id']!=segment['dependency']['upstream_ref'] or take['state']!='available':issues.append('上游结果不可用或来源不符')
                self.m.valid_range(take,draft['upstream_range']);path=self.path(p,take)
                if draft['upstream_range']['out_ms']-draft['upstream_range']['in_ms']<1000:issues.append('续接上下文至少需要1秒有效视频')
                upstream=dict(file=str(path),sha256=take['media']['content_hash'],range=draft['upstream_range'],take_id=tid,media=take['media'])
        result=dict(preflight_id=uid(),input_hash=digest([bundle,draft]),ready=not issues,issues=issues,inference_executed=False,source_bundle_id=bundle['bundle_id'],generation_draft_hash=digest(draft),frame_plan=frame_plan)
        return result,dict(bundle=bundle,source=source,draft=draft,settings=settings,assets=assets,prompt=prompt,frame_plan=frame_plan,upstream=upstream)

    def prepare(self,pid,data):
        request_contract('PrepareGeneration',data)
        with self.store.lock:
            p=self.c.get(pid,'movie');previous=next((r for r in p.get('movie_prepared',[]) if r['request_key']==data['request_key']),None)
            if previous:
                if previous['request_hash']!=digest(data):raise Conflict('准备请求标识已用于其他内容')
                return previous
            pf,values=self.preflight(pid,{k:v for k,v in data.items() if k in ('revision','request_key','segment_id')})
            if pf['source_bundle_id']!=data['source_bundle_id'] or pf['generation_draft_hash']!=data['generation_draft_hash']:raise Conflict('生成草稿已变化')
            if not pf['ready']:raise ValueError('；'.join(pf['issues']))
        rid=uid();directory=self.store.directory(pid)/'movie'/'prepared'/rid;directory.mkdir(parents=True,exist_ok=True)
        settings=values['settings'];frame_plan=values['frame_plan'];part={k:frame_plan[k] for k in ('raw','head','deliver','tail')};context=None
        if values['upstream']:
            up=values['upstream'];size=geometry(settings)
            context=self.tail(up['file'],up['range']['in_ms']/1000,up['range']['out_ms']/1000,directory,size['width'],size['height'],self.store.directory(pid))
            for k in ('video','audio'):context[k]='time_forest_movie/'+pid+'/'+context[k]
        seed=secrets.randbits(52)
        if context:compiled=compiler.compile_tail(self.st.recipes,pid,data['segment_id'],settings,part,seed,values['prompt'],context,rid,values['assets'])
        else:
            seg=dict(id=data['segment_id'],index=0,assets=[a['id'] for a in values['assets']],inherit_ids=[],asset_mode='custom' if values['assets'] else 'none',actual_seed=seed,seed=str(seed),**part)
            compiled=self.st.recipes.compile(dict(id=pid,mode='image_story',settings=settings),seg,values['assets'],values['prompt'],attempt=rid)
        if compiled['issues']:raise ValueError('工作流检查失败：'+'；'.join(compiled['issues']))
        sourcehash=file_digest(SOURCES/RECIPES[settings['recipe']]['source'])
        inputs=[dict(reference_key=a['id'],media=dict(media_id=a['library_reference']['media'],version=a['library_reference']['version'],content_hash=a['sha256']),usage=a['purpose'],range=None) for a in values['assets']]
        if values['upstream']:inputs.append(dict(reference_key='upstream',media=values['upstream']['media'],usage='external_decoded_av',range=values['upstream']['range']))
        snapshot=dict(snapshot_id=uid(),movie_id=pid,segment_id=data['segment_id'],source_bundle_id=values['bundle']['bundle_id'],profile_id=values['draft']['profile_id'],profile_revision='1',workflow_source_hash=sourcehash,adapter_revision='movie-1',prompt_mode=values['source']['prompt']['prompt_mode'],actual_prompt_text=values['prompt'],actual_prompt_hash=digest(values['prompt']),parameters=dict(settings,actual_seed=seed),inputs=inputs,upstream_take_id=values['draft']['upstream_take_id'],frame_plan=frame_plan,prepared_artifacts=[rid])
        validate(snapshot,read('数据契约/generation-snapshot.schema.json'))
        record=dict(prepared_request_id=rid,request_key=data['request_key'],request_hash=digest(data),project_id=pid,source_bundle_id=values['bundle']['bundle_id'],generation_draft_hash=digest(values['draft']),snapshot=snapshot,compiled=compiled,assets=values['assets'],context=context,created=time.time())
        record['prepared_hash']=digest(record)
        with self.store.lock:
            latest=self.c.get(pid)
            if self.m.bundle(latest,data['segment_id'])['bundle_id']!=record['source_bundle_id'] or digest(self.m.draft(latest,data['segment_id']))!=record['generation_draft_hash']:raise Conflict('准备期间草稿已更新，未替换新稿')
            latest.setdefault('movie_prepared',[]).append(record);self.store.save(latest,latest['revision'])
        return record

    def job(self,pid,data,kind,record,worker):
        with self.store.lock:
            p=self.c.get(pid,'movie');old=next((j for j in p['creation_jobs'] if j.get('request_key')==data['request_key']),None)
            if old:
                if old['request_hash']!=digest(data):raise Conflict('请求标识已用于其他执行')
                return old
            if p['revision']!=data['revision']:raise Conflict('项目已更新')
            if any(j['state'] in ACTIVE for j in p['creation_jobs']):raise Conflict('请先处理当前运行或待确认提交')
            jid=uid();job=dict(job_id=jid,kind=kind,project_id=pid,state='queued',phase='等待生成' if kind=='generation' else '等待导出',event_seq=1,candidate_ids=[],provider_request_id=None,failure_code=None,result_ref=None,inference_executed=False,request_key=data['request_key'],request_hash=digest(data),record=record,created=time.time(),updated=time.time())
            p['creation_jobs'].append(job);p['content']['job_ids'].append(jid);self.store.save(p,p['revision'])
        event=threading.Event();self.controls[jid]=event
        if not self.st.jobs.start('movie_'+kind,pid,lambda:self.worker(pid,jid,worker,event),lane='gpu' if kind=='generation' else 'media'):
            self.update(pid,jid,state='failed',phase='通道忙碌',failure_code='CHANNEL_BUSY');self.controls.pop(jid,None)
        return self.c.writing.find(jid,'creation_jobs')[1]

    def submit(self,pid,data):
        request_contract('SubmitGeneration',data);p=self.c.get(pid,'movie')
        old=next((j for j in p['creation_jobs'] if j.get('request_key')==data['request_key']),None)
        if old:
            if old['request_hash']!=digest(data):raise Conflict('请求标识已用于其他执行')
            return old
        record=next((r for r in p.get('movie_prepared',[]) if r['prepared_request_id']==data['prepared_request_id']),None)
        if not record or record['prepared_hash']!=data['prepared_hash']:raise Conflict('准备快照不存在或已变化')
        sid=record['snapshot']['segment_id']
        if self.m.bundle(p,sid)['bundle_id']!=record['source_bundle_id'] or digest(self.m.draft(p,sid))!=record['generation_draft_hash']:raise Conflict('准备后草稿已改变，请重新准备')
        if self.backend is None and self.st.ctx['cfg'].get('studio_disable_generation'):raise ProviderError('EXECUTION_FORBIDDEN','隔离环境禁止真实生成提交')
        return self.job(pid,data,'generation',record,self.generate)

    def update(self,pid,jid,**values):return self.c.writing.update_job(pid,jid,**values)

    def generate(self,p,j,event):
        r=j['record'];pid=p['id'];jid=j['job_id'];directory=self.store.directory(pid)/'movie'/'runs'/jid;directory.mkdir(parents=True,exist_ok=True)
        progress=lambda text:self.update(pid,jid,phase=text)
        if self.backend:return self.backend(p,r,directory,event,progress)
        for asset in r['assets']:
            if file_digest(asset['path'])!=asset['sha256']:raise ValueError('参考原件在准备后已改变，请重新准备')
        for item in r['snapshot']['inputs']:
            if item['reference_key']=='upstream':
                take=self.m.take(p,r['snapshot']['upstream_take_id']);self.path(p,take)
        self.st.prepare_execution_inputs(pid,{},r['assets'])
        if r['context']:
            for k in ('video','audio'):
                name=r['context'][k];relative=name.split('/'+pid+'/',1)[1];source=self.store.directory(pid)/relative
                if file_digest(source)!=r['context'][k+'_sha256']:raise ValueError('准备的上下文已改变')
                destination=self.st.input/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
        queue=self.st.comfy._get('/queue')
        if queue.get('queue_running') or queue.get('queue_pending'):raise Conflict('ComfyUI已有任务，本次尚未提交')
        if event.is_set():raise media.Cancelled('已取消')
        self.update(pid,jid,state='submitting',phase='提交 H3 片段')
        client='time-forest-movie-'+jid
        prompt_id=self.st.comfy.submit(r['compiled']['workflow'],client)
        self.update(pid,jid,state='running',phase='H3 正在生成',provider_request_id=prompt_id,client_id=client,inference_executed=True)
        history=self.st.comfy.wait(prompt_id)
        return self.collect(p,j,event,history,prompt_id,directory,progress)

    def collect(self,p,j,event,history,prompt_id,directory,progress):
        r=j['record'];pid=p['id'];jid=j['job_id']
        if event.is_set():raise media.Cancelled('已取消接收')
        raw=self.st.comfy.first_video(history,prompt_id,r['compiled']['output_node'],self.st.output);meta=media.inspect(raw,event);plan=r['snapshot']['frame_plan']
        if meta['duration']+.02<(plan['head']+plan['deliver'])/24 or not meta['audio']:raise ValueError('结果缺少有效帧或原生声音，未发布候选')
        self.update(pid,jid,state='preparing',phase='提取交付片段')
        return self.assemble([dict(file=str(raw),start=plan['head']/24,end=(plan['head']+plan['deliver'])/24)],directory,dict(width=meta['width'],height=meta['height'],fps=24,fit='contain'),event,progress)

    def resolve_unknown(self,jid,close=False):
        p,j=self.c.writing.find(jid,'creation_jobs')
        if p['mode']!='movie' or j['state']!='submission_unknown':raise Conflict('此任务没有待核对的提交')
        if jid in self.controls:raise Conflict('原处理仍在收尾，请稍后核对')
        if close:
            self.update(p['id'],jid,state='cancelled',phase='已结束等待；未确认的原提交不会重试',closed_without_result=True)
            return self.c.writing.find(jid,'creation_jobs')[1]
        if self.st.ctx['cfg'].get('studio_disable_generation'):raise ProviderError('EXECUTION_FORBIDDEN','隔离环境禁止查询真实生成引擎')
        prompt_id=j.get('provider_request_id')
        if not prompt_id:raise Conflict('原请求未取得引擎编号，无法安全定位；可以结束等待，网站不会重新提交')
        history=self.st.comfy._get('/history/'+prompt_id);record=history.get(prompt_id)
        if not record:raise Conflict('尚未取得原提交的完成记录，请稍后核对；未重新提交')
        submitted=record.get('prompt',[])
        if len(submitted)<4 or submitted[1]!=prompt_id or submitted[3].get('client_id')!=j.get('client_id'):raise Conflict('引擎记录归属无法核对，未接收其他任务结果')
        event=threading.Event();self.controls[jid]=event
        def collect(p,j,event):
            directory=self.store.directory(p['id'])/'movie'/'runs'/jid;directory.mkdir(parents=True,exist_ok=True)
            return self.collect(p,j,event,history,prompt_id,directory,lambda text:self.update(p['id'],jid,phase=text))
        if not self.st.jobs.start('movie_reconcile',p['id'],lambda:self.worker(p['id'],jid,collect,event),lane='gpu'):
            self.controls.pop(jid,None);raise Conflict('通道忙碌，请稍后核对；未重新提交')
        return self.c.writing.find(jid,'creation_jobs')[1]

    def worker(self,pid,jid,fn,event):
        try:
            p=self.c.get(pid);j=next(j for j in p['creation_jobs'] if j['job_id']==jid);self.update(pid,jid,state='running',phase='处理片段')
            if event.is_set():raise media.Cancelled('已取消')
            file,report=fn(p,j,event)
            if event.is_set():raise media.Cancelled('已取消，未发布未完成结果')
            path=Path(file).resolve();root=self.store.directory(pid).resolve()
            if not path.is_relative_to(root) or not path.is_file():raise ValueError('输出不属于当前项目')
            mid=uid();fixed=dict(media_id=mid,version=uid(),content_hash=file_digest(path));rid=uid()
            def complete(q):
                q.setdefault('movie_media',{})[mid]=dict(relative_path=path.relative_to(root).as_posix(),report=report)
                job=next(job for job in q['creation_jobs'] if job['job_id']==jid)
                if j['kind']=='generation':
                    snapshot=j['record']['snapshot'];q['artifacts'][snapshot['snapshot_id']]=snapshot
                    take=dict(take_id=rid,movie_segment_id=snapshot['segment_id'],job_id=jid,origin='generated',snapshot_id=snapshot['snapshot_id'],media=fixed,duration_ms=round(report['duration']*1000),state='available',currently_adopted=False,created_at=str(time.time()))
                    take['lineage']=dict(inputs=[copy.deepcopy(a['library_reference']) for a in j['record']['assets']],previous=dict(project=pid,run=snapshot['upstream_take_id']) if snapshot['upstream_take_id'] else None)
                    q.setdefault('movie_takes',[]).append(take);q['content']['take_ids'].append(rid)
                else:q.setdefault('movie_exports',[]).append(dict(export_id=rid,media=fixed,manifest=j['record'],duration_ms=round(report['duration']*1000),created_at=str(time.time())))
                job.update(state='succeeded',phase='已完成',result_ref=dict(kind='candidate' if j['kind']=='generation' else 'export',id=rid),candidate_ids=[rid] if j['kind']=='generation' else [],event_seq=job['event_seq']+1,updated=time.time())
            self.store.mutate(pid,complete)
        except Exception as exc:
            latest=self.c.writing.find(jid,'creation_jobs')[1]
            state='cancelled' if event.is_set() or isinstance(exc,media.Cancelled) else 'submission_unknown' if latest['state'] in ('submitting','running') and (latest.get('provider_request_id') or latest['state']=='submitting') else 'failed'
            self.update(pid,jid,state=state,phase='处理未完成',failure_code=getattr(exc,'code','EXECUTION_FAILED'),error=str(exc))
        finally:self.controls.pop(jid,None)

    def cancel(self,jid):
        p,j=self.c.writing.find(jid,'creation_jobs');event=self.controls.get(jid)
        if j['state'] not in ACTIVE:return j
        if not event:raise Conflict('原提交结果待确认；未重新提交或自动恢复')
        if j['state']=='submitting':raise Conflict('正在提交，请等引擎编号返回后再停止')
        if j.get('provider_request_id') and j['state']=='running':
            queue=self.st.comfy._get('/queue');owned=[x for x in queue.get('queue_running',[])+queue.get('queue_pending',[]) if len(x)>3 and x[1]==j['provider_request_id'] and x[3].get('client_id')==j.get('client_id')]
            if not owned:raise Conflict('无法核对引擎任务归属，未中断其他任务')
            if not self.st.comfy.cancel_job(j['provider_request_id']):raise Conflict('任务已离开队列，请等待结果')
        event.set();self.update(p['id'],jid,state='cancel_requested',phase='正在停止此任务');return self.c.writing.find(jid,'creation_jobs')[1]

    def export_preflight(self,pid,data):
        request_contract('ExportPreflight',data);p=self.m.checked(pid,data);edit=p['content']['edit'];parts=[];issues=[]
        if not edit['initialized_at']:issues.append('请先建立剪辑时间轴')
        for iid in edit['order']:
            item=next(i for i in edit['items'] if i['id']==iid)
            if not item['included']:continue
            take=self.m.take(p,item['take_id']);self.m.valid_range(take,item['range']);path=self.path(p,take)
            parts.append(dict(file=str(path),sha256=take['media']['content_hash'],start=item['range']['in_ms']/1000,end=item['range']['out_ms']/1000,item=copy.deepcopy(item)))
        if not parts:issues.append('没有纳入成片的片段')
        if data['edit_content_hash']!=digest(edit):raise Conflict('导出前剪辑已变化')
        output=data['output'];partial=len({i['item']['movie_segment_id'] for i in parts})<len(p['content']['segment_order'])
        if min(output['width'],output['height'])<16 or max(output['width'],output['height'])>8192 or output['width']%2 or output['height']%2:raise ValueError('导出尺寸须为16～8192之间的偶数')
        if output['fps_num']/output['fps_den'] not in (24,25,30,50,60):raise ValueError('请选择受支持的导出帧率')
        manifest=dict(manifest_id=uid(),movie_id=pid,movie_revision=p['revision'],items=[copy.deepcopy(x['item']) for x in parts],output=copy.deepcopy(output),accepted_seams=[],pending_summary=['部分剧本片段未纳入本次成片'] if partial else [])
        validate(manifest,read('数据契约/export-manifest.schema.json'))
        seams=self.m.seams(p)
        payload=dict(parts=parts,output=dict(width=output['width'],height=output['height'],fps=output['fps_num']/output['fps_den'],fit=output['fit']),edit_hash=digest(edit),partial=partial,export_manifest=manifest,seam_warnings=seams)
        plan=plans.make(self.store,p,'export',[],payload)
        return dict(preflight_id=plan['plan_id'],input_hash=plan['plan_hash'],ready=not issues,issues=issues,inference_executed=False,partial=partial,seam_warnings=seams)

    def export(self,pid,data):
        request_contract('CreateExport',data);p=self.c.get(pid,'movie')
        old=next((j for j in p['creation_jobs'] if j.get('request_key')==data['request_key']),None)
        if old:
            if old['request_hash']!=digest(data):raise Conflict('请求标识已用于其他导出')
            return old
        plan=plans.read(self.store,p,dict(plan_id=data['preflight_id'],plan_hash=data['preflight_hash']),'export');record=plan['payload']
        if not record['parts']:raise ValueError('没有可导出的片段')
        if record['partial'] and not data['confirmed_partial_export']:raise ValueError('本次只导出已纳入的部分剧本，请确认部分导出')
        expected={s['id'] for s in record.get('seam_warnings',[])}
        if set(data.get('accepted_seams',[]))!=expected:raise ValueError('请核对并明确接受本次剪辑的接点变化')
        record['export_manifest']['accepted_seams']=data.get('accepted_seams',[])
        return self.job(pid,data,'media_export',record,self.render_export)

    def render_export(self,p,j,event):
        for part in j['record']['parts']:
            if file_digest(part['file'])!=part['sha256']:raise ValueError('导出原件已变化，未发布不完整成片')
        return self.assemble(j['record']['parts'],self.store.directory(p['id'])/'movie'/'exports'/j['job_id'],j['record']['output'],event,lambda text:self.update(p['id'],j['job_id'],phase=text))
