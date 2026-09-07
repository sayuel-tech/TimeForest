"""Discard/restore edit tasks through isolated real routes; never invoke an engine."""
import copy
import unittest


class ImageTaskDiscardTests(unittest.TestCase):
    def setUp(self):
        from tests.test_image_result_actions import ImageResultActionsTests
        self.f=ImageResultActionsTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=self.f.s;self.c=self.f.c;self.pid=self.f.pid;self.tid=self.f.task['id']
        self.path=f'/api/v5/image-projects/{self.pid}/tasks/{self.tid}/discard'

    def discard(self,**extra):
        return self.c.post(self.path,json={'revision':self.s.snapshot(self.pid)['revision'],**extra})

    def test_last_task_disappears_and_restores_without_selecting_or_losing_asset(self):
        asset=self.c.post(self.f.base,json={'select_output':False}).get_json()
        before=self.s.snapshot(self.pid);runs=copy.deepcopy(before['runs']);inputs=copy.deepcopy(before['inputs'])
        paths=[self.s.store.get('outputs',o['id'])['path'] for o in before['outputs']]
        result=self.discard();self.assertEqual(result.status_code,200,result.get_json())
        p=result.get_json();self.assertEqual(p['tasks'],[]);self.assertEqual(p['outputs'],[]);self.assertEqual(p['runs'],[]);self.assertIsNone(p['current_task'])
        self.assertEqual(self.s.summaries()[0]['tasks'],0);self.assertEqual(self.s.summaries()[0]['outputs'],0)
        from pathlib import Path
        self.assertTrue(all(Path(path).is_file() for path in paths))
        self.assertEqual(self.s.lib.store.get(asset['id'])['version'],asset['version'])
        rows=self.c.get('/api/v5/recycle-bin?category=projects').get_json()['items']
        item=next(r for r in rows if r['type']=='image_task');self.assertEqual(item['id'],self.tid)
        self.assertEqual(self.discard(restore=True).status_code,200)
        restored=self.s.snapshot(self.pid);self.assertEqual(restored['current_task'],self.tid)
        self.assertEqual(restored['runs'],runs);self.assertEqual(restored['inputs'],inputs)
        self.assertFalse(any(o['selected'] for o in restored['outputs']))
        self.assertEqual(len(restored['outputs']),2)

    def test_stale_save_and_direct_candidate_operations_cannot_resurrect_task(self):
        before=self.s.snapshot(self.pid);plan=self.s.plan(self.pid,before)
        self.discard()
        response=self.c.post(f'/api/v5/image-projects/{self.pid}/apply',json={'token':plan['token']});self.assertEqual(response.status_code,409)
        before['revision']=self.s.snapshot(self.pid)['revision']
        response=self.c.post(f'/api/v5/image-projects/{self.pid}/change-plan',json=before);self.assertEqual(response.status_code,409)
        for action in ('select','continue','library'):
            response=self.c.post(f'/api/v5/image-projects/{self.pid}/outputs/'+ '2'*32+'/'+action,json={'revision':before['revision']})
            self.assertEqual(response.status_code,409,(action,response.get_json()))
        response=self.c.get(f'/api/v5/image-projects/{self.pid}/tasks/{self.tid}/preflight');self.assertEqual(response.status_code,409)
        response=self.c.post(f'/api/v5/projects/{self.pid}/records/visibility',json={'revision':before['revision'],'record':'2'*32,'removed':False});self.assertEqual(response.status_code,409)

    def test_active_revision_and_foreign_task_protections(self):
        before=self.s.snapshot(self.pid)
        self.assertEqual(self.discard(revision=0).status_code,409)
        self.assertEqual(self.discard(restore='yes').status_code,400)
        other=self.s.create('另一个项目')
        response=self.c.post(f'/api/v5/image-projects/{other["id"]}/tasks/{self.tid}/discard',json={'revision':other['revision']})
        self.assertEqual(response.status_code,400)
        for state in ('waiting','submitting','running','unknown'):
            self.s.store.mutate('runs','1'*32,lambda r:r.update(state=state))
            self.assertEqual(self.discard().status_code,409)
        self.assertFalse(self.s.store.get('tasks',self.tid).get('discarded_at'))
        self.assertEqual(self.s.snapshot(self.pid)['revision'],before['revision'])

    def test_remaining_task_and_empty_project_can_save_without_reviving_discarded(self):
        p=self.s.snapshot(self.pid);new=copy.deepcopy(p['tasks'][0]);new['id']='new-task';new['name']='保留任务';p['tasks'].append(new)
        plan=self.s.plan(self.pid,p);self.s.store.apply(self.pid,plan['token'])
        result=self.discard().get_json();self.assertEqual(result['current_task'],'new-task')
        self.assertEqual([t['id'] for t in result['tasks']],['new-task'])
        plan=self.s.plan(self.pid,result);self.s.store.apply(self.pid,plan['token'])
        result=self.c.post(f'/api/v5/image-projects/{self.pid}/tasks/new-task/discard',json={'revision':self.s.snapshot(self.pid)['revision']}).get_json()
        plan=self.s.plan(self.pid,result);self.s.store.apply(self.pid,plan['token'])
        result=self.s.snapshot(self.pid);new['id']='third-task';result['tasks']=[new];result['current_task']=new['id']
        plan=self.s.plan(self.pid,result);self.s.store.apply(self.pid,plan['token'])
        self.assertEqual([t['id'] for t in self.s.snapshot(self.pid)['tasks']],['third-task'])

    def test_recycle_parent_and_separately_removed_candidate_remain_distinct(self):
        self.s.store.mutate('runs','2'*32,lambda r:r.update(removed_at=123))
        self.s.store.mutate('outputs','2'*32,lambda r:r.update(removed_at=123))
        self.discard()
        data=self.c.get('/api/v5/recycle-bin?category=generations').get_json()
        self.assertIn('恢复编辑任务',data['items'][0]['blocked_reason'])
        self.s.trash(self.pid,{'revision':self.s.snapshot(self.pid)['revision']})
        data=self.c.get('/api/v5/recycle-bin?category=projects').get_json()
        task=next(r for r in data['items'] if r['type']=='image_task');self.assertIn('恢复所属项目',task['blocked_reason'])
        self.assertNotEqual(self.c.post(self.path,json={'revision':task['revision'],'restore':True}).status_code,200)
        self.s.trash(self.pid,{'revision':task['revision'],'restore':True})
        self.assertEqual(self.discard(restore=True).status_code,200)
        self.assertEqual(self.s.store.get('runs','2'*32)['removed_at'],123)
        self.assertEqual(self.s.store.get('outputs','2'*32)['removed_at'],123)


if __name__=='__main__':unittest.main()
