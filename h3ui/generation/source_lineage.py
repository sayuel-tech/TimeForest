"""Capture source identities beside execution data, without changing the graph."""
import copy
import json
from pathlib import Path
from ..studio_inputs import inventory


def capture(studio, project, segment, assets, previous):
    refs=[]
    for row in inventory(project,segment,assets):
        asset=next((a for a in assets if a.get('id')==row.get('asset_id')),None)
        if row['kind']=='video' and row.get('asset_id'):
            try: asset=studio.store.asset(project['id'],row['asset_id'])
            except ValueError: asset=None
        reference=(asset or {}).get('library_reference')
        refs.append(dict(kind=row['kind'],tag=row['tag'],purpose=row.get('purpose'),
                         project_asset=row.get('asset_id'),reference=copy.deepcopy(reference)))
    parent=None
    if previous:
        if project.get('_task_execution') and segment['index']==0:
            parent=copy.deepcopy(project.get('_story_source_lineage',{}).get('previous'))
        else:
            prior=project['segments'][segment['index']-1]
            selected=next((a for a in prior.get('attempts',[]) if a['id']==prior.get('selected')),None)
            if selected:
                parent=dict(project=project['id'],segment=prior['id'],run=selected['id'])
                if project.get('_task_execution'):
                    owner=project.get('_story_owner',{})
                    parent=dict(project=project['id'],segment=owner.get('segment'),run=owner.get('run'),
                                internal_segment=prior['id'],internal_run=selected['id'])
    return dict(version=1,inputs=refs,previous=parent,previous_recorded=not bool(previous) or parent is not None)


def saved_manifest(store,pid,attempt):
    """Only the recorded run directory, contained in its project; never a glob."""
    directory=Path(attempt.get('directory','')).resolve()
    root=store.directory(pid).resolve()
    path=directory/'manifest.json'
    if root not in directory.parents or root not in path.resolve().parents:return {}
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data,dict) else {}
    except (OSError,ValueError):return {}


def attempt_records(store,pid,attempt):
    manifest=saved_manifest(store,pid,attempt)
    records=dict(manifest=manifest)
    if isinstance(attempt.get('source_lineage'),dict):
        records['source_lineage']=copy.deepcopy(attempt['source_lineage'])
    return records


def video_attempts(project):
    """Yield user-visible candidates, including retained older layouts, once."""
    seen=set()
    groups=[(project.get('segments',[]),False),(project.get('removed_drafts',[]),True)]
    groups.extend((layout,True) for layout in project.get('previous_layouts',[]) if isinstance(layout,list))
    for segments,historical in groups:
        for segment in segments:
            for attempt in segment.get('attempts',[]):
                key=(segment['id'],attempt['id'])
                if key in seen:continue
                seen.add(key)
                yield segment,attempt,historical


def find_attempt(project,reference):
    found=next(((s,a,h) for s,a,h in video_attempts(project) if s['id']==reference.get('segment') and a['id']==reference.get('run')),None)
    if found is None:raise KeyError('候选不属于指定片段')
    segment,attempt,historical=found
    if reference.get('internal_run') or reference.get('internal_segment'):
        internal=next((a for t in attempt.get('tasks',[]) if t['id']==reference.get('internal_segment') for a in t.get('attempts',[]) if a['id']==reference.get('internal_run')),None)
        if internal is None:raise KeyError('内部运行不属于指定候选')
        return internal,historical,bool(attempt.get('removed_at') or internal.get('removed_at'))
    return attempt,historical,bool(attempt.get('removed_at'))


def export_records(store,project):
    pid=project['id'];path=Path(project.get('export',{}).get('file','')).resolve().parent/'manifest.json'
    if store.directory(pid).resolve() not in path.resolve().parents:return {}
    try:manifest=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}
    if not isinstance(manifest,dict):return {}
    selected={r.get('attempt') for r in manifest.get('selected',[]) if isinstance(r,dict)}
    return dict(segments=manifest,selected_runs=[dict(segment=s['id'],candidate=a['id'],records=attempt_records(store,pid,a))
                for s,a,_ in video_attempts(project) if a['id'] in selected])
