"""Read-only pages of project results whose saved sources reach fixed library media."""
import json
import time
from .lineage import AssetLineage
from ..generation.source_lineage import video_attempts, attempt_records, export_records


def project_results(origins,p):
    pid=p['id']
    if p.get('mode')=='movie':
        for take in p.get('movie_takes',[]):
            yield dict(id=take['take_id'],run=take['take_id'],eligible=True,name='电影片段候选',created=float(take['created_at']),completed=float(take['created_at']),removed=take['state']=='removed',origin=dict(mode='movie',project=pid,movie_lineage=take.get('lineage',{})),target=dict(run=take['take_id'],segment=take['movie_segment_id']))
        for export in p.get('movie_exports',[]):
            yield dict(id=export['export_id'],run=export['export_id'],eligible=True,name='电影成片',created=float(export['created_at']),completed=float(export['created_at']),removed=False,origin=dict(mode='movie',project=pid,movie_lineage=dict(parts=[dict(project=pid,run=x['item']['take_id']) for x in export['manifest']['parts']])),target=dict(run=export['export_id']))
    elif p.get('mode')=='video_assembly':
        for run in p.get('assembly',{}).get('runs',[]):
            removed=bool(run.get('removed_at'))
            for clip in p['assembly'].get('clips',[]):
                for extension in clip.get('extensions',[]):
                    if extension['id']==run.get('extension'):removed=removed or bool(clip.get('removed_at') or extension.get('removed_at'))
            yield dict(id=run['id'],run=run['id'],eligible=run.get('state')=='success' and run.get('kind') in ('generate','export'),name='拼接成片' if run.get('kind')=='export' else '视频续接候选',created=run.get('created',0),completed=run.get('finished') or 0,removed=removed,
                       origin=dict(type='generated',project=pid,snapshot=run.get('snapshot'),tasks=run.get('tasks')),target=dict(run=run['id']))
    else:
        for segment,run,historical in video_attempts(p):
            yield dict(id=run['id'],run=run['id'],eligible=run.get('status')=='complete',name='片段候选',created=run.get('created',0),completed=run.get('completed') or 0,removed=bool(run.get('removed_at')),historical=historical,
                       origin=dict(type='generated',project=pid),_attempt=run,target=dict(segment=segment['id'],run=run['id']))
        if p.get('export'):
            stamp=p['export'].get('created')
            yield dict(id='final:'+str(stamp),run='final:'+str(stamp),name='项目成片',created=stamp or 0,
                       origin=dict(type='generated',project=pid),_export=p,target=dict(final=str(stamp) if stamp is not None else 'unknown'))


def generation_descendants(origins,aid,version,mid,cursor=None,before=None):
    item=origins.lib.store.get(aid,version)
    if not any(m['id']==mid for m in item['snapshot']['media']):raise ValueError('所选媒体不属于该资产版本')
    try:
        stage,position,offset=(cursor or '0:0:').split(':',2)
        stage,position=int(stage),int(position)
        before=float(before) if before is not None else time.time()
        if stage not in (0,1) or position<0 or len(offset)>160 or not 0<=before<=time.time()+1:raise ValueError()
    except (ValueError,TypeError):raise ValueError('生成结果分页位置无效') from None
    result=[];scanned=0;unknown=0;budget=0
    reader=AssetLineage(origins,dict(asset=aid,version=version,media=mid))

    def examine(candidate,pid):
        nonlocal scanned,unknown
        if candidate.get('created',0)>before or candidate.get('completed',0)>before or candidate.get('eligible') is False:return
        scanned+=1
        if '_attempt' in candidate:
            candidate['origin']['records']=attempt_records(origins.studio.store,pid,candidate['_attempt'])
        if '_export' in candidate:
            candidate['origin']['records']=export_records(origins.studio.store,candidate['_export'])
        lineage=AssetLineage(origins,{}).read(candidate['origin'])
        match=any(r.get('kind')=='asset' and (r.get('asset'),r.get('version'),r.get('media'))==(aid,version,mid) and r['state'] in ('available','removed') for r in lineage['rows'])
        if match:
            result.append({k:v for k,v in candidate.items() if k in ('id','run','output','name','removed','historical')})
            result[-1]['project']=reader.project(pid,**candidate['target'])
        record=candidate['origin'].get('records',{})
        known=bool('movie_lineage' in candidate['origin'] or candidate['origin'].get('snapshot') or record.get('source_lineage') or record.get('manifest',{}).get('source_lineage') or record.get('segments') or record.get('snapshot'))
        if not known or lineage['truncated'] or any(r['state'] in ('missing','incomplete','cycle','limit','external') or (r['kind']=='boundary' and r['state']=='unrecorded') for r in lineage['rows']):unknown+=1

    # Bound work even when many projects contain no successful results.
    while budget<25:
        if stage==0:
            with origins.studio.store.connect() as db:
                row=db.execute('SELECT rowid,body FROM projects WHERE rowid>=? ORDER BY rowid LIMIT 1',(position,)).fetchone()
            if row is None:stage=1;position=0;offset='';continue
            rid,body=row;p=json.loads(body)
            if rid!=position:position=rid;offset=''
            candidates=sorted((c for c in project_results(origins,p) if c.get('created',0)<=before and c['id']>offset),key=lambda c:c['id'])
            candidate=candidates[0] if candidates else None
            budget+=1
            if candidate is None:position=rid+1;offset='';continue
            offset=candidate['id'];examine(candidate,p['id'])
        else:
            images=origins.images
            if images is None:break
            with images.store.connect() as db:
                row=db.execute('SELECT rowid,body FROM image_outputs WHERE rowid>? ORDER BY rowid LIMIT 1',(position,)).fetchone()
            if row is None:break
            position,body=row;out=json.loads(body);budget+=1
            try:
                run=images.store.get('runs',out['run'],out['project'])
                task=images.store.get('tasks',out['task'],out['project'])
                examine(dict(id=out['id'],output=out['id'],run=run['id'],name='图片候选',created=run.get('created',0),completed=run.get('finished') or 0,removed=bool(out.get('removed_at') or task.get('discarded_at')),
                             origin=dict(type='generated_image',project=out['project'],records=run),target=dict(run=run['id'],task=out['task'],output=out['id'])),out['project'])
            except (KeyError,ValueError):unknown+=1
    else:
        return dict(version=1,rows=result,scanned=scanned,incomplete=unknown,before=before,cursor=f'{stage}:{position}:{offset}')
    return dict(version=1,rows=result,scanned=scanned,incomplete=unknown,before=before,cursor=None)
