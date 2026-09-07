"""Local UI fixture: real static app and isolated image API choices.

Run from the repository with its existing Python environment:
  .venv/Scripts/python.exe tests/image_parameter_ui_fixture.py --port 5097 \
    --evidence-dir D:/<external-check-directory> --real-image-api

Only repo/static files are served. By default projects/transactions are synthetic.
--real-image-api uses the actual image blueprint, ImageStudio, temporary SQLite
and temporary filename-only model folders. It never calls the application factory.
The API log/state are written only into the explicitly supplied external folder.
No production config, database, model folder or ComfyUI is read/run.
GET /__fixture/state exposes the synthetic state and request counters.
POST /__fixture/control accepts refresh_error, save_error and run_error.
POST /__fixture/reset restores the initial synthetic state.
"""
import argparse
import copy
import hashlib
import io
import json
import mimetypes
import sys
import threading
import time
import tempfile
import uuid
from contextlib import ExitStack
from email.parser import BytesParser
from email.policy import default as email_policy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw
from h3ui.image_studio import compiler
from h3ui.image_studio.parameters import public_parameters
from h3ui.studio_capabilities import decorate_catalog
from h3ui.studio_recipes import RECIPES, PARAMETERS, defaults
from h3ui.studio_story import storyboard

PID = 'fixture-image'
STAMP = 1788739200
RAW_ERROR = ('KSampler node 26 / field sampler_name: fixture execution_error\n'
             'Value not in list: sampler_name=fixture-invalid\n'
             '<script>window.fixtureUnsafe=true</script>')

CONTROL_PAGE = '''<!doctype html><meta charset="utf-8"><title>隔离检查控制</title>
<h1>图片参数隔离检查</h1><p>本页仅控制内存模拟 API；真实工作区使用仓库当前静态页面。</p>
<nav><a href="/#/p/fixture-image">图片工作区</a> · <a href="/#/p/fixture-swap">换人对照</a> ·
<a href="/#/p/fixture-image-story">参考图对照</a> · <a href="/#/p/fixture-text-story">文生对照</a></nav>
<p><button data-control="refresh_error" data-value="true">启用模型刷新失败</button>
<button data-control="refresh_error" data-value="false">恢复模型刷新</button>
<button data-control="save_error" data-value="true">启用保存失败</button>
<button data-control="save_error" data-value="false">恢复保存</button></p>
<p><button data-control="run_error" data-value="true">显示模拟运行原始错误</button>
<button data-control="run_error" data-value="false">恢复预置成功运行</button>
<button id="reset">重置全部隔离草稿</button><button id="reload">读取状态</button></p>
<pre id="state"></pre><script>
async function show(){const state=await (await fetch('/__fixture/state')).json();
document.querySelector('#state').textContent=JSON.stringify(state,null,2);}
document.querySelectorAll('[data-control]').forEach(button=>button.onclick=async()=>{
await fetch('/__fixture/control',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({[button.dataset.control]:button.dataset.value==='true'})});await show();});
document.querySelector('#reset').onclick=async()=>{await fetch('/__fixture/reset',{method:'POST'});await show();};
document.querySelector('#reload').onclick=show;show();</script>'''


def picture(color, variant=False, mask=False):
    image = Image.new('L' if mask else 'RGB', (720, 960), 0 if mask else color)
    draw = ImageDraw.Draw(image)
    if mask:
        draw.ellipse((170, 230, 550, 760), fill=255)
    else:
        draw.rectangle((0, 650, 720, 960), fill='#a7b29b')
        draw.polygon([(0, 650), (240, 240), (510, 650)], fill='#8eab9f')
        draw.ellipse((245, 130, 455, 340), fill='#dcbca0')
        draw.polygon([(245, 340), (455, 340), (545, 800), (175, 800)],
                     fill='#406a64' if variant else '#73819a')
        draw.text((28, 28), 'ISOLATED UI FIXTURE - SYNTHETIC MEDIA', fill='#304642')
    output = io.BytesIO()
    image.save(output, 'PNG')
    return output.getvalue()


