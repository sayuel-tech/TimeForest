"""Read fixed natural-language records. Never compile graphs or use current drafts."""
import json
from pathlib import Path
from .families import identify


def read_attempt(attempt, root):
    root=Path(root).resolve();directory=Path(attempt.get('directory','')).resolve()
    if root not in directory.parents: return {}
    result={}
    for filename,key in [('manifest.json','manifest'),('prompt.txt','actual_prompt')]:
        path=directory/filename
        if path.is_file() and root in path.resolve().parents:
            try: result[key]=json.loads(path.read_text(encoding='utf-8')) if key=='manifest' else path.read_text(encoding='utf-8')
            except (OSError,ValueError): pass
    if attempt.get('tasks'):
        result['tasks']=[dict(index=t.get('index'),selected=t.get('selected'),runs=[dict(id=a['id'],records=read_attempt(a,root)) for a in t.get('attempts',[]) if a['id']==t.get('selected')]) for t in attempt['tasks']]
    return result


def prompt_records(origin, extra=()):
    rows=[]
    def walk(node,title,source,depth=0):
        if not isinstance(node,dict) or depth>16:return
        if node.get('type')=='portable_pack':
            walk(node.get('records'),title,{**source,'project':None,'external':True},depth+1);return
        source={**source,**{k:node[k] for k in ('project','project_name','mode','run','candidate','segment','task','output') if k in node and not source.get('external')}}
        if source.get('external'):source['project']=None
        manifest=node.get('manifest') or {}
        snapshot=node.get('snapshot') or {}
        settings=manifest.get('settings',{})
        purpose='image' if node.get('type')=='generated_image' or snapshot.get('submode') or source.get('mode')=='image_assets' else 'video'
        if purpose=='image':settings=snapshot.get('models',node.get('records',{}).get('snapshot',{}).get('models',{}))
        text=node.get('actual_prompt')
        if not isinstance(text,str):
            if snapshot.get('submode') and isinstance(snapshot.get('prompt'),str):
                text=snapshot['prompt'];settings=snapshot.get('models',{});purpose='image'
            elif isinstance(snapshot.get('extension'),dict):
                e=snapshot['extension'];text=e.get('prompt');settings=e.get('configurations',{}).get(e.get('recipe'),{})
        if isinstance(text,str) and text.strip() and not (isinstance(node.get('records'),dict) and node['records'].get('actual_prompt')==text):
            identity=identify(settings.get('model') or settings.get('unet'),purpose,extra)
            rows.append(dict(title=title,content=dict(type='text',text=text),purpose=purpose,source={**source,**identity}))
        if isinstance(node.get('records'),dict):
            walk(node['records'],title,source,depth+1)
        for i,row in enumerate(node.get('selected_runs',[]) if isinstance(node.get('selected_runs'),list) else []):
            walk(row,f'{title} · 片段 {i+1}',source,depth+1)
        for i,task in enumerate(node.get('tasks',[]) if isinstance(node.get('tasks'),list) else []):
            if not isinstance(task,dict):continue
            for r in task.get('runs',[]) if isinstance(task.get('runs'),list) else []:
                if r.get('id')==task.get('selected'):walk(r.get('records'),f'{title} · 内部任务 {i+1}',source,depth+1)
    walk(origin,'生成时提示词',{})
    # Old provenance sometimes stores the same text both at the root and in records.
    unique=[];seen=set()
    for row in rows:
        key=json.dumps([row['title'],row['content'],row['source']],sort_keys=True)
        if key not in seen:unique.append(row);seen.add(key)
    return unique


