import unittest,uuid
from pathlib import Path
import test_studio as fixture
from h3ui.studio_store import Conflict,StudioStore
from h3ui.projects import Registry

class ProjectArchive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.StudioAcceptance.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):fixture.StudioAcceptance.tearDownClass.__func__(cls)
    def new(self):return self.st.create('text_story','删除验收',15)
    def trash(self,p,**kwargs):return self.client.post(f"/api/v5/projects/{p['id']}/trash",json=dict(revision=p['revision'],**kwargs))
    def ids(self,trash=False):return [p['id'] for p in self.client.get('/api/v5/projects?trash='+str(int(trash))).json['projects']]
    def test_hide_restore_and_persist_without_removing_assets(self):
        p=self.new();a=fixture.StudioAcceptance.asset(self,p);p=self.st.store.get(p['id'])
        marker=self.st.store.directory(p['id'])/'result.txt';marker.write_text('immutable result')
        self.assertEqual(self.trash(p).status_code,200)
        self.assertNotIn(p['id'],self.ids());self.assertIn(p['id'],self.ids(True))
        self.assertEqual(self.client.get('/api/v5/projects/'+p['id']).status_code,404)
        reloaded=StudioStore(self.st.store.root)
        self.assertTrue(reloaded.get(p['id'],include_deleted=True)['deleted_at'])
        self.assertTrue(Path(a['path']).is_file());self.assertEqual(marker.read_text(),'immutable result')
        self.assertEqual(self.st.store.asset(p['id'],a['id']),a)
        trashed=reloaded.get(p['id'],include_deleted=True)
        self.assertEqual(self.trash(trashed,restore=True).status_code,200)
        self.assertIn(p['id'],self.ids());self.assertNotIn(p['id'],self.ids(True))
        self.assertEqual(self.st.store.get(p['id'])['segments'],p['segments'])
    def test_stale_revision_cannot_delete_or_restore(self):
        p=self.new();changed=self.st.store.mutate(p['id'],lambda x:x.update(name='新名称'))
        self.assertEqual(self.trash(p).status_code,409)
        self.assertEqual(self.st.store.get(p['id']),changed)
        self.assertEqual(self.trash(changed).status_code,200)
        self.assertEqual(self.trash(changed,restore=True).status_code,409)
    def test_jobs_and_running_status_block_delete(self):
        p=self.new();lease=self.st.jobs._reserve('v5_generate',p['id'])
        try:self.assertEqual(self.trash(p).status_code,409)
        finally:self.st.jobs._release(lease)
        self.assertEqual(self.st.store.get(p['id']),p)
        p=self.st.store.mutate(p['id'],lambda x:x.update(status='assembling'))
        self.assertEqual(self.trash(p).status_code,409)
    def test_pending_save_cannot_resurrect_deleted_project(self):
        p=self.new();token=self.st.store.stage(p['id'],p['revision'],dict(project=p,summary='旧草稿'))
        self.assertEqual(self.trash(p).status_code,200)
        with self.assertRaises(Conflict):self.st.store.apply(p['id'],token)
        with self.assertRaises(KeyError):self.st.store.mutate(p['id'],lambda x:x.update(name='旧页面'))
    def test_legacy_hide_restore_and_migration_guard(self):
        registry=self.st.ctx['projects'];pid=uuid.uuid4().hex
        p=dict(id=pid,name='旧版删除验收',status='idle',segments=[])
        registry.create(p);marker=registry.project_dir(pid)/'result.txt';marker.write_text('legacy result')
        route=f'/api/v5/legacy/{pid}/trash'
        self.assertEqual(self.client.post(route,json={}).status_code,200)
        self.assertNotIn(pid,[p['id'] for p in registry.list()['projects']])
        self.assertIn(pid,[p['id'] for p in registry.list(trash=True)['projects']])
        self.assertTrue(Registry(registry.cfg).get(pid)['deleted_at'])
        self.assertEqual(self.client.post(f'/api/v5/legacy/{pid}/migrate',json={}).status_code,404)
        self.assertEqual(self.client.post(route,json={'restore':True}).status_code,200)
        self.assertEqual(marker.read_text(),'legacy result')
        self.assertIn(pid,[p['id'] for p in registry.list()['projects']])
    def test_legacy_running_blocks_delete(self):
        registry=self.st.ctx['projects'];pid=uuid.uuid4().hex
        registry.create(dict(id=pid,name='忙碌旧项目',status='running',segments=[]))
        self.assertEqual(self.client.post(f'/api/v5/legacy/{pid}/trash',json={}).status_code,400)
        self.assertNotIn('deleted_at',registry.get(pid))

if __name__=='__main__':unittest.main()
