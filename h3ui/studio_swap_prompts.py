"""Swap prompt policy. Custom text is submitted without a hidden template."""
import copy
import re
from .prompts import PromptStore, OFFICIAL_PROMPT, DANCE_PROMPT
from .swap_template_v2 import FIELDS as V2_FIELDS
from .studio_speakers import speakers
from .swap_template_v3 import fields as v3_fields, VERSION as LATEST_VERSION

def normalize(value=None):
    if value is not None and not isinstance(value,dict):raise ValueError('换人提示词设置格式错误')
    result={'mode':'template','custom':'','version':1,**(value or {})}
    if set(result)!={'mode','custom','version'} or result['mode'] not in ['template','custom'] or not isinstance(result['custom'],str) or result['version'] not in [1,2,3]:raise ValueError('换人提示词设置不合法')
    return result

def build(p,seg,assets,timing):
    policy=normalize(p.get('swap_prompt'))
    choice=seg.get('swap_prompt_mode','inherit')
    if choice not in ['inherit','template','custom']:raise ValueError('本段换人提示词方式不支持')
    mode=policy['mode'] if choice=='inherit' else choice
    if mode=='custom':
        text=policy['custom'] if choice=='inherit' else seg.get('swap_custom_prompt','')
        if not text.strip():raise ValueError('请填写自定义换人提示词，或选择通用换人提示词')
        for label in ['Picture','Video']:
            if not re.search(r'<'+label+r'\s+1>',text):raise ValueError(f'自定义换人正文需明确引用 <{label} 1>；可从通用模板复制后编辑')
        if p['settings']['audio_policy']=='source' and re.search(r'<d>|\[S\d+\]',text):
            raise ValueError('正文要求生成对白，但输出选择了保留原声。请改为H3生成声音，或移除新对白指令')
        return text
    if policy['version']==3:
        if p['settings']['audio_policy']=='source' and any(re.search(r'<d>|\[S\d+\]',seg.get(key,'')) for key in ['prompt','beats','voice']):
            raise ValueError('正文要求新对白，但输出选择了保留原声；请切换H3生成声音或移除新对白要求')
        return PromptStore({}).build_full(fields=v3_fields(p,seg,assets,timing),picture_count=sum(a['kind']=='image' for a in assets))
    fields=copy.deepcopy(V2_FIELDS if policy['version']==2 else OFFICIAL_PROMPT if p['settings']['recipe']=='official_swap' else DANCE_PROMPT)
    if p['settings']['audio_policy']=='native':
        fields['overall_soundscape']='Generate synchronized natural ambience and physical sounds appropriate to the scene. '+seg.get('soundscape','')
    audio=[a for a in assets if a['kind']=='audio']
    if policy['version']==2 and audio:
        mapping=speakers(seg,p['settings']['recipe']) or {}
        for i,a in enumerate(audio,1):
            sid=a.get('subject') or '1';number=mapping.get(sid);speaker=f' (S{number})' if number else ''
            fields['subject_definitions']+=f'\n<Audio {i}> provides the voice timbre and speaking manner of <Subject {sid}>{speaker}; use only these qualities, never repeat the recording’s words.'
            fields['retention_analysis']+=f'\n<Audio {i}>: reference - voice qualities only; speak the new dialogue in the direction below.'
        fields['summary']=fields['summary'].replace('[video editing + reference generation]','[video editing + reference generation + audio reference]')
    text=PromptStore({}).build_full(fields=fields,picture_count=sum(a['kind']=='image' for a in assets))
    notes=timing+'\n'+seg.get('prompt','').strip()
    for i,a in enumerate([a for a in assets if a['kind']=='audio'],1):
        notes+=f'\n<Audio {i}> provides voice timbre and speaking manner only. Do not repeat its words.'
    return text.replace('\n\noverall_soundscape:', '\n'+notes+'\n\noverall_soundscape:')
