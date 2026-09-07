"""Reconcile uncertain submissions by exact client id across queue and history."""
import json
from pathlib import Path


def client_id(prompt):
    if isinstance(prompt,(list,tuple)) and len(prompt)>3 and isinstance(prompt[3],dict):
        return prompt[3].get('client_id')
    return None


def resolve_submission(comfy,attempt):
    prompt_id=attempt.get('prompt_id')
    if not prompt_id:
        request=Path(attempt['directory'])/'request.json'
        if request.is_file():
            saved=json.loads(request.read_text(encoding='utf-8'))
            if saved.get('attempt')==attempt['id']:prompt_id=saved.get('prompt_id')
    queue=comfy._get('/queue')
    if not prompt_id:
        identity='time-forest-'+attempt['id'];candidates=set()
        records=comfy._get('/history?max_items=200')
        for key,record in records.items():
            if client_id(record.get('prompt'))==identity:candidates.add(key)
        for record in queue.get('queue_running',[])+queue.get('queue_pending',[]):
            if client_id(record)==identity:candidates.add(record[1])
        if len(candidates)!=1:raise ValueError('提交结果待确认：队列与历史中无法唯一匹配本次运行；暂不重复生成')
        prompt_id=candidates.pop()
    queued=any(isinstance(record,(list,tuple)) and len(record)>1 and record[1]==prompt_id for record in queue.get('queue_running',[])+queue.get('queue_pending',[]))
    history=comfy._get('/history/'+prompt_id)
    return prompt_id,history,queued


def assert_no_uncertain_runs(project,indices):
    for index in indices:
        segment=project['segments'][index]
        for attempt in segment.get('attempts',[]):
            runs=[a for task in attempt.get('tasks',[]) for a in task.get('attempts',[])] if attempt.get('tasks') else [attempt]
            if any(run.get('status') in ('submitting','submitted','interrupted') for run in runs):
                raise ValueError(f'P{index+1}还有提交结果待确认的运行，请先查询并恢复；不能直接再排一次生成')


def restore_existing(studio):
    """Only recorded active work may reconnect at startup. Never submit new generation."""
    if studio.ctx['cfg'].get('studio_disable_generation') or not studio.ctx['cfg'].get('studio_auto_recover',True):return
    for pid,index in studio.pending_recovery:
        def recover(pid=pid,index=index):
            try:studio.recover(pid,index)
            except Exception as exc:studio.store.mutate(pid,lambda p:p.update(error='已有任务恢复未完成：'+str(exc)))
        studio.jobs.start('v5_recover',pid,recover)
