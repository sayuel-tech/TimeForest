"""One authoritative resolver shared by writing and movie input preparation."""
import copy


def references(project, bindings):
    """Resolve the exact role-specific reference, with a legacy fixed-version fallback."""
    result=[]
    for binding in bindings:
        if binding['state']!='bound':continue
        reference=next((r for r in project.get('creation_references',[]) if
            (r['id']==binding['reference_id'] if binding.get('reference_id') else
             r['library_reference']['asset']==binding['asset_ref'] and r['library_reference']['version']==binding['asset_version'])),None)
        if not reference:raise ValueError('已绑定的资产缺少对应素材引用，请在来源卡片重新选择')
        if reference not in result:result.append(copy.deepcopy(reference))
    return result


def resolve(creation, project, target_id=None):
    data=(creation.layer(project,'asset_bindings') or {}).get('content',{})
    segments=(creation.layer(project,'segment') or {}).get('content',{}).get('segments',[])
    segment=next((s for s in segments if s['ref']==target_id),None)
    shot=segment['shot_ref'] if segment else target_id
    chain=[('project',project['id'])]+([('shot',shot)] if shot else [])+([('segment',target_id)] if segment else [])
    policies=data.get('policies',{});result=[]
    for need in data.get('needs',[]):
        selected=None;project_binding=None
        for kind,identity in chain:
            policy=policies.get(identity,'parent')
            if kind!='project':
                if policy=='project':selected=project_binding
                elif policy=='independent':selected=None
            binding=next((b for b in data.get('bindings',[]) if b['need_ref']==need['ref'] and b['scope_kind']==kind and identity in b['scope_ids']),None)
            if binding:
                if binding.get('source')=='project':selected=project_binding
                elif binding['state']!='inherit':selected=binding
            if kind=='project':project_binding=selected
        value=copy.deepcopy(selected) if selected else dict(need_ref=need['ref'],state='pending',scope_kind='project',scope_ids=[])
        result.append(value)
    return result
