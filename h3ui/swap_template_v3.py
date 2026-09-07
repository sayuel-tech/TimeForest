"""Ref2VA character-edit template v3; authored descriptions stay optional.

Sources and evidence limits: docs/prompts/swap-template-v3.md.
"""
from .studio_speakers import speakers

VERSION = 3

def fields(p, seg, assets, timing):
    image=next((a for a in assets if a['kind']=='image'),None)
    if image is None:raise ValueError('请先上传一张目标角色图，再查看本段换人提示词')
    sid=image.get('subject') or '1';subject=f'<Subject {sid}>'
    appearance=seg.get('staging','').strip()
    performance=seg.get('beats','').strip()
    direction=seg.get('prompt','').strip()
    voice=seg.get('voice','').strip()
    native=p['settings']['audio_policy']=='native'
    definitions=[f'{subject} is the replacement person from <Picture 1>. The face, hair, physique, clothing, accessories and footwear come from that person in the image; their performance is taken from the person being replaced in <Video 1>.',
        '<Video 1> is the source video for the target video edit, providing its shot sequence and performance timing.']
    if appearance:definitions[0]+=f' Visible appearance: {appearance}'
    retention=[f'{subject} (appears in [Shot 1]): fully_preserved - keep the depicted person\'s identity and outfit, while animating them through the source performance.',
        '<Video 1> (source edit): partially_preserved - keep the shot arrangement, performance trajectory, scene and non-target content; replace the target performer\'s face, hair, body appearance and clothing.']
    summary=f'[video editing + reference generation] The target video is an edited version of <Video 1>. Replace the source performer with {subject}, including their complete outfit, throughout the source performance.'
    audio=[a for a in assets if a['kind']=='audio']
    mapping=speakers(seg,p['settings']['recipe']) or {}
    for i,a in enumerate(audio,1):
        if (a.get('subject') or '1')!=sid:
            raise ValueError(f'通用换人模板的声音须绑定目标角色{sid}；多发声主体请使用完整自定义正文')
        speaker=f' (S{mapping[sid]})' if sid in mapping else ''
        definitions.append(f'<Audio {i}> is the voice-quality reference for {subject}{speaker}, supplying timbre and delivery rather than recorded words.')
        retention.append(f'<Audio {i}>: reference - use the voice qualities for the requested new speech, without copying the recording or its dialogue.')
    if audio:summary=summary.replace('[video editing + reference generation]','[video editing + reference generation + audio reference]')
    action=performance or 'The replacement performs the source person\'s visible action sequence, with the same entrances, exits, gestures and movement rhythm.'
    visual=f'{subject}, {appearance},' if appearance else subject
    detail=(f'The scene keeps the visual medium and location of the source edit. The replacement is a person acting inside that scene.\n'
        f'[Shot 1] {visual} takes the place of the source performer wherever that performer is visible. {action}\n'
        'The replacement keeps the appearance of the image reference while moving; the original costume and facial features are not part of the resulting character. Preserve the performance and relative blocking while allowing the replacement\'s own body shape and clothing to determine their silhouette. Rebuild fabric motion, contact shadows and occlusions for that silhouette.\n'
        'Retain the framing, camera movement and non-target surroundings. The image is an appearance reference, not the opening frame: its background and layout are not transferred. If it contains several views of the same person, use them as complementary views of one identity, not additional performers.')
    if direction:detail+='\n'+direction
    if native and voice:detail+='\nVoice direction for '+subject+': '+voice
    if native and audio:detail+='\nUse the assigned audio references only when the replacement speaks the new dialogue specified here; do not reproduce their sample words.'
    if timing:detail+='\n'+timing
    return dict(subject_definitions='\n'.join(definitions),summary=summary,retention_analysis='\n'.join(retention),detailed_description=detail,
        overall_soundscape=(seg.get('soundscape','').strip() or 'Synchronized ambience and physical action sounds appropriate to the visible scene. Do not invent dialogue or narration.') if native else 'N/A',
        non_diegetic_music=(seg.get('music','').strip() or 'N/A') if native else 'N/A')
