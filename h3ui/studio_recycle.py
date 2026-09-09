"""Read-only index over existing removal markers; restore uses the original APIs."""
from flask import Blueprint, current_app, jsonify, request

bp=Blueprint('recycle_bin',__name__,url_prefix='/api/v5')


def recycle_index(studio,images,library):
    groups=dict(assets=[],projects=[],generations=[])
    with library.store.connect() as db:
        for row in db.execute('SELECT id,name,revision,kind,deleted FROM assets WHERE deleted IS NOT NULL'):
            groups['assets'].append(dict(id=row['id'],title=row['name'],revision=row['revision'],kind=row['kind'],
                type='asset',removed_at=row['deleted'],open_url='#/assets/'+row['id']))
    projects=studio.store.list()+studio.store.list(trash=True)
    for p in projects:
        deleted=bool(p.get('deleted_at'));busy=studio.jobs.is_busy(p['id'])
        if deleted:
            groups['projects'].append(dict(id=p['id'],title=p['name'],type='project',revision=p['revision'],
                mode=p['mode'],removed_at=p['deleted_at'],open_url='#/p/'+p['id'],blocked_reason='项目仍有任务正在处理' if busy else ''))
        if p['mode'] in ('authoring','movie'):
            rows=p.get('movie_takes',[]) if p['mode']=='movie' else p.get('candidates',[])
            for record in rows:
                if not record.get('removed_at'):continue
                rid=record.get('take_id') or record['candidate_id']
                groups['generations'].append(dict(id=rid,title=p['name'],task_name='电影候选' if p['mode']=='movie' else '剧本文本候选',type='creation_record',project=p['id'],revision=p['revision'],mode=p['mode'],removed_at=record['removed_at'],state='complete',open_url='#/p/'+p['id'],blocked_reason='请先恢复所属项目' if deleted else '项目仍有任务正在处理' if busy else ''))
        if p['mode']=='video_assembly':
            blocked='请先恢复所属项目' if deleted else '项目仍有运行或待确认任务' if busy or any(r['state'] in ('preparing','submitting','running','unknown') for r in p['assembly']['runs']) else ''
            for clip in p['assembly']['clips']:
                for value,kind in [(clip,'clip')]+[(e,'extension') for e in clip['extensions']]:
                    if value.get('removed_at'):
                        groups['projects'].append(dict(id=value['id'],title=clip['name'],task_name=p['name']+' · '+('视频片段' if kind=='clip' else '续写段'),type='assembly_'+kind,project=p['id'],revision=p['revision'],mode=p['mode'],removed_at=value['removed_at'],open_url='#/p/'+p['id'],blocked_reason=blocked or ('请先恢复所属视频片段' if kind=='extension' and clip.get('removed_at') else '')))
            for run in p['assembly']['runs']:
                if run.get('removed_at'):
                    groups['generations'].append(dict(id=run['id'],title=p['name'],task_name='续接候选' if run['kind']=='generate' else '拼接成片',type='assembly_run',project=p['id'],revision=p['revision'],mode=p['mode'],removed_at=run['removed_at'],open_url='#/p/'+p['id'],blocked_reason=blocked,state=run['state'],seed=run.get('seed')))
        for segment in p.get('segments',[]):
            for run in segment.get('attempts',[]):
                if not run.get('removed_at'):continue
                groups['generations'].append(dict(id=run['id'],type='video_run',title=p['name'],project=p['id'],
                    segment=segment['id'],task_name=f"片段 {segment['index']+1}",revision=p['revision'],mode=p['mode'],
                    seed=run.get('seed'),state=run['status'],removed_at=run['removed_at'],parent_deleted=deleted,
                    blocked_reason='请先在“项目移除的”中恢复所属项目' if deleted else '项目仍有任务正在处理' if busy else '',open_url='#/p/'+p['id']))
    if images:
        runs_by_project={}
        for run in images.store.all('runs'):runs_by_project.setdefault(run['project'],[]).append(run)
        tasks={t['id']:t for t in images.store.all('tasks')}
        for p in images.store.all('projects'):
            runs=runs_by_project.get(p['id'],[]);deleted=bool(p.get('deleted_at'))
            busy=studio.jobs.is_busy(p['id']) or any(r['state'] in ('waiting','submitting','running','unknown') for r in runs)
            if deleted:
                groups['projects'].append(dict(id=p['id'],title=p['name'],type='project',revision=p['revision'],mode='image_assets',
                    removed_at=p['deleted_at'],open_url='#/p/'+p['id'],blocked_reason='项目仍有运行或待确认提交' if busy else ''))
            for task in tasks.values():
                if task['project']==p['id'] and task.get('discarded_at'):
                    groups['projects'].append(dict(id=task['id'],title=task['name'],task_name=p['name']+' · 编辑任务',
                        type='image_task',project=p['id'],revision=p['revision'],mode='image_assets',removed_at=task['discarded_at'],
                        open_url='#/p/'+p['id'],blocked_reason='请先恢复所属项目' if deleted else '项目仍有运行或待确认提交' if busy else ''))
            for run in runs:
                if not run.get('removed_at'):continue
                task_discarded=bool(tasks.get(run['task'],{}).get('discarded_at'))
                groups['generations'].append(dict(id=run['id'],type='image_run',title=p['name'],project=p['id'],
                    task_name=tasks.get(run['task'],{}).get('name','图片任务'),revision=p['revision'],mode='image_assets',
                    seed=run.get('seed'),state=run['state'],removed_at=run['removed_at'],parent_deleted=deleted,
                    blocked_reason='请先在“项目移除的”中恢复所属项目' if deleted else '请先在“项目移除的”中恢复编辑任务' if task_discarded else '项目仍有运行或待确认提交' if busy else '',open_url='#/p/'+p['id']))
    registry=studio.ctx['projects']
    page=1
    while True:
        data=registry.list(page=page,per_page=100,trash=True)
        for p in data['projects']:
            groups['projects'].append(dict(id=p['id'],title=p['name'],type='legacy_project',mode='legacy',
                removed_at=(registry.snapshot(p['id']) or {}).get('deleted_at'),blocked_reason='旧项目仍有任务正在处理' if studio.jobs.is_busy(p['id']) else ''))
        if page>=data['pages']:break
        page+=1
    return groups


