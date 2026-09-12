"""Real isolated import follows the displayed script directory, without generation."""
import copy
import unittest
from . import test_creation


class ImportOrderTests(unittest.TestCase):
    def setUp(self):
        self.c=test_creation.CreationTests();self.c.setUp();self.addCleanup(self.c.doCleanups)
        result=self.c.save('storyboard',{'shots':[{'ref':'tmp:a','title':'开场','text':'进入树林'}, {'ref':'tmp:b','title':'结尾','text':'走出树林'}]})
        self.a=result['id_map']['tmp:a'];self.b=result['id_map']['tmp:b']
        result=self.c.save('segment',{'segments':[{'ref':'tmp:'+key,'shot_ref':shot,'text':key,'planned_seconds':5} for key,shot in [('b1',self.b),('a1',self.a),('b2',self.b),('a2',self.a)]]})
        self.ids={key:result['id_map']['tmp:'+key] for key in ['a1','a2','b1','b2']}

    def create(self,ids=None):
        return self.c.post('/movie/projects',dict(title='目录顺序电影',source_project_id=self.c.p['id'],source_revision=self.c.p['revision'],segment_ids=ids or []))

    def test_import_follows_shot_directory_and_keeps_unready_sources(self):
        original=copy.deepcopy(self.c.p['content'])
        movie=self.create()
        self.assertEqual(movie['content']['segment_order'],[self.ids[k] for k in ['a1','a2','b1','b2']])
        self.assertEqual(self.c.service.snapshot(self.c.p['id'])['content'],original)
        self.assertTrue(all(b['ready_state']=='draft' for b in movie['content']['source_bundles']))
        pf=self.c.post('/movie/projects/'+movie['id']+'/preflight',dict(revision=movie['revision'],segment_id=self.ids['a1']))
        self.assertFalse(pf['ready']);self.assertIn('正式 Prompt 尚未确认','；'.join(pf['issues']))
        self.assertEqual(self.c.service.snapshot(movie['id'])['creation_jobs'],[])

    def test_subset_uses_script_order_and_sync_keeps_existing_movie_order(self):
        movie=self.create([self.ids['b2'],self.ids['a2']])
        original_order=[self.ids['a2'],self.ids['b2']]
        self.assertEqual(movie['content']['segment_order'],original_order)
        shots=self.c.service.layer(self.c.p,'storyboard')['content']['shots']
        self.c.save('storyboard',{'shots':list(reversed(shots))})
        # A fresh import follows the newly saved directory.
        self.assertEqual(self.create()['content']['segment_order'],[self.ids[k] for k in ['b1','b2','a1','a2']])
        plan=self.c.post('/movie/projects/'+movie['id']+'/sync/preview',dict(revision=movie['revision'],source_project_id=self.c.p['id'],source_revision=self.c.p['revision'],target_segment_ids=list(original_order)))
        self.c.post('/movie/projects/'+movie['id']+'/sync/apply',dict(revision=movie['revision'],plan_id=plan['plan_id'],plan_hash=plan['plan_hash'],selected_change_ids=original_order))
        current=self.c.service.snapshot(movie['id'])
        self.assertEqual(current['content']['segment_order'],original_order)
        self.assertEqual(current['content']['edit'],movie['content']['edit'])

if __name__=='__main__':unittest.main()
