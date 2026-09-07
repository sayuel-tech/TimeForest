"""Local authoring must never require a network connection or GPU submission."""
import copy
import io
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from h3ui import create_app
from h3ui.comfy import ComfyClient
from h3ui.jobs import JobManager
from h3ui.studio_recipes import defaults


class LocalServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        cfg = json.loads(Path('config.example.json').read_text(encoding='utf-8'))
        cfg.update(studio_data_dir=str(self.root/'projects'), data_dir=str(self.root/'legacy'),
                   asset_library_dir=str(self.root/'library'),
                   comfy_input_dir=str(self.root/'engine-input'), comfy_output_dir=str(self.root/'engine-output'),
                   studio_progress_disabled=True, studio_disable_generation=True, open_browser=False)
        path = self.root/'config.json'
        path.write_text(json.dumps(cfg), encoding='utf-8')
        self.network = patch.object(ComfyClient, '_get', side_effect=AssertionError('LOCAL ACTION TOUCHED ENGINE'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.addCleanup(self.tmp.cleanup)
        self.app = create_app(str(path))
        self.st = self.app.config['STUDIO']
        self.client = self.app.test_client()

    def test_no_cache_create_save_upload_catalog_and_compile_offline(self):
        for url in ['/', '/api/v5/health', '/api/v5/catalog', '/api/v5/projects']:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True)[:400])
            response.close()
        health = self.client.get('/api/v5/health').get_json()
        self.assertFalse(health['comfy_connected'])
        for mode in ['image_story','text_story']:
            p = self.st.create(mode,'offline check',15)
            p['segments'][0]['prompt'] = 'A quiet forest, natural wind.'
            if mode == 'image_story':
                stream=io.BytesIO();Image.new('RGBA',(128,128),(150,120,80,127)).save(stream,format='PNG');stream.seek(0)
                response=self.client.post(f"/api/v5/projects/{p['id']}/assets",data={'kind':'image','purpose':'character','subject':'1','file':(stream,'character.png')})
                self.assertEqual(response.status_code,200)
                p['segments'][0]['assets']=[response.get_json()['id']]
            plan=self.st.edit_plan(p['id'],p);self.st.store.apply(p['id'],plan['token'])
            result=self.st.preflight(p['id'])
            self.assertTrue(result['ready'],result['errors'])
        self.assertFalse((self.root/'engine-input').exists())

    def test_explicit_connect_failure_does_not_disable_authoring(self):
        response=self.client.post('/api/v5/engine/connect')
        self.assertEqual(response.status_code,400)
        self.assertEqual(self.client.get('/api/v5/catalog').status_code,200)
        self.assertEqual(self.st.create('text_story','still authoring')['name'],'still authoring')

    def test_model_selection_is_preserved_online_and_offline(self):
        self.st.recipes.offline=False
        settings=defaults()
        settings['model']='minimax_h3_hybrid_custom.safetensors'
        self.assertEqual(self.st.recipes.normalize(settings,'image_story')['model'],settings['model'])
        self.assertEqual(self.st.recipes.normalize(settings,'image_story',online=True)['model'],settings['model'])

    def test_explicit_catalog_sync_is_cached_but_not_assumed_online_after_restart(self):
        from h3ui.generation.catalog import EngineCatalog
        builtin=Path('h3ui/studio_sources/builtin_catalog.json')
        nodes=json.loads(builtin.read_text(encoding='utf-8'))
        with patch.object(self.st.comfy,'_get',return_value=nodes):
            self.st.recipes.connect()
        restored=EngineCatalog(self.st.comfy,self.st.root/'engine-catalog.json',builtin)
        self.assertEqual(restored.source,'cache')
        self.assertFalse(restored.connected)
        self.assertIsNotNone(restored.updated)

    def test_other_project_can_save_while_gpu_project_is_leased(self):
        first=self.st.create('text_story','rendering')
        second=self.st.create('text_story','editing')
        key=self.st.jobs._reserve('v5_generate',first['id'])
        try:
            second['name']='saved during generation'
            plan=self.st.edit_plan(second['id'],second)
            self.st.store.apply(second['id'],plan['token'])
            self.assertFalse(self.st.snapshot(self.st.store.get(second['id']))['busy'])
            with self.assertRaises(ValueError):self.st.edit_plan(first['id'],first)
            local=self.st.jobs._reserve('v5_prepare',second['id'])
            self.assertIsNotNone(local)
            self.assertIsNone(self.st.jobs._reserve('v5_generate','third'))
            self.st.jobs._release(local)
        finally:self.st.jobs._release(key)

    def test_library_chunk_resume_and_offline_preview(self):
        image=io.BytesIO()
        Image.new('RGBA',(40,40),(10,30,90,70)).save(image,format='PNG')
        body=image.getvalue()
        result=self.client.post('/api/v5/library/upload-sessions',json={'name':'alpha.png','size':len(body),'metadata':{'categories':['character']}})
        self.assertEqual(result.status_code,200,result.get_data(as_text=True))
        token=result.get_json()['token'];url='/api/v5/library/upload-sessions/'+token
        first=self.client.put(url+'?offset=0',data=body[:20],content_type='application/octet-stream')
        self.assertEqual(first.get_json()['offset'],20)
        wrong=self.client.put(url+'?offset=0',data=body[20:],content_type='application/octet-stream')
        self.assertEqual(wrong.status_code,400)
        self.client.put(url+'?offset=20',data=body[20:],content_type='application/octet-stream')
        task=self.client.post(url+'/complete').get_json()
        for _ in range(100):
            task=self.client.get('/api/v5/library/tasks/'+task['id']).get_json()
            if task['state'] in ('done','failed'):break
            time.sleep(.03)
        self.assertEqual(task['state'],'done',task)
        duplicate=self.client.post(url+'/complete').get_json()
        self.assertEqual(duplicate['id'],task['id'])
        data=self.client.get('/api/v5/library/assets?category=character').get_json()
        self.assertEqual(data['total'],1)
        media=data['items'][0]['snapshot']['media'][0]
        self.assertTrue(media['meta']['alpha'])
        with self.client.get(media['url']) as response:self.assertEqual(response.data,body)
        # Wait for the finite dispatcher to exit before disposing this test directory.
        dispatcher=self.app.config['ASSET_LIBRARY'].tasks.thread
        if dispatcher:dispatcher.join(2)


if __name__=='__main__':unittest.main()
