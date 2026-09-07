"""Image-only actions; shared project directory routes remain in studio.py."""
from flask import Blueprint,current_app,jsonify,request
from . import compiler
from ..studio_store import Conflict
from .runner import error_fields

bp=Blueprint('image_studio',__name__,url_prefix='/api/v5/image-projects')
def service():return current_app.config['IMAGE_STUDIO']

@bp.errorhandler(Exception)
def error(exc):
    detail=error_fields(exc)
    return jsonify(error=detail.pop('note'), **detail),409 if isinstance(exc,Conflict) else 404 if isinstance(exc,KeyError) else 400

@bp.get('/catalog')
def catalog():return jsonify(service().catalog())

@bp.post('/catalog/sync')
def sync():return jsonify(service().catalog(sync=True))

@bp.post('/<pid>/change-plan')
def plan(pid):return jsonify(service().plan(pid,request.get_json()))

@bp.post('/<pid>/apply')
def apply(pid):
    service().store.apply(pid,request.get_json()['token'])
    return jsonify(service().snapshot(pid))

@bp.post('/<pid>/inputs')
def upload(pid):return jsonify(service().upload(pid,request.files['file'],request.form.get('source')))

@bp.post('/<pid>/library-input')
def library_input(pid):return jsonify(service().library_input(pid,request.get_json()))

@bp.post('/<pid>/geometry')
def geometry(pid):
    data=request.get_json();s=service();s.store.project(pid)
    if data['submode']=='text':return jsonify(compiler.geometry('text',0,0,data.get('settings')))
    image=s.store.get('inputs',data['A'],pid)
    return jsonify(compiler.geometry(data['submode'],image['width'],image['height'],data.get('settings')))

@bp.get('/<pid>/tasks/<tid>/preflight')
def preflight(pid,tid):return jsonify(service().preflight(pid,tid))

@bp.post('/<pid>/tasks/<tid>/generate')
def generate(pid,tid):
    data=request.get_json()
    return jsonify(service().runner.submit(pid,tid,data['revision'],data.get('key')))

@bp.post('/<pid>/tasks/<tid>/discard')
def discard_task(pid,tid):
    s=service();data=request.get_json() or {}
    return jsonify(s.st.jobs.run_inline('image_task_discard',pid,lambda:s.discard_task(pid,tid,data)))

@bp.post('/<pid>/runs/<rid>/cancel')
def cancel(pid,rid):return jsonify(service().runner.cancel(pid,rid))

@bp.post('/<pid>/runs/<rid>/reconcile')
def reconcile(pid,rid):
    s=service();s.store.get('runs',rid,pid)
    if s.cfg.get('studio_disable_generation'):raise ValueError('开发环境不连接生成引擎')
    s.runner.wake()
    return jsonify(ok=True)

@bp.post('/<pid>/outputs/<oid>/<action>')
def output(pid,oid,action):
    s=service();data=request.get_json() or {}
    if action=='select':return jsonify(s.select(pid,oid))
    if action=='continue':return jsonify(s.continue_output(pid,oid,data['revision']))
    if action=='library':return jsonify(s.ingest(pid,oid,data))
    raise ValueError('结果操作不支持')
