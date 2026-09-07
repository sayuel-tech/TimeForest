"""Stable subjects, per-run media ordinals, no generated story text."""
import re
from .studio_inputs import grouped, validate, validate_tags
from .studio_speakers import speakers

def build(p,seg,assets):
    inputs=validate(p,seg,assets);groups=grouped(assets);images=groups['image'];audio=groups['audio']
    subjects={};definitions=[];speaker_map=speakers(seg,p['settings']['recipe'])
    for i,a in enumerate(images,1):
        subject=(a.get('subject') or '').strip();purpose=a.get('purpose','character')
        tag=f'<Picture {i}>'
        if purpose in ['character','face','costume']:
            if not subject:raise ValueError(f'图片{i}需要角色ID，例如1；同角色多个视图填写相同ID')
            if not re.fullmatch(r'[1-9][0-9]?',subject):raise ValueError('角色ID须为1～99整数')
            subjects.setdefault(subject,[]).append(tag)
        else:definitions.append(f'{tag} provides {dict(scene="scene/environment",palette="color palette and visual style only, never render swatches",prop="prop appearance").get(purpose,purpose)}.')
    for sid,tags in subjects.items():definitions.append(f'<Subject {sid}> is the character defined by {", ".join(tags)}; preserve identity, hairstyle, physique and outfit. Multiple views depict this same individual, never a collage.')
    for i,a in enumerate(audio,1):
        sid=a.get('subject') or '1'
        legacy=p.get('input_prompt_version',1)==1 and not speaker_map
        number=sid if speaker_map is None or legacy else speaker_map.get(sid)
        speaker=f' (S{number})' if number else ''
        definitions.append(f'<Audio {i}> provides voice timbre and speaking manner for <Subject {sid}>{speaker}. Refer only to the voice qualities; do not repeat the recording\'s words. Speak only the new dialogue written below.')
    user=seg.get('prompt','').strip()
    if seg.get('task_instruction'):user=seg['task_instruction']+'\n'+user
    if p['mode']!='swap' and not user:raise ValueError('请填写本段人工提示词')
    head=seg['head'];timing=f'This output contains {seg["raw"]} frames at 24fps. '
    if head:timing+=f'The first {head} frames repeat the previous audiovisual context. Continue the new action after that boundary; do not restart or repeat dialogue.'
    else:timing+='Establish the requested opening immediately.'
    if head and seg.get('asset_mode')=='none':timing+=' Use the supplied previous audiovisual context to continue the established appearance, scene, voice and ambience. No additional still-image or voice reference is supplied. Speak only the new dialogue below.'
    if seg['tail']:timing+=f' Only {seg["deliver"]/24:.6f} seconds after the context will be delivered. Finish the requested dialogue/action within this window; continue naturally through the unused tail.'
    if seg.get('prompt_mode')=='full' and p['mode']!='swap':
        text=user
    elif p['mode']=='swap':
        from .studio_swap_prompts import build as swap_prompt
        text=swap_prompt(p,seg,assets,timing)
    elif p['settings']['recipe']=='wenxi_av':
        text='\n'.join(definitions)+'\n'+seg.get('voice','')+'\n人物站位与场景：'+seg.get('staging','')+'\n整段设计：'+seg.get('beats','')+'\n'+user+'\n末段状态：'+seg.get('ending','')+'\n整段声音：'+seg.get('soundscape','')+'\n'+timing+'\n【禁止项】\n画面字幕/文字/UI/水印/Logo。\n【强制声明】\n'+('无背景音乐，仅保留人声、环境音和音效。' if not seg.get('music') else '配乐：'+seg['music'])
    else:
        if seg.get('prompt_mode')=='full':text=user
        elif images or audio or (p['settings']['recipe']!='official_text' and not (p['mode']=='text_story' and p['settings']['recipe']=='dance_split')):
            text='subject_definitions:\n'+'\n'.join(definitions)+'\n'+seg.get('voice','')+'\n\nsummary:\n[reference generation] '+seg.get('beats','Generate the requested scene.')+'\n\nretention_analysis:\nPreserve the defined character identities and the stated reference responsibilities.\n\ndetailed_description:\n'+seg.get('staging','')+'\n'+('[Shot 1]\n' if '[Shot' not in user else '')+user+'\nEnd state: '+seg.get('ending','')+'\n'+timing+'\n\noverall_soundscape:\n'+(seg.get('soundscape') or 'Generate the described dialogue, physical sounds and natural ambience.')+'\n\nnon_diegetic_music:\n'+(seg.get('music') or 'N/A')
        else:
            text='integrated_multimodal_description:\n'+('[Shot 1]\n' if '[Shot' not in user else '')+seg.get('voice','')+'\n'+seg.get('staging','')+'\n'+user+'\nEnd state: '+seg.get('ending','')+'\n'+timing+'\n\noverall_soundscape:\n'+(seg.get('soundscape') or 'Natural synchronized sound and requested dialogue.')+'\n\nnon_diegetic_music:\n'+(seg.get('music') or 'N/A')
    validate_tags(text,inputs)
    return text