def image_project():
    inputs = [dict(id=key, name=name, width=720, height=960, mask=key == 'mask',
                   url=f'/__fixture/media/{key}.png')
              for key, name in [('A', '隔离底图 A'), ('B', '隔离参考图 B'), ('mask', '隔离局部标注')]]
    tasks = [dict(id='task-' + mode, name=compiler.TOOLS[mode] + ' · 隔离任务',
                  project=PID, submode=mode, A=None if mode=='text' else 'A', B='B' if mode == 'dual' else None,
                  mask='mask' if mode == 'region' else None,
                  prompt='保留人物与画面构图，将服装改为深绿色。',
                  settings=copy.deepcopy(compiler.DEFAULTS), models=dict(compiler.MODELS))
             for mode in compiler.TOOLS]
    # A current selection absent from the synthetic local directory must survive refresh.
    tasks[0]['models']['unet'] = 'preserved/current-model-missing.safetensors'
    tasks[0]['settings']['seed'] = 0
    run = dict(id='fixture-run-zero', task=tasks[0]['id'], project=PID, state='success',
               seed=0, note='隔离预置候选；未生成', snapshot=copy.deepcopy(tasks[0]),
               created=STAMP, finished=STAMP + 1, prompt_id='fixture-prompt-zero')
    outputs = [dict(id=f'candidate-{i}', task=tasks[0]['id'], project=PID,
                    run=run['id'], url=f'/__fixture/media/candidate-{i}.png',
                    width=720, height=960, selected=False) for i in (1, 2)]
    return dict(id=PID, project=PID, kind='image', mode='image_assets',
                name='图片制作参数 · 隔离检查', revision=1, current_task=tasks[0]['id'],
                created=STAMP, updated=STAMP, image_contract_version=1, busy=False,
                tasks=tasks, inputs=inputs, runs=[run], outputs=outputs)


def video_project(mode):
    project_id = 'fixture-' + mode.replace('_', '-')
    segments = []
    for plan in storyboard(15):
        segments.append(dict(plan, id=project_id + '-shot', prompt='隔离视频草稿：人物在森林中转身。',
                             prompt_mode='structured', swap_prompt_mode='inherit', swap_custom_prompt='',
                             staging='', beats='', voice='', speaker_order='', soundscape='', music='',
                             ending='', assets=[], inherit_ids=[], asset_mode='auto', seed_mode='random',
                             seed='730001', last_seed=None, status='draft', attempts=[], selected=None,
                             resolved_assets=[], source_preview_url=None))
    return dict(id=project_id, name={'swap': '换人', 'image_story': '参考图', 'text_story': '文生'}[mode] + ' · 隔离参数对照',
                mode=mode, revision=1, created=STAMP, updated=STAMP, settings=defaults(),
                duration=15, timing_mode='natural', storyboard_version=1, input_contract_version=2,
                segments=segments, status='draft', review='manual', source_asset=None,
                source_ready=True, source_progress=None, export=None, changes=[], error=None,
                pause=False, busy=False, asset_library=[], runtime=None, saved_draft=None,
                input_prompt_version=2, swap_prompt=dict(mode='custom', custom='隔离换人指令。', version=3))


def video_catalog():
    data = dict(recipes=[dict(id=k, **r, defaults=defaults(k)) for k, r in RECIPES.items()],
                parameters=[dict(key=k, label=l, type=t, group=g, help=h) for k, l, t, g, h in PARAMETERS],
                models=list(dict.fromkeys(r['model'] for r in RECIPES.values())),
                loras=['fixture/video-lora.safetensors'], clips=[defaults()['clip']],
                vaes=[defaults()['video_vae'], defaults()['audio_vae']],
                samplers=['euler', 'res_multistep'], schedulers=['beta', 'simple'],
                local_models=dict(updated=STAMP, source='isolated fixture', errors=[]),
                swap_preparation_version=1, swap_template_version=3, asset_library_version=1,
                local_server_version=1, swap_prompt_modes=['template', 'custom'],
                asset_reference_modes=['auto', 'custom', 'none'], engine=dict(connected=False))
    return decorate_catalog(data, {})


