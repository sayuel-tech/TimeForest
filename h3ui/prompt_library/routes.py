"""Prompt library API. This blueprint has no generation side effects."""
import tempfile
import sqlite3
from pathlib import Path
from flask import Blueprint, current_app, jsonify, request, send_file
from ..studio_store import Conflict
from .store import PURPOSES

bp=Blueprint('prompt_library',__name__,url_prefix='/api/v5/prompt-library')
def service(): return current_app.config['PROMPT_LIBRARY']

@bp.errorhandler(ValueError)
@bp.errorhandler(KeyError)
@bp.errorhandler(OSError)
@bp.errorhandler(sqlite3.Error)
def error(exc):
    return jsonify(error=str(exc),error_raw=str(exc),code='REVISION_CONFLICT' if isinstance(exc,Conflict) else 'PROMPT_LIBRARY_ERROR'),409 if isinstance(exc,Conflict) else 404 if isinstance(exc,KeyError) else 400

@bp.get('/catalog')
def catalog():
    return jsonify(prompt_library_version=1,purposes=PURPOSES,branches=service().store.branches(),content_types=['text','fields'])

@bp.post('/identify')
def identify():
    d=request.get_json();return jsonify(service().family(d.get('model'),d.get('purpose')))

@bp.post('/model-branches')
def branch_create(): return jsonify(service().store.branch(request.get_json()))

@bp.post('/model-branches/<ident>')
def branch_edit(ident):
    data=request.get_json()
    branch=next((b for b in service().store.branches() if b['id']==ident),None)
    if data.get('removed') and branch and any(m.get('purpose')==branch['purpose'] and m.get('family')==branch['family'] for m in service().cfg.get('prompt_model_families',[])):
        raise ValueError('此家族仍被工作流模型来源配置使用，请先调整对应配置')
    return jsonify(service().store.branch(data,ident))

@bp.get('/entries')
def entries():
    result=service().store.list(request.args)
    result['items']=[public(row) for row in result['items']]
    return jsonify(result)

@bp.post('/entries')
def create(): return jsonify(public(service().store.save(request.get_json())))

@bp.post('/favorite-current')
def favorite_current():
    row=service().store.favorite_current(request.get_json())
    return jsonify(entry=public(row) if row else None)

@bp.get('/entries/<ident>')
def get(ident): return jsonify(public(service().store.get(ident)))

@bp.post('/entries/<ident>')
def edit(ident): return jsonify(public(service().store.save(request.get_json(),ident)))

@bp.get('/entries/<ident>/versions')
def versions(ident): return jsonify(items=service().store.versions(ident))

@bp.get('/entries/<ident>/versions/<int:version>')
def version(ident,version): return jsonify(public(service().store.get(ident,version)))

@bp.get('/pending/<pid>')
def pending(pid): return jsonify(items=service().pending(pid))

@bp.post('/receipts/<token>/retry')
def retry(token): return jsonify(service().retry(token))

@bp.get('/backup')
def backup():
    handle=tempfile.NamedTemporaryFile(suffix='.sqlite3',delete=False);handle.close()
    service().store.backup(handle.name)
    # Windows cannot unlink a file while send_file still holds it. Send bytes then clean.
    import io
    blob=Path(handle.name).read_bytes();Path(handle.name).unlink()
    return send_file(io.BytesIO(blob),as_attachment=True,download_name='TimeForest-Prompts.sqlite3',mimetype='application/vnd.sqlite3')

@bp.post('/check-tags')
def check_tags():
    from .validation import warnings
    d=request.get_json()
    return jsonify(warnings=warnings(str(d.get('text','')),d.get('rows',[]),d.get('segment'),d.get('recipe')))

@bp.post('/check-assembly/<pid>')
def check_assembly(pid):
    from ..studio_inputs import inventory
    from .validation import warnings
    assembly=current_app.config['VIDEO_ASSEMBLY'];p=assembly.get(pid);d=request.get_json();_,e=assembly.find_extension(p,d['extension'])
    e={**e,'references':d.get('references',e.get('references',[]))}
    assets=assembly.reference_assets(p,e,verify=False)
    rows=inventory(dict(mode='image_story'),{},assets)
    return jsonify(warnings=warnings(str(d.get('text','')),rows,recipe=e.get('recipe')))

@bp.get('/records/<pid>')
def records(pid):
    from .records import project_records
    return jsonify(items=project_records(current_app.config,pid,request.args))

@bp.get('/asset-records/<aid>')
def asset_records(aid):
    from .records import asset_records as read
    return jsonify(items=read(current_app.config,aid,request.args.get('version'),request.args.get('media')))


def public(row):
    from ..asset_library.origins import AssetOrigins
    from urllib.parse import urlencode
    source=row.get('source') or {}
    if source.get('project') and not source.get('external'):
        resolver=AssetOrigins(current_app.config['ASSET_LIBRARY'],current_app.config['STUDIO'],current_app.config.get('IMAGE_STUDIO'))
        project=resolver.project(source['project'],source.get('project_name'))
        if project and project.get('state')=='available':
            target={k:source[k] for k in ('run','output','task','segment') if source.get(k)}
            if source.get('candidate') and 'run' not in target: target['run']=source['candidate']
            if not target and source.get('target') and source['target']!='project':
                if source.get('mode')=='image_assets':target['task']=source['target']
                elif source.get('mode')!='video_assembly':target['segment']=source['target']
            if target:project['url']+='?'+urlencode({'origin_'+k:v for k,v in target.items()})
        row={**row,'source_project':project}
    return row
