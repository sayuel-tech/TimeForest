"""Compile the four Krea edit branches and their native text adapter, offline."""
import copy
import hashlib
import json
import math
import re
from pathlib import Path

SOURCE = Path(__file__).parent / 'sources' / 'krea-edit.json'
SOURCE_HASH = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
PLUGIN_VERSION = '86f886dac23013d88996e3a2e99093ba44d322fb'
TOOLS = {'single': '单图编辑', 'dual': '双图编辑', 'region': '局部重绘／移除', 'outpaint': '图像扩展', 'text': '文生图'}
OUTPUTS = {'single': 27, 'dual': 2, 'region': 91, 'outpaint': 66, 'text': 27}
TEXT_ADAPTER_REVISION = 1
DEFAULTS = dict(megapixels=1, output_mp=1.5, ratio='2:3', steps=10, cfg=1,
                sampler_name='euler', scheduler='simple', seed=None, ref_boost=4,
                ref_boost_a=1, grounding_px=768, fit_mode='fit', strength_model=1,
                left=504, top=0, right=504, bottom=0, feathering=0)
MODELS = dict(unet='krea2_turbo_int8_convrot.safetensors', clip='qwen3vl_4b_fp8_scaled.safetensors',
              vae='qwen_image_vae.safetensors', lora='Krea2-编辑identity_edit_v1_2.safetensors')
WIDGETS = {
    'UNETLoader': ['unet_name', 'weight_dtype'], 'CLIPLoader': ['clip_name', 'type', 'device'],
    'VAELoader': ['vae_name'], 'LoraLoaderModelOnly': ['lora_name', 'strength_model'],
    'Krea2EditModelPatch': ['ref_boost', 'ref_boost_a', 'fit_mode'],
    'Krea2EditGroundedEncode': ['prompt', 'grounding_px', 'system_prompt'],
    'KSampler': ['seed', None, 'steps', 'cfg', 'sampler_name', 'scheduler', 'denoise'],
    'EmptySD3LatentImage': ['width', 'height', 'batch_size'],
    'ImageScaleToTotalPixels': ['upscale_method', 'megapixels', 'resolution_steps'],
    'ResolutionSelector': ['aspect_ratio', 'megapixels', 'multiple'],
    'LoadImage': ['image'], 'SaveImage': ['filename_prefix'],
    'DrawMaskOnImage': ['color', 'device'],
    'ImagePadForOutpaint': ['left', 'top', 'right', 'bottom', 'feathering'],
    'VAEEncode': [], 'VAEDecode': [], 'GetImageSize+': [],
    'CLIPTextEncode': ['text'],
}


def model_roles(mode):
    return ('unet','clip','vae') if mode=='text' else ('unet','clip','vae','lora')


def required_nodes(mode):
    graph,_=compile_graph(mode,'contract',{'A':'A.png','B':'B.png'},{'seed':0})
    return {node['class_type'] for node in graph.values()}


def settings(raw=None):
    if raw is not None and not isinstance(raw, dict):
        raise ValueError('图片参数必须是字段对象')
    p = {**DEFAULTS, **{k: v for k, v in (raw or {}).items() if k in DEFAULTS}}
    for key, lo, hi in [('megapixels', .25, 2), ('output_mp', .25, 2), ('steps', 1, 50),
                        ('cfg', 1, 10), ('ref_boost', 0, 20), ('ref_boost_a', 0, 20),
                        ('strength_model', 0, 2), ('grounding_px', 0, 2048),
                        *[(k, 0, 4096) for k in ('left', 'right', 'top', 'bottom', 'feathering')]]:
        integer = key not in ('megapixels', 'output_mp', 'cfg', 'ref_boost', 'ref_boost_a', 'strength_model')
        if isinstance(p[key], bool) or p[key] is None:
            raise ValueError(f'参数 {key} 必须是有效数字')
        try:
            value = strict_integer(p[key], key) if integer else float(p[key])
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f'参数 {key} 必须是有效'+('整数' if integer else '数字')) from exc
        if not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f'参数 {key} 超出范围 {lo}—{hi}')
        p[key] = value
    if p['ratio'] not in ('1:1', '2:3', '3:2', '16:9', '9:16', '4:3', '3:4'):
        raise ValueError('输出比例不支持')
    if p['fit_mode'] not in ('fit', 'crop (legacy)') or p['sampler_name'] not in ('euler', 'heun', 'dpmpp_2m') or p['scheduler'] not in ('simple', 'normal', 'karras'):
        raise ValueError('采样或参考适配方式不支持')
    if p['seed'] not in (None, ''):
        p['seed'] = strict_integer(p['seed'], '固定种子')
        if not 0 <= p['seed'] <= 2**53-1:
            raise ValueError('固定种子超出范围')
    else:
        p['seed'] = None
    return p


def strict_integer(value, label):
    """Accept safe integer values, never truncate decimals or coerce booleans."""
    if isinstance(value, bool):
        raise ValueError(f'{label} 必须是整数')
    if isinstance(value, str):
        if not re.fullmatch(r'[0-9]+', value):
            raise ValueError(f'{label} 必须是十进制整数')
        value = int(value)
    elif not isinstance(value, (int, float)) or (isinstance(value, float) and (not math.isfinite(value) or not value.is_integer())):
        raise ValueError(f'{label} 必须是整数')
    if not 0 <= value <= 2**53-1:
        raise ValueError(f'{label} 超出安全整数范围 0—9007199254740991')
    return int(value)


