"""Lossless pass-2 tail collection, outside the original sampling core."""
import json,shutil,wave
from pathlib import Path
from PIL import Image
from . import studio_media as av
from .studio_plan import geometry


def outputs(studio,history,prompt_id,node_id,suffixes):
    result=[]
    for value in history.get(prompt_id,{}).get('outputs',{}).get(str(node_id),{}).values():
        if not isinstance(value,list):continue
        for item in value:
            if isinstance(item,dict) and item.get('filename'):
                path=studio.comfy.output_path(item,studio.output)
                if path.suffix.lower() in suffixes:
                    if not path.is_file():raise ValueError('二采尾部输出文件缺失：'+path.name)
                    result.append(path)
    return result


def save_tail(studio,p,seg,attempt,directory,history,prompt_id,compiled):
    images=outputs(studio,history,prompt_id,compiled['tail_image_node'],{'.png'})
    audios=outputs(studio,history,prompt_id,compiled['tail_audio_node'],{'.flac','.wav'})
    end=seg['head']+seg['deliver'];count=min(22,end)
    if len(images)!=count or len(audios)!=1:raise ValueError(f'二采无损尾部不完整：需要{count}张PNG及1份无损声音，实际{len(images)}图/{len(audios)}声音')
    root=Path(directory)/'tail';root.mkdir(parents=True,exist_ok=True)
    input_base=f'time_forest_v5/{p["id"]}/{attempt}/tail'
    target=studio.input/input_base;target.mkdir(parents=True,exist_ok=True)
    paths=[];hashes=[]
    for i,src in enumerate(images):
        with Image.open(src) as im:im.verify()
        name=f'frame_{i:02d}.png';dst=root/name;shutil.copy2(src,dst);shutil.copy2(dst,target/name)
        paths.append(input_base+'/'+name);hashes.append(av.digest(dst))
    native=root/'native_audio.flac';shutil.copy2(audios[0],native)
    source=Path(p['source_normalized']) if p['mode']=='swap' and p['settings']['audio_policy']=='source' else native
    end_frames=seg['start']+seg['deliver'] if source!=native else end
    duration_frames=min(24,end)
    first=round((end_frames-duration_frames)*32000/24);last=round(end_frames*32000/24)
    wav=root/'context.wav'
    av.run(['ffmpeg','-y','-v','error','-i',source,'-vn','-af',f'aresample=32000,atrim=start_sample={first}:end_sample={last},asetpts=PTS-STARTPTS','-ac','2','-ar','32000','-c:a','pcm_s16le',wav])
    with wave.open(str(wav),'rb') as f:
        missing=last-first-f.getnframes()
    # 40 Hz audio vs 24 fps video can leave a sub-frame rounding gap.
    # Permit only this bounded gap, not a missing soundtrack.
    if not 0<=missing<=800:raise ValueError('二采尾部声音明显不足，不能把不完整声音作为连续上下文')
    if missing:
        padded=root/'context_padded.wav'
        av.run(['ffmpeg','-y','-v','error','-i',wav,'-af',f'apad=pad_len={missing}','-c:a','pcm_s16le',padded])
        padded.replace(wav)
    shutil.copy2(wav,target/'context.wav')
    # A 22-frame RGB-lossless container avoids retaining 21 progressively
    # concatenated IMAGE batches in Comfy's cache. Audio stays separate to
    # preserve its independently end-aligned one-second window.
    video=root/'context.mkv'
    av.run(['ffmpeg','-y','-v','error','-framerate','24','-i',root/'frame_%02d.png','-frames:v',str(count),'-c:v','ffv1','-level','3','-pix_fmt','bgr0',video])
    shutil.copy2(video,target/'context.mkv')
    context=dict(version=1,kind='pass2_lossless_tail',images=paths,audio=input_base+'/context.wav',video=input_base+'/context.mkv',video_hash=av.digest(video),
        image_hashes=hashes,audio_hash=av.digest(wav),frame_count=count,frame_end=end,audio_samples=last-first,audio_grid_padding_samples=missing,
        source_attempt=attempt,model=p['settings']['model'],video_vae=p['settings']['video_vae'],audio_vae=p['settings']['audio_vae'],
        geometry=compiled['geometry'],native_audio=str(native))
    (root/'context.json').write_text(json.dumps(context,ensure_ascii=False,indent=2),encoding='utf-8')
    return context


def validate_tail(studio,context,settings):
    if context.get('kind')!='pass2_lossless_tail':raise ValueError('当前配方需要二采完成后的无损尾部检查点')
    for key in ['model','video_vae','audio_vae']:
        if context.get(key)!=settings[key]:raise ValueError('前段模型或VAE与当前参数不兼容；请重生成相关前段或明确选择新场景')
    size=geometry(settings)
    if any(context.get('geometry',{}).get(k)!=size[k] for k in ['width','height','output_width','output_height']):raise ValueError('前段画布/倍率与当前连续参数不兼容，请重生成前段或明确选择新场景')
    if len(context.get('images',[]))!=len(context.get('image_hashes',[])):raise ValueError('尾部检查点摘要不完整')
    for name,digest in zip(context.get('images',[]),context.get('image_hashes',[])):
        path=(studio.input/name).resolve()
        if studio.input.resolve() not in path.parents or not path.is_file() or av.digest(path)!=digest:raise ValueError('前段无损尾帧缺失或被修改，请恢复对应候选')
    audio=(studio.input/context.get('audio','')).resolve()
    if studio.input.resolve() not in audio.parents or not audio.is_file() or av.digest(audio)!=context.get('audio_hash'):raise ValueError('前段PCM上下文缺失或被修改')
    video=(studio.input/context.get('video','')).resolve()
    if studio.input.resolve() not in video.parents or not video.is_file() or av.digest(video)!=context.get('video_hash'):raise ValueError('前段无损尾部视频缺失或被修改')
    if len(context.get('images',[]))!=22:raise ValueError('前段有效尾帧不足22帧，请检查片段边界')
    return context
