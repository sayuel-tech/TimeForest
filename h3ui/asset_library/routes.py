"""Local-only asset API. Mutations use revisions and recorded identifiers."""
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file

from ..studio_store import Conflict

bp = Blueprint('asset_library', __name__, url_prefix='/api/v5/library')


@bp.get('/maintenance-guide')
def maintenance_guide():
    from ..config import ROOT
    return send_file(ROOT / 'docs' / 'asset-library-maintenance.md', as_attachment=True)


def library():
    return current_app.config['ASSET_LIBRARY']


@bp.errorhandler(ValueError)
def invalid(exc):
    return jsonify(error=str(exc)), 409 if isinstance(exc, Conflict) else 400


@bp.errorhandler(KeyError)
def missing(exc):
    return jsonify(error=str(exc)), 404


@bp.errorhandler(OSError)
def disk_error(exc):
    return jsonify(error='本地文件操作失败，请检查目录权限、可用空间或原件是否存在：' + str(exc)), 400


@bp.errorhandler(Exception)
def unexpected(exc):
    return jsonify(error='资产操作未完成：' + str(exc)), 400


@bp.get('/catalog')
def catalog():
    return jsonify(**library().store.catalog(), storage=library().storage())


@bp.get('/assets')
def assets():
    return jsonify(library().query(request.args))


@bp.get('/assets/<aid>')
def detail(aid):
    lib = library()
    with lib.store.connect() as db:
        refs = [dict(r) for r in db.execute('SELECT project,version FROM refs WHERE asset=? GROUP BY project,version', (aid,))]
    return jsonify(**lib.public(lib.store.get(aid, request.args.get('version'))), versions=lib.store.versions(aid), references=refs)


@bp.post('/uploads')
def upload():
    import json
    lib = library()
    file = request.files.get('file')
    if not file:
        raise ValueError('请选择文件')
    path = lib.stage(file.stream, file.filename)
    try:
        return jsonify(lib.ingest(path, request.form.get('name') or Path(file.filename).stem,
                                   metadata=json.loads(request.form.get('metadata', '{}')),
                                   key=request.form.get('key'), aid=request.form.get('asset') or None,
                                   revision=int(request.form['revision']) if request.form.get('asset') else None))
    finally:
        path.unlink(missing_ok=True)


@bp.patch('/assets/<aid>')
def update(aid):
    data = request.get_json()
    return jsonify(library().update(aid, data['revision'], data['changes']))


@bp.post('/assets/<aid>/trash')
def trash(aid):
    data = request.get_json()
    lib = library()
    return jsonify(lib.public(lib.store.trash(aid, data['revision'], bool(data.get('restore')))))


@bp.get('/media/<sha>')
def original(sha):
    lib = library()
    obj = lib.store.object(sha)
    return send_file(lib.store.path(obj['path']), mimetype=obj['mime'], conditional=True,
                     as_attachment=request.args.get('download') == '1', download_name=sha + obj['extension'])


@bp.get('/media/<sha>/preview')
def preview(sha):
    lib = library()
    lib.store.object(sha)
    return send_file(lib.store.path(f'previews/{sha}/cover.png'), mimetype='image/png', conditional=True)


@bp.post('/categories')
def categories():
    data = request.get_json()
    return jsonify(library().store.category(data.get('name'), data.get('id'), data.get('move_to'), bool(data.get('delete'))))


@bp.post('/collections')
def collections():
    data = request.get_json()
    return jsonify(library().store.collection(data['name'], data.get('description', ''), data.get('id'), data.get('revision'), data.get('items')))


@bp.get('/collections/<cid>')
def collection(cid):
    lib = library()
    row = next((x for x in lib.store.catalog()['collections'] if x['id'] == cid), None)
    if not row:
        raise KeyError('合集不存在')
    return jsonify(**row, items=lib.store.collection_items(cid))


@bp.post('/backup')
def backup():
    return jsonify(library().tasks.submit('backup', {}, request.get_json(silent=True).get('key') if request.is_json else None))


@bp.get('/tasks')
def tasks():
    return jsonify(items=library().tasks.list())


@bp.get('/tasks/<tid>')
def task(tid):
    return jsonify(library().tasks.get(tid))


@bp.post('/tasks/<tid>/retry')
def retry(tid):
    return jsonify(library().tasks.retry(tid))


@bp.post('/upload-sessions')
def start_upload():
    data = request.get_json()
    return jsonify(library().uploads.start(data['name'], data['size'], data.get('metadata'), data.get('asset'), data.get('revision')))


@bp.get('/upload-sessions/<token>')
def upload_status(token):
    return jsonify(library().uploads.status(token))


@bp.put('/upload-sessions/<token>')
def chunk(token):
    return jsonify(library().uploads.append(token, request.args.get('offset', 0), request.stream, request.content_length))


@bp.post('/upload-sessions/<token>/complete')
def complete_upload(token):
    return jsonify(library().uploads.complete(token))


@bp.get('/assets/<aid>/bindings')
def bindings(aid):
    from .bindings import expand
    return jsonify(expand(library(), aid, request.args.get('version'), request.args.get('owner')))


@bp.post('/projects/<pid>/use-plan')
def use_plan(pid):
    return jsonify(library().project_import.plan(pid, request.get_json()))


@bp.post('/projects/<pid>/use-apply')
def use_apply(pid):
    data = request.get_json()
    return jsonify(library().tasks.submit('project_apply', {'project': pid, 'token': data['token']}, 'asset-use:' + data['token']))


@bp.post('/derive')
def derive_media():
    from .store import uid
    data = request.get_json()
    # Construct server-owned task identifiers, never interpret client strings as staging paths.
    data['operation_id'] = uid()
    return jsonify(library().tasks.submit('derive', data))


@bp.get('/projects/<pid>/outputs')
def project_outputs(pid):
    return jsonify(items=library().results.outputs(pid))


@bp.post('/project-results')
def import_project_result():
    data = request.get_json()
    return jsonify(library().tasks.submit('project_result', data, 'result-task:' + data['output']))


@bp.post('/scan')
def scan_directory():
    return jsonify(library().tasks.submit('scan', request.get_json()))


@bp.post('/scan-import')
def scan_import():
    data = request.get_json()
    return jsonify(library().tasks.submit('scan_import', data, 'scan-task:' + data['file']))


@bp.post('/pack-plan')
def pack_plan():
    return jsonify(library().packs.preview(request.get_json()))


@bp.post('/pack-export')
def pack_export():
    data = request.get_json()
    return jsonify(library().tasks.submit('pack', {'token':data['token']}, 'pack-export:' + data['token']))


@bp.get('/packs/<token>')
def pack_download(token):
    import re
    if not re.fullmatch('[a-f0-9]{32}',token):raise ValueError('素材包ID不合法')
    return send_file(library().store.path('exports/'+token+'.zip'),as_attachment=True,download_name='时间森林素材包.zip')


@bp.post('/pack-upload')
def pack_upload():
    if 'file' not in request.files:raise ValueError('请选择素材包')
    return jsonify(library().packs.stage(request.files['file'].stream))


@bp.post('/pack-import')
def pack_import():
    data=request.get_json()
    return jsonify(library().tasks.submit('pack_import', {'token':data['token']}, 'pack-import:'+data['token']))
