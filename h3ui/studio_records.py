"""Reversible removal from candidate lists; original media and references stay put."""
import time
from flask import Blueprint, current_app, jsonify, request
from .studio_store import Conflict

bp=Blueprint('candidate_records',__name__,url_prefix='/api/v5/projects')


def image_visibility(service,pid,data):
    store=service.store
    with store.lock,store.connect() as db:
        p=store.project(pid)
        if p['revision']!=data.get('revision'):raise Conflict('项目已更新，请保存或刷新后再整理候选')
        run=store.get('runs',data['record'],pid)
        service.active_task(pid,run['task'])
        if any(r['state'] in ('waiting','submitting','running','unknown') for r in store.all('runs',pid)):
            raise Conflict('本项目仍有运行或待确认提交，请处理完成后再整理记录')
        if run['state'] not in ('success','failed','cancelled'):raise Conflict('此记录尚未结束，不能移除')
        outputs=[o for o in store.all('outputs',pid) if o['run']==run['id']]
        if data['removed'] and any(o.get('selected') for o in outputs):raise Conflict('这是当前选用结果，请先选定另一张候选再移除')
        when=(run.get('removed_at') or time.time()) if data['removed'] else None
        run['removed_at']=when;store.put('runs',run,db)
        for out in outputs:
            out['removed_at']=when;store.put('outputs',out,db)
        p.update(revision=p['revision']+1,updated=time.time());store.put('projects',p,db)
        return dict(ok=True,revision=p['revision'],removed=data['removed'])


def video_visibility(studio,pid,data):
    with studio.store.lock:
        p=studio.store.get(pid)
        if p['revision']!=data.get('revision'):raise Conflict('项目已更新，请保存或刷新后再整理候选')
        segment=next((s for s in p['segments'] if s['id']==data.get('segment')),None)
        if not segment:raise KeyError('片段不存在')
        attempt=next((a for a in segment.get('attempts',[]) if a['id']==data['record']),None)
        if not attempt:raise KeyError('运行记录不属于当前片段')
        if attempt['status'] not in ('complete','failed'):raise Conflict('此记录仍可执行或提交结果待确认，请先查询恢复结果')
        if data['removed'] and segment.get('selected')==attempt['id']:raise Conflict('这是当前选用结果，请先接受另一候选再移除')
        attempt['removed_at']=(attempt.get('removed_at') or time.time()) if data['removed'] else None
        p=studio.store.save(p,p['revision'])
        return dict(ok=True,revision=p['revision'],removed=data['removed'])


@bp.post('/<pid>/records/visibility')
def visibility(pid):
    data=request.get_json() or {}
    try:
        if not isinstance(data.get('removed'),bool) or not isinstance(data.get('record'),str):raise ValueError('缺少有效的记录或移除/恢复操作')
        studio=current_app.config['STUDIO'];images=current_app.config.get('IMAGE_STUDIO')
        action=lambda:image_visibility(images,pid,data) if images and images.store.exists(pid) else video_visibility(studio,pid,data)
        return jsonify(studio.jobs.run_inline('candidate_visibility',pid,action))
    except (ValueError,KeyError,RuntimeError) as exc:
        return jsonify(error=str(exc),error_raw=str(exc),error_kind='conflict'),409