class Fixture:
    def __init__(self, evidence):
        self.evidence = evidence
        self.pid = PID
        self.backend_mode = 'synthetic'
        self.lock = threading.RLock()
        self.calls = []
        self.generation_requests = 0
        self.reset()

    def reset(self):
        self.projects = {PID: image_project()}
        self.projects.update((p['id'], p) for p in map(video_project, ('swap', 'image_story', 'text_story')))
        self.plans = {}
        self.media = {'A.png': picture('#dce6dd'), 'B.png': picture('#e5d9c3', True),
                      'mask.png': picture('', mask=True), 'candidate-1.png': picture('#dce6dd', True),
                      'candidate-2.png': picture('#d6dee5', True)}
        self.controls = dict(refresh_error=False, save_error=False)
        self.refresh_count = 0

    def catalog(self):
        self.refresh_count += 1
        choices = {k: [v, 'fixture/extra-' + k + '.safetensors'] for k, v in compiler.MODELS.items()}
        result = dict(tools=compiler.TOOLS, defaults=compiler.DEFAULTS, models=compiler.MODELS,
                      choices=choices, checked=None, missing=None, source_hash=compiler.SOURCE_HASH,
                      plugin_version=compiler.PLUGIN_VERSION, generation_verified=False,
                      parameter_contract_version=1, text_to_image_version=1, parameters=public_parameters(),
                      local_models=dict(updated=STAMP + self.refresh_count, source='filesystem',
                                        errors=[], roots={key: ['fixture-only'] for key in ('models', 'clips', 'vaes', 'loras')},
                                        engine_url='http://127.0.0.1:1'),
                      node_catalog=dict(updated=None, source='none', error=None, engine_url='http://127.0.0.1:1'))
        return result

    def record(self, method, path, body, status):
        call = dict(method=method, path=path, body=body, status=status, time=time.time())
        self.calls.append(call)
        with (self.evidence / 'fixture-api.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(call, ensure_ascii=False) + '\n')
        (self.evidence / 'fixture-state.json').write_text(json.dumps(self.state(), ensure_ascii=False, indent=2), encoding='utf-8')

    def state(self):
        return dict(projects=self.projects, controls=self.controls, refresh_count=self.refresh_count,
                    generation_requests=self.generation_requests, calls=self.calls,
                    backend_mode=self.backend_mode)

    def close(self):
        pass

    def request(self, method, path, body):
        if path == '/__fixture/state' and method == 'GET':
            return 200, self.state()
        if path == '/__fixture/reset' and method == 'POST':
            self.reset()
            return 200, {'ok': True}
        if path == '/__fixture/control' and method == 'POST':
            self.controls.update({k: body[k] for k in self.controls if k in body})
            if 'run_error' in body:
                run = self.projects[PID]['runs'][0]
                run.update(state='failed' if body['run_error'] else 'success',
                           note='隔离执行失败' if body['run_error'] else '隔离预置候选；未生成',
                           error_kind='engine' if body['run_error'] else None,
                           error_raw=json.dumps(dict(status_str='error', messages=[['execution_error',
                               dict(exception_message=RAW_ERROR, node_id='26', node_type='KSampler',
                                    prompt_id='fixture-prompt-zero', field='sampler_name')]]), ensure_ascii=False)
                               if body['run_error'] else None)
            return 200, self.controls
        if any(part in path.split('/') for part in ('generate', 'prompt', 'run', 'run-all', 'prepare', 'assemble', 'launch', 'connect')):
            self.generation_requests += 1
            return 403, {'error': '隔离界面 fixture 禁止生成、准备、合成或引擎调用'}
        if path == '/api/v5/health':
            return 200, dict(local_server_version=1, comfy_connected=False, busy=False, image_assets_enabled=True)
        if path == '/api/v5/projects':
            return 200, dict(projects=list(self.projects.values()), image_assets_enabled=True)
        if path == '/api/v5/catalog' and method == 'GET':
            return 200, video_catalog()
        if path == '/api/v5/image-projects/catalog' and method == 'GET':
            if self.controls['refresh_error']:
                return 503, {'error': '隔离本地目录扫描失败：fixture-only / permission denied',
                             'error_kind': 'website',
                             'error_raw': 'fixture-only / PermissionError: directory access denied\nSource: filesystem fixture; no model files scanned'}
            return 200, self.catalog()
        if path == '/api/v5/image-projects/catalog/sync' and method == 'POST':
            return 503, {'error': '隔离节点同步失败：未连接 ComfyUI', 'error_kind': 'network',
                         'error_raw': 'ComfyUI request GET /object_info: fixture connection refusal (no request sent)'}
        parts = path.strip('/').split('/')
        if len(parts) >= 4 and parts[:2] == ['api', 'v5'] and parts[2] in ('projects', 'image-projects'):
            pid = parts[3]
            if pid not in self.projects:
                return 404, {'error': '未知隔离项目'}
            project = self.projects[pid]
            tail = parts[4:]
            if method == 'GET' and not tail:
                return 200, project
            if tail == ['geometry'] and method == 'POST':
                return 200, compiler.geometry(body['submode'], 720, 960, body['settings'])
            if tail == ['change-plan'] and method == 'POST':
                if self.controls['save_error']:
                    return 409, {'error': '隔离保存冲突：当前任务版本已变化，草稿保留', 'error_kind': 'conflict',
                                 'error_raw': 'Fixture revision conflict; synthetic stored revision unchanged'}
                if body['revision'] != project['revision']:
                    return 409, {'error': '隔离项目版本冲突'}
                if project.get('kind') == 'image':
                    for task in body['tasks']:
                        task['settings'] = compiler.settings(task['settings'])
                token = uuid.uuid4().hex
                self.plans[token] = (pid, copy.deepcopy(body))
                return 200, dict(token=token, summary=['隔离草稿变化'], needs_confirmation=False, segments=project.get('segments', []))
            if tail == ['apply'] and method == 'POST':
                plan = self.plans.pop(body['token'])
                if plan[0] != pid:
                    return 409, {'error': '隔离保存 token 与项目不符'}
                keys = ('name', 'current_task', 'tasks') if project.get('kind') == 'image' else ('name', 'settings', 'segments')
                project.update({k: copy.deepcopy(plan[1][k]) for k in keys if k in plan[1]})
                project['revision'] += 1
                return 200, project
            if tail == ['inputs'] and method == 'POST':
                key = 'uploaded-' + uuid.uuid4().hex
                payload = body.pop('_file_bytes')
                self.media[key + '.png'] = payload
                with Image.open(io.BytesIO(payload)) as image:
                    width, height = image.size
                record = dict(id=key, name=body.get('_filename', 'mask.png'), width=width, height=height,
                              mask=bool(body.get('source')), url=f'/__fixture/media/{key}.png')
                project['inputs'].append(record)
                return 200, record
            if len(tail) == 3 and tail[0] == 'outputs' and tail[2] == 'select':
                for out in project['outputs']:
                    if out['task'] == next(x['task'] for x in project['outputs'] if x['id'] == tail[1]):
                        out['selected'] = out['id'] == tail[1]
                return 200, project
            if len(tail) == 3 and tail[0] == 'outputs' and tail[2] == 'library':
                out = next(x for x in project['outputs'] if x['id'] == tail[1])
                out['library'] = dict(asset='fixture-asset', version='fixture-version')
                return 200, dict(id='fixture-asset', version='fixture-version', snapshot=dict(name=body.get('name', '隔离资产')))
            if len(tail) == 3 and tail[0] == 'tasks' and tail[2] == 'preflight':
                return 200, dict(ready=True, errors=[], note='仅隔离输入反馈，未调用真实预检')
        return 404, {'error': f'隔离 fixture 未实现此请求：{method} {path}'}


class RealImageFixture(Fixture):
    """Real image HTTP routes and persistence; synthetic media and video data only."""

    def __init__(self, evidence):
        from flask import Flask, jsonify, send_from_directory, request
        from h3ui.asset_library.service import Library
        from h3ui.comfy import ComfyError
        from h3ui.image_studio.routes import bp
        from h3ui.image_studio.service import ImageStudio
        from h3ui.image_studio.parameters import PARAMETER_CONTRACT_VERSION

        self.resources = ExitStack()
        self.engine_attempts = []
        self.real_api_calls = []
        self.temp_root = Path(self.resources.enter_context(
            tempfile.TemporaryDirectory(prefix='real-image-api-', dir=evidence))).resolve()
        cfg = dict(studio_data_dir=str(self.temp_root/'projects'),
                   asset_library_dir=str(self.temp_root/'library'),
                   comfy_base_dir=str(self.temp_root/'comfy'),
                   comfy_input_dir=str(self.temp_root/'comfy/input'),
                   comfy_output_dir=str(self.temp_root/'comfy/output'),
                   comfy_url='http://127.0.0.1:1', comfy_extra_model_paths=[],
                   studio_disable_generation=True, studio_auto_recover=False,
                   studio_progress_disabled=True, image_assets_enabled=True)
        self.fake_model_names = {}
        for role, folder in [('unet','diffusion_models'), ('clip','text_encoders'), ('vae','vae'), ('lora','loras')]:
            relative = Path('fixture')/('真实目录-' + role + '.safetensors')
            target = self.temp_root/'comfy/models'/folder/relative
            target.parent.mkdir(parents=True)
            target.write_bytes(b'filename-only fixture; not model weights')
            self.fake_model_names[role] = str(relative)

        def forbid_engine(endpoint, *args, **kwargs):
            self.engine_attempts.append(endpoint)
            raise ComfyError('ComfyUI request ' + endpoint + ': forbidden by isolated fixture; no network sent')

        context = SimpleNamespace(ctx={'cfg': cfg}, root=self.temp_root/'projects',
                                  comfy=SimpleNamespace(url=cfg['comfy_url'], _get=forbid_engine, _post=forbid_engine),
                                  jobs=SimpleNamespace(gpu_guards=[], is_busy=lambda *args: False))
        self.image_service = ImageStudio(context, Library(self.temp_root/'library', cfg))
        self.flask_app = Flask('timeforest_real_image_api_fixture', static_folder=None)
        self.flask_app.config['IMAGE_STUDIO'] = self.image_service
        self.flask_app.register_blueprint(bp)

        @self.flask_app.before_request
        def prevent_engine_routes():
            if self.forbidden(request.path):
                return jsonify(error='隔离环境禁止生成或引擎动作'), 403

        # Production bootstrap reads this shared endpoint; its payload is the real snapshot.
        @self.flask_app.get('/api/v5/projects/<pid>')
        def snapshot(pid):
            return jsonify(self.image_service.snapshot(pid))

        @self.flask_app.get('/api/v5/health')
        def health():
            return jsonify(local_server_version=1, comfy_connected=False, busy=False,
                           image_assets_enabled=True,
                           image_parameter_contract_version=PARAMETER_CONTRACT_VERSION)

        @self.flask_app.get('/api/v5/projects/<pid>/files/<path:subpath>')
        def file(pid, subpath):
            directory = self.image_service.store.directory(pid).resolve()
            target = (directory/subpath).resolve()
            if directory not in target.parents:
                return jsonify(error='隔离媒体路径越界'), 400
            return send_from_directory(directory, subpath)

        self.client = self.flask_app.test_client()
        try:
            super().__init__(evidence)
            self.backend_mode = 'real-image-blueprint'
        except BaseException:
            self.close()
            raise

    @staticmethod
    def forbidden(path):
        return any(part in path.split('/') for part in
                   ('generate', 'prompt', 'run', 'run-all', 'prepare', 'assemble', 'launch', 'connect', 'reconcile'))

    def _response(self, method, path, body=None):
        kwargs = {}
        if body and '_file_bytes' in body:
            kwargs['data'] = {key: value for key, value in body.items() if not key.startswith('_')}
            kwargs['data']['file'] = (io.BytesIO(body['_file_bytes']), body.get('_filename', 'fixture.png'))
        elif body is not None:
            kwargs['json'] = body
        # LocalModels must never discover the user's desktop extra-model config.
        with patch.dict('os.environ', {'APPDATA': str(self.temp_root/'appdata')}):
            response = self.client.open(path, method=method, **kwargs)
        self.real_api_calls.append(dict(method=method, path=path, status=response.status_code))
        return response

    def reset(self):
        super().reset()
        p = self.image_service.create('真实图片 API · 隔离检查')
        self.pid = p['id']
        base = '/api/v5/image-projects/' + self.pid
        inputs = {}
        for role in ('A', 'B', 'mask'):
            upload = dict(_file_bytes=self.media[role+'.png'], _filename=role+'.png')
            if role == 'mask': upload['source'] = inputs['A']['id']
            response = self._response('POST', base+'/inputs', upload)
            if response.status_code != 200:
                raise RuntimeError('真实隔离上传失败：' + response.get_data(as_text=True))
            inputs[role] = response.get_json()
        template = image_project()
        for index, task in enumerate(template['tasks']):
            task.update(id=p['tasks'][0]['id'] if index == 0 else uuid.uuid4().hex, project=self.pid,
                        A=inputs['A']['id'] if task['submode']!='text' else None, B=inputs['B']['id'] if task['submode']=='dual' else None,
                        mask=inputs['mask']['id'] if task['submode']=='region' else None)
        p.update(tasks=template['tasks'], current_task=template['tasks'][0]['id'])
        planned = self._response('POST', base+'/change-plan', p)
        if planned.status_code != 200:
            raise RuntimeError('真实隔离草稿计划失败：' + planned.get_data(as_text=True))
        applied = self._response('POST', base+'/apply', {'token': planned.get_json()['token']})
        if applied.status_code != 200:
            raise RuntimeError('真实隔离草稿保存失败：' + applied.get_data(as_text=True))
        task = applied.get_json()['tasks'][0]
        run = dict(id=uuid.uuid4().hex, project=self.pid, task=task['id'], state='success',
                   seed=0, note='合成预置候选；没有执行生成', snapshot=copy.deepcopy(task),
                   created=STAMP, finished=STAMP+1, prompt_id='fixture-prompt-zero',
                   source_hash=compiler.SOURCE_HASH, plugin_version=compiler.PLUGIN_VERSION,
                   graph_hash='synthetic-output-no-execution')
        self.image_service.store.put('runs', run)
        directory = self.image_service.store.directory(self.pid)/'image_runs'/run['id']
        directory.mkdir(parents=True)
        for index in (1, 2):
            target = directory/f'candidate-{index}.png'
            payload = self.media[f'candidate-{index}.png']
            target.write_bytes(payload)
            self.image_service.store.put('outputs', dict(id=uuid.uuid4().hex, project=self.pid,
                task=task['id'], run=run['id'], path=str(target), width=720, height=960,
                selected=False, hash=hashlib.sha256(payload).hexdigest()))
        self.projects.pop(PID)
        self.projects[self.pid] = self.image_service.snapshot(self.pid)

    def state(self):
        self.projects[self.pid] = self.image_service.snapshot(self.pid)
        return dict(super().state(), temporary_data_root=str(self.temp_root),
                    engine_attempts=self.engine_attempts, real_api_calls=self.real_api_calls)

    def request(self, method, path, body):
        if self.forbidden(path):
            self.generation_requests += 1
            return 403, {'error': '隔离环境禁止生成或引擎动作'}
        if path == '/__fixture/control' and method == 'POST':
            self.controls.update({key: body[key] for key in self.controls if key in body})
            if 'run_error' in body:
                run = self.image_service.store.all('runs', self.pid)[0]
                run.update(state='failed' if body['run_error'] else 'success',
                           note='隔离模拟执行失败' if body['run_error'] else '合成预置候选；没有执行生成',
                           error_kind='engine' if body['run_error'] else None,
                           error_raw=RAW_ERROR if body['run_error'] else None)
                self.image_service.store.put('runs', run)
            return 200, self.controls
        if path == '/api/v5/projects' and method == 'GET':
            self.projects[self.pid] = self.image_service.snapshot(self.pid)
        real_path = (path.startswith('/api/v5/image-projects/') or
                     path == '/api/v5/projects/' + self.pid or path == '/api/v5/health')
        if not real_path:
            return super().request(method, path, body)
        with ExitStack() as scope:
            if path == '/api/v5/image-projects/catalog':
                self.refresh_count += 1
                if self.controls['refresh_error']:
                    scope.enter_context(patch.object(self.image_service.local_models, 'scan',
                        side_effect=PermissionError('隔离真实目录扫描故障')))
            if path.endswith('/change-plan') and self.controls['save_error']:
                from h3ui.studio_store import Conflict
                scope.enter_context(patch.object(self.image_service, 'plan',
                    side_effect=Conflict('隔离真实保存冲突，草稿保留')))
            response = self._response(method, path, body)
        return response.status_code, response.get_json()

    def media_response(self, path):
        response = self._response('GET', path)
        return response.status_code, response.get_data(), response.content_type

    def close(self):
        self.resources.close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, status, body, content_type='application/json; charset=utf-8'):
        payload = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-TimeForest-Fixture', 'synthetic-no-engine')
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        self.handle_request('GET')

    def do_POST(self):
        self.handle_request('POST')

    def handle_request(self, method):
        path = unquote(urlsplit(self.path).path)
        if path.startswith('/__fixture__/'):
            path = '/__fixture/' + path[len('/__fixture__/'):]
        fixture = self.server.fixture
        if method == 'GET' and path in ('/__fixture', '/__fixture/'):
            page = CONTROL_PAGE.replace('href="/#/p/fixture-image"', 'href="/#/p/'+fixture.pid+'"')
            if fixture.backend_mode == 'real-image-blueprint':
                page = page.replace('本页仅控制内存模拟 API', '本页使用真实图片 API 与临时数据库；视频对照为合成数据')
                page = page.replace("fetch('/__fixture/reset',{method:'POST'});await show();",
                                    "fetch('/__fixture/reset',{method:'POST'});location.reload();")
            return self.send(200, page.encode('utf-8'), 'text/html; charset=utf-8')
        if method == 'GET' and (path == '/' or path.startswith('/static/')):
            relative = 'index.html' if path == '/' else path[len('/static/'):]
            static = (ROOT / 'static').resolve()
            target = (static / relative).resolve()
            if static not in target.parents or not target.is_file():
                return self.send(404, {'error': '非白名单静态资源'})
            mime = 'text/javascript' if target.suffix == '.js' else mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
            return self.send(200, target.read_bytes(), mime)
        if method == 'GET' and isinstance(fixture, RealImageFixture) and path.startswith('/api/v5/projects/'+fixture.pid+'/files/'):
            with fixture.lock:
                status, payload, mime = fixture.media_response(path)
                fixture.record(method, path, {}, status)
                return self.send(status, payload, mime)
        if method == 'GET' and (path.startswith('/__fixture/media/') or '/files/image_inputs/' in path):
            key = path.rsplit('/', 1)[-1] if path.startswith('/__fixture/media/') else path.split('/image_inputs/')[1].split('/')[0] + '.png'
            return self.send(200, fixture.media[key], 'image/png') if key in fixture.media else self.send(404, {'error': '未知隔离媒体'})
        body = None
        try:
            if method == 'POST':
                payload = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                content_type = self.headers.get('Content-Type', '')
                if content_type.startswith('multipart/form-data'):
                    message = BytesParser(policy=email_policy).parsebytes(('Content-Type: ' + content_type + '\r\n\r\n').encode() + payload)
                    body = {}
                    for part in message.iter_parts():
                        key = part.get_param('name', header='content-disposition')
                        if key == 'file':
                            body['_file_bytes'] = part.get_payload(decode=True)
                            body['_filename'] = part.get_filename()
                        else:
                            body[key] = part.get_payload(decode=True).decode()
                else:
                    body = json.loads(payload or b'{}')
            with fixture.lock:
                status, result = fixture.request(method, path, body)
                logged_body = {k: v for k, v in (body or {}).items() if k != '_file_bytes'}
                fixture.record(method, path, logged_body, status)
                self.send(status, result)
        except (ValueError, TypeError, KeyError) as error:
            fixture.record(method, path, {'invalid_request': str(error)}, 400)
            self.send(400, {'error': str(error)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=5097)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    parser.add_argument('--resume-log', action='store_true', help='Append existing fixture log; project state resets on server restart')
    parser.add_argument('--real-image-api', action='store_true', help='Use actual image blueprint/service/SQLite with isolated fake model files')
    args = parser.parse_args()
    evidence = args.evidence_dir.resolve()
    if evidence == ROOT or ROOT in evidence.parents:
        parser.error('evidence-dir 必须在真实仓库外')
    evidence.mkdir(parents=True, exist_ok=True)
    if (evidence / 'fixture-api.jsonl').exists() and not args.resume_log:
        parser.error('此目录已有 fixture 日志，请选择新的外部目录以保留证据')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.fixture = (RealImageFixture if args.real_image_api else Fixture)(evidence)
    info = dict(url=f'http://127.0.0.1:{args.port}/#/p/{server.fixture.pid}',
                videos=[f'http://127.0.0.1:{args.port}/#/p/{key}' for key in server.fixture.projects if key != server.fixture.pid],
                evidence=str(evidence), generation='forbidden', production_config='not loaded',
                backend_mode=server.fixture.backend_mode)
    (evidence / 'fixture-info.json').write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(info, ensure_ascii=False), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        server.fixture.close()


if __name__ == '__main__':
    main()
