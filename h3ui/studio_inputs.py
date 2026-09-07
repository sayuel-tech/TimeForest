"""One ordered input contract for authoring, prompts and the execution graph.

Asset descriptions/record prompts are deliberately excluded. Context is not a
standalone reference file and never consumes a Picture/Audio ordinal.
"""
import re

CONTRACT_VERSION = 2

def inventory(p, seg, assets):
    rows=[]
    for kind,label,prefix in [('image','Picture','ref_images.ref_image_'),('audio','Audio','ref_audios.ref_audio_')]:
        for ordinal,a in enumerate((a for a in assets if a['kind']==kind),1):
            rows.append(dict(kind=kind,tag=f'<{label} {ordinal}>',ordinal=ordinal,
                asset_id=a.get('id'),name=a.get('name') or '尚未上传',subject=a.get('subject',''),
                purpose=a.get('purpose',''),sha256=a.get('sha256'),
                loader_node=str(400+len(rows)),conditioning_node='20',
                conditioning_input=prefix+str(ordinal-1),input_name=a.get('input_name'),
                library_reference=a.get('library_reference')))
    if p['mode']=='swap':
        rows.append(dict(kind='video',tag='<Video 1>',ordinal=1,asset_id=p.get('source_asset'),
            name=f'P{seg["index"]+1} 源表演',subject='',purpose='source',loader_node='43',
            conditioning_node='20',conditioning_input='ref_videos.ref_video_0',input_name=seg.get('input_name')))
    return rows

def grouped(assets):
    # Kept here so compiler and prompt compiler cannot drift in ordering rules.
    return {kind:[a for a in assets if a['kind']==kind] for kind in ['image','audio']}

def validate(p, seg, assets):
    rows=inventory(p,seg,assets); groups=grouped(assets)
    max_images=1 if p['mode']=='swap' else 0 if p['settings']['recipe']=='official_text' else 9
    if len(groups['image'])>max_images:raise ValueError(f'当前模式/工作流最多支持{max_images}张图片')
    max_audio=0 if p['settings']['recipe']=='official_text' else 3
    if len(groups['audio'])>max_audio:raise ValueError(f'当前工作流最多支持{max_audio}个参考声音')
    if len(rows)>12:raise ValueError('图片、视频和声音合计不能超过12个输入')
    if p['mode']=='swap' and groups['audio'] and p['settings'].get('audio_policy')=='source':
        raise ValueError('参考音色与保留源原声冲突，请保存并确认切换为H3生成声音')
    if sum(a.get('duration',0) for a in groups['audio'])>15.05:raise ValueError('参考声音总长不能超过15秒')
    return rows

def validate_tags(text, rows):
    for label,kind in [('Picture','image'),('Audio','audio'),('Video','video')]:
        count=sum(row['kind']==kind for row in rows)
        missing=sorted({int(n) for n in re.findall(r'<'+label+r'\s*(\d+)>',text) if not 1<=int(n)<=count})
        if missing:raise ValueError(f'提示词{label}引用不存在：{missing}')

def public_inventory(rows):
    return [{k:v for k,v in row.items() if k!='input_name'} for row in rows]
