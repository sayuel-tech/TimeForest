"""Auditable workflow compiler. Builds API graphs, never queues them."""
import copy, json, math, time, hashlib
from pathlib import Path
from .studio_plan import geometry
from .studio_capabilities import decorate_catalog, RANGES
from .studio_inputs import validate as validate_inputs, public_inventory

SOURCES=Path(__file__).parent/'studio_sources'
B25='minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors'
REF='minimax_h3_ref2va_pruned_int8_convrot.safetensors'
FL='minimax_h3_fl2va_pruned_int8_convrot.safetensors'
FEI='FeiHou_MiniMax-H3_Remix_v0.6_int8_convrot_v2.safetensors'
CLIP='qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors'
UPSCALE='minimax_h3_latent_upscaler_3d_fp16.safetensors'
TURBO='minimax_h3_turbo_v4_step600_ema_pruned_comfyui.safetensors'
RECIPES={
 'dance_split':dict(name='跳舞原核心 · 8＋4',modes=['swap','image_story','text_story'],model=B25,two_pass=True,official=False,source='dance.json',description='原12步日程切为8＋4，Euler/beta；中间去噪预测做1.5×学习型放大，最终声画取二采。连续段以二采无损尾部衔接；扩展未生成实测。'),
 'dance_av':dict(name='旧实验 · 完整一采＋独立精修',modes=['swap','image_story','text_story'],model=B25,two_pass=True,official=False,source='dance.json',description='旧项目兼容：完整12步一采＋独立精修，不是原8＋4。保留既有记录，可在制作参数中确认切换原核心。'),
 'official_swap':dict(name='官方Ref2VA · 视频参考低显存',modes=['swap'],model=REF,two_pass=False,official=True,source='official_r2v.json',description='官方Ref2VA单段采样主体＋可选低显存/加速补丁；连续段另加AV上下文。'),
 'official_image':dict(name='官方Ref2VA · 图片参考低显存',modes=['image_story'],model=REF,two_pass=False,official=True,source='official_r2v.json',description='官方多参考音视频采样主体；独立图片/声音输入，长视频使用明确的AV扩展。'),
 'official_text':dict(name='官方T2VA · 文生音视频低显存',modes=['text_story'],model=FL,two_pass=False,official=True,source='official_t2v.json',description='官方FL2VA文字音视频主体；上传用户声音参考时须确认切到Ref2VA配方。'),
 'text_ref':dict(name='官方Ref2VA · 文字与声音参考',modes=['text_story'],model=REF,two_pass=False,official=True,source='official_r2v.json',description='以官方Ref2VA承载文字＋用户音色参考，原生生成目标音轨。'),
 'wenxi_av':dict(name='八月文戏 · 双时钟AV扩展',modes=['image_story'],model=FEI,two_pass=True,official=False,source='wenxi.json',description='保留文戏双时钟、4＋4细化、学习型放大/调和；新增完整低清AV检查点支路，交付用其声音，额外采样未实测。'),
}

def options(info,node,key):
    n=info.get(node,{});spec=n.get('input',{}).get('required',{}).get(key) or n.get('input',{}).get('optional',{}).get(key)
    if not spec:return []
    if isinstance(spec[0],list):return spec[0]
    return spec[1].get('options',[]) if len(spec)>1 and isinstance(spec[1],dict) else []

def model_family(name):
    v=name.lower()
    if 'hybrid' in v or 'feihou_minimax' in v:return 'hybrid'
    if 'ref2va' in v:return 'ref'
    if 'fl2va' in v:return 'fl'
    return None

