"""External decoded-tail adapters. Never mutate the existing recipe definitions."""
import copy
import math
from ..studio_plan import aligned, frames
from ..studio_recipes import defaults
from ..studio_inputs import inventory, validate_tags

ADAPTER_VERSION = 1
RECIPES = {'dance_split': '跳舞工作流 · 8＋4 续接', 'official_image': '官方工作流 · 续接适配'}


def settings(recipes, value):
    if value.get('recipe') not in RECIPES:
        raise ValueError('请选择跳舞或官方续接工作流')
    return recipes.normalize(value, 'image_story')


def plan(seconds, cap_seconds=15):
    total = frames(seconds)
    if not 24 <= total <= 86400:
        raise ValueError('新增时长须为1～3600秒')
    cap = 5 + 17 * math.floor((min(frames(cap_seconds), 360) - 5) / 17)
    if cap < 124:
        raise ValueError('单次渲染上限至少约5.167秒')
    result = []
    while total:
        deliver = min(total, cap - 22)
        raw = max(124, aligned(deliver + 22))
        result.append(dict(raw=raw, head=22, deliver=deliver, tail=raw-22-deliver))
        total -= deliver
    return result


def compile_tail(recipes, pid, sid, configuration, part, seed, prompt, context, run_id, assets=None):
    s = settings(recipes, configuration)
    if context.get('kind') != 'external_decoded_av' or context.get('frame_count') != 22 or not context.get('video') or not context.get('audio'):
        raise ValueError('续接需要经过准备的22帧视频尾部和对齐声音')
    if not str(prompt).strip():
        raise ValueError('请填写后续画面与声音描述')
    # The private compiler projection is not a saved story project. No source
    # video or library prompt is bound to the Ref2VA reference-video slot.
    p = dict(id=pid, mode='image_story', settings=s)
    assets = assets or []
    seg = dict(id=sid, index=0, assets=[a['id'] for a in assets], inherit_ids=[], asset_mode='custom' if assets else 'none',
               seed=str(seed), actual_seed=seed, **part)
    previous = dict(video=context['video'], audio=context['audio'], frame_count=22, frames=22)
    validate_tags(prompt, inventory(p,seg,assets))
    result = recipes.compile(p, seg, assets, prompt, attempt=run_id, previous=previous)
    graph = result['workflow']
    if s['recipe'] == 'official_image':
        # Existing generic video branch takes the video's entire audio stream.
        # External tails use their independently aligned one-second audio.
        graph['645'] = dict(class_type='LoadAudio', inputs=dict(audio=context['audio']))
        graph['105']['inputs']['context_audio'] = ['645', 0]
    # This mode always prepares explicit pixel/audio tails; no latent checkpoint
    # is reused or advertised as an original lossless pass-2 checkpoint.
    for node in ('393', '394', '395', '396'):
        graph.pop(node, None)
    result.update(issues=recipes.validate(graph), context_kind='external_decoded_av',
                  adapter_id='assembly.'+s['recipe'], adapter_revision=ADAPTER_VERSION, context=copy.deepcopy(context),
                  context_relative=None, tail_image_node=None, tail_audio_node=None)
    result['patches'] = [text for text in result['patches'] if not text.startswith(('continuation only:', 'Trimmed storyboard boundary:'))]
    result['patches'].append('External decoded AV tail adapter: 22 video / 24 audio frames; no latent or internal pass-2 checkpoint reuse')
    result['bindings'] += [dict(parameter='tail.video', node='101', input='file', value=context['video']),
                           dict(parameter='tail.audio', node='645', input='audio', value=context['audio'])]
    return result


def catalog(recipes):
    result = recipes.catalog()
    result['assembly_contract_version'] = ADAPTER_VERSION
    result['assembly_reference_version'] = 1
    result['assembly_track_version'] = 1
    result['assembly_source_parameters_version'] = 1
    result['assembly_tail_preparation_version'] = 2
    result['recipes'] = [{**r, 'name': RECIPES[r['id']]} for r in result['recipes'] if r['id'] in RECIPES]
    # These fields are not consumed by this external-tail adapter. Conditional
    # visibility of the remaining definitions is resolved per recipe by UI.
    omitted = {'recipe', 'export_fps', 'audio_policy', 'shift_video', 'shift_audio', 'refine_denoise', 'refine_steps'}
    result['parameters'] = [p for p in result['parameters'] if p['key'] not in omitted]
    for recipe in result['recipes']:
        recipe['parameters'] = [p for p in recipe['parameters'] if p['key'] not in omitted]
    result['defaults'] = {key: defaults(key) for key in RECIPES}
    return result
