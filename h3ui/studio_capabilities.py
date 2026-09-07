"""UI contracts derived from registered compiler recipes; no rendering or queueing."""
import copy

RANGES = {
    'steps': (1, 50), 'refine_steps': (1, 20), 'refine_denoise': (.01, 1),
    'denoise': (1, 1), 'scale': (1, 2), 'head_chunks': (1, 32), 'ff_chunks': (1, 32),
    'seq_threshold': (128, 32768), 'render_cap': (124/24, 15),
    'shift_video': (.01, 100), 'shift_audio': (.01, 100), 'accel_strength': (-10, 10),
}

def decorate_catalog(catalog, node_info):
    """Versioned additive fields; v5 clients can continue using their existing keys."""
    result=copy.deepcopy(catalog)
    result['contract_version']=2
    result['input_contract_version']=2
    for recipe in result['recipes']:
        rid=recipe['id'];official=recipe['official'];two=recipe['two_pass']
        omitted=set()
        if rid!='dance_split':omitted.add('split_step')
        else:omitted.update(['refine_steps','refine_denoise'])
        if not two:omitted.update(['scale','refine_steps','refine_denoise','temporal_chunking','force_unload'])
        if rid=='official_text':omitted.add('reference_size')
        if rid=='wenxi_av':omitted.update(['sampler','scheduler','steps','refine_steps','refine_denoise','temporal_chunking','force_unload'])
        else:omitted.update(['shift_video','shift_audio'])
        if not official:omitted.update(['acceleration','accel_file','accel_strength'])
        fields=[]
        for original in result['parameters']:
            key=original['key']
            if key in omitted:continue
            f=copy.deepcopy(original)
            if key in ['width','height']:f['when']={'size_mode':'custom'}
            if key in ['aspect','megapixels']:f['when']={'size_mode':'area'}
            if key in ['head_chunks','ff_chunks','seq_threshold']:f['when']={'low_vram':True}
            if key in ['accel_file','accel_strength']:f['when']={'acceleration':True}
            bounds=RANGES.get(key)
            if key=='split_step':bounds=(1,49)
            if key in ['width','height']:bounds=(128,2048)
            if bounds:f.update(min=bounds[0],max=bounds[1])
            f['step']=32 if key in ['width','height'] else 1 if key in ['steps','split_step','refine_steps','head_chunks','ff_chunks','seq_threshold'] else .01
            if key=='render_cap':f['step']='any'
            if rid=='dance_split':
                replacements={
                    'steps':('总采样步数','同一条日程的总步数；一采切点8、总步数12时，二采使用剩余4步。'),
                    'sampler':('两采共享采样器','两采共用一个采样器；原跳舞基线为Euler。'),
                    'scheduler':('两采共享调度器','原基线beta，整条日程降噪1.0；按切点分配两采，不另设二采降噪。'),
                }
                if key in replacements:f['label'],f['help']=replacements[key]
            fields.append(f)
        recipe['parameters']=fields
        recipe['capabilities']={
            'native_fps':24,'max_render_seconds':15,'reference_images':rid!='official_text',
            'model_families':['fl'] if rid=='official_text' else ['ref','hybrid'],
            'reference_audio':rid!='official_text','max_images':9 if rid!='official_text' else 0,
            'max_audio':3 if rid!='official_text' else 0,'max_audio_seconds':15,
            'source_video':'swap' in recipe['modes'],'generated_audio':True,
            'continuation':'pass2_lossless_tail' if rid=='dance_split' else 'av_context',
            'lora_slots':0 if official else 3,'official_acceleration':official,
            'sampler_structure':'split_schedule' if rid=='dance_split' else 'dual_clock' if rid=='wenxi_av' else 'independent_refinement' if two else 'single_pass',
            'memory_modules':[{ 'key':key,'node':node,'installed':node in node_info} for key,node in [('low_vram','MiniMaxLowVRAMAttention'),('feed_forward','MiniMaxChunkFeedForward'),('sage','MiniMaxH3MemoryEfficientSageAttentionPatch')]],
            'verification':'结构适配；不代表所有参数组合的显存和生成质量已验证',
        }
        recipe['capabilities']['by_mode']={mode:{'max_images':1 if mode=='swap' else 0 if rid=='official_text' else 9,
            'max_audio':0 if rid=='official_text' else 3,'max_mixed_inputs':12,
            'source_video':mode=='swap'} for mode in recipe['modes']}
    return result