def defaults(recipe='dance_split'):
    r=RECIPES[recipe];official=r['official'];wenxi=recipe=='wenxi_av'
    result=dict(recipe=recipe,model=r['model'],clip=CLIP,video_vae='minimax_h3_video_vae_fp16.safetensors' if official or wenxi else 'minimax_h3_video_vae_int8_convrot.safetensors',
                audio_vae='minimax_h3_audio_vae_fp32.safetensors',size_mode='area',aspect='9:16',megapixels=.3,width=416,height=736,
                two_pass=r['two_pass'],scale=1.5,steps=8 if wenxi else 20 if official else 12,refine_steps=4 if wenxi else 3,denoise=1.,refine_denoise=.3,
                sampler='res_multistep' if official else 'euler',scheduler='simple' if official else 'beta',reference_size='match' if official else 'max',
                low_vram=True,sage=True,head_chunks=4,ff_chunks=4,seq_threshold=1024,temporal_chunking=True,force_unload=True,
                render_cap=15,export_fps=24,audio_policy='source' if recipe=='official_swap' else 'native',
                acceleration=False,accel_file='minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors' if recipe=='official_text' else 'minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors',accel_strength=1.,
                loras=[dict(file='wushu_spatial_physics_v2_1000_pruned.safetensors',strength=.3,bypass=True),dict(file='MysticXXX_MMH3-V1.safetensors',strength=.5,bypass=False),dict(file=TURBO,strength=1.,bypass=False)] if not official and not wenxi else [dict(file='minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors',strength=.75,bypass=not wenxi)]+[dict(file='',strength=1.,bypass=True) for _ in range(2)],
                shift_video=12.,shift_audio=3.)
    if recipe=='dance_split':result.update(split_step=8,refine_steps=4,acceleration=True,accel_file=TURBO)
    return result

PARAMETERS=[
 ('recipe','工作流','choice','core','选择单段核心及长链扩展；不同模式均有官方选项。'),
 ('model','底模文件','model','core','读取本地底模目录；按所选文件提交，兼容性由ComfyUI判断。'),
 ('size_mode','画布设置方式','choice','picture','面积＋比例或自定义32倍数宽高。'),('aspect','画面比例','choice','picture','改变生成画布比例；连续链尺寸变化会使上下文过期。'),
 ('megapixels','一采面积（MP）','number','picture','推荐0.3MP；显示实际32像素对齐结果。'),('width','一采宽度','number','picture','自定义时生效，128～2048内32的倍数。'),('height','一采高度','number','picture','自定义时生效，128～2048内32的倍数。'),
 ('scale','二采边长倍率','number','picture','两采配方生效；推荐1.5×，不是1.5MP。'),('export_fps','导出帧率','choice','picture','H3原生24fps不变；导出真实重采样，保持时长与声音速度。'),
 ('render_cap','单次渲染上限（秒）','number','sampling','最大15秒；有效片段会扣除上下文，合法raw最多345帧。'),
 ('steps','完整一采步数','number','sampling','真实写入调度器；官方加速开启时按匹配LoRA联动。'),('sampler','一采采样器','sampler','sampling','写入实际采样节点；文戏使用固定双时钟Euler。'),('scheduler','一采调度器','scheduler','sampling','写入实际调度器；文戏使用自己的双时钟/细化计划。'),
 ('refine_steps','二采精修步数','number','sampling','两采配方生效；文戏保留4＋4细化合同。'),('refine_denoise','二采去噪','number','sampling','跳舞长链独立精修生效；文戏由其细化sigma计划控制。'),
 ('split_step','一采步数／切点','number','sampling','原跳舞日程的分割位置，默认8。二采自动使用剩余步数与对应sigmas，不另建去噪日程。'),
 ('reference_size','参考图精度','choice','assets','max保留较多参考细节，可能明显增加显存和耗时。'),('audio_policy','输出声音','choice','assets','原生声音来自采样解码；换人还可选择源片原声。'),
 ('low_vram','低显存分块','boolean','memory','实际添加Attention/FeedForward分块。'),('sage','Sage注意力','boolean','memory','添加SageAttention补丁；不与另一注意力补丁重复叠加。'),('head_chunks','Attention分块数','number','memory','低显存分块开启时写入节点。'),('ff_chunks','FeedForward分块数','number','memory','低显存分块开启时写入节点。'),('seq_threshold','FF序列阈值','number','memory','达到该阈值时分块。'),
 ('temporal_chunking','放大器时间分块','boolean','memory','跳舞学习型放大器的内存优化，不拆生成任务。'),('force_unload','放大后卸载','boolean','memory','跳舞放大器移出GPU；文戏使用offload_after。'),
 ('acceleration','官方加速LoRA','boolean','lora','仅官方配方；启用真实加载，基线步数仍保留。'),('accel_file','加速LoRA文件','lora','lora','从本地LoRA目录选择；文件按原选择加载，兼容性由ComfyUI判断。'),('accel_strength','加速强度','number','lora','0强度视为旁路，恢复原基线步数。'),
 ('video_vae','视频VAE','vae','advanced','读取本地VAE目录；按原选择加载，兼容性由ComfyUI判断。'),('audio_vae','音频VAE','vae','advanced','真实音频解码器。'),('clip','文本编码器','clip','advanced','H3对应的Qwen编码器。'),('shift_video','文戏视频shift','number','advanced','文戏双时钟与精修节点同时绑定。'),('shift_audio','文戏音频shift','number','advanced','文戏双时钟与精修节点同时绑定。')]

