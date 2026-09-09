from flask import Blueprint, current_app, jsonify, request
from ..studio_store import Conflict
from .contracts import loads
from .presentation import job as public_job,prepared as public_prepared,dto

bp=Blueprint('creation',__name__,url_prefix='/api/v5')


def service(): return current_app.config['CREATION']
def body(): return loads(request.get_data(as_text=True))


@bp.errorhandler(Exception)
def error(exc):
    code=getattr(exc,'code',None) or ('REVISION_CONFLICT' if isinstance(exc,Conflict) else 'INVALID_REQUEST')
    return jsonify(error=str(exc),error_raw=str(exc),error_kind='conflict' if isinstance(exc,Conflict) else 'provider' if getattr(exc,'code',None) else 'input',
                   code=code,field_errors=[],retryable=False,request_id=''),409 if isinstance(exc,Conflict) else 404 if isinstance(exc,KeyError) else 400


@bp.post('/authoring/projects')
def create_authoring(): return jsonify(service().create('authoring',body()))


@bp.post('/movie/projects')
def create_movie(): return jsonify(service().create('movie',body()))


@bp.get('/authoring/projects/<pid>')
def read_authoring(pid): return jsonify(service().snapshot(pid))


@bp.get('/movie/projects/<pid>')
def read_movie(pid): return jsonify(service().snapshot(pid))


@bp.post('/authoring/projects/<pid>/save')
def save(pid): return jsonify(service().save(pid,body()))


@bp.post('/authoring/projects/<pid>/conversation')
def save_conversation(pid):
    from .conversations import save
    return jsonify(save(service(),pid,body()))


@bp.post('/authoring/projects/<pid>/confirm')
def confirm(pid): return jsonify(service().confirm(pid,body()))


@bp.post('/authoring/projects/<pid>/references')
def import_reference(pid):return jsonify(service().references.attach(pid,body()))

@bp.post('/authoring/projects/<pid>/references/remove')
def remove_reference(pid):return jsonify(service().references.remove(pid,body()))


@bp.post('/authoring/projects/<pid>/image-handoffs')
def image_handoff(pid):return jsonify(service().handoffs.create(pid,body()))


@bp.post('/authoring/projects/<pid>/image-bind/preflight')
def image_bind_preview(pid):return jsonify(service().handoffs.preview(pid,body()))


@bp.post('/authoring/projects/<pid>/image-bind/apply')
def image_bind_apply(pid):return jsonify(service().handoffs.apply(pid,body()))


@bp.get('/authoring/providers')
def providers(): return jsonify(items=service().writing.providers.list())


@bp.post('/authoring/providers/save')
def save_provider(): return jsonify(service().writing.providers.save(body()))


@bp.post('/authoring/providers/credential')
def credential(): return jsonify(service().writing.providers.credential(body()))


@bp.post('/authoring/providers/credential/remove')
def remove_credential(): return jsonify(service().writing.providers.credential(body(),True))


@bp.post('/authoring/providers/discover')
def discover():
    from .contracts import request_contract
    data=body();request_contract('DiscoverProvider',data);p=service().writing.providers
    result=p.send(p.get(data['config_id']),resource='models')
    return jsonify(contract_version=1,capabilities=dict(models=result.get('data',[])),configuration_gaps=[])


@bp.post('/authoring/projects/<pid>/context')
def request_context(pid):
    data=body()
    return jsonify(service().writing.context(pid,data['task_type'],data.get('target_ids'),data.get('instruction',''),data.get('prompt_mode'),data.get('layer'),data.get('include_images',False)))


@bp.post('/authoring/jobs/preflight')
def writing_preflight(): return jsonify(service().writing.preflight(body())[0])


@bp.post('/authoring/jobs')
def writing_start(): return jsonify(public_job(service().writing.start(body())))


@bp.post('/authoring/jobs/repair')
def repair_candidate():return jsonify(public_job(service().writing.repair(body())))


@bp.get('/authoring/jobs/<jid>')
def writing_job(jid): return jsonify(public_job(service().writing.find(jid,'creation_jobs')[1]))


@bp.get('/authoring/jobs/<jid>/events')
def writing_events(jid):
    job=service().writing.find(jid,'creation_jobs')[1]
    return jsonify(contract_version='tf-authoring/2.9',job_id=jid,event_seq=job['event_seq'],event_type='state',state=job['state'],phase=job['phase'],message=job.get('error') or job['phase'],candidate_ids=job['candidate_ids'])


@bp.get('/authoring/jobs/<jid>/response')
def writing_response(jid):
    p,job=service().writing.find(jid,'creation_jobs')
    if not job.get('result_ref'):raise KeyError('尚无最终响应')
    return jsonify(dto('ResponseArtifact',p['artifacts'][job['result_ref']['id'] if isinstance(job['result_ref'],dict) else job['result_ref']]))


@bp.post('/authoring/jobs/<jid>/cancel')
def writing_cancel(jid):
    from .contracts import request_contract
    data=body();request_contract('CancelJob',data)
    if data['job_id']!=jid:raise ValueError('任务归属不一致')
    return jsonify(public_job(service().writing.cancel(jid)))


@bp.get('/authoring/candidates/<cid>')
def candidate(cid): return jsonify(dto('Candidate',service().writing.find(cid,'candidates')[1]))


@bp.post('/authoring/projects/<pid>/candidates/apply')
def apply_candidate(pid): return jsonify(service().writing.apply(pid,body()))


