"""Package-scoped asset identities. External project IDs never become local IDs."""
import copy


def media_origin(snapshot,media):
    origin=media.get('provenance')
    if origin is None and len(snapshot['media'])==1:origin=snapshot.get('provenance')
    origin=origin if isinstance(origin,dict) else {}
    # Older imports preserved raw per-media provenance under a pack snapshot.
    root=snapshot.get('provenance') or {}
    if isinstance(root,dict) and root.get('type')=='portable_pack' and origin.get('type')!='portable_pack':
        return dict(type='portable_pack',records=origin)
    return origin


def direct_links(origin):
    """Fallback for library-only callers without access to project run stores."""
    links=[]
    def add(ref,relation):
        if isinstance(ref,dict) and all(ref.get(k) for k in ('asset','version','media','hash')):
            links.append(dict(ref,relation=relation))
    if origin.get('type')=='portable_pack':
        for link in origin.get('pack_links',[]):
            if link.get('state')=='mapped':add(link.get('reference'),'ancestor')
        return links
    add(origin.get('parent'),'derived');add(origin.get('library_reference'),'derived')
    snap=origin.get('snapshot',{}) or {}
    add(snap.get('source',{}).get('origin'),'continuation')
    for i,part in enumerate(snap.get('parts',[])):
        add(part.get('origin'),'part_'+str(i+1))
    records=origin.get('records',{}) or {}
    if origin.get('type')=='generated_image':
        saved=records.get('snapshot',{})
        roles=['A']+(['B'] if saved.get('submode')=='dual' else [])+(['mask'] if saved.get('submode')=='region' else [])
        if saved.get('submode')!='text':
            for role in roles:add(saved.get('inputs',{}).get(role,{}).get('provenance'),'image_'+role)
    saved=records.get('source_lineage',records.get('manifest',{}).get('source_lineage',{}))
    for row in saved.get('inputs',[]):add(row.get('reference'),'reference_'+str(row.get('kind','unknown')))
    return links


def export_links(library,snapshot,media,selected,origins=None):
    origin=media_origin(snapshot,media)
    if origins is not None:
        from .lineage import AssetLineage
        data=AssetLineage(origins,{}).read(origin)
        refs=[]
        for row in data['rows']:
            if row['kind']!='asset' or row['state'] not in ('available','removed'):continue
            item=library.store.get(row['asset'],row['version'])
            source=next(m for m in item['snapshot']['media'] if m['id']==row['media'])
            refs.append(dict(asset=row['asset'],version=row['version'],media=row['media'],hash=source['hash'],relation=row['relation'] if row['parent'] is None else 'ancestor'))
        incomplete=data['truncated'] or any(r['state'] in ('missing','incomplete','cycle','limit','external','unrecorded') for r in data['rows'])
    else:
        refs=direct_links(origin)
        incomplete=(origin.get('pack_lineage_version')!=1 or origin.get('pack_lineage_incomplete',False) or any(x.get('state')!='mapped' for x in origin.get('pack_links',[]))) if origin.get('type')=='portable_pack' else origin.get('type') not in ('local','derived')
    links=[];seen=set()
    for ref in refs:
        identity=tuple(ref[k] for k in ('asset','version','media','hash'))
        if identity in seen:continue
        seen.add(identity)
        target=selected.get(ref['version'])
        included=bool(target and target['asset_id']==ref['asset'] and any(m['id']==ref['media'] and m['hash']==ref['hash'] for m in target['media']))
        links.append(dict(reference=dict(zip(('asset','version','media','hash'),identity)),relation=ref['relation'],state='included' if included else 'outside'))
    return dict(version=1,links=links[:64],incomplete=bool(incomplete or len(links)>64))


def validate(versions):
    """Validate all exact references and combined ordering before any import write."""
    for snap in versions.values():
        for binding in snap.get('bindings',[]):
            target=versions.get(binding['version'])
            if not target or binding.get('asset')!=target.get('asset_id'):
                raise ValueError('素材包绑定资产与版本不匹配')
        for media in snap['media']:
            data=media.get('portable_lineage')
            if data is None:continue
            if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('links'),list) or len(data['links'])>64:
                raise ValueError('素材包来源关系格式不支持')
            for link in data['links']:
                if not isinstance(link,dict) or link.get('state') not in ('included','outside') or not isinstance(link.get('relation'),str):raise ValueError('素材包来源关系无效')
                ref=link.get('reference',{})
                if not isinstance(ref,dict) or not all(isinstance(ref.get(k),str) and ref[k] for k in ('asset','version','media','hash')):raise ValueError('素材包来源身份不完整')
                if link['state']=='included':
                    target=versions.get(ref['version'])
                    if not target or target['asset_id']!=ref['asset'] or not any(m['id']==ref['media'] and m['hash']==ref['hash'] for m in target['media']):
                        raise ValueError('素材包来源版本、媒体或摘要不匹配')
    active=set();seen=set()
    def visit(vid):
        if vid in active:raise ValueError('素材包来源与绑定存在循环')
        if vid in seen:return
        active.add(vid)
        snap=versions[vid]
        dependencies=[b['version'] for b in snap.get('bindings',[])]
        dependencies.extend(link['reference']['version'] for m in snap['media'] for link in m.get('portable_lineage',{}).get('links',[]) if link['state']=='included')
        for dependency in dependencies:visit(dependency)
        active.remove(vid);seen.add(vid)
    for vid in versions:visit(vid)


def imported_origin(snapshot,media,pack_hash,save):
    raw=copy.deepcopy(media_origin(snapshot,media))
    data=media.get('portable_lineage',{})
    links=[]
    for link in data.get('links',[]):
        ref=link['reference']
        if link['state']=='included':
            target=save(ref['version'])
            exact=next(m for m in target['snapshot']['media'] if m['id']==ref['media'] and m['hash']==ref['hash'])
            links.append(dict(state='mapped',relation=link['relation'],reference=dict(asset=target['id'],version=target['snapshot']['id'],media=exact['id'],hash=exact['hash'])))
        else:links.append(dict(state='outside',relation=link['relation']))
    return dict(type='portable_pack',pack_hash=pack_hash,original_asset=snapshot.get('asset_id'),original_version=snapshot['id'],
                records=raw,pack_lineage_version=1 if data.get('version')==1 else None,pack_links=links,pack_lineage_incomplete=data.get('incomplete',False))
