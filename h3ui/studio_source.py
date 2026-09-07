"""Versioned source preparation. FFmpeg only; never submits a model workflow."""
import copy
import math
import re
import shutil
import subprocess
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from . import media
from .segmenter import plan_segments
from .studio_plan import geometry
from .studio_progress import read, write
from .studio_store import Conflict

SOURCE_DEFAULTS = dict(segment_seconds=124/24, detect_cuts=True, cut_threshold=.45)
SOURCE_AUTHORED = ['prompt','prompt_mode','staging','beats','voice','speaker_order','soundscape','music','ending',
                   'assets','inherit_ids','asset_mode','seed_mode','seed','swap_prompt_mode','swap_custom_prompt']

def source_options(value=None):
    if value is not None and not isinstance(value,dict):raise ValueError('源视频分段设置格式错误')
    result={**SOURCE_DEFAULTS,**(value or {})}
    if set(result)!=set(SOURCE_DEFAULTS):raise ValueError('未知源视频分段设置')
    seconds=float(result['segment_seconds']);threshold=float(result['cut_threshold'])
    if not math.isfinite(seconds) or not 124/24-1e-4<=seconds<=15:raise ValueError('单段目标时长须为5.167～15秒；短源镜头按实际长度处理')
    if not math.isfinite(threshold) or not .05<=threshold<=.95:raise ValueError('切镜阈值须为0.05～0.95')
    if not isinstance(result['detect_cuts'],bool):raise ValueError('自动识别切镜须为开关值')
    return dict(segment_seconds=seconds,cut_threshold=threshold,detect_cuts=result['detect_cuts'])

def source_signature(settings, options=None):
    size=geometry(settings);options=source_options(options)
    seconds=min(options['segment_seconds'],float(settings['render_cap']),15)
    raw=5+17*math.floor((seconds*24-5+1e-3)/17)
    return dict(width=size['width'],height=size['height'],fps=24,raw=max(124,raw),
                detect_cuts=options['detect_cuts'],cut_threshold=options['cut_threshold'] if options['detect_cuts'] else None)

def ready(p):
    if not p.get('source_ready'):return False
    manifest=p.get('source_manifest')
    return not manifest or (manifest['asset_id']==p.get('source_asset') and
                           manifest['signature']==source_signature(p['settings'],p.get('source_options')))

def run_ffmpeg(args, on_progress, on_stderr=None):
    """Drain both pipes, retain bounded diagnostics and parse actual FFmpeg reports."""
    errors=deque(maxlen=12)
    command=['ffmpeg','-y','-nostdin','-progress','pipe:1','-nostats',*map(str,args)]
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace')
    def drain():
        for line in process.stderr:
            errors.append(line.rstrip())
            if on_stderr:on_stderr(line)
    thread=threading.Thread(target=drain,daemon=True);thread.start()
    values={}
    try:
        for line in process.stdout:
            key,sep,value=line.strip().partition('=')
            if sep:values[key]=value
            if key=='progress':on_progress(dict(values))
        code=process.wait();thread.join()
        if code:raise media.MediaError('源视频处理失败：'+'\n'.join(errors))
        return values
    finally:
        if process.poll() is None:process.kill();process.wait()
        thread.join();process.stdout.close();process.stderr.close()