def project_records(app,pid,query):
    studio=app['STUDIO'];images=app.get('IMAGE_STUDIO')
    extra=app['PROMPT_LIBRARY'].cfg.get('prompt_model_families',[])
    if images and images.store.exists(pid):
        p=images.store.project(pid);run_id=query.get('run')
        if query.get('output'):
            output=images.store.get('outputs',query['output'],pid);run_id=output['run']
        run=images.store.get('runs',run_id,pid)
        return prompt_records(dict(type='generated_image',project=pid,project_name=p['name'],mode='image_assets',run=run['id'],task=run['task'],output=query.get('output'),snapshot=run['snapshot']),extra)
    p=studio.store.get(pid)
    base=dict(project=pid,project_name=p['name'],mode=p['mode'])
    if p['mode']=='movie':
        rid=query.get('run');take=next((t for t in p.get('movie_takes',[]) if t['take_id']==rid),None)
        export=next((e for e in p.get('movie_exports',[]) if e['export_id']==rid),None)
        if not take and not export:raise KeyError('此电影生成记录不存在，未替换为最新结果')
        takes=[take] if take else [next(t for t in p['movie_takes'] if t['take_id']==part['item']['take_id']) for part in export['manifest']['parts']]
        rows=[]
        for index,take in enumerate(takes):
            snapshot=p['artifacts'][take['snapshot_id']]
            batch=prompt_records(dict(**base,run=take['take_id'],segment=take['movie_segment_id'],actual_prompt=snapshot['actual_prompt_text'],manifest=dict(settings=snapshot['parameters'])),extra)
            if export:
                for row in batch:row['title']=f'成片 · 片段 {index+1} · '+row['title']
            rows.extend(batch)
        return rows
    if p['mode']=='video_assembly':
        run=app['VIDEO_ASSEMBLY'].find_run(p,query.get('run'))
        return assembly_records(app,{**base,'candidate':run['id'],'snapshot':run['snapshot']},set())
    root=studio.store.directory(pid)
    if query.get('final'):
        output=p.get('export') or {}
        if str(output.get('created'))!=query['final']: raise KeyError('该次成片记录已不可定位；没有替换为最新导出')
        manifest=Path(output.get('file','')).parent/'manifest.json'
        if root.resolve() not in manifest.resolve().parents or not manifest.is_file():return []
        saved=json.loads(manifest.read_text(encoding='utf-8'));ids=[r.get('attempt') for r in saved.get('selected',[])]
    else:ids=[query.get('run')]
    rows=[]
    attempts={a['id']:(s,a) for s in p['segments'] for a in s.get('attempts',[])}
    for index,ident in enumerate(ids):
        if ident in attempts:
            seg,attempt=attempts[ident]
            batch=prompt_records(dict(**base,segment=seg['id'],run=attempt['id'],records=read_attempt(attempt,root)),extra)
            if query.get('final'):
                for row in batch:row['title']=f'成片 · 片段 {index+1} · '+row['title']
            rows.extend(batch)
    if not rows and not query.get('final') and not any(a['id'] in ids for s in p['segments'] for a in s.get('attempts',[])): raise KeyError('该生成记录不存在')
    return rows


def assembly_records(app, origin, seen):
    extra=app['PROMPT_LIBRARY'].cfg.get('prompt_model_families',[])
    rows=prompt_records(origin,extra)
    pid=origin.get('project');rid=origin.get('candidate') or origin.get('run')
    key=('run',pid,rid)
    if key in seen or len(seen)>=50:return rows
    seen.add(key)
    # Only exact identities in the frozen export manifest are followed.
    for i,part in enumerate(origin.get('snapshot',{}).get('parts',[])):
        source=part.get('origin') or {};candidate=part.get('candidate') or source.get('candidate');batch=[]
        try:
            if candidate:
                p=app['STUDIO'].store.get(pid);r=app['VIDEO_ASSEMBLY'].find_run(p,candidate)
                batch=assembly_records(app,{**origin,'candidate':r['id'],'snapshot':r['snapshot']},seen)
            elif source.get('type')=='library':
                batch=asset_records(app,source['asset'],source['version'],source['media'],seen)
        except (KeyError,ValueError,FileNotFoundError):
            # Old missing records remain absent, never substituted with live drafts.
            continue
        for row in batch:row['title']=f'成片 · 片段 {i+1} · '+row['title']
        rows.extend(batch)
    return rows


def asset_records(app,aid,version,mid,seen=None):
    from ..asset_library.pack_lineage import media_origin
    if not version or not mid: raise ValueError('请选择固定资产版本和媒体，不能用最新版本补齐来源')
    item=app['ASSET_LIBRARY'].store.get(aid,version)
    media=next((m for m in item['snapshot']['media'] if m['id']==mid),None)
    if not media:raise ValueError('媒体不属于该固定版本')
    seen=set() if seen is None else seen
    key=('asset',aid,item['snapshot']['id'],mid)
    if key in seen or len(seen)>=50:return []
    seen.add(key)
    origin=media_origin(item['snapshot'],media)
    rows=assembly_records(app,origin,seen) if origin.get('mode')=='video_assembly' and origin.get('type')!='portable_pack' else prompt_records(origin,app['PROMPT_LIBRARY'].cfg.get('prompt_model_families',[]))
    for row in rows:row['source'].update(asset=aid,asset_version=item['snapshot']['id'],media=mid)
    return rows
