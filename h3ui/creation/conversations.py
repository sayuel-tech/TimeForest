"""Object-scoped writing drafts in the existing project document."""
import copy
import json
from .contracts import digest, validate, read
from ..studio_store import Conflict


def scope(layer, targets):
    return layer + ':' + ','.join(targets)


def save(creation, pid, data):
    validate(data, read('API契约/save-conversation.schema.json'))
    def change(p):
        creation.get(pid,'authoring')
        targets=data['target_ids'];key=scope(data['layer'],targets)
        if targets:
            ids={x['ref'] for name,array in [('storyboard','shots'),('segment','segments')] for x in (creation.layer(p,name) or {}).get('content',{}).get(array,[])}
            if set(targets)-ids:raise ValueError('沟通对象不存在，请返回目录选择')
        records=p.setdefault('writing_drafts',{})
        if (digest(records[key]) if key in records else None)!=data['base_hash']:raise Conflict('此对象的沟通已在其他窗口更新，当前输入保留')
        candidate=data['draft']['basis_candidate_id']
        if candidate:
            found=next((c for c in p['candidates'] if c['candidate_id']==candidate and c['disposition']!='discarded'),None)
            job=next((j for j in p['creation_jobs'] if found and j['job_id']==found['job_id']),None)
            if not job or scope(job['context']['target']['layer'],job['context']['target']['target_ids'])!=key:raise ValueError('续写依据不属于当前对象')
        edited=data['draft'].get('edited_candidate')
        if edited:
            found=next((c for c in p['candidates'] if c['candidate_id']==edited.get('id') and c['disposition']!='discarded'),None)
            job=next((j for j in p['creation_jobs'] if found and j['job_id']==found['job_id']),None)
            if not job or scope(job['context']['target']['layer'],job['context']['target']['target_ids'])!=key:raise ValueError('编辑的输出不属于当前对象')
            if not isinstance(edited.get('payload'),dict):raise ValueError('输出草稿格式不正确')
        records[key]=copy.deepcopy(data['draft'])
        return [key],{}
    return creation.mutate(pid,data,change)


def materials(p, layer, targets):
    """Immutable recent rounds and an explicitly selected output, never another scope."""
    key=scope(layer,targets);draft=p.get('writing_drafts',{}).get(key,{})
    jobs=[j for j in p.get('creation_jobs',[]) if scope(j['context']['target']['layer'],j['context']['target']['target_ids'])==key]
    result=[]
    for job in jobs[-4:]:
        candidates=[c for c in p['candidates'] if c['job_id']==job['job_id'] and c['disposition']!='discarded']
        for candidate in candidates:
            result.append(dict(reference_key='round:'+candidate['candidate_id'],kind='text',media=None,
                content=json.dumps(dict(request=job['context']['user_instruction'],output=candidate['payload']),ensure_ascii=False)))
    candidate=next((c for c in p['candidates'] if c['candidate_id']==draft.get('basis_candidate_id') and c['disposition']!='discarded'),None)
    if candidate:
        edited=draft.get('edited_candidate') or {}
        payload=edited['payload'] if edited.get('id')==candidate['candidate_id'] else candidate['payload']
        result.append(dict(reference_key='basis:'+candidate['candidate_id'],kind='text',media=None,content=json.dumps(payload,ensure_ascii=False)))
    return result