class SourcePreparation:
    def source_progress(self,pid):
        data=read(self.store.directory(pid)/'source-progress.json')
        if data.get('active') and self.store.get(pid).get('status')!='preparing':
            data.update(active=False,error='准备任务已中断，请重新准备当前视频',phase='准备中断')
        return data

    def start_source(self,pid,aid,revision=None,continue_to=None):
        if continue_to not in [None,'edit']:raise ValueError('准备完成后的目标页面不支持')
        with self.store.lock:
            p=self.store.get(pid);a=self.store.asset(pid,aid)
            if revision is not None and int(revision)!=p['revision']:raise Conflict('项目已变化，请保存后重新准备')
            if p['mode']!='swap' or a['kind']!='video':raise ValueError('此项目需要源视频')
            if not Path(a['path']).is_file():raise ValueError('已上传原视频文件缺失，请重新上传')
            source_signature(p['settings'],p.get('source_options'))
            def work():
                try:self.prepare_source(pid,aid,continue_to=continue_to)
                except Exception as e:
                    data=self.source_progress(pid)
                    data.update(active=False,phase='准备失败',error=str(e),finished=time.time(),updated=time.time())
                    write(self.store.directory(pid)/'source-progress.json',data)
                    self.store.mutate(pid,lambda q:q.update(status='failed',error=str(e),source_ready=False))
            if not self.jobs.start('v5_prepare',pid,work):raise Conflict('已有任务运行，请待任务结束后准备源视频')
            self.store.mutate(pid,lambda q:q.update(status='preparing',source_candidate=aid,source_ready=False,error=None))
            write(self.store.directory(pid)/'source-progress.json',dict(id=uuid.uuid4().hex,asset_id=aid,active=True,started=time.time(),updated=time.time(),phase='开始准备源视频',continue_to=continue_to))

    def prepare_source(self,pid,aid,continue_to=None):
        # start_source reserves the job before releasing the store lock.
        with self.store.lock:p=self.store.get(pid)
        a=self.store.asset(pid,aid);signature=source_signature(p['settings'],p.get('source_options'))
        if p['mode']!='swap' or a['kind']!='video':raise ValueError('此项目需要源视频')
        version=uuid.uuid4().hex;directory=self.store.directory(pid)/'source'/version
        directory.mkdir(parents=True);norm=directory/'source24.mp4'
        state=dict(id=version,asset_id=aid,started=time.time(),active=True,error=None,continue_to=continue_to)
        def progress(phase,stage,**detail):
            if stage!=state.get('stage'):
                for key in ['completed','total','processed_seconds','total_seconds']:state.pop(key,None)
            state.update(dict(phase=phase,stage=stage,stages=5,updated=time.time(),percent=None))
            state.update(detail)
            write(self.store.directory(pid)/'source-progress.json',state)
        progress('读取视频信息',1)
        duration=float(a.get('duration') or 0)
        def report(phase,stage,total):
            def update(values):
                try:seconds=max(0,int(values.get('out_time_us','0') or 0)/1e6)
                except ValueError:seconds=0
                progress(phase,stage,processed_seconds=round(seconds,2),total_seconds=total,
                         percent=min(99,seconds/total*100) if total else None)
            return update
        progress('转换生成输入',2,total_seconds=duration)
        run_ffmpeg(['-v','error','-i',a['path'],'-vf',
                    f"fps=24,scale={signature['width']}:{signature['height']}:force_original_aspect_ratio=decrease,pad={signature['width']}:{signature['height']}:(ow-iw)/2:(oh-ih)/2:color=black",
                    '-c:v','libx264','-crf','16','-pix_fmt','yuv420p','-c:a','aac',norm],report('转换生成输入',2,duration))
        progress('核对标准化视频帧数',2)
        count=media.frame_count(norm)
        if count<1:raise ValueError('源视频没有可处理的画面')
        cuts=[]
        if signature['detect_cuts']:
            progress('识别镜头切换',3)
            def cut_line(line):
                match=re.search(r'pts_time:([0-9.]+)',line)
                if match:cuts.append(round(float(match.group(1))*24))
            run_ffmpeg(['-v','info','-i',norm,'-an','-vf',f"scale=160:-2,select='gt(scene,{signature['cut_threshold']})',showinfo",'-f','null','-'],
                       report('识别镜头切换',3,count/24),cut_line)
        else:progress('按固定长度规划片段（未启用切镜识别）',3)
        planned=plan_segments(count,signature['raw'],22,cuts)
        old=p['segments'];same_source=p.get('source_asset')==aid;used=set();segments=[]
        for item in planned:
            i=item['index'];target=directory/f'seg{i:05d}.mp4'
            progress(f'生成切片 {i+1}/{len(planned)}',4,completed=i,total=len(planned),percent=i/len(planned)*100)
            media.slice_segment(norm,item['start'],item['raw'],target,item['source_frames'])
            inp=f'time_forest_v5/{pid}/sources/{version}/seg{i:05d}.mp4'
            sg=self.new_segment(dict(index=i,start=item['content_start'],raw=item['raw'],head=item['context_frames'],deliver=item['deliver'],
                                     tail=item['pad_frames'],duration=item['deliver']/24,boundary='new_scene' if item['independent'] else 'continue'))
            # Only exact source-time matches inherit authored work. Never match by ordinal.
            match=next((s for s in old if same_source and s['start']==sg['start'] and s['deliver']==sg['deliver'] and s['boundary']==sg['boundary']),None)
            if match:
                for key in SOURCE_AUTHORED:
                    if key in match:sg[key]=copy.deepcopy(match[key])
                used.add(match['id'])
            elif i==0 and old:
                # Keep the chosen replacement character even when the source timeline changes.
                for key in ['assets','inherit_ids','asset_mode']:sg[key]=copy.deepcopy(old[0].get(key,sg[key]))
            sg.update(input_name=inp,source_file=str(target));segments.append(sg)
        progress('校验切片与时间线',5,completed=0,total=len(segments))
        if sum(s['deliver'] for s in segments)!=count:raise ValueError('切片没有完整覆盖源视频')
        for i,s in enumerate(segments):
            if media.frame_count(Path(s['source_file']))!=s['raw']:raise ValueError(f'P{i+1}切片帧数不符')
            progress('校验切片与时间线',5,completed=i+1,total=len(segments),percent=(i+1)/len(segments)*100)
        manifest=dict(version=version,asset_id=aid,sha256=a['sha256'],signature=signature,frames=count,cuts=cuts,created=time.time())
        write(directory/'manifest.json',manifest)
        def finish(q):
            if q.get('source_asset'):q.setdefault('source_history',[]).append(dict(source_asset=q['source_asset'],source_normalized=q.get('source_normalized'),source_manifest=q.get('source_manifest'),segments=q['segments'],export=q.get('export')))
            q.setdefault('removed_drafts',[]).extend(copy.deepcopy(s) for s in old if s['id'] not in used)
            q.update(segments=segments,source_asset=aid,source_candidate=None,source_manifest=manifest,source_ready=True,
                     source_normalized=str(norm),duration=count/24,status='draft',error=None,export=None)
        result=self.store.mutate(pid,finish)
        progress('源视频准备完成',5,active=False,finished=time.time(),percent=100,completed=len(segments),total=len(segments))
        return result
