"""Source-video import plans remain read-only until applying the validated draft."""
import copy
import unittest
from tests import test_video_assembly as fixtures
from h3ui.studio_store import Conflict

class AssetDraftTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.AssemblyTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.AssemblyTests.tearDownClass.__func__)
    setUp=fixtures.AssemblyTests.setUp

    def test_source_video_draft_preview_cancel_apply_and_conflict(self):
        item=self.s.lib.ingest(self.silent,'原片')
        p=self.st.create('swap','旧名称',15);draft=copy.deepcopy(p);draft['name']='新草稿名称'
        draft['swap_prompt']['custom']='素材确认时保存的完整正文'
        request=dict(revision=p['revision'],asset=item['id'],version=item['version'],target='source',draft=draft)
        plan=self.s.lib.project_import.plan(p['id'],request)
        self.assertTrue(plan['ready'],plan);self.assertEqual(self.st.store.get(p['id']),p)
        self.assertIsNone(self.s.lib.store.get(item['id'])['used'])
        self.s.lib.project_import.apply(dict(project=p['id'],token=plan['token']),lambda *a:None)
        saved=self.st.store.get(p['id']);self.assertEqual(saved['name'],'新草稿名称')
        self.assertTrue(saved['source_asset']);self.assertFalse(saved['source_ready'])
        rows=self.app.config['PROMPT_LIBRARY'].store.list({})['items']
        self.assertTrue(any(r['source']['project']==p['id'] and r['content'].get('text')=='素材确认时保存的完整正文' for r in rows))
        request.update(revision=saved['revision']);request['draft']=copy.deepcopy(saved)
        plan=self.s.lib.project_import.plan(p['id'],request)
        self.st.store.mutate(p['id'],lambda q:q.update(name='其他窗口的修改'))
        with self.assertRaises(Conflict):self.s.lib.project_import.apply(dict(project=p['id'],token=plan['token']),lambda *a:None)
        self.assertEqual(self.st.store.get(p['id'])['name'],'其他窗口的修改')

if __name__=='__main__':unittest.main()
