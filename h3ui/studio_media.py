"""AV post-processing shared by normal execution and recovery."""
import hashlib,json,subprocess
from pathlib import Path

def run(args):
    r=subprocess.run([str(x) for x in args],capture_output=True,text=True)
    if r.returncode:raise ValueError('媒体处理失败：'+r.stderr[-1800:])
    return r.stdout
def probe(path):
    return json.loads(run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',path]))
def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def av_trim(src,dst,head,deliver,audio_source=None,audio_offset=0.):
    dst=Path(dst);dst.parent.mkdir(parents=True,exist_ok=True)
    streams=probe(src)['streams'];has=any(s['codec_type']=='audio' for s in streams)
    if not audio_source and not has:raise ValueError('生成结果缺少原生音轨，不能以静音标记成功')
    start=head/24;duration=deliver/24
    args=['ffmpeg','-y','-v','error','-i',src]
    if audio_source:args+=['-i',audio_source]
    sound_index=1 if audio_source else 0;astart=audio_offset if audio_source else start
    filt=f'[0:v]trim=start_frame={head}:end_frame={head+deliver},setpts=PTS-STARTPTS[v];[{sound_index}:a]atrim=start={astart:.9f}:end={astart+duration:.9f},asetpts=PTS-STARTPTS,aresample=32000,apad,atrim=duration={duration:.9f}[a]'
    args+=['-filter_complex',filt,'-map','[v]','-map','[a]','-r','24','-frames:v',str(deliver),'-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-ar','32000','-ac','2','-t',f'{duration:.9f}','-movflags','+faststart',dst]
    run(args)
    wav=dst.with_suffix('.wav')
    run(['ffmpeg','-y','-v','error','-i',src if not audio_source else audio_source,'-vn','-af',f'atrim=start={astart:.9f}:end={astart+duration:.9f},asetpts=PTS-STARTPTS,aresample=32000,apad,atrim=duration={duration:.9f}','-ar','32000','-ac','2','-c:a','pcm_s16le',wav])
    return validate(dst,deliver,24)
def validate(path,expected_frames,fps):
    data=probe(path);v=next((x for x in data['streams'] if x['codec_type']=='video'),None);a=next((x for x in data['streams'] if x['codec_type']=='audio'),None)
    if not v or not a:raise ValueError('交付缺少视频或音频流')
    count=int(run(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=nb_read_frames','-of','csv=p=0',path]).strip())
    if count!=expected_frames:raise ValueError(f'交付帧数错误：{count}，期望{expected_frames}')
    duration=float(v.get('duration') or data['format']['duration'])
    if abs(duration-expected_frames/fps)>1/fps+.002:raise ValueError('视频时长与计划不符')
    return dict(frames=count,fps=fps,width=v['width'],height=v['height'],audio_rate=int(a['sample_rate']),channels=a['channels'],duration=duration)
def assemble(segments,out,fps=24):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    normalized=[];total=0
    first=probe(segments[0]['delivery']);video=next(x for x in first['streams'] if x['codec_type']=='video');w,h=video['width'],video['height']
    for i,s in enumerate(segments):
        src=Path(s['delivery']);wav=src.with_suffix('.wav')
        if not wav.exists():raise ValueError('缺少片段PCM音轨，请先恢复该结果')
        n=out/f'part-{i:04d}.mkv';duration=s['deliver']/24
        # Cumulative boundaries avoid independent rounding drift at 32kHz/24fps.
        sample_count=round((total+s['deliver'])*32000/24)-round(total*32000/24)
        run(['ffmpeg','-y','-v','error','-i',src,'-i',wav,'-map','0:v:0','-map','1:a:0','-vf',f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps=24','-af',f'apad,atrim=end_sample={sample_count}','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','pcm_s16le','-ar','32000','-ac','2','-t',f'{duration:.9f}',n])
        normalized.append(n);total+=s['deliver']
    listing=out/'parts.txt';listing.write_text(''.join("file '"+p.resolve().as_posix().replace("'","'\\''")+"'\n" for p in normalized),encoding='utf-8')
    dst=out/'final.mp4';expected=round(total*fps/24)
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',listing,'-map','0:v:0','-map','0:a:0','-vf',f'fps={fps}','-frames:v',str(expected),'-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-ar','32000','-ac','2','-t',f'{total/24:.9f}','-movflags','+faststart',dst])
    # Keep the concatenated PCM for a later project-level assembly. Never
    # repeatedly decode each storyboard's AAC when joining the full film.
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',listing,'-vn','-af',f'apad,atrim=end_sample={round(total*32000/24)}','-c:a','pcm_s16le','-ar','32000','-ac','2',dst.with_suffix('.wav')])
    report=validate(dst,expected,fps);report['source_frames']=total;return dst,report