@bp.get('/recycle-bin')
def listing():
    category=request.args.get('category','assets')
    if category not in ('assets','projects','generations'):return jsonify(error='回收站分类无效'),400
    try:page=max(1,int(request.args.get('page',1)))
    except ValueError:return jsonify(error='页码无效'),400
    groups=recycle_index(current_app.config['STUDIO'],current_app.config.get('IMAGE_STUDIO'),current_app.config['ASSET_LIBRARY'])
    query=request.args.get('q','').strip().casefold()
    rows=[r for r in groups[category] if not query or query in ' '.join(str(r.get(k,'')) for k in ('title','task_name','id','seed')).casefold()]
    rows.sort(key=lambda r:(r.get('removed_at') or 0,r['id']),reverse=True)
    limit=24;total=len(rows);page=min(page,max(1,(total+limit-1)//limit))
    items=rows[(page-1)*limit:page*limit]
    library=current_app.config['ASSET_LIBRARY'];images=current_app.config.get('IMAGE_STUDIO')
    for item in items:
        if item['type']=='asset':
            public=library.public(library.store.get(item['id']),compact=True)
            media=public['snapshot'].get('media',[])
            primary=next((m for m in media if m.get('role')=='primary'),media[0] if media else {})
            item['preview']=primary.get('preview_url') or (primary.get('url') if item.get('kind')=='image' else None)
        elif item['type']=='image_run' and not item['parent_deleted']:
            output=next((o for o in images.store.all('outputs',item['project']) if o['run']==item['id']),None)
            if output:item['preview']=images.url(item['project'],output['path'])
    return jsonify(category=category,counts={k:len(v) for k,v in groups.items()},items=items,page=page,limit=limit,total=total)
