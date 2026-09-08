"""User storyboards and their private, resumable render tasks (no GPU imports)."""
import copy
import json
import math
import re
import time
import uuid
from pathlib import Path
from .studio_plan import frames, aligned
from . import studio_media as av, studio_prompts
from .studio_progress import local_progress


def storyboard(seconds, cap_seconds=15, boundaries=None, timing_mode='natural'):
    total = frames(seconds)
    if not 24 <= total <= 86400:
        raise ValueError('目标时长须为1～3600秒')
    cap = 5 + 17 * math.floor((min(frames(cap_seconds), 360) - 5) / 17)
    if cap < 124:
        raise ValueError('单次渲染上限至少约5.167秒')
    result = []
    actual_cursor=0
    for i, start in enumerate(range(0, total, 360)):
        requested = min(360, total-start)
        boundary = 'new_scene' if i == 0 or (boundaries or {}).get(i) == 'new_scene' else 'continue'
        first_head=0 if boundary=='new_scene' else 22
        # Natural pacing tolerates at most one grid interval plus the AV
        # context (38 frames). A much lower user render cap must not silently
        # turn a 15-second storyboard into e.g. 5 seconds.
        deliver=requested
        shortage=requested-(cap-first_head)
        if timing_mode=='natural' and 0<shortage<=38:deliver=cap-first_head
        remaining = deliver
        tasks = []
        cursor = 0
        # Fill legal tasks in order. Only the last task of a storyboard may trim
        # its tail. Its successor must use decoded, delivered AV context.
        count=1 if deliver<=cap-first_head else 1+math.ceil((deliver-(cap-first_head))/(cap-22))
        while remaining:
            head = 0 if not tasks and boundary == 'new_scene' else 22
            left=count-len(tasks)-1
            if left:
                choices=[r for r in range(124,cap+1,17) if 1<=remaining-(r-head)<=left*(cap-22)]
                raw=min(choices,key=lambda r:abs(r-head-remaining/(left+1)))
                n=raw-head
            else:
                n=remaining;raw=max(124,aligned(n+head))
            tasks.append(dict(index=len(tasks),raw=raw,head=head,deliver=n,
                              tail=raw-head-n,start=actual_cursor+cursor,offset=cursor,
                              duration=n/24,boundary='new_scene' if not head else 'continue'))
            remaining -= n
            cursor += n
        result.append(dict(index=i,start=actual_cursor,deliver=deliver,duration=deliver/24,
                           requested_frames=requested,requested_start=start,
                           raw=sum(t['raw'] for t in tasks),head=tasks[0]['head'],
                           tail=tasks[-1]['tail'],boundary=boundary,task_plan=tasks))
        actual_cursor+=deliver
    return result


def replan(studio, project, incoming, duration, cap):
    """Preserve drafts by index; archive removed content, never merge prompts."""
    prior = copy.deepcopy(incoming)
    plan = storyboard(duration, cap, {s['index']:s['boundary'] for s in prior},project.get('timing_mode','natural'))
    result = []
    for i, item in enumerate(plan):
        s = prior[i] if i < len(prior) else studio.new_segment(item)
        s.update(item)
        result.append(s)
    return result, prior[len(plan):]


def task_segments(studio, p, shot):
    """Allocate authored clauses once; do not ask for extra prompt boxes.

    Dialogue tags are indivisible. This is deterministic editorial allocation,
    not a claim that the model will execute precise semantic timing.
    """
    user = shot.get('prompt','').strip()
    if shot.get('beats','').strip() and len(shot['task_plan'])>1:
        user=shot['beats'].strip()+'\n'+user
    units = re.findall(r'<d>.*?</d>|[^<。！？!?\n]+[。！？!?]?|<(?!d>)[^\n]*', user, re.S)
    units = [s.strip() for s in units if s.strip()]
    if not units and user:
        units = [user]
    buckets = [[] for _ in shot['task_plan']]
    weight = sum(len(u) for u in units) or 1
    used = 0
    for unit in units:
        # Keep long clauses/dialogue at their start, never split their text.
        position = used / weight * shot['deliver']
        j = next((j for j,t in enumerate(shot['task_plan']) if position < t['offset']+t['deliver']),len(buckets)-1)
        buckets[j].append(unit)
        used += len(unit)
    assets = [a['id'] for a in studio.resolve(p, shot)]
    tasks = []
    for i, plan in enumerate(shot['task_plan']):
        task = studio.new_segment(plan)
        for k in ['voice','speaker_order','staging','soundscape','music','seed_mode','seed']:
            task[k] = shot.get(k,task[k])
        task.update(assets=assets,inherit_ids=[],asset_mode='custom' if assets else shot.get('asset_mode','auto'),story_index=shot['index'],story_task=i,
                    story_task_total=len(shot['task_plan']),
                    story_offset=plan['offset']/24,story_duration=shot['duration'])
        if len(buckets)==1:
            task.update(prompt=user,prompt_mode=shot.get('prompt_mode','structured'),
                        beats=shot.get('beats',''),ending=shot.get('ending',''))
        else:
            task['prompt']='\n'.join(buckets[i]) or 'Continue the established ongoing movement naturally. No new dialogue or repeated events.'
            task['beats']=''
            task['ending']=shot.get('ending','') if i==len(buckets)-1 else ''
            task['task_instruction']=(f'This is internal render {i+1}/{len(buckets)} of storyboard {shot["index"]+1}, '
                f'covering storyboard time {plan["offset"]/24:.3f}–{(plan["offset"]+plan["deliver"])/24:.3f}s. '
                'Perform only the authored events below. Preserve the established camera and scene; '
                'do not restart the storyboard or repeat earlier dialogue. Do not create an extra shot transition.')
        tasks.append(task)
    return tasks


