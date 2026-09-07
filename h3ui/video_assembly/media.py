"""Cancellable local media operations. All outputs are new project artifacts."""
import json
import math
import subprocess
import time
from pathlib import Path
from fractions import Fraction
from ..studio_media import digest


class Cancelled(RuntimeError):
    pass


def command(args, cancel=None, timeout=5400):
    if cancel and cancel.is_set():
        raise Cancelled('已停止本次处理，原文件及已完成结果保留')
    flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
    process = subprocess.Popen([str(v) for v in args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=flags)
    deadline = time.monotonic() + timeout
    try:
        while True:
            if cancel and cancel.is_set():
                raise Cancelled('已停止本次处理，原文件及已完成结果保留')
            if time.monotonic() > deadline:
                raise RuntimeError('媒体处理超时，未发布未完成文件')
            try:
                out, err = process.communicate(timeout=.2)
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode:
            raise ValueError('媒体处理失败：' + err.decode('utf-8', 'replace')[-2400:])
        return out.decode('utf-8', 'replace')
    finally:
        if process.poll() is None:
            process.terminate()
            try: process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill(); process.communicate()


def inspect(path, cancel=None):
    data = json.loads(command(['ffprobe','-v','error','-show_streams','-show_format','-of','json',path],cancel,30))
    video = next((s for s in data['streams'] if s['codec_type']=='video' and not s.get('disposition',{}).get('attached_pic')),None)
    if not video:
        raise ValueError('所选文件没有可用视频流')
    duration = float(video.get('duration') or data['format'].get('duration') or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('无法读取有效视频时长')
    rotation = int(float(video.get('tags',{}).get('rotate',0)))
    for side in video.get('side_data_list',[]):
        if 'rotation' in side: rotation=int(side['rotation'])
    w,h = video['width'],video['height']
    try:sar=float(Fraction(video.get('sample_aspect_ratio','1:1').replace(':','/')))
    except (ValueError,ZeroDivisionError):sar=1
    w=round(w*(sar if sar>0 else 1))
    if abs(rotation)%180==90: w,h=h,w
    rate = video.get('avg_frame_rate','0/1')
    try: fps=float(Fraction(rate))
    except (ValueError,ZeroDivisionError): fps=0
    return dict(width=w,height=h,duration=duration,fps=fps,
                audio=any(s['codec_type']=='audio' for s in data['streams']),rotation=rotation,start_time=float(video.get('start_time') or 0))


def geometry_filter(width,height,fit='contain'):
    if fit=='cover':
        return f'scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1'
    return f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1'


def normalize(source,destination,start,end,width,height,fps=24,fit='contain',mute=False,cancel=None,lossless=False):
    meta=inspect(source,cancel); duration=end-start
    if start<0 or duration<=0 or end>meta['duration']+.05:
        raise ValueError('使用范围超出原视频时长')
    n=max(1,round(duration*fps)); duration=n/fps
    destination=Path(destination); destination.parent.mkdir(parents=True,exist_ok=True)
    args=['ffmpeg','-nostdin','-y','-v','error','-i',source]
    vf=f'setpts=PTS-STARTPTS,trim=start={start}:end={end},setpts=PTS-STARTPTS,scale=trunc(iw*sar/2)*2:ih,setsar=1,{geometry_filter(width,height,fit)},fps={fps},tpad=stop_mode=clone:stop_duration={1/fps},trim=end_frame={n}'
    if meta['audio'] and not mute:
        af=f"[0:a:0]asetpts=PTS-{meta['start_time']}/TB,atrim=start={start}:end={end},asetpts=PTS-{start}/TB,aresample=32000:async=1:first_pts=0,apad,atrim=duration={duration}[a]"
    else:
        af=f'anullsrc=r=32000:cl=stereo,atrim=duration={duration}[a]'
    codec=['-c:v','ffv1','-pix_fmt','bgr0'] if lossless else ['-c:v','libx264','-crf','18','-pix_fmt','yuv420p']
    args+=['-filter_complex',f'[0:v:0]{vf}[v];{af}','-map','[v]','-map','[a]',
           *codec,'-c:a','pcm_s16le','-ar','32000','-ac','2',
           '-t',str(duration),destination]
    command(args,cancel)
    return dict(file=str(destination),frames=n,duration=duration)


TAIL_PREPARATION = 'source_geometry_v2'


def tail(source,start,end,directory,width,height,input_root,cancel=None,*,preparation=TAIL_PREPARATION):
    if end-start < 1-.001:
        raise ValueError('AI续接需要至少1秒有效片尾；短片仍可普通拼接')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    normalized=directory/'last-second.mkv'
    meta=inspect(source,cancel)
    if preparation==TAIL_PREPARATION:
        # Match the original video modes: MotionContext resizes the complete
        # source frames to the latent canvas. Pre-padding here teaches the
        # model to continue black bars caused by 32-pixel canvas alignment.
        frame_width,frame_height=meta['width'],meta['height']
    elif preparation=='legacy_contain_v1':
        frame_width,frame_height=width,height
    else:
        raise ValueError('未知片尾准备版本，未替换原提交上下文')
    normalize(source,normalized,end-1,end,frame_width,frame_height,cancel=cancel,lossless=True)
    video=directory/'tail.mkv'; audio=directory/'tail.wav'
    command(['ffmpeg','-nostdin','-y','-v','error','-i',normalized,'-an','-vf',
             'trim=start_frame=2:end_frame=24,setpts=PTS-STARTPTS','-c:v','ffv1','-pix_fmt','bgr0',video],cancel)
    command(['ffmpeg','-nostdin','-y','-v','error','-i',normalized,'-vn','-c:a','pcm_s16le','-ar','32000','-ac','2',audio],cancel)
    return dict(kind='external_decoded_av',frame_count=22,audio_frames=24,preparation=preparation,
                frame_width=frame_width,frame_height=frame_height,
                video=video.resolve().relative_to(Path(input_root).resolve()).as_posix(),
                audio=audio.resolve().relative_to(Path(input_root).resolve()).as_posix(),
                source_sha256=digest(source),video_sha256=digest(video),audio_sha256=digest(audio),
                start=start,end=end,silent_source=not meta['audio'])


def assemble(parts,directory,output,cancel=None,progress=lambda text:None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    prepared=[];frames=0
    for index,part in enumerate(parts):
        progress(f'规范化片段 {index+1}/{len(parts)}')
        if part.get('sha256') and digest(part['file'])!=part['sha256']:raise ValueError('成片输入与运行快照不一致，未替换来源')
        item=normalize(part['file'],directory/f'part-{index:04d}.mkv',part['start'],part['end'],
                       output['width'],output['height'],output['fps'],output['fit'],part.get('mute',False),cancel)
        prepared.append(Path(item['file']));frames+=item['frames']
    listing=directory/'parts.txt'
    listing.write_text(''.join("file '"+p.name+"'\n" for p in prepared),encoding='utf-8')
    progress('拼接完整视频与声音')
    dest=directory/'final.mp4'
    command(['ffmpeg','-nostdin','-y','-v','error','-f','concat','-safe','1','-i',listing,
             '-map','0:v:0','-map','0:a:0','-c:v','copy','-c:a','aac','-ar','32000','-ac','2',
             '-t',str(frames/output['fps']),'-movflags','+faststart',dest],cancel)
    report=inspect(dest,cancel)
    if abs(report['duration']-frames/output['fps'])>1/output['fps']+.02 or not report['audio']:
        raise ValueError('合成结果时长或音轨校验失败')
    report['frames']=frames
    return str(dest),report
