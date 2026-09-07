"""Time Forest v5 application service and API, isolated from legacy projects."""
import copy,hashlib,json,os,shutil,threading,time,uuid
from pathlib import Path
from flask import Blueprint,current_app,jsonify,request,send_from_directory
from .studio_store import StudioStore,Conflict
from .comfy import ComfyCancelled
from .studio_plan import story_plan,frames,geometry
from .studio_recipes import Recipes,RECIPES,defaults
from . import studio_media as av,studio_prompts,media
from .studio_story import StoryExecution,storyboard,replan
from .studio_progress import ProgressWatch,local_progress,snapshot_runtime
from .studio_tail import save_tail,validate_tail
from .studio_source import SourcePreparation,source_options,source_signature,ready as source_ready
from . import studio_swap_prompts
from .studio_inputs import inventory, public_inventory

bp=Blueprint('studio',__name__,url_prefix='/api/v5')
def uid():return uuid.uuid4().hex
def dump(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(path)
def service():return current_app.config['STUDIO']

class Studio(StoryExecution,SourcePreparation):
    def __init__(self,ctx):
        self.ctx=ctx;cfg=ctx['cfg'];self.root=Path(cfg.get('studio_data_dir') or ctx['root']/'data_v5');self.store=StudioStore(self.root)
        self.comfy=ctx['comfy'];self.recipes=Recipes(self.comfy,self.root/'engine-catalog.json',cfg);self.jobs=ctx['jobs'];self.active=None;self.lock=threading.RLock()
        from .config import resolve_path
        self.input=resolve_path(cfg,'comfy_input_dir');self.output=resolve_path(cfg,'comfy_output_dir')
        self.pending_recovery=[]
        from .generation.drafts import DraftStore
        self.drafts=DraftStore(self.store)
        from .generation.launcher import EngineLauncher
        self.launcher=EngineLauncher(self)
        for p in self.store.list() if ctx.get('startup_recovery', True) else []:
            if p.get('status') in ['generating','assembling','preparing']:
                p['status']='interrupted';p['error']='工作台上次中断。先查询已有任务或重新准备素材。'
                for s in p['segments']:
                    if s['status']=='generating':
                        s['status']='interrupted'
                        self.pending_recovery.append((p['id'],s['index']))
                        for a in s.get('attempts',[]):
                            for t in a.get('tasks',[]):
                                if t['status']=='generating':t['status']='interrupted'
                self.store.save(p,p['revision'])
    def snapshot(self,p):
        p=copy.deepcopy(p);p['busy']=self.jobs.is_busy(p['id']);p['current_job']=self.jobs.current(p['id']);assets=self.store.assets(p['id'])
        p['saved_draft']=self.drafts.get(p['id']);p['draft_storage_version']=1
        p['asset_library']=[self.public_asset(a) for a in assets]
        for s in p['segments']:
            s['source_preview_url']=None
            if s.get('source_file'):
                try:
                    source=Path(s['source_file']).resolve()
                    if source.is_file():s['source_preview_url']=self.url(p['id'],source)
                except (OSError,ValueError):pass
            s['source_preview_note']='模型输入切片（无音轨）；源声音在原视频中查看。' if s.get('source_file') else ''
            try:
                resolved=self.resolve(p,s)
                s['resolved_assets']=[self.public_asset(a) for a in resolved]
                s['effective_inputs']=public_inventory(inventory(p,s,resolved))
            except ValueError:s['resolved_assets']=[]
            s['asset_source']='本段素材' if s['assets'] else 'P01素材' if s['index'] else '未上传素材'
            for a in s.get('attempts',[]):
                if a.get('delivery'):a['delivery_url']=self.url(p['id'],a['delivery'])
            selected=next((a for a in s.get('attempts',[]) if a['id']==s.get('selected')),None)
            if selected:s['delivery_url']=self.url(p['id'],selected['delivery'])
        if p.get('export'):p['export']['url']=self.url(p['id'],p['export']['file'])
        if p['mode']=='swap':
            p['source_ready']=source_ready(p)
            p['source_progress']=self.source_progress(p['id'])
        p['runtime']=snapshot_runtime(p,self.store.directory(p['id']))
        p['input_contract_version']=2
        return p
    def url(self,pid,path):
        rel=Path(path).resolve().relative_to(self.store.directory(pid).resolve());return f'/api/v5/projects/{pid}/files/{rel.as_posix()}'
    def public_asset(self,a):return {**{k:v for k,v in a.items() if k not in ['path','input_name']},'url':self.url(a['project'],a['path'])}
    def new_segment(self,plan):return {**plan,'id':uid(),'prompt':'','prompt_mode':'structured','swap_prompt_mode':'inherit','swap_custom_prompt':'','staging':'','beats':'','voice':'','speaker_order':'','soundscape':'','music':'','ending':'','assets':[],'inherit_ids':[],'asset_mode':'auto','seed_mode':'random','seed':'730001','last_seed':None,'status':'draft','attempts':[],'selected':None}
    def create(self,mode,name,duration=30):
        if mode not in ['swap','image_story','text_story']:raise ValueError('创作模式不支持')
        s=self.store.get_default(mode)
        if not s or s.get('recipe')=='dance_av':s=defaults()
        s=copy.deepcopy(s);s['audio_policy']='native'
        duration=float(duration)
        p=self.store.create(dict(mode=mode,name=str(name or '未命名项目')[:120],settings=s,duration=duration,timing_mode='natural',storyboard_version=0 if mode=='swap' else 1,segments=[] if mode=='swap' else [self.new_segment(x) for x in storyboard(duration,s['render_cap'])],status='draft',review='manual',source_asset=None,source_ready=False,export=None,changes=[],error=None,pause=False))
        p['input_prompt_version']=2
        if mode=='swap':
            p['swap_prompt']={'mode':'template','custom':'','version':studio_swap_prompts.LATEST_VERSION}
        p=self.store.save(p,p['revision'])
        return p
    def upload(self,pid,file,kind,purpose,subject):
        self.store.get(pid)
        if kind not in ['image','audio','video']:raise ValueError('素材类型不支持')
        aid=uid();suffix=Path(file.filename or '').suffix.lower()
        allowed={'image':['.png','.jpg','.jpeg','.webp'], 'audio':['.wav','.mp3','.m4a','.flac','.ogg','.mp4'],'video':['.mp4','.mov','.webm','.mkv','.avi']}
        if suffix not in allowed[kind]:raise ValueError('素材文件格式不支持')
        directory=self.store.directory(pid)/'assets'/aid;directory.mkdir(parents=True);path=directory/('original'+suffix);file.save(path)
        meta={}
        try:
            if kind=='image':
                from PIL import Image,ImageOps
                with Image.open(path) as im:
                    im=ImageOps.exif_transpose(im).convert('RGB');meta={'width':im.width,'height':im.height};im.thumbnail((4096,4096));normalized=directory/'image.png';im.save(normalized)
                path=normalized
            else:
                data=av.probe(path);duration=float(data['format'].get('duration') or 0)
                if not duration>0:raise ValueError('素材时长无法读取')
                meta['duration']=duration
                if kind=='audio':
                    if not 2<=duration<=15.05:raise ValueError('声音参考须为2～15秒，请先裁切后上传')
                    normalized=directory/'audio.wav';av.run(['ffmpeg','-y','-v','error','-i',path,'-vn','-ar','32000','-ac','2',normalized]);path=normalized
                else:meta['has_audio']=any(s['codec_type']=='audio' for s in data['streams'])
            input_name=f'time_forest_v5/{pid}/{aid}{path.suffix}'
            a=dict(id=aid,project=pid,kind=kind,purpose=purpose or 'character',subject=str(subject or ''),name=file.filename,path=str(path),input_name=input_name,sha256=av.digest(path),bytes=path.stat().st_size,**meta)
            self.store.add_asset(pid,a);return a
        except Exception:
            # Failed uploads are not attached; retained temporary files can be cleaned.
            raise
    def resolve(self,p,s):
        mode=s.get('asset_mode','auto')
        if mode not in ['auto','custom','none']:raise ValueError('素材引用方式不支持')
        if mode=='none':return []
        ids=s.get('assets',[])
        if mode=='auto' and not ids and s['index']>0:ids=p['segments'][0].get('assets',[])
        ids=list(dict.fromkeys(ids+s.get('inherit_ids',[])))
        return [self.store.asset(p['id'],aid) for aid in ids]
    def edit_plan(self,pid,data):
        if self.jobs.is_busy(pid):raise Conflict('已有任务运行；编辑内容仍可保留在页面草稿，暂停后再保存')
        p=self.store.get(pid)
        if int(data.get('revision',0))!=p['revision']:raise Conflict('项目版本已变化，请刷新再保存')
        q=copy.deepcopy(p);q['name']=str(data.get('name',p['name']))[:120];q['review']=data.get('review',p['review'])
        if q['review'] not in ['manual','automatic']:raise ValueError('审核方式不支持')
        if p['mode']=='swap':
            q['source_options']=source_options(data.get('source_options',p.get('source_options')))
            q['swap_prompt']=studio_swap_prompts.normalize(data.get('swap_prompt',p.get('swap_prompt')))
        settings=data.get('settings',p['settings']);s=self.recipes.normalize(settings,p['mode']);q['settings']=s
        duration=float(data.get('duration',p['duration']));q['duration']=duration
        incoming=data.get('segments',p['segments']);summary=[]
        q['timing_mode']=data.get('timing_mode',p.get('timing_mode','natural'))
        if q['timing_mode'] not in ['natural','exact']:raise ValueError('时长方式不支持')
        if q['timing_mode']!=p.get('timing_mode','natural'):summary.append('时长方式已改变，请检查预计长度和内部任务数')
        # Removed browser drafts can contain edits newer than the saved layout.
        # Retain their authored fields, never accept client-supplied run records.
        for removed in data.get('removed_drafts',[]):
            draft=self.new_segment({k:removed[k] for k in ['index','start','raw','head','deliver','tail','duration','boundary'] if k in removed})
            for key in ['prompt','prompt_mode','staging','beats','voice','speaker_order','soundscape','music','ending','assets','inherit_ids','asset_mode','swap_prompt_mode','swap_custom_prompt']:
                if key in removed:draft[key]=copy.deepcopy(removed[key])
            for aid in draft['assets']+draft['inherit_ids']:self.store.asset(pid,aid)
            q.setdefault('removed_drafts',[]).append(draft)
        if data.get('removed_drafts'):summary.append(f'有{len(data["removed_drafts"])}段未采用内容归档到可恢复草稿')
        if p['mode']!='swap' and data.get('storyboard_version')==1 and not p.get('storyboard_version'):
            q['storyboard_version']=1
            q.setdefault('previous_layouts',[]).append(copy.deepcopy(p['segments']))
            summary.append('升级为每15秒一个创作片段；原编排完整归档，提示词不会自动拼接，请检查片段内容')
        editable=['prompt','prompt_mode','staging','beats','voice','speaker_order','soundscape','music','ending','assets','inherit_ids','asset_mode','swap_prompt_mode','swap_custom_prompt','seed_mode','seed','boundary']
        byid={x['id']:x for x in incoming if 'id' in x}
        for seg in q['segments']:
            seg.setdefault('asset_mode','auto')
            inc=byid.get(seg['id'],{})
            if p['mode']=='swap' and inc.get('boundary',seg['boundary'])!=seg['boundary']:raise ValueError('换人模式的场景边界由源视频切片确定，请重新准备素材；不能只改标记而不改切片')
            for key in editable:
                if key in inc:seg[key]=copy.deepcopy(inc[key])
            if seg.get('swap_prompt_mode','inherit') not in ['inherit','template','custom'] or not isinstance(seg.get('swap_custom_prompt',''),str):raise ValueError('本段换人提示词设置不合法')
            if seg['seed_mode'] not in ['random','fixed']:raise ValueError('种子模式不支持')
            if not str(seg['seed']).isascii() or not str(seg['seed']).isdigit() or not 0<=int(seg['seed'])<=9007199254740991:raise ValueError('种子须为0～9007199254740991整数')
            if seg['boundary'] not in ['new_scene','continue']:raise ValueError('场景边界不支持')
            if any(not isinstance(seg[k],list) for k in ['assets','inherit_ids']):raise ValueError('素材列表格式错误')
            for aid in seg['assets']+seg['inherit_ids']:self.store.asset(pid,aid)
        if p['mode']!='swap':
            boundaries={x['index']:x['boundary'] for x in incoming}
            planned=storyboard(duration,s['render_cap'],boundaries,q['timing_mode']) if q.get('storyboard_version') else story_plan(duration,s['render_cap'],boundaries)
            prior=q['segments'];q['segments']=[]
            for i,item in enumerate(planned):
                seg=prior[i] if i<len(prior) else self.new_segment(item)
                if i>=len(prior) and i<len(incoming):
                    for key in editable:
                        if key in incoming[i]:seg[key]=copy.deepcopy(incoming[i][key])
                seg.update(item);q['segments'].append(seg)
            if len(prior)>len(planned):q.setdefault('removed_drafts',[]).extend(prior[len(planned):])
            if [(x['raw'],x['deliver']) for x in p['segments']]!=[(x['raw'],x['deliver']) for x in q['segments']]:summary.append('时间线已重新规划，正文按片段保留；移除段归档为草稿')
            if q.get('storyboard_version') and (summary or duration!=p['duration']):
                summary.append(f'计划{duration:g}秒 / 预计有效{sum(x["deliver"] for x in q["segments"])/24:.3f}秒；{len(q["segments"])}个片段、{sum(len(x["task_plan"]) for x in q["segments"])}次内部渲染')
        has_audio=any(any(a['kind']=='audio' for a in self.resolve(q,sg)) for sg in q['segments'])
        has_images=any(any(a['kind']=='image' for a in self.resolve(q,sg)) for sg in q['segments'])
        if p['mode']=='swap' and has_audio and s['audio_policy']=='source':
            s['audio_policy']='native'
            summary.append('已选择音色参考，与最终保留源原声冲突：确认后改由H3生成声音，只参考音色与说话方式，不复制录音台词')
        if s['recipe']=='official_text' and (has_audio or has_images):
            old=s;new=defaults('text_ref')
            for key in ['size_mode','aspect','megapixels','width','height','export_fps','render_cap','low_vram','sage','head_chunks','ff_chunks']:new[key]=old[key]
            new['acceleration']=old['acceleration'];q['settings']=self.recipes.normalize(new,p['mode'])
            summary.append('图片或声音参考与官方T2VA冲突：确认后切换官方Ref2VA参考配方、Ref2VA底模、相应加速文件及正文适配')
            s=q['settings']
        recipe_changed=p['settings']['recipe']!=s['recipe']
        generation_settings_changed=any(p['settings'].get(k)!=s.get(k) for k in s if k!='export_fps')
        structural=any(p['settings'].get(k)!=s.get(k) for k in ['recipe','model','video_vae','audio_vae','clip','size_mode','aspect','megapixels','width','height','scale','loras','acceleration','audio_policy'])
        if structural:summary.append('工作流/模型/素材条件或画布发生变化，受影响结果将标记过期，原文件保留')
        elif generation_settings_changed:summary.append('生成参数已改变，已选结果将过期；下一次生成使用新参数')
        if recipe_changed:summary.append('提示词适配器随配方变化，请检查最终提交正文；人工原文不会被改写')
        if s['recipe']=='dance_split':
            if recipe_changed:summary.append(f'切换原跳舞核心：总{s["steps"]}步按{s["split_step"]}＋{s["refine_steps"]}切开，声画改取二采；已有结果保留但不自动作为新核心上下文')
            if s['split_step']<6 or s['refine_steps']<4:summary.append('当前步数低于原作者推荐（一采≥6、二采≥4）；将按你的参数执行，质量未验证')
            if s['sampler']!='euler' or s['scheduler']!='beta':summary.append('已偏离原Euler/beta采样组合；保留切分结构，但不沿用原配置的质量结论')
        swap_prompt_changed=p['mode']=='swap' and studio_swap_prompts.normalize(p.get('swap_prompt'))!=q['swap_prompt']
        if swap_prompt_changed:summary.append('项目换人提示词已改变，继承项目提示词的生成结果将过期')
        prevmap={x['id']:x for x in p['segments']};changed_ids=set();cascade=False
        for seg in q['segments']:
            old=prevmap.get(seg['id']);old_assets=self.resolve(p,old) if old else []
            if old:old={**old,'asset_mode':old.get('asset_mode','auto'),'swap_prompt_mode':old.get('swap_prompt_mode','inherit'),'swap_custom_prompt':old.get('swap_custom_prompt',''),'speaker_order':old.get('speaker_order','')}
            seg.setdefault('speaker_order','');seg.setdefault('swap_prompt_mode','inherit');seg.setdefault('swap_custom_prompt','')
            assets=self.resolve(q,seg)
            if seg['seed_mode'] not in ['random','fixed'] or not str(seg['seed']).isascii() or not str(seg['seed']).isdigit() or not 0<=int(seg['seed'])<=9007199254740991:raise ValueError('片段种子设置不合法')
            if seg['boundary']=='new_scene':cascade=False
            changed=old is None or generation_settings_changed or (swap_prompt_changed and seg.get('swap_prompt_mode','inherit')=='inherit') or any(seg.get(k)!=old.get(k) for k in editable+['raw','head','deliver','tail'] if k not in ['seed','seed_mode']) or [a['id'] for a in assets]!=[a['id'] for a in old_assets]
            if changed or cascade:
                if seg.get('selected'):summary.append(f'P{seg["index"]+1:02d}当前结果过期')
                seg['selected']=None;seg['status']='draft';changed_ids.add(seg['id']);cascade=True
            images=[a for a in assets if a['kind']=='image'];audios=[a for a in assets if a['kind']=='audio']
            if len(images)>9 or len(audios)>3 or sum(a.get('duration',0) for a in audios)>15.05:raise ValueError(f'P{seg["index"]+1}参考超限：最多9图/3音频，音频合计≤15秒')
            if old and seg['index']>0 and bool(old['assets'])!=bool(seg['assets']):summary.append(f'P{seg["index"]+1:02d}素材继承方式改变，请检查本段实际素材清单')
            if old and seg.get('asset_mode','auto')!=old.get('asset_mode','auto'):
                label={'auto':'默认沿用P1（有本段素材时优先本段）','custom':'仅使用本段指定素材','none':'不使用参考素材'}[seg['asset_mode']]
                summary.append(f'P{seg["index"]+1:02d}参考素材改为：{label}；声画续接仍由连续承接/新场景设置决定')
        if q['review']!=p['review']:summary.append('执行方式改为'+('人工逐段审核' if q['review']=='manual' else '全自动；不会自动识别人物替换质量'))
        if p['mode']=='swap' and source_signature(s,q['source_options'])!=source_signature(p['settings'],p.get('source_options')):
            q['source_ready']=False;summary.append('源视频输入尺寸或分段规则改变：使用已上传原视频重新准备切片，无需更换文件')
        if changed_ids or s['export_fps']!=p['settings']['export_fps']:q['export']=None
        q['status']='draft' if changed_ids else p['status'];q['error']=None
        plan=dict(project=q,summary=list(dict.fromkeys(summary)) or ['保存本段草稿/参数'],affected=list(changed_ids))
        token=self.store.stage(pid,p['revision'],plan)
        return dict(token=token,requires_confirmation=bool(summary),summary=plan['summary'],affected=plan['affected'],settings=q['settings'],segments=[dict(index=x['index'],raw=x['raw'],head=x['head'],deliver=x['deliver'],tail=x['tail']) for x in q['segments']])
    def preflight(self,pid):
        if self.store.get(pid).get('storyboard_version'):return self.story_preflight(pid)
        p=self.store.get(pid);issues=[];rows=[]
        if not p['segments']:issues.append('尚未规划片段，请先准备源视频')
        if p['mode']=='swap' and not source_ready(p):issues.append('当前参数需要重新准备源视频切片，请点击使用原视频重新准备，无需重新上传')
        self.recipes.refresh()
        for seg in p['segments']:
            errors=[];assets=[];compiled=None;text=''
            try:
                assets=self.resolve(p,seg);images=[a for a in assets if a['kind']=='image'];audios=[a for a in assets if a['kind']=='audio']
                if p['mode']=='swap' and len(images)!=1:raise ValueError('换人模式需要且只需要1张角色图')
                context_only=seg.get('asset_mode')=='none' and seg['head']>0
                if p['mode']=='image_story' and not images and not context_only:raise ValueError('首段或新场景需要参考图片；连续片段可选择不使用参考素材，承接上一段画面与声音')
                if p['settings']['recipe']=='official_text' and (images or any(a['kind']=='audio' for a in assets)):raise ValueError('官方T2VA不接收参考资产，请先保存并确认切换Ref2VA工作流')
                if p['settings']['recipe']=='text_ref' and not (images or audios) and not context_only:raise ValueError('Ref2VA声音配方缺少参考音频，请切回原生文生配方')
                if p['settings']['recipe']=='official_text' and audios:raise ValueError('请先确认音频参考配方变更')
                if len(images)>9 or len(audios)>3 or sum(a.get('duration',0) for a in audios)>15.05:raise ValueError('参考素材超过模型上限')
                text=studio_prompts.build(p,seg,assets)
                previous=self.previous(p,seg,required=False)
                compiled=self.recipes.compile(p,seg,assets,text,previous=previous)
                errors+=compiled['issues']
                for a in assets:
                    if not Path(a['path']).is_file():errors.append('素材丢失：'+a['name'])
                if seg['raw']>345:errors.append('渲染超过15秒硬上限')
            except (ValueError,KeyError) as e:errors.append(str(e))
            rows.append(dict(id=seg['id'],index=seg['index'],errors=errors,raw=seg['raw'],head=seg['head'],deliver=seg['deliver'],tail=seg['tail'],prompt=text,compiled=compiled))
            issues.extend([f'P{seg["index"]+1:02d}: '+e for e in errors])
        return dict(ready=not issues,revision=p['revision'],errors=issues,segments=rows,online_verified=not self.recipes.offline,note='本地结构预检；生成前检查在线节点结构；模型兼容性由ComfyUI提交与执行结果反馈。15秒/多资产显存和生成效果未实测。')
    def previous(self,p,seg,required=True):
        if not seg['head']:return None
        if p.get('_task_execution') and seg['index']==0:return p.get('_story_previous')
        prev=p['segments'][seg['index']-1];a=next((a for a in prev['attempts'] if a['id']==prev.get('selected')),None)
        if not a or prev['status'] not in ['accepted','done']:
            if required:raise ValueError('上一段尚未接受，不能提交下一段')
            return None
        if p['settings']['recipe']=='dance_split':
            if not a.get('tail_context'):raise ValueError('上一段没有原8＋4二采无损尾部，请在新配方下重生成前段')
            return validate_tail(self,a['tail_context'],p['settings'])
        if not a.get('context') or not Path(a['context']).is_file():raise ValueError('上一段AV检查点缺失')
        if prev['tail']:
            if not a.get('delivery') or not Path(a['delivery']).is_file():raise ValueError('上一片段交付文件缺失')
            return dict(video=a['delivery'],frames=prev['deliver'])
        return a['context']
    def launch(self,pid,index=None,all_segments=False):
        if self.ctx['cfg'].get('studio_disable_generation'):raise ValueError('该验收环境禁止提交模型生成任务')
        from .generation.recovery import assert_no_uncertain_runs
        p=self.store.get(pid)
        indices=range(len(p['segments'])) if all_segments else [index] if isinstance(index,int) and 0<=index<len(p['segments']) else []
        assert_no_uncertain_runs(p,indices)
        self.launcher.connect_for_generation()
        self.recipes.normalize(self.store.get(pid)['settings'],self.store.get(pid)['mode'],online=True)
        report=self.preflight(pid)
        if not all_segments and (not isinstance(index,int) or not 0<=index<len(report['segments'])):raise ValueError('片段索引不正确')
        if self.store.get(pid)['mode']=='swap' and not source_ready(self.store.get(pid)):raise ValueError('请重新准备源视频')
        bad=report['errors'] if all_segments else report['segments'][index]['errors']
        if bad:raise ValueError('\n'.join(bad))
        p=self.store.get(pid)
        if not all_segments:self.previous(p,p['segments'][index])
        queue=self.comfy._get('/queue')
        if queue.get('queue_running') or queue.get('queue_pending'):raise Conflict('ComfyUI已有任务，请待队列空闲后提交')
        local_progress(self.store.directory(pid),'准备提交工作流',started=time.time(),finished=None,shot=index or 0,task=0,connected=False)
        if not self.jobs.start('v5_generate',pid,lambda:self.run_chain(pid,index,all_segments)):raise Conflict('已有工作台任务运行')
    def run_chain(self,pid,index,all_segments):
        try:
            with self.jobs._lock:
                stopped=any(j.get('stop_requested') for j in self.jobs._jobs.values() if j['project_id']==pid)
                self.store.mutate(pid,lambda p:p.update(pause=stopped,error=None))
            indexes=range(len(self.store.get(pid)['segments'])) if all_segments else [index]
            for i in indexes:
                p=self.store.get(pid);seg=p['segments'][i]
                if p.get('pause'):break
                if seg['status'] in ['accepted','done']:continue
                if seg['status']=='needs_review':break
                self.generate_one(pid,i)
                p=self.store.get(pid)
                if p['segments'][i]['status'] not in ['accepted','done']:break
            p=self.store.get(pid)
            if p['segments'] and all(s['status'] in ['accepted','done'] for s in p['segments']):self.export(pid)
        except Exception as e:self.store.mutate(pid,lambda p:p.update(status='failed',error=str(e)))
    def prepare_execution_inputs(self,pid,seg,assets):
        for a in assets:
            target=(self.input/a['input_name']).resolve()
            if self.input.resolve() not in target.parents:raise ValueError('生成输入路径越界')
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists() or av.digest(target)!=a['sha256']:shutil.copy2(a['path'],target)
        if seg.get('source_file') and seg.get('input_name'):
            target=(self.input/seg['input_name']).resolve()
            if self.input.resolve() not in target.parents:raise ValueError('源切片路径越界')
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(seg['source_file'],target)

    def generate_one(self,pid,index):
        if self.store.get(pid).get('storyboard_version'):return self.generate_story(pid,index)
        p=self.store.get(pid);seg=p['segments'][index];previous=self.previous(p,seg);assets=self.resolve(p,seg)
        self.prepare_execution_inputs(pid,seg,assets)
        aid=uid();seed=str(int.from_bytes(os.urandom(7),'big')%(2**52)) if seg['seed_mode']=='random' else str(seg['seed']);seg['actual_seed']=seed
        compiled=self.recipes.compile(p,seg,assets,studio_prompts.build(p,seg,assets),aid,previous)
        if compiled['issues']:raise ValueError('; '.join(compiled['issues']))
        directory=self.store.directory(pid)/'segments'/seg['id']/'attempts'/aid;directory.mkdir(parents=True)
        dump(directory/'workflow.json',compiled['workflow']);dump(directory/'manifest.json',dict(settings=p['settings'],segment=seg,compiled=compiled,previous=previous,revision=p['revision']))
        (directory/'prompt.txt').write_text(studio_prompts.build(p,seg,assets),encoding='utf-8')
        attempt=dict(id=aid,status='submitting',seed=seed,created=time.time(),directory=str(directory),prompt_id=None)
        def start(q):q['segments'][index]['attempts'].append(attempt);q['segments'][index].update(status='generating',last_seed=seed);q.update(status='generating',error=None)
        self.store.mutate(pid,start)
        watch=ProgressWatch(self.comfy.url,'time-forest-'+aid,compiled['workflow'],directory,self.store.directory(pid),seg.get('story_index',index),seg.get('story_task',0),seg.get('story_task_total',1))
        if not self.ctx['cfg'].get('studio_progress_disabled'):watch.start()
        try:
            promptid=self.comfy.submit(compiled['workflow'],'time-forest-'+aid)
            watch.submitted(promptid)
            dump(directory/'request.json',dict(prompt_id=promptid,attempt=aid))
            def submitted(q):q['segments'][index]['attempts'][-1].update(prompt_id=promptid,status='submitted')
            self.store.mutate(pid,submitted)
            history=self.comfy.wait(promptid);dump(directory/'history.json',history)
            watch.close()
            local_progress(self.store.directory(pid),'裁切重复画面与声音，检查生成文件',connected=False)
            self.finish(pid,index,aid,history,promptid)
            local_progress(self.store.directory(pid),'本次渲染已完成',finished=time.time(),connected=False)
        except Exception as e:
            dump(directory/'error.json',dict(error=str(e)))
            def fail(q):
                status='failed' if isinstance(e,ComfyCancelled) else 'interrupted'
                a=next(a for a in q['segments'][index]['attempts'] if a['id']==aid);a.update(status=status,error=str(e));q['segments'][index].update(status=status);q.update(status=status,error=str(e))
            self.store.mutate(pid,fail)
            local_progress(self.store.directory(pid),'生成中断，请查询并恢复',finished=time.time(),error=str(e),connected=False)
        finally:watch.close()
    def finish(self,pid,index,aid,history,promptid):
        p=self.store.get(pid);seg=p['segments'][index];a=next(a for a in seg['attempts'] if a['id']==aid);directory=Path(a['directory']);manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'));compiled=manifest['compiled']
        server=self.comfy.first_video(history,promptid,compiled['output_node'],self.output);raw=directory/'raw.mp4';shutil.copy2(server,raw)
        if media.frame_count(raw)!=seg['raw']:raise ValueError('生成raw帧数与计划不符')
        contextsrc=self.output/compiled['context_relative'];context=directory/'context.safetensors'
        if not contextsrc.is_file():raise ValueError('AV检查点没有保存')
        with contextsrc.open('rb') as f:
            length=int.from_bytes(f.read(8),'little')
            if not 0<length<16_000_000:raise ValueError('AV检查点头损坏')
            head=json.loads(f.read(length))
            if 'video' not in head or 'audio' not in head:raise ValueError('检查点缺少视频或音频latent')
        shutil.copy2(contextsrc,context)
        tail_context=save_tail(self,p,seg,aid,directory,history,promptid,compiled) if compiled.get('context_kind')=='pass2_lossless_tail' else None
        delivery=directory/'delivery.mp4';source=None
        if p['mode']=='swap' and p['settings']['audio_policy']=='source':
            source=p['source_normalized']
            if not media.has_audio(Path(source)):raise ValueError('源片没有声音，请明确选择H3原生声音后重新生成')
        audio_offset=seg['start']/24
        if tail_context and source is None:source=tail_context['native_audio'];audio_offset=seg['head']/24
        qa=av.av_trim(raw,delivery,seg['head'],seg['deliver'],source,audio_offset)
        thumb=directory/'thumb.jpg';media.make_thumbnail(delivery,thumb)
        dump(directory/'qa.json',qa)
        def saved(q):
            sg=q['segments'][index];aa=next(a for a in sg['attempts'] if a['id']==aid)
            aa.update(status='complete',delivery=str(delivery),context=str(context),context_sha256=av.digest(context),qa=qa,completed=time.time(),prompt_id=promptid)
            if tail_context:aa['tail_context']=tail_context
            sg.update(status='needs_review' if q['review']=='manual' else 'done',selected=aid)
            q.update(status=sg['status'],error=None)
        return self.store.mutate(pid,saved)
    def approve(self,pid,index,continue_run=False,attempt=None):
        if self.jobs.is_busy(pid):raise Conflict('当前还有任务运行')
        def accept(p):
            s=p['segments'][index];a=next((a for a in s['attempts'] if a['id']==(attempt or s.get('selected'))),None)
            if a and a.get('removed_at'):raise Conflict('候选已移除，请先恢复后选用')
            if not a or a['status']!='complete':raise ValueError('当前没有可接受的完整结果')
            manifest=json.loads((Path(a['directory'])/'manifest.json').read_text(encoding='utf-8'))
            before={k:v for k,v in manifest['settings'].items() if k!='export_fps'};after={k:v for k,v in p['settings'].items() if k!='export_fps'}
            if before!=after or any(manifest['segment'][k]!=s[k] for k in ['raw','head','deliver','tail']):raise ValueError('候选结果与当前参数/时间线不一致，不能选用过期结果')
            if self.previous(p,s)!=manifest.get('previous'):raise ValueError('候选结果的上一段上下文已变化，必须重生成')
            text=(Path(a['directory'])/'prompt.txt').read_text(encoding='utf-8')
            if text!=studio_prompts.build(p,s,self.resolve(p,s)):raise ValueError('候选结果与当前提示词/素材映射不一致')
            if s.get('selected')!=a['id']:
                for later in p['segments'][index+1:]:
                    if later['boundary']=='new_scene':break
                    later.update(selected=None,status='draft')
            s.update(selected=a['id'],status='accepted');p.update(status='ready',export=None)
        p=self.store.mutate(pid,accept)
        if all(s['status'] in ['accepted','done'] for s in p['segments']):self.jobs.start('v5_export',pid,lambda:self.export_safe(pid))
        elif continue_run:self.launch(pid,all_segments=True)
        return self.store.get(pid)
    def reroll(self,pid,index):
        if self.jobs.is_busy(pid):raise Conflict('当前还有任务运行')
        p=self.store.get(pid);self.previous(p,p['segments'][index])
        if p['segments'][index]['status']=='interrupted':raise ValueError('中断任务请先查询恢复，避免重复提交')
        self.launcher.connect_for_generation()
        self.recipes.normalize(p['settings'],p['mode'],online=True)
        def reset(q):
            for i,s in enumerate(q['segments'][index:],index):
                if i>index and s['boundary']=='new_scene':break
                s.update(selected=None,status='draft')
            q.update(export=None,status='draft')
        self.store.mutate(pid,reset);self.launch(pid,index)
    def recover(self,pid,index):
        p=self.store.get(pid);s=p['segments'][index]
        if not s['attempts']:raise ValueError('没有运行记录')
        if p.get('storyboard_version'):return self.continue_story(pid,index,s['attempts'][-1]['id'],recover=True)
        from .generation.recovery import resolve_submission
        a=s['attempts'][-1];promptid,history,queued=resolve_submission(self.comfy,a)
        def identified(q):q['segments'][index]['attempts'][-1].update(prompt_id=promptid)
        self.store.mutate(pid,identified)
        if queued and not history.get(promptid):
            local_progress(self.store.directory(pid),'恢复监控已提交任务（不会重复生成）',started=a['created'],finished=None,connected=True)
            try:history=self.comfy.wait(promptid)
            except ComfyCancelled as exc:
                def stopped(q):
                    q['segments'][index]['attempts'][-1].update(status='failed',error=str(exc))
                    q['segments'][index]['status']='failed';q.update(status='failed',error=str(exc))
                return self.store.mutate(pid,stopped)
        record=history.get(promptid)
        if not record:raise ValueError('任务未完成或记录不可用，稍后再恢复')
        if record.get('status',{}).get('status_str')=='error':
            def failed(q):q['segments'][index]['attempts'][-1]['status']='failed';q['segments'][index]['status']='failed';q.update(status='failed',error='ComfyUI已确认任务失败，可以调整后重生成')
            return self.store.mutate(pid,failed)
        if record.get('status',{}).get('status_str')!='success':raise ValueError('该任务没有成功结果，请查看ComfyUI错误记录')
        dump(Path(a['directory'])/'history.json',history);return self.finish(pid,index,a['id'],history,promptid)
    def export(self,pid):
        p=self.store.get(pid)
        if not p['segments'] or not all(s['status'] in ['accepted','done'] for s in p['segments']):raise ValueError('还有未生成/未接受的片段')
        selected=[]
        for s in p['segments']:
            a=next(a for a in s['attempts'] if a['id']==s['selected']);selected.append(dict(delivery=a['delivery'],deliver=s['deliver'],attempt=a['id']))
        self.store.mutate(pid,lambda q:q.update(status='assembling'))
        local_progress(self.store.directory(pid),'合成完整视频与声音',started=time.time(),finished=None,shot=None,connected=False)
        dst,report=av.assemble(selected,self.store.directory(pid)/'exports'/uid(),int(p['settings']['export_fps']))
        dump(dst.parent/'manifest.json',dict(selected=selected,report=report,settings=p['settings']))
        result=self.store.mutate(pid,lambda q:q.update(status='complete',error=None,export=dict(file=str(dst),report=report,created=time.time())))
        local_progress(self.store.directory(pid),'完整视频已合成',finished=time.time(),connected=False)
        return result
    def export_safe(self,pid):
        try:self.export(pid)
        except Exception as e:self.store.mutate(pid,lambda p:p.update(status='failed',error=str(e)))

@bp.errorhandler(Exception)
def error(exc):return jsonify(error=str(exc),code='REVISION_CONFLICT' if isinstance(exc,Conflict) else 'INVALID_REQUEST'),409 if isinstance(exc,Conflict) else 404 if isinstance(exc,KeyError) else 400
@bp.get('/catalog')
def catalog():return jsonify(service().recipes.catalog())
@bp.get('/projects')
def listing():
    st=service();items=[]
    for p in st.store.list(trash=request.args.get("trash")=="1"):
        cover=None
        if p['segments']:
            try:cover=next((st.url(p['id'],a['path']) for a in st.resolve(p,p['segments'][0]) if a['kind']=='image'),None)
            except ValueError:pass
        items.append(dict(revision=p['revision'],deleted_at=p.get('deleted_at'),busy=st.jobs.is_busy(p['id']),id=p['id'],name=p['name'],mode=p['mode'],status=p['status'],duration=p['duration'],updated=p['updated_at'],cover=cover,segments=len(p['segments']),accepted=sum(s['status'] in ['accepted','done'] for s in p['segments'])))
    images=current_app.config.get('IMAGE_STUDIO')
    if images:items.extend(images.summaries(trash=request.args.get('trash')=='1'))
    return jsonify(projects=sorted(items,key=lambda p:p['updated'],reverse=True),image_assets_enabled=bool(images))
@bp.post('/projects/<pid>/trash')
def project_trash(pid):
    st=service();data=request.get_json() or {}
    images=current_app.config.get('IMAGE_STUDIO')
    if images and images.store.exists(pid):return jsonify(images.trash(pid,data))
    if st.jobs.is_busy(pid):raise Conflict('该项目有任务正在处理，请稍后再删除')
    try:
        p=st.jobs.run_inline('project_archive',pid,lambda:st.store.trash(pid,data.get('revision'),data.get('restore') is True))
    except RuntimeError as e:raise Conflict(str(e))
    return jsonify(id=p['id'],revision=p['revision'],deleted=bool(p.get('deleted_at')))

@bp.post('/projects')
def create():
    d=request.get_json()
    if d.get('mode')=='image_assets':
        images=current_app.config.get('IMAGE_STUDIO')
        if not images:raise ValueError('图片创作尚未启用')
        return jsonify(images.create(d.get('name'),d.get('submode','single')))
    return jsonify(service().snapshot(service().create(d.get('mode'),d.get('name'),d.get('duration',30))))

@bp.post('/projects/<pid>/preview')
def preview_story(pid):
    st=service();p=st.store.get(pid);d=request.get_json()
    if p['mode']=='swap':raise ValueError('换人模式请按源视频时间线准备')
    p['timing_mode']=d.get('timing_mode',p.get('timing_mode','natural'))
    if p['timing_mode'] not in ['natural','exact']:raise ValueError('时长方式不支持')
    segments,removed=replan(st,p,d.get('segments',p['segments']),d.get('duration',p['duration']),d.get('settings',p['settings'])['render_cap'])
    return jsonify(segments=segments,removed=removed,duration=sum(s['deliver'] for s in segments)/24)

@bp.post('/projects/<pid>/segments/<int:index>/resume')
def resume_story(pid,index):
    st=service();p=st.store.get(pid)
    if st.ctx['cfg'].get('studio_disable_generation'):raise ValueError('该验收环境禁止提交模型生成任务')
    if not p.get('storyboard_version'):raise ValueError('仅用于新版片段')
    if st.jobs.is_busy(pid):raise Conflict('已有任务运行')
    s=p['segments'][index]
    if s['status']!='interrupted' or not s['attempts']:raise ValueError('没有可继续的片段任务')
    a=s['attempts'][-1]
    if any(t['status']=='interrupted' for t in a['tasks']):raise ValueError('请先查询并恢复，确认已有提交状态')
    manifest=json.loads((Path(a['directory'])/'manifest.json').read_text(encoding='utf-8'))
    if manifest['settings']!=p['settings'] or manifest['segment']['prompt']!=s['prompt']:raise ValueError('参数/提示词已改变，请重生成')
    st.launcher.connect_for_generation()
    st.recipes.normalize(p['settings'],p['mode'],online=True)
    queue=st.comfy._get('/queue')
    if queue.get('queue_running') or queue.get('queue_pending'):raise Conflict('ComfyUI已有任务')
    if not st.jobs.start('v5_resume_story',pid,lambda:st.resume_story_chain(pid,index,a['id'])):raise Conflict('已有任务运行')
    return jsonify(ok=True)
@bp.get('/projects/<pid>')
def get(pid):
    images=current_app.config.get('IMAGE_STUDIO')
    return jsonify(images.snapshot(pid) if images and images.store.exists(pid) else service().snapshot(service().store.get(pid)))
@bp.post('/projects/<pid>/assets')
def upload(pid):
    a=service().upload(pid,request.files['file'],request.form['kind'],request.form.get('purpose'),request.form.get('subject'));return jsonify(service().public_asset(a))
@bp.post('/projects/<pid>/change-plan')
def change(pid):return jsonify(service().edit_plan(pid,request.get_json()))

@bp.post('/projects/<pid>/draft')
def save_authoring_draft(pid):return jsonify(service().drafts.save(pid,request.get_json()))

@bp.post('/projects/<pid>/draft/discard')
def discard_authoring_draft(pid):
    service().drafts.discard(pid,request.get_json()['revision']);return jsonify(ok=True)
@bp.post('/projects/<pid>/apply')
def apply(pid):
    if service().jobs.is_busy(pid):raise Conflict('任务运行中，暂不能应用设置')
    return jsonify(service().snapshot(service().store.apply(pid,request.get_json()['token'])))
@bp.get('/projects/<pid>/preflight')
def preflight(pid):return jsonify(service().preflight(pid))
@bp.post('/projects/<pid>/input-preview')
@bp.post('/projects/<pid>/prompt-preview')
def input_preview(pid):
    st=service();p=st.store.get(pid);data=request.get_json() or {}
    from .studio_inputs import validate
    from .studio_speakers import speakers
    prompt_only=request.path.endswith('/prompt-preview')
    if prompt_only:
        if data.get('revision')!=p['revision']:raise Conflict('项目已更新，请刷新后查看当前提示词')
        if p['mode']!='swap':raise ValueError('本段换人提示词预览仅用于换人模式')
        p['swap_prompt']=studio_swap_prompts.normalize(data.get('swap_prompt',p.get('swap_prompt')))
    if isinstance(data.get('settings'),dict):p['settings']=st.recipes.normalize(data['settings'],p['mode'])
    drafts=data.get('segments',[])
    if not isinstance(drafts,list) or len(drafts)!=len(p['segments']):raise ValueError('片段数量已变化，请先保存编排')
    for s,d in zip(p['segments'],drafts):
        if s['id']!=d.get('id'):raise ValueError('片段已变化，请刷新后重试')
        for key in ['assets','inherit_ids','asset_mode','speaker_order','prompt','voice','swap_prompt_mode','swap_custom_prompt','soundscape','music','staging','beats']:
            if key in d:s[key]=copy.deepcopy(d[key])
    s=next((s for s in p['segments'] if s['id']==data.get('segment')),None)
    if s is None:raise ValueError('片段不存在')
    assets=st.resolve(p,s);rows=validate(p,s,assets);mapping=speakers(s,p['settings']['recipe'])
    if prompt_only:
        return jsonify(prompt=studio_prompts.build(p,s,assets),revision=p['revision'],segment=s['id'],state='draft')
    warnings=[]
    if any(a['kind']=='audio' for a in assets) and not mapping and mapping is not None:
        warnings.append('旧项目仍保留原声音编号。填写本段发声顺序后改用显式映射；历史运行正文不变。' if p.get('input_prompt_version',1)==1 else '尚未指定发声顺序；不会把角色ID自动当成S编号。请按本段实际先后填写或在完整正文中明确映射。')
    return jsonify(state='draft',revision=p['revision'],inputs=public_inventory(rows),speaker_map=mapping,warnings=warnings,
        context='承接上一段已接受的画面与声音' if s.get('head') else '本段独立开始',
        note='此处为当前草稿输入；已保存预检和实际运行清单分别保留。资产资料PROMPT不会注入正文。')
@bp.post('/projects/<pid>/swap-template')
def swap_template(pid):
    st=service();p=st.store.get(pid);data=request.get_json() or {}
    if p['mode']!='swap':raise ValueError('仅换人模式提供此模板')
    p['settings']=st.recipes.normalize(data.get('settings',p['settings']),'swap')
    p['swap_prompt']={**studio_swap_prompts.normalize(p.get('swap_prompt')),'version':studio_swap_prompts.LATEST_VERSION}
    if isinstance(data.get('segments'),list):
        # Resolve draft asset ids using the project store; never accept client paths.
        if len(data['segments'])!=len(p['segments']):raise ValueError('片段数量已变化，请先保存编排')
        for saved,draft in zip(p['segments'],data['segments']):
            if saved['id']!=draft.get('id'):raise ValueError('片段已变化，请重新载入模板')
            for key in ['assets','inherit_ids','asset_mode','speaker_order','voice','staging','beats','soundscape','music']:
                if key in draft:saved[key]=copy.deepcopy(draft[key])
    index=int(data.get('index',0))
    seg=copy.deepcopy(p['segments'][index]) if 0<=index<len(p['segments']) else st.new_segment(dict(index=0,head=0,raw=124,tail=0,deliver=124))
    seg.update(swap_prompt_mode='template',prompt='')
    assets=st.resolve(p,seg) if p['segments'] else []
    if not any(a['kind']=='image' for a in assets):assets=[*assets,dict(kind='image',purpose='character',subject='1')]
    if data.get('scope')=='project':
        for key in ['staging','beats','voice','soundscape','music','speaker_order']:seg[key]=''
    prompt=studio_swap_prompts.build(p,seg,assets,'') if data.get('scope')=='project' else studio_prompts.build(p,seg,assets)
    return jsonify(prompt=prompt,template_version=studio_swap_prompts.LATEST_VERSION,placeholder=not any(a.get('id') for a in assets if a['kind']=='image'),effective_inputs=public_inventory(inventory(p,seg,assets)),note='模板使用Picture 1指代角色图、Video 1指代本段源视频。项目模板不绑定某一段的时间；自定义正文提交时不会再附加模板。')
@bp.post('/projects/<pid>/prepare')
def prepare(pid):
    data=request.get_json();st=service()
    st.start_source(pid,data['asset_id'],data.get('revision'),data.get('continue_to'))
    return jsonify(ok=True)
@bp.post('/projects/<pid>/generate')
def generate(pid):
    d=request.get_json() or {};service().launch(pid,d.get('index'),d.get('all',True));return jsonify(ok=True)
@bp.post('/projects/<pid>/segments/<int:index>/<action>')
def segment_action(pid,index,action):
    st=service();p=st.store.get(pid)
    if not 0<=index<len(p['segments']):raise ValueError('片段不存在')
    d=request.get_json(silent=True) or {}
    if action=='approve':st.approve(pid,index,d.get('continue',False),d.get('attempt'))
    elif action=='reroll':st.reroll(pid,index)
    elif action=='recover':
        def work():
            try:st.recover(pid,index)
            except Exception as e:st.store.mutate(pid,lambda p:p.update(error=str(e)))
        if not st.jobs.start('v5_recover',pid,work):raise Conflict('已有任务运行')
    else:raise ValueError('操作不存在')
    return jsonify(ok=True)
@bp.post('/projects/<pid>/pause')
def pause(pid):service().store.mutate(pid,lambda p:p.update(pause=True));return jsonify(ok=True)
@bp.post('/projects/<pid>/export')
def export(pid):
    st=service()
    if not st.jobs.start('v5_export',pid,lambda:st.export_safe(pid)):raise Conflict('已有任务运行')
    return jsonify(ok=True)
@bp.post('/projects/<pid>/defaults')
def set_defaults(pid):
    p=service().store.get(pid);service().store.set_default(p['mode'],p['settings']);return jsonify(ok=True)

@bp.post('/projects/<pid>/assets/<aid>/version')
def asset_version(pid,aid):
    st=service();a=st.store.asset(pid,aid);d=request.get_json();purpose=d.get('purpose',a['purpose']);subject=str(d.get('subject',a.get('subject','')))
    if purpose not in ['character','face','costume','scene','palette','prop','voice']:raise ValueError('素材用途不支持')
    if purpose in ['character','face','costume','voice'] and (not subject.isdigit() or not 1<=int(subject)<=99):raise ValueError('角色ID须为1～99')
    a={**a,'id':uid(),'purpose':purpose,'subject':subject,'parent_asset':aid};st.store.add_asset(pid,a);return jsonify(st.public_asset(a))
@bp.get('/projects/<pid>/diagnostic')
def diagnostic(pid):
    p=service().store.get(pid);return jsonify(project=p,preflight=service().preflight(pid))
@bp.get('/projects/<pid>/files/<path:subpath>')
def files(pid,subpath):
    directory=service().store.directory(pid).resolve();target=(directory/subpath).resolve()
    if directory not in target.parents:raise ValueError('文件路径越界')
    return send_from_directory(directory,subpath,conditional=True)

@bp.get('/health')
def health():
    st=service();state=st.recipes.engine_catalog.status()
    return jsonify(ok=True,version=5,local_server_version=1,image_assets_enabled='IMAGE_STUDIO' in current_app.config,image_parameter_contract_version=st.ctx.get('image_parameter_contract_version'),startup_recovery=st.ctx.get('startup_recovery',True),deployment=str(st.ctx['root']),comfy_connected=state['connected'],engine=state,busy=st.jobs.is_busy(),job=st.jobs.current(),jobs=st.jobs.snapshot(),devices=state['devices'])

@bp.post('/engine/connect')
def connect_engine():
    st=service();st.recipes.connect()
    return jsonify(st.recipes.catalog())

@bp.get('/engine/status')
def engine_status():return jsonify(service().recipes.engine_catalog.status())

@bp.get('/legacy')
def legacy():
    st=service();items=st.ctx['projects'].list(page=int(request.args.get('page',1)),per_page=24,query=request.args.get('q',''),trash=request.args.get('trash')=='1')
    return jsonify(items)

@bp.post('/legacy/<pid>/trash')
def legacy_trash(pid):
    st=service();data=request.get_json() or {}
    if st.jobs.is_busy(pid):raise Conflict('旧项目有任务正在处理，请稍后再删除')
    try:p=st.jobs.run_inline('project_archive',pid,lambda:st.ctx['projects'].trash(pid,data.get('restore') is True))
    except RuntimeError as e:raise Conflict(str(e))
    return jsonify(id=p['id'],deleted=bool(p.get('deleted_at')))

@bp.post('/legacy/<pid>/migrate')
def migrate(pid):
    st=service();old=st.ctx['projects'].get(pid)
    if not old or old.get('deleted_at'):raise KeyError('旧项目不存在或已删除，请先恢复')
    if st.jobs.is_busy(pid):raise Conflict('请先等当前任务完成')
    p=st.create(old.get('creation_mode','swap'),old.get('name','旧项目')+' · v5制作副本');newid=p['id']
    from werkzeug.datastructures import FileStorage
    imported=[]
    for path in old.get('refs',[]):
        path=Path(path)
        if path.is_file():
            with path.open('rb') as f:imported.append(st.upload(newid,FileStorage(stream=f,filename=path.name),'image','character','1')['id'])
    if p['mode']=='swap':
        source=st.ctx['projects'].project_dir(pid)/'source/upload.mp4'
        if source.is_file():
            with source.open('rb') as f:a=st.upload(newid,FileStorage(stream=f,filename=source.name),'video','source','')
            st.prepare_source(newid,a['id'])
    else:
        seconds=old.get('source_frames',720)/24
        st.store.mutate(newid,lambda q:q.update(duration=seconds,segments=[st.new_segment(s) for s in story_plan(seconds)]))
    def update(q):
        if q['segments']:
            q['segments'][0]['assets']=imported;q['segments'][0]['prompt']=old.get('manual_prompt','')
        q['legacy_source']=pid
    return jsonify(st.snapshot(st.store.mutate(newid,update)))

@bp.get('/projects/<pid>/storage')
def storage(pid):
    st=service();st.store.get(pid);root=st.store.directory(pid);groups={}
    for path in root.rglob('*'):
        if path.is_file():
            key=path.relative_to(root).parts[0];groups[key]=groups.get(key,0)+path.stat().st_size
    return jsonify(groups=groups,bytes=sum(groups.values()))

@bp.post('/projects/<pid>/cleanup')
def cleanup(pid):
    st=service()
    if st.jobs.is_busy(pid):raise Conflict('任务运行中不可清理')
    p=st.store.get(pid);kind=request.get_json().get('kind');root=st.store.directory(pid).resolve();freed=0
    protected={s.get('selected') for s in p['segments']}
    candidates=[]
    if kind=='exports':
        current=Path(p['export']['file']).parent if p.get('export') else None
        candidates=[x for x in (root/'exports').glob('*') if x.is_dir() and x!=current]
    elif kind=='failed':
        for s in p['segments']:
            for a in s['attempts']:
                if a['status']=='failed' and a['id'] not in protected and a.get('directory'):candidates.append(Path(a['directory']))
    else:raise ValueError('清理类型不支持')
    for path in candidates:
        path=path.resolve()
        if root not in path.parents:raise ValueError('清理目标越界')
        if path.exists():freed+=sum(f.stat().st_size for f in path.rglob('*') if f.is_file());shutil.rmtree(path)
    return jsonify(freed_bytes=freed,removed=len(candidates))

@bp.post('/projects/<pid>/archive')
def archive(pid):
    if service().jobs.is_busy(pid):raise Conflict('任务运行中不能归档')
    value=bool(request.get_json().get('archived',True));service().store.mutate(pid,lambda p:p.update(archived=value));return jsonify(ok=True)

@bp.get('/engine/launcher')
def engine_launcher_status():return jsonify(service().launcher.status())

@bp.post('/engine/launcher')
def engine_launcher_save():
    if service().jobs.is_busy():raise Conflict('请等待当前任务结束后修改引擎启动设置')
    return jsonify(service().launcher.save(request.get_json()))