class TaskStore:
    """Project store view over one storyboard attempt. Writes remain atomic."""
    def __init__(self, parent, pid, index, aid):
        self.parent,self.pid,self.index,self.aid=parent,pid,index,aid
    def __getattr__(self,key):return getattr(self.parent,key)
    def _attempt(self,p):return next(a for a in p['segments'][self.index]['attempts'] if a['id']==self.aid)
    def get(self,pid):
        p=self.parent.get(pid);a=self._attempt(p)
        return {**p,'segments':a['tasks'],'review':'automatic','storyboard_version':0,
                '_task_execution':True,'_story_previous':a.get('previous'),
                '_story_source_lineage':a.get('source_lineage',{}),
                '_story_owner':dict(segment=p['segments'][self.index]['id'],run=self.aid)}
    def mutate(self,pid,fn):
        def update(p):
            a=self._attempt(p)
            view={**copy.deepcopy(p),'segments':a['tasks'],'review':'automatic','storyboard_version':0,
                  '_task_execution':True,'_story_previous':a.get('previous'),
                  '_story_source_lineage':a.get('source_lineage',{}),
                  '_story_owner':dict(segment=p['segments'][self.index]['id'],run=self.aid)}
            fn(view);a['tasks']=view['segments']
            if view.get('error'):a['error']=view['error']
            a['completed_tasks']=sum(t['status'] in ['done','accepted'] for t in a['tasks'])
        self.parent.mutate(pid,update)
        return self.get(pid)


