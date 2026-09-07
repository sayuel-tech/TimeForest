"""Image parameter regression checks; temporary stores and no engine network."""
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from h3ui import create_app
from h3ui.comfy import ComfyClient, ComfyError
from h3ui.image_studio import compiler
from h3ui.generation.local_models import LocalModels


class ImageParameterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        cfg = dict(studio_data_dir=str(self.root/'projects'), data_dir=str(self.root/'legacy'),
                   asset_library_dir=str(self.root/'library'), comfy_base_dir=str(self.root/'comfy'),
                   comfy_input_dir=str(self.root/'comfy/input'), comfy_output_dir=str(self.root/'comfy/output'),
                   comfy_url='http://127.0.0.1:8188', studio_disable_generation=True,
                   studio_progress_disabled=True, studio_auto_recover=False, image_assets_enabled=True,
                   open_browser=False)
        path = self.root/'config.json'; path.write_text(json.dumps(cfg), encoding='utf-8')
        env = patch.dict('os.environ', {'APPDATA': str(self.root/'appdata')}); env.start(); self.addCleanup(env.stop)
        for name in ('_get', '_post'):
            mock = patch.object(ComfyClient, name, side_effect=AssertionError('Engine network forbidden'))
            stub = mock.start(); self.addCleanup(mock.stop)
            if name == '_get': self.engine_get = stub
        self.app = create_app(str(path)); self.client = self.app.test_client()
        self.s = self.app.config['IMAGE_STUDIO']; self.p = self.s.create('参数隔离检查')

    def test_seed_and_integer_fields_reject_truncation_and_bool(self):
        for value in (True, False, 1.5, '1.5', '1e3', ' ', 'not-a-seed', -1, 2**53):
            with self.subTest(seed=value), self.assertRaises(ValueError):
                compiler.settings({'seed': value})
        for key in ('steps', 'grounding_px', 'left', 'right', 'top', 'bottom', 'feathering'):
            for value in (True, 2.5, '2.5'):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    compiler.settings({key: value})
        for value, expected in ((None, None), ('', None), (0, 0), ('0', 0), (2**53-1, 2**53-1)):
            self.assertEqual(compiler.settings({'seed': value})['seed'], expected)

    def test_catalog_discovers_local_relative_files_without_engine(self):
        for folder, role in (('diffusion_models', 'unet'), ('text_encoders', 'clip'), ('vae', 'vae'), ('loras', 'lora')):
            file = self.root/'comfy/models'/folder/'custom'/'未登记.safetensors'
            file.parent.mkdir(parents=True); file.write_bytes(b'fixture filename only')
        before = self.s.snapshot(self.p['id'])
        result = self.client.get('/api/v5/image-projects/catalog').get_json()
        for role in ('unet', 'clip', 'vae', 'lora'):
            self.assertIn(str(Path('custom/未登记.safetensors')), result['choices'][role])
        self.assertEqual(result['local_models']['source'], 'filesystem')
        self.assertIsNotNone(result['local_models']['updated'])
        self.assertEqual(self.s.snapshot(self.p['id']), before)
        self.engine_get.assert_not_called()

    def test_history_failure_preserves_engine_detail(self):
        run = dict(id='a'*32, project=self.p['id'], task=self.p['current_task'], state='unknown', prompt_id='owned')
        self.s.store.put('runs', run)
        status = {'status_str': 'error', 'messages': [['execution_error', {'node_id':'7', 'exception_message':'precise plugin error'}]]}
        with patch('h3ui.image_studio.runner.resolve_submission', return_value=('owned', {'owned': {'status': status}}, False)):
            self.s.runner.reconcile(run)
        actual = self.s.store.get('runs', run['id'])
        self.assertEqual(actual['state'], 'failed')
        self.assertEqual(actual['error_kind'], 'engine')
        self.assertEqual(json.loads(actual['error_raw']), status)
        self.assertIn('precise plugin error', actual['note'])

    def save(self, p):
        response = self.client.post(f"/api/v5/image-projects/{p['id']}/change-plan", json=p)
        self.assertEqual(response.status_code, 200, response.get_json())
        applied = self.client.post(f"/api/v5/image-projects/{p['id']}/apply", json={'token': response.get_json()['token']})
        self.assertEqual(applied.status_code, 200, applied.get_json())
        return self.s.snapshot(p['id'])

    def test_all_public_fields_save_reload_and_bind_four_real_branches(self):
        catalog = self.s.catalog()
        self.assertEqual(catalog['parameter_contract_version'], 1)
        values = dict(megapixels=.75, output_mp=1.25, ratio='4:3', steps=17, cfg=2.3,
                      sampler_name='heun', scheduler='normal', seed=0, ref_boost=2.4, ref_boost_a=.7,
                      grounding_px=640, fit_mode='crop (legacy)', strength_model=.55,
                      left=64, top=24, right=96, bottom=8, feathering=16)
        models = {role: '未登记/'+role+'.safetensors' for role in compiler.MODELS}
        direct = {'unet':'unet_name', 'clip':'clip_name', 'vae':'vae_name', 'lora':'lora_name'}
        for mode in ('single','dual','region','outpaint'):
            with self.subTest(mode=mode):
                p = self.s.create(mode, mode); t = p['tasks'][0]
                t.update(prompt='保留原正文', models=models, settings={**t['settings'], **values})
                saved = self.save(p); actual = saved['tasks'][0]
                self.assertEqual(actual['settings'], values)
                self.assertEqual(actual['models'], models)
                graph, out = compiler.compile_graph(mode, actual['prompt'], {'A':'A.png', 'B':'B.png'}, actual['settings'], actual['models'])
                self.assertEqual(graph[out]['class_type'], 'SaveImage')
                ports = [n['inputs'] for n in graph.values()]
                fields = catalog['parameters'][mode]
                self.assertEqual(len(fields), len({(f['scope'], f['key']) for f in fields}))
                for f in fields:
                    key = f['key']; expected = actual[f['scope']][key]
                    if key in ('ratio', 'megapixels', 'output_mp'):
                        continue
                    self.assertTrue(any(v.get(direct.get(key,key)) == expected for v in ports), f'{mode}: {key} binding lost')
                scales = [n['inputs']['megapixels'] for n in graph.values() if n['class_type']=='ImageScaleToTotalPixels']
                self.assertEqual(set(scales), {1, values['output_mp']} if mode=='outpaint' else {values['megapixels']})
                keys = {f['key'] for f in fields}
                self.assertEqual('ratio' in keys, mode=='dual')
                self.assertEqual('ref_boost_a' in keys, mode=='dual')
                self.assertEqual('megapixels' in keys, mode!='outpaint')
                self.assertEqual('output_mp' in keys, mode=='outpaint')
                self.assertEqual('left' in keys, mode=='outpaint')
                if mode=='outpaint':
                    self.assertTrue({'left','right','top','bottom'} <= {f['key'] for f in fields if f.get('quick')})
                if mode!='dual':
                    patch_node=next(n for n in graph.values() if n['class_type']=='Krea2EditModelPatch')
                    self.assertEqual(patch_node['inputs']['ref_boost_a'],1)
                    self.assertEqual(actual['settings']['ref_boost_a'],.7)
                if mode=='dual':
                    w,h = compiler.scale_size(4,3,.75)
                    self.assertEqual((graph['4']['inputs']['width'],graph['4']['inputs']['height']), (w,h))

    def test_invalid_seed_api_preserves_saved_draft_and_original_error(self):
        p = copy.deepcopy(self.p); p['tasks'][0]['prompt']='尚未保存的正文'; p['tasks'][0]['settings']['seed']=.5
        before = self.s.snapshot(p['id'])
        response = self.client.post(f"/api/v5/image-projects/{p['id']}/change-plan", json=p)
        body = response.get_json()
        self.assertEqual(response.status_code,400)
        self.assertEqual(body['error_kind'],'input')
        self.assertEqual(body['error_raw'],body['error'])
        self.assertEqual(self.s.snapshot(p['id']),before)

    def test_run_snapshot_records_fixed_zero_or_actual_random_seed(self):
        for seed, expected in ((0, 0), (None, 517)):
            p=self.s.create('实际种子快照'); stream=io.BytesIO()
            Image.new('RGB',(16,24),'green').save(stream,'PNG'); stream.seek(0)
            uploaded=self.client.post(f"/api/v5/image-projects/{p['id']}/inputs",data={'file':(stream,'fixture.png')}).get_json()
            p['tasks'][0].update(A=uploaded['id'],prompt='保留这一正文')
            p['tasks'][0]['settings']['seed']=seed; p=self.save(p)
            self.s.cfg['studio_disable_generation']=False
            with patch.object(self.s.runner,'wake'), patch('h3ui.image_studio.runner.secrets.randbelow',return_value=517) as random:
                run=self.s.runner.submit(p['id'],p['current_task'],p['revision'],'seed-snapshot')
            self.s.cfg['studio_disable_generation']=True
            self.assertEqual(random.call_count,0 if seed is not None else 1)
            self.assertEqual(run['seed'],expected)
            self.assertEqual(run['snapshot']['settings']['seed'],expected)
            self.assertEqual(self.s.snapshot(p['id'])['tasks'][0]['settings']['seed'],seed)
            graph,_=compiler.compile_graph('single',run['snapshot']['prompt'],{'A':'fixture.png'},run['snapshot']['settings'])
            self.assertEqual(next(n for n in graph.values() if n['class_type']=='KSampler')['inputs']['seed'],expected)
        self.engine_get.assert_not_called()

    def test_local_scan_failure_and_missing_file_preserve_task_selection(self):
        file = self.root/'comfy/models/unet/new/model.pt'; file.parent.mkdir(parents=True); file.write_bytes(b'fixture')
        p = copy.deepcopy(self.p); p['tasks'][0]['models']['unet']='new\\model.pt'; saved=self.save(p)
        before = self.s.snapshot(p['id']); initial = self.s.catalog()
        with patch.object(LocalModels,'scan',side_effect=OSError('fixture directory denied')):
            failed = self.s.catalog()
        self.assertEqual(failed['choices'],initial['choices'])
        self.assertEqual(failed['local_models']['updated'],initial['local_models']['updated'])
        self.assertEqual(failed['local_models']['errors'],['fixture directory denied'])
        file.unlink(); refreshed=self.s.catalog()
        self.assertNotIn('new\\model.pt',refreshed['choices']['unet'])
        self.assertEqual(self.s.snapshot(saved['id']),before)

    def test_remote_catalog_never_claims_local_files_or_wrong_engine_cache(self):
        self.s.st.comfy.url='https://remote.invalid:8188'
        path=self.s.st.root/'image-catalog.json'
        path.write_text(json.dumps(dict(url='http://127.0.0.1:8188',checked=12,models={'unet':['wrong.pt']})),encoding='utf-8')
        with patch.object(LocalModels,'scan',side_effect=AssertionError('Remote must not scan local files')):
            mismatched=self.s.catalog()
            self.assertEqual(mismatched['choices']['unet'],[])
            self.assertEqual(mismatched['local_models']['source'],'remote_unavailable')
            path.write_text(json.dumps(dict(url=self.s.st.comfy.url,checked=23,models={'unet':['remote/nested.pt']})),encoding='utf-8')
            remote=self.s.catalog()
            self.assertEqual(remote['choices']['unet'],['remote/nested.pt'])
            self.assertEqual(remote['local_models']['updated'],23)
            self.assertEqual(remote['local_models']['roots'],{})

    def test_node_sync_failure_preserves_matching_cache_and_raw_error(self):
        path=self.s.st.root/'image-catalog.json'
        cached=dict(url=self.s.st.comfy.url,checked=23,missing=[],models={r:['engine.pt'] for r in compiler.MODELS})
        path.write_text(json.dumps(cached),encoding='utf-8'); before=path.read_bytes()
        message='ComfyUI request /object_info failed: fixture network disconnected'
        with patch.object(self.s.st.comfy,'_get',side_effect=ComfyError(message)) as request:
            response=self.client.post('/api/v5/image-projects/catalog/sync')
        self.assertEqual(request.call_count,1)
        self.assertEqual(response.status_code,200)
        result=response.get_json(); self.assertEqual(result['node_catalog']['error'],message)
        self.assertEqual(result['node_catalog']['error_kind'],'network')
        self.assertEqual(result['node_catalog']['updated'],23)
        self.assertEqual(path.read_bytes(),before)
        with patch.object(self.s.st.comfy,'_get',return_value={k:{} for k in compiler.WIDGETS}), patch('h3ui.image_studio.service.write',side_effect=OSError('fixture cache write denied')):
            failed_write=self.s.catalog(sync=True)
        self.assertEqual(failed_write['node_catalog']['error'],'fixture cache write denied')
        self.assertEqual(failed_write['node_catalog']['error_kind'],'website')
        self.assertEqual(failed_write['node_catalog']['updated'],23)
        self.assertEqual(path.read_bytes(),before)

    def test_catalog_failure_kind_reaches_runner_without_becoming_engine_failure(self):
        from h3ui.image_studio.runner import error_fields
        run=dict(id='c'*32,project=self.p['id'],task=self.p['current_task'],state='waiting',created=1)
        self.s.store.put('runs',run)
        catalog=dict(node_catalog=dict(error='fixture cache write denied',error_kind='website'))
        with patch.object(self.s.st.comfy,'_get',return_value={}), patch.object(self.s,'catalog',return_value=catalog):
            with self.assertRaises(ComfyError) as caught:
                self.s.runner.execute(run)
        self.assertEqual(error_fields(caught.exception)['error_kind'],'website')
        self.assertEqual(error_fields(caught.exception)['error_raw'],'fixture cache write denied')

    def test_sync_scopes_cache_to_engine_and_does_not_mix_local_choices(self):
        nodes={k:{} for k in compiler.WIDGETS}
        for ct,field in [('UNETLoader','unet_name'),('CLIPLoader','clip_name'),('VAELoader','vae_name'),('LoraLoaderModelOnly','lora_name')]:
            nodes[ct]={'input':{'required':{field:[['engine-only.pt']]}}}
        with patch.object(self.s.st.comfy,'_get',return_value=nodes) as request:
            result=self.s.catalog(sync=True)
        self.assertEqual(request.call_args.args,('/object_info',))
        self.assertEqual(result['missing'],[])
        self.assertEqual(result['node_catalog']['source'],'online')
        self.assertNotIn('engine-only.pt',result['choices']['unet'])
        cache=json.loads((self.s.st.root/'image-catalog.json').read_text(encoding='utf-8'))
        self.assertEqual(cache['url'],self.s.st.comfy.url)
        self.assertEqual(cache['models']['unet'],['engine-only.pt'])

    def test_dispatch_preserves_raw_engine_and_network_failures_without_retry(self):
        for n, message, kind in [(1, 'ComfyUI /prompt HTTP 400: node 7 steps invalid', 'engine'),
                                  (2, 'ComfyUI request /queue failed: offline', 'network')]:
            run=dict(id=str(n)*32,project=self.p['id'],task=self.p['current_task'],state='waiting',created=n)
            self.s.store.put('runs',run)
            with patch.object(self.s.runner,'execute',side_effect=ComfyError(message)) as execute:
                self.s.runner._dispatch()
            self.assertEqual(execute.call_count,1)
            actual=self.s.store.get('runs',run['id'])
            self.assertEqual(actual['error_kind'],kind)
            self.assertEqual(actual['error_raw'],message)
            self.assertEqual(actual['state'],'failed')


if __name__ == '__main__': unittest.main()
