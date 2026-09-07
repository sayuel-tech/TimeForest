"""Startup reload policy on temporary records; never run workers or an engine."""
import copy
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

from h3ui import create_app
from h3ui.comfy import ComfyClient


class StartupRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cfg = dict(studio_data_dir=str(self.root/'projects'), data_dir=str(self.root/'legacy'),
                        asset_library_dir=str(self.root/'library'), comfy_base_dir=str(self.root/'comfy'),
                        comfy_input_dir=str(self.root/'comfy/input'), comfy_output_dir=str(self.root/'comfy/output'),
                        comfy_url='http://127.0.0.1:8188', studio_disable_generation=False,
                        studio_auto_recover=True, studio_progress_disabled=True,
                        image_assets_enabled=True, open_browser=False)
        self.path = self.root/'config.json'; self.path.write_text(json.dumps(self.cfg),encoding='utf-8')
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict('os.environ', {'APPDATA': str(self.root/'appdata')}))
        self.get = self.stack.enter_context(patch.object(ComfyClient,'_get',side_effect=AssertionError('No engine network')))
        self.post = self.stack.enter_context(patch.object(ComfyClient,'_post',side_effect=AssertionError('No engine network')))
        self.image_wake = self.stack.enter_context(patch('h3ui.image_studio.runner.Runner.wake'))
        self.local_wake = self.stack.enter_context(patch('h3ui.local_tasks.LocalTasks.wake'))
        self.restore = self.stack.enter_context(patch('h3ui.generation.recovery.restore_existing'))
        app = create_app(str(self.path))
        self.st = app.config['STUDIO']; self.images = app.config['IMAGE_STUDIO']; self.library = app.config['ASSET_LIBRARY']
        video = self.st.create('text_story','Temporary active video',15)
        def active(p):
            p['status']='generating'; p['segments'][0]['status']='generating'
        self.video = self.st.store.mutate(video['id'],active)
        image = self.images.create('Temporary queued image')
        for n,state in enumerate(('waiting','submitting','running','unknown'),1):
            self.images.store.put('runs',dict(id=str(n)*32,project=image['id'],task=image['current_task'],state=state,created=n))
        with self.library.store.connect() as db:
            for n,state in enumerate(('running','queued'),1):
                db.execute('INSERT INTO local_tasks VALUES(?,?,?,?,?,?,?,?,?,?)',
                           (str(n)*32,'fixture-'+str(n),'backup','{}',state,0,'original fixture note',None,n,n))
        self.image_wake.reset_mock(); self.local_wake.reset_mock(); self.restore.reset_mock()

    def local_rows(self, library):
        with library.store.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM local_tasks ORDER BY id')]

    def test_no_startup_recovery_keeps_records_and_does_not_start_workers(self):
        original_config=self.path.read_bytes(); video=copy.deepcopy(self.st.store.get(self.video['id']))
        images=self.images.store.all('runs'); local=self.local_rows(self.library)
        app=create_app(str(self.path),recover_tasks=False)
        self.assertEqual(app.config['STUDIO'].store.get(video['id']),video)
        self.assertEqual(app.config['STUDIO'].pending_recovery,[])
        self.assertEqual(app.config['IMAGE_STUDIO'].store.all('runs'),images)
        self.assertEqual(self.local_rows(app.config['ASSET_LIBRARY']),local)
        self.assertFalse(app.config['H3UI']['cfg']['studio_disable_generation'])
        self.assertTrue(app.config['H3UI']['cfg']['studio_auto_recover'])
        self.assertEqual(self.path.read_bytes(),original_config)
        self.image_wake.assert_not_called(); self.local_wake.assert_not_called(); self.restore.assert_not_called()
        self.get.assert_not_called(); self.post.assert_not_called()
        with patch('h3ui.image_studio.parameters.PARAMETER_CONTRACT_VERSION',99):
            health=app.test_client().get('/api/v5/health').get_json()
        self.assertFalse(health['startup_recovery'])
        self.assertEqual(health['image_parameter_contract_version'],1)

    def test_default_startup_retains_previous_recovery_wiring(self):
        app=create_app(str(self.path))
        video=app.config['STUDIO'].store.get(self.video['id'])
        self.assertEqual(video['status'],'interrupted')
        self.assertEqual(video['segments'][0]['status'],'interrupted')
        self.assertEqual(app.config['STUDIO'].pending_recovery,[(video['id'],0)])
        self.assertEqual([r['state'] for r in self.local_rows(app.config['ASSET_LIBRARY'])],['interrupted','queued'])
        self.image_wake.assert_called_once(); self.local_wake.assert_called_once()
        self.restore.assert_called_once_with(app.config['STUDIO'])
        self.get.assert_not_called(); self.post.assert_not_called()
        self.assertTrue(app.test_client().get('/api/v5/health').get_json()['startup_recovery'])

    def test_cli_option_is_process_local_and_default_remains_enabled(self):
        import run
        for extra,expected in (([],True),(['--no-startup-recovery'],False)):
            fake=Mock(); fake.config={'H3UI':{'cfg':{'open_browser':False}}}
            with patch.object(run,'create_app',return_value=fake) as factory, patch('sys.argv',['run.py','--config',str(self.path),'--no-browser',*extra]):
                self.assertEqual(run.main(),0)
            factory.assert_called_once_with(str(self.path),recover_tasks=expected)
            fake.run.assert_called_once_with(host='127.0.0.1',port=5093,threaded=True,debug=False)


if __name__=='__main__': unittest.main()