def scale_size(w, h, mp):
    scale = math.sqrt(mp * 1024 * 1024 / (w * h))
    return max(8, round(w * scale / 8) * 8), max(8, round(h * scale / 8) * 8)


def geometry(mode, width, height, raw=None):
    p = settings(raw)
    if mode=='text':
        final=list(scale_size(*map(int,p['ratio'].split(':')),p['megapixels']))
        return dict(original=None,work=final,canvas=final,output=final,offset=[0,0])
    if mode not in TOOLS or min(width, height) < 1:
        raise ValueError('图片尺寸或工具无效')
    work = scale_size(width, height, 1 if mode == 'outpaint' else p['megapixels'])
    canvas = work
    if mode == 'outpaint':
        if not sum(p[k] for k in ('left', 'top', 'right', 'bottom')):
            raise ValueError('请至少扩展一边')
        canvas = (work[0]+p['left']+p['right'], work[1]+p['top']+p['bottom'])
        if canvas[0]*canvas[1] > 24*1024*1024:
            raise ValueError('扩展画布过大，请减少扩边')
        final = scale_size(*canvas, p['output_mp'])
    elif mode == 'dual':
        final = scale_size(*map(int, p['ratio'].split(':')), p['megapixels'])
    else:
        final = work
    return dict(original=[width, height], work=list(work), canvas=list(canvas), output=list(final),
                offset=[p['left'], p['top']] if mode == 'outpaint' else [0, 0])


def compile_graph(mode, prompt, files, raw=None, models=None, prefix='time-forest/image', size=None):
    if mode not in TOOLS or not str(prompt).strip():
        raise ValueError('请选择工具并填写编辑指令')
    if mode!='text' and (not files.get('A') or (mode == 'dual' and not files.get('B'))):
        raise ValueError('缺少图片A或B')
    p = settings(raw)
    if p['seed'] is None:
        raise ValueError('提交前必须确定实际种子')
    models = {**MODELS, **(models or {})}
    workflow = json.loads(SOURCE.read_text(encoding='utf-8'))
    nodes = {n['id']: n for n in workflow['nodes']}
    links = {l[0]: l for l in workflow['links']}
    if mode=='text':
        # Derive the source single-image chain without reference conditioning.
        # Keep its loader widgets, sampler, seed, decode and SaveImage wiring.
        nodes[35]={**copy.deepcopy(nodes[43]),'id':35}
        for nid in (36,34):
            original=nodes[nid]
            nodes[nid]={**original,'type':'CLIPTextEncode','widgets_values':[prompt.strip() if nid==36 else ''],
                        'inputs':[port for port in original['inputs'] if port['name']=='clip']}
        w,h=scale_size(*map(int,p['ratio'].split(':')),p['megapixels'])
        nodes[28]={**nodes[28],'inputs':[],'widgets_values':[w,h,1]}
    result = {}

    def node(nid):
        n = nodes[nid]
        kind = n['type']
        if kind == 'Seed (rgthree)':
            return p['seed']
        if kind == 'PrimitiveStringMultiline':
            return prompt.strip()
        key = str(nid)
        if key in result:
            return [key, 0]
        if kind not in WIDGETS:
            raise ValueError('附件包含未适配执行节点：'+kind)
        inputs = {k: v for k, v in zip(WIDGETS[kind], n.get('widgets_values') or []) if k}
        result[key] = dict(class_type=kind, inputs=inputs)
        for port in n.get('inputs', []):
            if port.get('link') is not None:
                link = links[port['link']]
                value = node(link[1])
                inputs[port['name']] = [str(link[1]), link[2]] if isinstance(value, list) else value
        if kind == 'LoadImage':
            inputs['image'] = files['B' if nid == 9 else 'A']
        elif kind == 'UNETLoader': inputs['unet_name'] = models['unet']
        elif kind == 'CLIPLoader': inputs.update(clip_name=models['clip'], type='krea2')
        elif kind == 'VAELoader': inputs['vae_name'] = models['vae']
        elif kind == 'LoraLoaderModelOnly': inputs.update(lora_name=models['lora'], strength_model=p['strength_model'])
        elif kind == 'Krea2EditModelPatch':
            inputs.update({k: p[k] for k in ('ref_boost', 'fit_mode')})
            if mode == 'dual': inputs['ref_boost_a'] = p['ref_boost_a']
        elif kind == 'Krea2EditGroundedEncode': inputs['grounding_px'] = p['grounding_px']
        elif kind == 'KSampler': inputs.update({k: p[k] for k in ('seed', 'steps', 'cfg', 'sampler_name', 'scheduler')})
        elif kind == 'SaveImage': inputs['filename_prefix'] = prefix
        elif kind == 'ImagePadForOutpaint': inputs.update({k: p[k] for k in ('left', 'top', 'right', 'bottom', 'feathering')})
        elif kind == 'ImageScaleToTotalPixels': inputs['megapixels'] = (p['output_mp'] if nid == 86 else 1) if mode == 'outpaint' else p['megapixels']
        elif kind == 'ResolutionSelector':
            # Precomputed by the same scale/round rule, replacing only the selector.
            w, h = scale_size(*map(int, p['ratio'].split(':')), p['megapixels'])
            result.pop(key)
            return [key, 0]
        return [key, 0]

    node(OUTPUTS[mode])
    if mode == 'dual':
        w, h = scale_size(*map(int, p['ratio'].split(':')), p['megapixels'])
        result['4']['inputs'].update(width=w, height=h)
    if size and mode == 'outpaint': geometry(mode, *size, p)
    return result, str(OUTPUTS[mode])
