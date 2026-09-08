"""On-demand, bounded metadata scan for collected downstream media.

Historical versions are explicit results. No usage refs, file-name matching,
project mutation, migration or automatic background scan.
"""
import json
from .lineage import AssetLineage, mapping
from .pack_lineage import media_origin


def descendants(origins, aid, version, mid, cursor='0:0', upper=None):
    item=origins.lib.store.get(aid,version)
    media=next((m for m in item['snapshot']['media'] if m['id']==mid),None)
    if media is None: raise ValueError('所选媒体不属于该资产版本')
    try:
        after,index=(int(x) for x in cursor.split(':'))
        if after<0 or index<0: raise ValueError()
        upper=int(upper) if upper is not None else None
        if upper is not None and upper<after: raise ValueError()
    except (ValueError,TypeError): raise ValueError('下游查看分页位置无效') from None
    with origins.lib.store.connect() as db:
        if upper is None: upper=db.execute('SELECT COALESCE(MAX(rowid),0) FROM versions').fetchone()[0]
        # Page media, not entire version bodies: an asset can have many alternates.
        batch=db.execute('''SELECT v.rowid AS position, v.asset, v.id AS version,
                   json_extract(v.body,'$.name') AS name, m.key AS media_index, m.value AS media,
                   a.deleted, a.version AS current_version
            FROM versions v JOIN assets a ON a.id=v.asset, json_each(v.body,'$.media') m
            WHERE v.rowid<=? AND (v.rowid>? OR (v.rowid=? AND m.key>?))
            ORDER BY v.rowid,m.key LIMIT 26''',(upper,after,after,index)).fetchall()
    rows=[];incomplete=0
    for entry in batch[:25]:
        m=json.loads(entry['media'])
        if (entry['asset'],entry['version'],m.get('id'))==(aid,version,mid): continue
        # Use the same fallback rules and exact identity validation as origin reads.
        candidate=origins.lib.store.get(entry['asset'],entry['version'])
        snap=candidate['snapshot']
        origin=media_origin(snap,m)
        lineage=AssetLineage(origins,{}).read(mapping(origin))
        match=next((r for r in lineage['rows'] if r.get('kind')=='asset' and r.get('asset')==aid and r.get('version')==version and r.get('media')==mid and r['state'] in ('available','removed')),None)
        if match:
            rows.append(dict(asset=entry['asset'],version=entry['version'],media=m['id'],name=entry['name'],
                             removed=bool(entry['deleted']),historical=entry['current_version']!=entry['version']))
        if lineage['truncated'] or any(r['state'] in ('missing','incomplete','cycle','limit','external') or (r['kind']=='boundary' and r['state']=='unrecorded') for r in lineage['rows']):
            incomplete+=1
    last=batch[min(len(batch),25)-1] if batch else None
    return dict(version=1,rows=rows,scanned=min(len(batch),25),incomplete=incomplete,upper=upper,
                cursor=f"{last['position']}:{last['media_index']}" if len(batch)>25 else None)