class Recipes:
    def __init__(self,comfy,cache_path=None,model_config=None):
        from .generation.catalog import EngineCatalog
        from .generation.local_models import LocalModels
        self.local_models=LocalModels(model_config) if model_config else None
        self.comfy=comfy;self.checked=0;self.offline=True
        self.engine_catalog=EngineCatalog(comfy,cache_path or SOURCES/'engine_catalog.local.json',SOURCES/'builtin_catalog.json')
        self.info=self.engine_catalog.info
    def refresh(self):
        """Compatibility entry point: ordinary reads never touch the engine."""
        return self.info
    def connect(self):
        try:return self.engine_catalog.connect()
        finally:
            self.info=self.engine_catalog.info;self.offline=not self.engine_catalog.connected
    def catalog(self):
        self.refresh()
        catalog = dict(recipes=[dict(id=k,**r,defaults=defaults(k),validation='结构适配，未运行生成') for k,r in RECIPES.items()],
                    parameters=[dict(key=k,label=l,type=t,group=g,help=h) for k,l,t,g,h in PARAMETERS],offline=self.offline,
                    models=options(self.info,'UNETLoader','unet_name'),loras=options(self.info,'LoraLoaderModelOnly','lora_name'),
                    vaes=options(self.info,'VAELoader','vae_name'),clips=options(self.info,'CLIPLoader','clip_name'),
                    samplers=options(self.info,'KSamplerSelect','sampler_name'),schedulers=options(self.info,'BasicScheduler','scheduler'),sources=json.loads((SOURCES/'manifest.json').read_text(encoding='utf-8')))
        if self.local_models:catalog.update(self.local_models.scan())
        catalog['swap_preparation_version']=1
        catalog['swap_prompt_modes']=['template','custom']
        catalog['swap_template_version']=3
        catalog['asset_reference_modes']=['auto','custom','none']
        catalog['local_server_version']=1
        catalog['asset_library_version']=1
        catalog['engine']=self.engine_catalog.status()
        catalog['model_families']={name:model_family(name) for name in catalog['models']}
        result=decorate_catalog(catalog,self.info)
        if self.offline:
            for recipe in result['recipes']:
                for module in recipe['capabilities']['memory_modules']:module['installed']=None
        return result
    def normalize(self,s,mode,online=False):
        s=copy.deepcopy(s);r=RECIPES.get(s.get('recipe'))
        if not r or mode not in r['modes']:raise ValueError('工作流与当前模式不匹配')
        base=defaults(s['recipe']); unknown=set(s)-set(base)
        if unknown:raise ValueError('未知参数：'+','.join(sorted(unknown)))
        s={**base,**s};s['two_pass']=r['two_pass']
        if s['recipe']=='dance_split':
            total=float(s['steps']);split=float(s['split_step'])
            if not math.isfinite(split) or not split.is_integer() or not 1<=split<total:raise ValueError('一采切点须为整数，且小于总步数、两采均至少1步')
            s['split_step']=int(split);s['refine_steps']=int(total)-int(split)
        self.refresh()
        for key,node,field in [('model','UNETLoader','unet_name'),('video_vae','VAELoader','vae_name'),('audio_vae','VAELoader','vae_name'),('clip','CLIPLoader','clip_name')]:
            if not isinstance(s[key],str) or not s[key].strip():raise ValueError(f'{key}文件不能为空')
        ranges=dict(RANGES)
        if s['recipe']=='dance_split':ranges['refine_steps']=(1,49)
        for key,(low,high) in ranges.items():
            value=float(s[key])
            if not math.isfinite(value) or not low<=value<=high:raise ValueError(f'{key}须为{low}～{high}')
            if key in ['steps','refine_steps','head_chunks','ff_chunks','seq_threshold']:
                if not value.is_integer():raise ValueError(f'{key}必须是整数')
                s[key]=int(value)
            else:s[key]=value
        for k in ['sage','low_vram','acceleration','temporal_chunking','force_unload']:
            if not isinstance(s[k],bool):raise ValueError(k+'必须是开关值')
        if int(s['export_fps']) not in [24,25,30,50,60]:raise ValueError('导出帧率不支持')
        if s['reference_size'] not in ['match','max']:raise ValueError('参考精度不支持')
        if s['audio_policy'] not in (['source','native'] if mode=='swap' else ['native']):raise ValueError('该模式必须输出原生声音')
        if s['sampler'] not in options(self.info,'KSamplerSelect','sampler_name') or s['scheduler'] not in options(self.info,'BasicScheduler','scheduler'):raise ValueError('采样器或调度器不支持')
        if s['recipe']=='wenxi_av' and (s['steps']!=8 or s['refine_steps']!=4 or s['sampler']!='euler' or s['scheduler']!='beta'):raise ValueError('文戏配方使用8步基础/4＋4细化及双时钟Euler；该合同暂不允许任意更换')
        loras=s['loras']
        if not isinstance(loras,list) or len(loras)!=3:raise ValueError('必须保留3个LoRA槽')
        full=0
        for item in loras:
            if not isinstance(item.get('bypass'),bool):raise ValueError('LoRA Bypass须为开关值')
            val=float(item['strength'])
            if not math.isfinite(val) or not -10<=val<=10:raise ValueError('LoRA强度须为-10～10')
            item['strength']=val
            if not item['bypass'] and val:
                if not item.get('file'):raise ValueError('启用的LoRA须选择文件')
                if item['file']=='minimax_h3_turbo_v4_step600_ema.safetensors':full+=1
        if full>1:raise ValueError('完整Turbo补丁只能启用一次')
        if r['official'] and any(not x['bypass'] and x['strength'] for x in loras):raise ValueError('官方基线仅开放匹配的加速LoRA；其他LoRA请使用跳舞配方')
        if s['recipe']=='dance_split':
            # Single source of truth: the three visible LoRA slots. No fourth
            # accelerator is silently appended by an unrelated global flag.
            active=[x for x in loras if not x['bypass'] and x['strength'] and 'turbo' in x['file'].lower()]
            s['acceleration']=bool(active)
            if active:s['accel_file']=active[0]['file'];s['accel_strength']=active[0]['strength']
            enabled=[x['file'] for x in loras if not x['bypass'] and x['strength']]
            if len(enabled)!=len(set(enabled)):raise ValueError('同一个LoRA不能在多个已启用槽位重复加载')
        elif s['acceleration']:
            if not r['official']:raise ValueError('该加速开关仅用于官方工作流，跳舞配方使用三个LoRA槽')
            if not isinstance(s['accel_file'],str) or not s['accel_file'].strip():raise ValueError('启用加速LoRA时须选择文件')
        geometry(s);return s

    def compile(self,p,seg,assets,prompt,attempt='preview',previous=None,prepare=False):
        input_rows=validate_inputs(p,seg,assets)
        s=p['settings'];r=RECIPES[s['recipe']];g={};bindings=[];size=geometry(s)
        faithful=s['recipe']=='dance_split'
        def node(n,typ,**kw):g[str(n)]=dict(class_type=typ,inputs=kw);return [str(n),0]
        def bind(key,n,k):bindings.append(dict(parameter=key,node=str(n),input=k,value=g[str(n)]['inputs'].get(k)))
        model=node(1,'UNETLoader',unet_name=s['model'],weight_dtype='default');bind('model',1,'unet_name')
        clip=node(2,'CLIPLoader',clip_name=s['clip'],type='minimax',device='default');vvae=node(3,'VAELoader',vae_name=s['video_vae']);avae=node(4,'VAELoader',vae_name=s['audio_vae'])
        for k,n,f in [('clip',2,'clip_name'),('video_vae',3,'vae_name'),('audio_vae',4,'vae_name')]:bind(k,n,f)
        if s['sage']:model=node(210,'MiniMaxH3MemoryEfficientSageAttentionPatch',model=model)
        effective_steps=s['steps'];patches=['source: '+r['source']]
        if r['official']:
            if s['acceleration'] and s['accel_strength']:
                model=node(200,'LoraLoaderModelOnly',model=model,lora_name=s['accel_file'],strength_model=s['accel_strength']);effective_steps=8 if s['recipe']=='official_text' else 4
                bind('accel_file',200,'lora_name');bind('accel_strength',200,'strength_model');patches.append('optional acceleration')
        else:
            for i,l in enumerate(s['loras']):
                if l['bypass'] or not l['strength']:continue
                nid=200+i
                if l['file']=='minimax_h3_turbo_v4_step600_ema.safetensors':model=node(nid,'MiniMaxH3TurboLoRA',model=model,lora_name=l['file'],strength=l['strength'],low_vram=True);strengthkey='strength'
                else:model=node(nid,'LoraLoaderBypassModelOnly' if s['recipe']=='wenxi_av' else 'LoraLoaderModelOnly',model=model,lora_name=l['file'],strength_model=l['strength']);strengthkey='strength_model'
                bind(f'loras.{i}.file',nid,'lora_name');bind(f'loras.{i}.strength',nid,strengthkey)
        if s['low_vram']:
            model=node(211,'MiniMaxLowVRAMAttention',model=model,head_chunks=s['head_chunks']);model=node(212,'MiniMaxChunkFeedForward',model=model,chunks=s['ff_chunks'],seq_threshold=s['seq_threshold'])
            for key,n,k in [('head_chunks',211,'head_chunks'),('ff_chunks',212,'chunks'),('seq_threshold',212,'seq_threshold')]:bind(key,n,k)
        inputs=dict(clip=clip,vae=vvae,audio_vae=avae,prompt=prompt,width=size['width'],height=size['height'],length=seg['raw'],ref_image_size=s['reference_size'])
        mapping=[]
        for row in input_rows:
            if row['kind']=='video':continue
            link=node(row['loader_node'],'LoadImage',image=row['input_name']) if row['kind']=='image' else node(row['loader_node'],'LoadAudio',audio=row['input_name'])
            inputs[row['conditioning_input']]=link
            mapping.extend(public_inventory([row]))
        if p['mode']=='swap':
            source=next(row for row in input_rows if row['kind']=='video')
            src=node(source['loader_node'],'LoadVideo',file=source['input_name'] or '__source_pending__.mp4');node(49,'GetVideoComponents',video=src);inputs[source['conditioning_input']]=['49',0]
        wenxi=s['recipe']=='wenxi_av'
        if s['recipe']=='official_text':
            inputs={k:v for k,v in inputs.items() if k not in ('audio_vae','ref_image_size')};ct='MiniMaxH3ImageToVideo'
        elif wenxi:
            inputs['video_vae']=inputs.pop('vae');inputs.update(task_type='Ref2VA',audio_mode='native',audio_denoise_strength=1.,add_source_as_reference=False,prompt_primary_audio_ordinal=0,strict_prompt_tags=True,reference_video_policy='model_minimum');ct='MiniMaxH3AudioConditioningT8'
        else:ct='MiniMaxH3ReferenceToVideo'
        cond=node(20,ct,**inputs);latent=['20',1];base_cond=cond
        for k,f in [('resolution.width','width'),('resolution.height','height'),('segment.raw','length'),('prompt','prompt')]:bind(k,20,f)
        if seg['head']:
            prevpath=previous or '__previous_selected_av_pending__.safetensors'
            if faithful:
                if previous is None:prevpath=dict(video='__previous_accepted_lossless_tail.mkv',frame_count=22,audio='__previous_accepted_tail.wav')
                if not isinstance(prevpath,dict) or prevpath.get('frame_count')!=22 or not prevpath.get('video') or not prevpath.get('audio'):raise ValueError('原8＋4续接需要二采完成后的22帧无损尾部及声音；不能接一采中间latent')
                video=node(101,'LoadVideo',file=prevpath['video']);node(102,'GetVideoComponents',video=video)
                resized=node(103,'ImageScale',image=['102',0],upscale_method='area',width=size['width'],height=size['height'],crop='disabled')
                sound=node(645,'LoadAudio',audio=prevpath['audio'])
                cond=node(105,'MiniMaxH3MotionContext',conditioning=base_cond,vae=vvae,latent=latent,context_frames=resized,context_audio=sound,audio_vae=avae,context_length='22',audio_context_length=24)
                patches.append('continuation only: encode accepted pass-2 lossless tail into base-size motion context; high pass keeps original conditioning')
            elif isinstance(prevpath,dict):
                video=node(101,'LoadVideo',file=prevpath['video'])
                node(102,'GetVideoComponents',video=video)
                tail=node(104,'ImageFromBatch',image=['102',0],batch_index=max(0,prevpath.get('frames',22)-22),length=22)
                resized=node(103,'ImageScale',image=tail,upscale_method='area',width=size['width'],height=size['height'],crop='disabled')
                cond=node(105,'MiniMaxH3MotionContext',conditioning=base_cond,vae=vvae,latent=latent,context_frames=resized,context_audio=['102',1],audio_vae=avae,context_length='22',audio_context_length=24)
                patches.append('Trimmed storyboard boundary: re-encode delivered 22-frame AV tail, never use future latent frames')
            else:
                prev=node(101,'MiniMaxH3MotionContextLoadLatent',latent_path=str(prevpath),clip_index=1)
                cond=node(105,'MiniMaxH3MotionContext',conditioning=base_cond,vae=vvae,latent=latent,context_latent=prev,audio_vae=avae,context_length='22',audio_context_length=24)
            patches.append('long-video AV context (not official baseline)')
        noise=node(12,'RandomNoise',noise_seed=int(seg.get('actual_seed',seg.get('seed','1'))));bind('actual_seed',12,'noise_seed')
        if wenxi:
            node(8,'MiniMaxH3DualClockSamplerT8',model=model,av_latent=latent,steps=8,shift_video=s['shift_video'],shift_audio=s['shift_audio'],sampler_name='dual_clock_euler',scheduler='native_flow')
            guide=node(15,'BasicGuider',model=['8',0],conditioning=cond)
            complete=node(16,'SamplerCustomAdvanced',noise=noise,guider=guide,sampler=['8',1],sigmas=['8',2],latent_image=latent)
            node(9,'MiniMaxH3LearnedTwoPassParityPlanT8Advanced',model=['8',0],base_steps=8,coarse_steps=4,refine_steps=4)
            node(50,'SamplerCustomAdvanced',noise=noise,guider=guide,sampler=['8',1],sigmas=['9',0],latent_image=latent)
            node(51,'MiniMaxH3LearnedLatentUpscaleT8Advanced',av_latent=['50',1],model_name=UPSCALE,size_mode='scale_by',scale_by=s['scale'],target_megapixels=1.,target_width=1280,target_height=704,aspect_policy='preserve_source',max_anisotropy=1.05,precision='fp16',release_policy='offload_after')
            hi=copy.deepcopy(inputs);hi.update(width=['51',1],height=['51',2]);node(52,ct,**hi)
            node(53,'MiniMaxH3TwoPassLatentReconcileT8Advanced',learned_latent=['51',0],highres_template=['52',1],positive=['52',0],audio_policy='auto',second_pass_audio_source='legacy_policy',second_pass_audio_strength=0.)
            node(54,'MiniMaxH3TwoPassDetailMixerT8Advanced',model=model,av_latent=['53',0],refine_sigmas=['9',1],shift_video=s['shift_video'],shift_audio=s['shift_audio'],enable_tail=False,extra_tail_steps=1,tail_spacing='video_sigma_linear',enable_model_time_bias=False,bias=-.025,bias_start_progress=.7,bias_end_progress=.95,bias_domain='video_sigma',enable_stg=False,stg_scale=.35,stg_double_blocks='25',stg_start_progress=.25,stg_end_progress=.85,enable_restart=False,restart_video_sigma=.15,restart_steps=3,restart_seed=int(seg.get('actual_seed',seg['seed'])))
            hi_guide=node(55,'BasicGuider',model=['54',0],conditioning=['53',1]);final=node(214,'SamplerCustomAdvanced',noise=noise,guider=hi_guide,sampler=['54',1],sigmas=['54',2],latent_image=['53',0])
            for k in ['shift_video','shift_audio']:bind(k,8,k);bind(k,54,k)
            bind('scale',51,'scale_by');patches.append('wenxi + extra complete low-res AV checkpoint/audio branch')
        elif faithful:
            sampler=node(13,'KSamplerSelect',sampler_name=s['sampler'])
            sigmas=node(14,'BasicScheduler',model=model,scheduler=s['scheduler'],steps=s['steps'],denoise=1.)
            node(289,'SplitSigmas',sigmas=sigmas,step=s['split_step'])
            guide=node(15,'BasicGuider',model=model,conditioning=cond)
            complete=node(16,'SamplerCustomAdvanced',noise=noise,guider=guide,sampler=sampler,sigmas=['289',0],latent_image=latent)
            node(216,'LTXVSeparateAVLatent',av_latent=['16',1])
            up=node(215,'MinimaxH3LatentUpscaler3D',latent=['216',0],model_name=UPSCALE,mode='scale by multiplier',**{'mode.scale':s['scale']},align=32,enable_temporal_chunking=s['temporal_chunking'],force_unload=s['force_unload'],device='cuda',precision='fp16')
            joined=node(217,'LTXVConcatAVLatent',video_latent=up,audio_latent=['216',1])
            # No MC on independent shots: reuse the exact same guider, as the
            # source does. Continuations must not reuse low-size MC keyframes.
            high_guide=node(220,'BasicGuider',model=model,conditioning=base_cond) if seg['head'] else guide
            node(214,'SamplerCustomAdvanced',noise=noise,guider=high_guide,sampler=sampler,sigmas=['289',1],latent_image=joined)
            final=['214',1]
            for k,n,f in [('steps',14,'steps'),('split_step',289,'step'),('sampler',13,'sampler_name'),('scheduler',14,'scheduler'),('scale',215,'mode.scale'),('temporal_chunking',215,'enable_temporal_chunking'),('force_unload',215,'force_unload')]:bind(k,n,f)
            patches.append('original split core: shared sigma schedule/noise/Euler; pass-1 denoised -> learned upscale -> remaining sigmas -> pass-2 denoised AV')
        else:
            sampler=node(13,'KSamplerSelect',sampler_name=s['sampler']);sigmas=node(14,'BasicScheduler',model=model,scheduler=s['scheduler'],steps=effective_steps,denoise=1.);guide=node(15,'BasicGuider',model=model,conditioning=cond)
            complete=node(16,'SamplerCustomAdvanced',noise=noise,guider=guide,sampler=sampler,sigmas=sigmas,latent_image=latent);final=complete
            bind('sampler',13,'sampler_name');bind('scheduler',14,'scheduler');bind('effective_steps',14,'steps')
            if s['two_pass']:
                node(216,'LTXVSeparateAVLatent',av_latent=complete)
                up=node(215,'MinimaxH3LatentUpscaler3D',latent=['216',0],model_name=UPSCALE,mode='scale by multiplier',**{'mode.scale':s['scale']},align=32,enable_temporal_chunking=s['temporal_chunking'],force_unload=s['force_unload'],device='cuda',precision='fp16')
                joined=node(217,'LTXVConcatAVLatent',video_latent=up,audio_latent=['216',1]);hi_guide=node(220,'BasicGuider',model=model,conditioning=base_cond)
                hi_sampler=node(221,'KSamplerSelect',sampler_name='res_multistep');hi_sigmas=node(222,'BasicScheduler',model=model,scheduler='simple',steps=s['refine_steps'],denoise=s['refine_denoise'])
                final=node(214,'SamplerCustomAdvanced',noise=noise,guider=hi_guide,sampler=hi_sampler,sigmas=hi_sigmas,latent_image=joined)
                for k,n,f in [('scale',215,'mode.scale'),('refine_steps',222,'steps'),('refine_denoise',222,'denoise'),('temporal_chunking',215,'enable_temporal_chunking'),('force_unload',215,'force_unload')]:bind(k,n,f)
                patches.append('complete base + independent refinement; not source 8+4')
        images_out=node(17,'VAEDecode',samples=final,vae=vvae)
        audio_out=node(23,'VAEDecodeAudio',samples=final if faithful else complete,vae=avae)
        combined=node(18,'CreateVideo',images=images_out,audio=audio_out,fps=24.,bit_depth=8)
        prefix=f'time_forest_v5/{p["id"]}/{seg["id"]}/{attempt}'
        node(19,'SaveVideo',video=combined,filename_prefix=prefix+'/raw',format='mp4',**{'format.codec':'h264'})
        node(393,'MiniMaxH3MotionContextSaveLatent',latent=final if faithful else complete,filename_prefix=prefix+'/context',clip_index=1)
        if faithful:
            tail_count=min(22,seg['head']+seg['deliver'])
            tail=node(394,'ImageFromBatch',image=images_out,batch_index=seg['head']+seg['deliver']-tail_count,length=tail_count)
            node(395,'SaveImage',images=tail,filename_prefix=prefix+'/tail/frame')
            node(396,'SaveAudio',audio=audio_out,filename_prefix=prefix+'/tail/audio')
        issues=self.validate(g)
        return dict(workflow=g,bindings=bindings,asset_map=mapping,input_inventory=public_inventory(input_rows),prompt_template_version=p.get('swap_prompt',{}).get('version',1) if p['mode']=='swap' else None,issues=issues,online_verified=not self.offline,patches=patches,output_node='19',context_relative=prefix+'/context_00001.safetensors',
                    geometry=size,effective_steps=s['split_step'] if faithful else effective_steps,generated_fps=24,export_fps=s['export_fps'],validation='未运行生成',
                    core_contract='dance-split-v1' if faithful else 'legacy-or-official',
                    source_sha256=hashlib.sha256((SOURCES/r['source']).read_bytes()).hexdigest(),
                    context_kind='pass2_lossless_tail' if faithful else 'complete_base_av',
                    tail_image_node='395' if faithful else None,tail_audio_node='396' if faithful else None)

    def validate(self,g):
        issues=[]
        for nid,n in g.items():
            schema=self.info.get(n['class_type'])
            if schema is None:issues.append('缺少节点：'+n['class_type']);continue
            for key,spec in schema.get('input',{}).get('required',{}).items():
                if key not in n['inputs']:issues.append(f'{nid}/{n["class_type"]}缺少必填输入{key}')
            def dynamic(key,spec):
                if spec[0]!='COMFY_DYNAMICCOMBO_V3' or key not in n['inputs']:return
                selected=n['inputs'][key]
                if isinstance(selected,list):return
                option=next((o for o in spec[1].get('options',[]) if o.get('key')==selected),None)
                if option is None:issues.append(f'{nid}.{key}动态选项不支持');return
                for child,cspec in option.get('inputs',{}).get('required',{}).items():
                    full=key+'.'+child
                    if full not in n['inputs']:issues.append(f'{nid}缺少动态输入{full}')
                    dynamic(full,cspec)
            for key,spec in {**schema.get('input',{}).get('required',{}),**schema.get('input',{}).get('optional',{})}.items():dynamic(key,spec)
            for k,v in n['inputs'].items():
                if isinstance(v,list) and len(v)==2:
                    src=g.get(str(v[0]))
                    if not src:issues.append(f'{nid}.{k}连接缺失');continue
                    outputs=self.info.get(src['class_type'],{}).get('output',[])
                    if not isinstance(v[1],int) or not 0<=v[1]<len(outputs):issues.append(f'{nid}.{k}输出槽越界')
                    elif k in schema.get('input',{}).get('required',{}):
                        expected=schema['input']['required'][k][0];actual=outputs[v[1]]
                        if isinstance(expected,str) and expected not in ['*','COMFY_DYNAMICCOMBO_V3','COMBO'] and actual not in ['*',expected] and actual not in expected.split(','):
                            issues.append(f'{nid}.{k}类型不匹配：{actual}→{expected}')
                else:
                    spec=schema.get('input',{}).get('required',{}).get(k) or schema.get('input',{}).get('optional',{}).get(k)
                    if spec and len(spec)>1 and isinstance(spec[1],dict) and isinstance(v,(int,float)) and not isinstance(v,bool):
                        if ('min' in spec[1] and v<spec[1]['min']) or ('max' in spec[1] and v>spec[1]['max']):issues.append(f'{nid}.{k}超出本机节点范围')
        seen=set();active=set()
        def visit(n):
            if n in active:raise ValueError('工作流存在循环连接')
            if n in seen or n not in g:return
            active.add(n)
            for v in g[n]['inputs'].values():
                if isinstance(v,list) and len(v)==2:visit(str(v[0]))
            active.remove(n);seen.add(n)
        try:
            for n in g:visit(n)
        except ValueError as e:issues.append(str(e))
        return issues
