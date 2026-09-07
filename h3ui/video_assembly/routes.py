from flask import Blueprint, current_app, jsonify, request
from ..studio_store import Conflict
from .compiler import catalog

bp=Blueprint('video_assembly',__name__,url_prefix='/api/v5/assembly')


def service(): return current_app.config['VIDEO_ASSEMBLY']


@bp.errorhandler(Exception)
def error(exc):
    return jsonify(error=str(exc),error_raw=str(exc),error_kind='conflict' if isinstance(exc,Conflict) else 'input' if isinstance(exc,ValueError) else 'website',code='REVISION_CONFLICT' if isinstance(exc,Conflict) else 'INVALID_REQUEST'),409 if isinstance(exc,Conflict) else 404 if isinstance(exc,KeyError) else 400


@bp.get('/catalog')
def directory(): return jsonify(catalog(service().st.recipes))


@bp.post('/catalog/refresh')
def refresh(): return jsonify(catalog(service().st.recipes))


@bp.post('/<pid>/save')
def save(pid): return jsonify(service().save(pid,request.get_json()))


@bp.post('/<pid>/import')
def import_video(pid):
    if request.is_json:
        data=request.get_json();return jsonify(service().import_video(pid,data['revision'],reference=data['reference']))
    return jsonify(service().import_video(pid,int(request.form['revision']),upload=request.files['file']))


@bp.post('/<pid>/extensions')
def extension(pid): return jsonify(service().add_extension(pid,request.get_json()))


@bp.post('/<pid>/visibility')
def visibility(pid): return jsonify(service().visibility(pid,request.get_json()))


@bp.post('/<pid>/select')
def select(pid): return jsonify(service().select(pid,request.get_json()))


@bp.get('/<pid>/preflight/<eid>')
def preflight(pid,eid): return jsonify(service().preflight(pid,eid))


@bp.post('/<pid>/generate')
def generate(pid): return jsonify(service().start(pid,request.get_json(),'generate'))


@bp.post('/<pid>/export')
def export(pid): return jsonify(service().start(pid,request.get_json(),'export'))


@bp.post('/<pid>/control')
def control(pid):
    data=request.get_json()
    if data.get('confirmed') is not True: raise ValueError('请确认操作范围')
    service().control(pid,data['run'],data['action']);return jsonify(service().snapshot(pid))


@bp.post('/<pid>/ingest')
def ingest(pid): return jsonify(service().ingest(pid,request.get_json()))


@bp.post('/<pid>/references')
def reference(pid):
    data=request.get_json() if request.is_json else request.form.to_dict()
    return jsonify(service().import_reference(pid,data,upload=request.files.get('file')))