@bp.post('/authoring/projects/<pid>/candidates/discard')
def discard_candidate(pid):
    from .contracts import request_contract
    data=body();request_contract('DiscardCandidate',data)
    def change(p):
        c=next(x for x in p['candidates'] if x['candidate_id']==data['candidate_id'])
        if c['disposition']=='applied':raise Conflict('已应用的制作记录保留，请移除未采用的候选')
        import time
        c['disposition']='discarded';c['removed_at']=time.time();return [c['candidate_id']],{}
    return jsonify(service().mutate(pid,data,change))


@bp.get('/movie/catalog')
def movie_catalog():return jsonify(service().movie.catalog())

@bp.get('/authoring/projects/<pid>/segments/<sid>/prompt-preview')
def authoring_prompt_preview(pid,sid):return jsonify(service().movie.authoring_preview(pid,sid))


@bp.post('/movie/projects/<pid>/sync/preview')
def movie_sync_preview(pid):return jsonify(service().movie.sync_preview(pid,body()))


@bp.post('/movie/projects/<pid>/sync/apply')
def movie_sync_apply(pid):return jsonify(service().movie.sync_apply(pid,body()))


@bp.post('/movie/projects/<pid>/generation-draft')
def movie_draft(pid):return jsonify(service().movie.save_draft(pid,body()))


@bp.post('/movie/projects/<pid>/preflight')
def movie_preflight(pid):return jsonify(service().movie.execution.preflight(pid,body())[0])


@bp.post('/movie/projects/<pid>/prepare')
def movie_prepare(pid):return jsonify(public_prepared(service().movie.execution.prepare(pid,body())))


@bp.post('/movie/projects/<pid>/generate')
def movie_generate(pid):return jsonify(public_job(service().movie.execution.submit(pid,body())))


@bp.get('/movie/projects/<pid>/segments/<sid>/takes')
def movie_takes(pid,sid):
    p=service().get(pid,'movie');service().movie.frozen(p,sid)
    return jsonify(items=[t for t in p.get('movie_takes',[]) if t['movie_segment_id']==sid])


@bp.post('/movie/projects/<pid>/adopt')
def movie_adopt(pid):return jsonify(service().movie.adopt(pid,body()))


@bp.get('/movie/jobs/<jid>')
def movie_job(jid):
    p,j=service().writing.find(jid,'creation_jobs')
    if p['mode']!='movie':raise ValueError('任务类型不匹配')
    return jsonify(public_job(j))


@bp.get('/movie/jobs/<jid>/events')
def movie_events(jid):return writing_events(jid)


@bp.post('/movie/jobs/<jid>/cancel')
def movie_cancel(jid):
    from .contracts import request_contract
    data=body();request_contract('CancelJob',data)
    if data['job_id']!=jid:raise ValueError('任务归属不一致')
    return jsonify(public_job(service().movie.execution.cancel(jid)))


@bp.post('/movie/projects/<pid>/edit/initialize')
def initialize_edit(pid):return jsonify(service().movie.initialize_edit(pid,body()))


@bp.get('/movie/projects/<pid>/edit')
def read_edit(pid):
    from .contracts import digest
    p=service().get(pid,'movie');return jsonify(edit=p['content']['edit'],content_hash=digest(p['content']['edit']))


@bp.post('/movie/projects/<pid>/edit/save')
def save_edit(pid):return jsonify(service().movie.save_edit(pid,body()))


@bp.post('/movie/projects/<pid>/edit/updates')
def edit_updates(pid):return jsonify(service().movie.edit_updates(pid,body()))


@bp.post('/movie/projects/<pid>/edit/updates/apply')
def apply_updates(pid):return jsonify(service().movie.apply_updates(pid,body()))


@bp.post('/movie/projects/<pid>/export/preflight')
def export_preflight(pid):return jsonify(service().movie.execution.export_preflight(pid,body()))


@bp.post('/movie/projects/<pid>/exports')
def export_movie(pid):return jsonify(public_job(service().movie.execution.export(pid,body())))


@bp.get('/movie/projects/<pid>/exports/<eid>')
def read_export(pid,eid):
    p=service().get(pid,'movie');return jsonify(next(e for e in p.get('movie_exports',[]) if e['export_id']==eid))


@bp.get('/movie/projects/<pid>/prepared/<rid>')
def read_prepared(pid,rid):
    p=service().get(pid,'movie');return jsonify(public_prepared(next(r for r in p.get('movie_prepared',[]) if r['prepared_request_id']==rid)))


@bp.get('/movie/projects/<pid>/input-contracts/<cid>')
def read_contract(pid,cid):
    p=service().get(pid,'movie')
    return jsonify(next(a['input_contract'] for a in p['artifacts'].values() if isinstance(a,dict) and a.get('input_contract',{}).get('input_contract_id')==cid))


@bp.get('/movie/projects/<pid>/takes/<tid>/source')
def take_source(pid,tid):return jsonify(service().movie.source_view(pid,tid))


@bp.get('/movie/projects/<pid>/edit/items/<iid>/source')
def item_source(pid,iid):
    p=service().get(pid,'movie');item=next(i for i in p['content']['edit']['items'] if i['id']==iid)
    return jsonify(service().movie.source_view(pid,item['take_id']))


@bp.post('/movie/projects/<pid>/ingest')
def ingest_movie(pid):return jsonify(service().movie.ingest(pid,body()))