class StoryExecution:
    def worker(self,pid,index,aid):
        worker=object.__new__(type(self));worker.__dict__=dict(self.__dict__)
        worker.store=TaskStore(self.store,pid,index,aid)
        return worker

    def story_preflight(self,pid):
        p=self.store.get(pid);rows=[];issues=[]
        self.recipes.refresh()
        for shot in p['segments']:
            errors=[];reports=[]
            try:
                if not shot.get('prompt','').strip():raise ValueError('请填写本片段人工提示词')
                tasks=task_segments(self,p,shot)
                if p['settings']['recipe']=='dance_split':previous=self.previous(p,shot,required=False)
                elif shot['head'] and shot['index'] and p['segments'][shot['index']-1]['tail']:
                    prevshot=p['segments'][shot['index']-1]
                    previous=self.previous(p,shot,required=False) or dict(video='__previous_story_delivery_pending__.mp4',frames=prevshot['deliver'])
                else:previous=self.previous(p,shot,required=False)
                # Reuse all existing asset and workflow validation on task view.
                class ReadView:
                    def get(_,key):return {**p,'segments':tasks,'storyboard_version':0,'_task_execution':True,'_story_previous':previous}
                    def __getattr__(_,key):return getattr(self.store,key)
                worker=object.__new__(type(self));worker.__dict__=dict(self.__dict__);worker.store=ReadView()
                reports=worker.preflight(pid)['segments']
                for r in reports:errors.extend(r['errors'])
            except ValueError as e:errors.append(str(e))
            rows.append(dict(id=shot['id'],index=shot['index'],raw=shot['raw'],head=shot['head'],
                             deliver=shot['deliver'],tail=shot['tail'],errors=errors,tasks=reports,
                             prompt=shot.get('prompt',''),compiled=None))
            issues.extend(f'P{shot["index"]+1}: {e}' for e in errors)
        return dict(ready=not issues,revision=p['revision'],errors=issues,segments=rows,
                    note='按片段审核；内部任务已检查结构，未运行H3生成。对白和动作时序仍需人工检查。')

    def generate_story(self,pid,index):
        p=self.store.get(pid);s=p['segments'][index]
        aid=uuid.uuid4().hex;previous=self.previous(p,s)
        tasks=task_segments(self,p,s)
        for i,t in enumerate(tasks):
            if s['seed_mode']=='fixed':t['seed']=str((int(s['seed'])+i)%9007199254740992)
        directory=self.store.directory(pid)/'segments'/s['id']/'attempts'/aid
        directory.mkdir(parents=True)
        from .generation.source_lineage import capture
        source_lineage=capture(self,p,s,self.resolve(p,s),previous)
        manifest=dict(settings=p['settings'],segment=s,previous=previous,revision=p['revision'],source_lineage=source_lineage)
        (directory/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')
        (directory/'prompt.txt').write_text(studio_prompts.build(p,s,self.resolve(p,s)),encoding='utf-8')
        attempt=dict(id=aid,status='submitting',seed=s['seed'] if s['seed_mode']=='fixed' else None,
                     created=time.time(),directory=str(directory),tasks=tasks,previous=previous,completed_tasks=0,source_lineage=source_lineage)
        def start(q):
            q['segments'][index]['attempts'].append(attempt)
            q['segments'][index].update(status='generating');q.update(status='generating',error=None)
        self.store.mutate(pid,start)
        return self.continue_story(pid,index,aid)

    def continue_story(self,pid,index,aid,recover=False):
        p=self.store.get(pid);shot=p['segments'][index]
        attempt=next(a for a in shot['attempts'] if a['id']==aid)
        manifest=json.loads((Path(attempt['directory'])/'manifest.json').read_text(encoding='utf-8'))
        authored=['prompt','prompt_mode','voice','speaker_order','staging','beats','soundscape','music','ending','assets','inherit_ids','raw','head','deliver','tail','boundary']
        if manifest['segment'].get('asset_mode','auto')!=shot.get('asset_mode','auto'):raise ValueError('候选结果的素材引用方式已变化，请重新生成')
        if manifest['settings']!=p['settings'] or any(manifest['segment'].get(k)!=shot.get(k) for k in authored) or manifest['previous']!=self.previous(p,shot):
            raise ValueError('片段参数、素材或前段上下文已改变，不能恢复旧任务到当前编排')
        worker=self.worker(pid,index,aid)
        try:
            for i in range(len(worker.store.get(pid)['segments'])):
                task=worker.store.get(pid)['segments'][i]
                if task['status'] in ['accepted','done']:continue
                if self.store.get(pid).get('pause') and not recover:
                    raise ValueError('用户已停止后续执行；已完成的内部任务保留，可稍后继续')
                if task['status']=='interrupted':
                    if not recover:raise ValueError('内部任务已中断，请查询并恢复')
                    worker.recover(pid,i)
                    task=worker.store.get(pid)['segments'][i]
                    if task['status']=='failed':raise ValueError('内部任务已确认失败，可点击继续未完成任务重试')
                    if task['status'] not in ['accepted','done']:raise ValueError('内部任务尚未恢复')
                    continue
                if recover:raise ValueError('已恢复已有结果；仍有未提交任务，请点击继续未完成任务')
                worker.generate_one(pid,i)
                if worker.store.get(pid)['segments'][i]['status'] not in ['accepted','done']:
                    raise ValueError(worker.store.get(pid).get('error') or '内部任务中断，请查询恢复')
            return self.finish_story(pid,index,aid)
        except Exception as e:
            def fail(q):
                shot=q['segments'][index];a=next(a for a in shot['attempts'] if a['id']==aid)
                a.update(status='interrupted',error=str(e));shot['status']='interrupted';q.update(status='interrupted',error=str(e))
            self.store.mutate(pid,fail)

    def resume_story_chain(self,pid,index,aid):
        with self.jobs._lock:
            stopped=any(j.get('stop_requested') for j in self.jobs._jobs.values() if j['project_id']==pid)
            self.store.mutate(pid,lambda p:p.update(pause=stopped))
        self.continue_story(pid,index,aid)
        p=self.store.get(pid)
        if p['segments'][index]['status'] in ['accepted','done']:
            self.run_chain(pid,None,True)

    def finish_story(self,pid,index,aid):
        p=self.store.get(pid);shot=p['segments'][index];a=next(a for a in shot['attempts'] if a['id']==aid)
        selected=[]
        for t in a['tasks']:
            candidate=next(x for x in t['attempts'] if x['id']==t['selected'])
            selected.append(dict(delivery=candidate['delivery'],deliver=t['deliver']))
        local_progress(self.store.directory(pid),'整理片段预览与声音',started=a['created'],finished=None,shot=index,connected=False)
        dst,report=av.assemble(selected,Path(a['directory'])/'assembled',24)
        last=a['tasks'][-1];candidate=next(x for x in last['attempts'] if x['id']==last['selected'])
        def saved(q):
            s=q['segments'][index];aa=next(x for x in s['attempts'] if x['id']==aid)
            aa.update(status='complete',error=None,delivery=str(dst),qa=report,context=candidate['context'],
                      seed=a['tasks'][0]['last_seed'],completed=time.time())
            if candidate.get('tail_context'):aa['tail_context']=candidate['tail_context']
            s.update(selected=aid,last_seed=aa['seed'],status='needs_review' if q['review']=='manual' else 'done')
            q.update(status=s['status'],error=None)
        result=self.store.mutate(pid,saved)
        local_progress(self.store.directory(pid),'片段已完成，等待审核' if p['review']=='manual' else '片段已完成',finished=time.time(),connected=False)
        return result
