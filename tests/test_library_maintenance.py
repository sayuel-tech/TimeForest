import importlib.util
import json
import socket
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from h3ui.asset_library.service import Library
spec=importlib.util.spec_from_file_location('maintenance','tools/library_maintenance.py');maintenance=importlib.util.module_from_spec(spec);spec.loader.exec_module(maintenance)

class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.lib=Library(self.root/'source');image=self.root/'sample.png';Image.new('RGBA',(32,32),(1,2,3,4)).save(image)
        self.asset=self.lib.ingest(image,'original',{'record_prompt':'notes only'})
        self.config=self.root/'config.json';self.config.write_text(json.dumps({'asset_library_dir':str(self.lib.root),'port':1}),encoding='utf-8')
    def test_migration_failure_preserves_configuration_and_success_roundtrip(self):
        before=self.config.read_bytes()
        with patch('h3ui.asset_library.service.shutil.copy2',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):maintenance.maintain(self.config,'migrate',self.root/'failed',True)
        self.assertEqual(self.config.read_bytes(),before)
        report=maintenance.maintain(self.config,'migrate',self.root/'moved',True)
        self.assertTrue(report['applied']);self.assertTrue(self.lib.store.db.is_file())
        moved=Library(self.root/'moved');self.assertEqual(moved.store.get(self.asset['id'])['version'],self.asset['version'])
        backup=moved.backup(self.root/'backup')
        # Allow a second config archive without relying on wall-clock sleeps.
        with patch.object(maintenance.time,'strftime',return_value='restore-fixture'):
            restored=maintenance.restore(self.config,backup['path'],self.root/'restored',True)
        self.assertTrue(restored['applied']);self.assertEqual(Library(self.root/'restored').store.get(self.asset['id'])['name'],'original')
    def test_running_website_prevents_maintenance(self):
        with socket.socket() as server:
            server.bind(('127.0.0.1',0));server.listen();cfg=json.loads(self.config.read_text());cfg['port']=server.getsockname()[1];self.config.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError,'停止本站'):maintenance.maintain(self.config,'migrate',self.root/'blocked',True)
            self.assertFalse((self.root/'blocked').exists())
    def test_cleanup_excludes_assets_and_unfinished_uploads(self):
        from h3ui.jobs import JobManager
        self.lib.attach_tasks(JobManager({}))
        finished=self.lib.root/'staging'/('a'*32);finished.mkdir();(finished/'temp.png').write_bytes(b'completed temp')
        pending=self.lib.root/'staging'/('b'*32);pending.mkdir();(pending/'keep').write_bytes(b'upload in progress')
        with self.lib.store.connect() as db:
            db.execute('INSERT INTO local_tasks VALUES(?,?,?,?,?,?,?,?,?,?)',('task',None,'derive',json.dumps({'operation_id':'a'*32}),'done',1,'done','{}',0,0))
        report=maintenance.maintain(self.config,'cleanup',apply=True)
        self.assertEqual(len(report['items']),1);self.assertFalse(finished.exists());self.assertTrue(pending.exists())
        self.assertEqual(self.lib.store.get(self.asset['id'])['version'],self.asset['version'])

if __name__=='__main__':unittest.main()
