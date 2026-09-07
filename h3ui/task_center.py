"""Read-through global task list; controls delegate to existing stores/workers."""
import time
from urllib.parse import quote
from flask import Blueprint, current_app, jsonify, request
from .studio_store import Conflict
from .comfy import ComfyError

bp=Blueprint('task_center',__name__,url_prefix='/api/v5/tasks')
IMAGE_ACTIVE={'waiting','submitting','running','unknown'}


def video_runs(project):
    for segment in project.get('segments',[]):
        for attempt in segment.get('attempts',[]):
            if attempt.get('tasks'):
                for task in attempt['tasks']:
                    yield from task.get('attempts',[])
            else:
                yield attempt


class TaskCenter:
    def __init__(self,studio,images,local):
        self.st,self.images,self.local=studio,images,local

    def snapshot(self):
        jobs=self.st.jobs.snapshot();rows=[];blockers=[]
        if self.images:
            projects={p['id']:p for p in self.images.store.all('projects')}
            tasks={t['id']:t for t in self.images.store.all('tasks')}
            for run in self.images.store.all('runs'):
                pid=run['project'];p=projects.get(pid,{})
                state=run['state'];actions=[]
                if state=='waiting':actions=['cancel']
                elif state=='unknown':actions=['close']
                elif state in ('submitting','running'):actions=['stop']
                row=dict(kind='image',id=run['id'],project=pid,name=p.get('name','图片项目'),
                         title=tasks.get(run['task'],{}).get('name','图片编辑'),state=state,
                         active=state in IMAGE_ACTIVE,attention=state=='unknown',actions=actions,
                         note=run.get('note',''),created=run.get('created',0),updated=run.get('updated',run.get('created',0)),
                         prompt_id=run.get('prompt_id'),seed=run.get('seed'),url='#/p/'+pid,
                         error_raw=run.get('error_raw'),stop_requested=run.get('stop_requested',False))
                if run.get('closed_without_result'):row['note']='已结束等待；原提交结果仍未确认，记录已保留'
                if state in ('submitting','running','unknown'):
                    blockers.append(dict(id=run['id'],project=pid,name=row['name'],state=state,url=row['url']))
                rows.append(row)
        for row in rows:
            if row['state']=='waiting':
                row['blocked_by']=blockers
                if blockers:row['note']='等待其他图片任务释放通道：'+ '、'.join(b['name']+('（待确认提交）' if b['state']=='unknown' else '（执行中）') for b in blockers)
                elif any(j['lane']=='gpu' for j in jobs):row['note']='等待正在执行的视频任务释放生成通道'
        projects=self.st.store.list()+self.st.store.list(trash=True)
        seen=set()
        for p in projects:
            if p['mode']=='video_assembly':
                seen.update(j['id'] for j in jobs if j['project_id']==p['id'])
                for r in p['assembly']['runs']:
                    if r['state'] not in ('preparing','submitting','running','unknown'):continue
                    rows.append(dict(kind='assembly',id=r['id'],project=p['id'],name=p['name'],title={'generate':'AI尾部续接','export':'视频拼接','import':'导入视频'}.get(r['kind'],'视频处理'),state=r['state'],active=True,attention=r['state']=='unknown',actions=['recover','close'] if r['state']=='unknown' else ['stop'],url='#/p/'+p['id'],created=r['created'],updated=r.get('started',r['created']),note=r.get('error') or r.get('note','')))
                continue
            owned=[j for j in jobs if j['project_id']==p['id'] and j['kind']!='library_media']
            attempts=list(video_runs(p));uncertain=any(a.get('status') in ('submitting','submitted','interrupted') for a in attempts)
            if not owned and not attempts and p.get('status') not in ('preparing','generating','assembling','interrupted','failed'):continue
            seen.update(j['id'] for j in owned)
            gpu=any(j['lane']=='gpu' for j in owned)
            state='stopping' if gpu and p.get('pause') else 'running' if owned else 'unknown' if uncertain else p.get('status','done')
            rows.append(dict(kind='video',id=p['id'],project=p['id'],name=p.get('name','视频项目'),title='视频制作',
                             state=state,active=bool(owned) or uncertain,attention=uncertain and not owned,
                             actions=['pause','stop'] if gpu else [],url='#/p/'+p['id'],
                             created=p.get('created_at',0),updated=p.get('updated_at',0),
                             note=('停止已请求；保留已完成结果' if p.get('pause') else p.get('error') or ('本地处理完成后结束' if owned and not gpu else '')),
                             progress=sum(s.get('status') in ('done','accepted') for s in p.get('segments',[]))/max(1,len(p.get('segments',[])))))
        for task in self.local.list():
            rows.append(dict(kind='local',id=task['id'],project=None,name='资产处理',title={'project_apply':'导入项目素材','project_result':'作品入库','backup':'资产备份'}.get(task['action'],'资产本地处理'),
                             state=task['state'],active=task['state'] in ('queued','running'),attention=task['state'] in ('failed','interrupted'),
                             actions=['cancel'] if task['state']=='queued' else [],note=task.get('note',''),progress=task.get('progress'),
                             created=task['created'],updated=task['updated'],url='#/assets?view=tasks'))
        for job in jobs:
            if job['id'] in seen or job['kind'].startswith('image_') or job['kind']=='library_media':continue
            rows.append(dict(kind='worker',id=job['id'],project=job['project_id'],name='本地处理',title='素材准备 / 导出',
                             state='running',active=True,attention=False,actions=[],note='正在完成本地处理，完成后释放通道',
                             created=job['started'],updated=job['started'],url='#/p/'+job['project_id']))
        rows=[r for r in rows if r['active']]
        rows.sort(key=lambda r:(not r['attention'],-r['updated']))
        return dict(version=1,tasks=rows,active_count=len(rows),attention_count=sum(r['attention'] for r in rows))

    def stop_prompt(self,run):
        prompt=run.get('prompt_id')
        if not prompt:raise Conflict('任务正在提交，尚无引擎任务编号，请刷新后再停止')
        queue=self.st.comfy._get('/queue',timeout=10)
        records=queue.get('queue_running',[])+queue.get('queue_pending',[])
        owned=[r for r in records if len(r)>1 and r[1]==prompt]
        if not owned:raise Conflict('任务已离开引擎队列；请等待结果回收，或处理待确认记录')
        if any(len(r)<4 or not isinstance(r[3],dict) or r[3].get('client_id')!='time-forest-'+run['id'] for r in owned):
            raise Conflict('无法确认引擎任务归属，未发送停止请求')
        # This engine endpoint atomically checks the exact job. No global fallback.
        result=self.st.comfy.cancel_job(prompt)
        if not result:raise Conflict('任务已完成或离开队列，未发生中断，请刷新状态')

    def action(self,body):
        if body.get('confirmed') is not True:raise Conflict('请先确认本次操作的范围与影响')
        kind,action=body.get('kind'),body.get('action');pid=body.get('project');rid=body.get('id')
        if kind=='assembly' and getattr(self,'assembly',None):
            self.assembly.control(pid,rid,action)
            return '任务状态已更新，历史结果保留'
        if kind=='image' and self.images:
            if not pid or not rid:raise ValueError('缺少项目或任务编号')
            store=self.images.store;runner=self.images.runner
            if action=='cancel':
                with store.lock:
                    run=store.get('runs',rid,pid)
                    if run['state']!='waiting':raise Conflict('任务已开始提交，请刷新后选择停止当前生成')
                    runner.cancel(pid,rid)
                return '已取消排队，历史记录保留'
            if action=='close':
                # Same lock order as JobManager GPU reservation: jobs -> image store.
                with self.st.jobs._lock,store.lock:
                    run=store.get('runs',rid,pid)
                    if run['state']!='unknown' or self.st.jobs.is_busy(pid):raise Conflict('任务状态已变化或仍有执行线程，请稍后刷新')
                    prompt=run.get('prompt_id')
                    if not prompt:raise Conflict('缺少原提交编号，无法安全结束等待；请先在项目中核对原提交')
                    queue=self.st.comfy._get('/queue',timeout=10);history=self.st.comfy._get('/history/'+quote(prompt,safe=''),timeout=10)
                    if any(len(r)>1 and r[1]==prompt for r in queue.get('queue_running',[])+queue.get('queue_pending',[])) or history.get(prompt):
                        raise Conflict('已找到原任务或执行记录，请回项目核对原提交并收回结果')
                    runner.update(run,state='cancelled',closed_without_result=True,finished=time.time(),
                                  note='用户结束等待；原提交结果未确认，快照与编号保留')
                runner.wake()
                return '已结束这条记录的等待；其他排队任务可继续，原提交不会重试'
            if action=='stop':
                # Do not hold a store lock during network I/O or worker completion.
                run=store.get('runs',rid,pid)
                if run['state'] not in ('submitting','running'):raise Conflict('任务状态已变化，请刷新')
                self.stop_prompt(run)
                store.mutate('runs',rid,lambda r:r.update(stop_requested=True,note='已请求停止当前生成，等待引擎确认') if r['state'] in IMAGE_ACTIVE else None)
                return '已请求停止当前生成；通道在引擎确认后释放，已完成结果保留'
        elif kind=='video' and action in ('pause','stop'):
            if pid!=rid:raise Conflict('项目编号不一致')
            with self.st.jobs._lock:
                job=next((j for j in self.st.jobs._jobs.values() if j['project_id']==pid and j['lane']=='gpu'),None)
                if not job:raise Conflict('该项目没有正在执行的生成任务，请刷新')
                job['stop_requested']=True
                p=self.st.store.mutate(pid,lambda p:p.update(pause=True))
            if action=='stop':
                runs=[r for r in video_runs(p) if r.get('status') in ('submitting','submitted','interrupted')]
                if not runs:raise Conflict('已停止后续执行；当前没有可中断的引擎任务，正在收尾或恢复，请刷新')
                try:self.stop_prompt(runs[-1])
                except (ValueError,ComfyError) as exc:raise Conflict('已停止后续执行；当前生成未确认中断：'+str(exc)) from exc
                return '已请求停止当前生成，并停止本项目后续执行；已有结果保留'
            return '将在当前内部生成任务完成后停止，不再提交后续任务'
        elif kind=='local' and action=='cancel':
            self.local.cancel(rid);return '已取消尚未开始的本地任务，原件保留'
        raise ValueError('该任务不支持此操作')


@bp.get('')
def listing():return jsonify(current_app.config['TASK_CENTER'].snapshot())


@bp.post('/action')
def control():
    try:return jsonify(ok=True,message=current_app.config['TASK_CENTER'].action(request.get_json() or {}))
    except (ValueError,KeyError,ComfyError) as exc:
        return jsonify(error=str(exc),error_raw=str(exc),error_kind='engine' if isinstance(exc,ComfyError) else 'conflict'),409
