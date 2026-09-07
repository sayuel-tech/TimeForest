"""Global task operations use temporary stores and a fake engine only."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock
from h3ui import create_app
from h3ui.comfy import ComfyClient, ComfyCancelled, ComfyError


class TaskCenterTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root=Path(temp.name)
        cfg=json.loads(Path('config.example.json').read_text(encoding='utf-8'))
        cfg.update({k:str(root/k) for k in ('studio_data_dir','data_dir','asset_library_dir','comfy_input_dir','comfy_output_dir')})
        cfg.update(studio_disable_generation=True,studio_progress_disabled=True,image_assets_enabled=True,open_browser=False)
        path=root/'config.json';path.write_text(json.dumps(cfg),encoding='utf-8')
        self.get=patch.object(ComfyClient,'_get',return_value={}).start()
        self.post=patch.object(ComfyClient,'_post',return_value={'cancelled':True}).start()
        self.addCleanup(patch.stopall)
        self.app=create_app(str(path),recover_tasks=False);self.c=self.app.test_client()
        self.s=self.app.config['IMAGE_STUDIO'];self.st=self.app.config['STUDIO']
        self.p=self.s.create('图片项目');self.pid=self.p['id']
        self.wake=patch.object(self.s.runner,'wake').start()

    def run_record(self,rid,state,prompt=None):
        r=dict(id=rid,project=self.pid,task=self.p['tasks'][0]['id'],state=state,prompt_id=prompt,created=1,seed=0,snapshot={'prompt':'保留正文'})
        self.s.store.put('runs',r);return r

    def action(self,rid,action,**body):
        return self.c.post('/api/v5/tasks/action',json=dict(kind='image',project=self.pid,id=rid,action=action,**body))

    def test_list_exposes_cross_project_blocker_without_engine_calls(self):
        self.run_record('a'*32,'unknown','old-prompt')
        self.run_record('b'*32,'waiting')
        result=self.c.get('/api/v5/tasks')
        self.assertEqual(result.status_code,200)
        data=result.get_json();self.assertEqual(data['active_count'],2)
        waiting=next(t for t in data['tasks'] if t['id']=='b'*32)
        self.assertIn('待确认',waiting['note']);self.assertEqual(waiting['blocked_by'][0]['id'],'a'*32)
        self.get.assert_not_called();self.post.assert_not_called();self.wake.assert_not_called()

    def test_close_unknown_requires_confirmation_and_preserves_snapshot(self):
        before=self.run_record('a'*32,'unknown','old-prompt')
        self.assertEqual(self.action(before['id'],'close').status_code,409)
        self.assertEqual(self.action(before['id'],'close',confirmed=True).status_code,200)
        after=self.s.store.get('runs',before['id'])
        self.assertEqual(after['state'],'cancelled');self.assertEqual(after['snapshot'],before['snapshot'])
        self.assertEqual(after['prompt_id'],'old-prompt');self.assertTrue(after['closed_without_result'])
        self.post.assert_not_called()

    def test_close_refuses_existing_engine_evidence_and_owned_worker(self):
        r=self.run_record('a'*32,'unknown','old-prompt')
        for response in ({'queue_running':[[0,'old-prompt']]},{'old-prompt':{'status':{'status_str':'success'}}}):
            self.get.return_value=response
            self.assertEqual(self.action(r['id'],'close',confirmed=True).status_code,409)
            self.assertEqual(self.s.store.get('runs',r['id'])['state'],'unknown')
        self.get.return_value={}
        lease=self.st.jobs._reserve('image_recover',self.pid,'gpu')
        self.assertIsNotNone(lease)
        self.assertEqual(self.action(r['id'],'close',confirmed=True).status_code,409)
        self.st.jobs._release(lease)

    def test_stop_uses_exact_engine_job_never_global_interrupt(self):
        r=self.run_record('a'*32,'running','owned-prompt')
        self.get.return_value={'queue_running':[[0,'owned-prompt',{}, {'client_id':'time-forest-'+r['id']}]]}
        self.assertEqual(self.action(r['id'],'stop',confirmed=True).status_code,200)
        self.post.assert_called_once_with('/api/jobs/owned-prompt/cancel',{})
        self.assertEqual(self.s.store.get('runs',r['id'])['state'],'running')
        self.assertTrue(self.s.store.get('runs',r['id'])['stop_requested'])

    def test_cancel_waiting_has_no_engine_effect_and_wrong_project_rejected(self):
        r=self.run_record('a'*32,'waiting')
        bad=self.c.post('/api/v5/tasks/action',json=dict(kind='image',project='b'*32,id=r['id'],action='cancel',confirmed=True))
        self.assertNotEqual(bad.status_code,200)
        self.assertEqual(self.action(r['id'],'cancel',confirmed=True).status_code,200)
        self.assertEqual(self.s.store.get('runs',r['id'])['state'],'cancelled')
        self.post.assert_not_called();self.get.assert_not_called()

    def test_completed_history_never_enters_current_queue(self):
        for n,state in enumerate(('success','failed','cancelled','waiting')):self.run_record(str(n)*32,state)
        data=self.c.get('/api/v5/tasks').get_json()
        self.assertEqual([r['state'] for r in data['tasks']],['waiting'])
        self.assertEqual(len(self.s.store.all('runs')),4)

    def test_stop_rejects_other_clients_and_keeps_state_on_engine_error(self):
        r=self.run_record('a'*32,'running','owned-prompt')
        self.get.return_value={'queue_running':[[0,'owned-prompt',{}, {'client_id':'someone-else'}]]}
        self.assertEqual(self.action(r['id'],'stop',confirmed=True).status_code,409)
        self.post.assert_not_called()
        self.get.return_value={'queue_running':[[0,'owned-prompt',{}, {'client_id':'time-forest-'+r['id']}]]}
        self.post.side_effect=ComfyError('endpoint unsupported')
        self.assertEqual(self.action(r['id'],'stop',confirmed=True).status_code,409)
        self.assertEqual(self.s.store.get('runs',r['id'])['state'],'running')
        self.assertNotIn('stop_requested',self.s.store.get('runs',r['id']))

    def test_local_queue_cancel_is_conditional_and_old_active_rows_not_lost(self):
        local=self.app.config['ASSET_LIBRARY'].tasks
        with local.store.connect() as db:
            for n in range(105):
                db.execute('INSERT INTO local_tasks VALUES(?,?,?,?,?,?,?,?,?,?)',(str(n),'key'+str(n),'backup','{}','queued' if n==0 else 'done',0,'',None,n,n))
        data=self.c.get('/api/v5/tasks').get_json()
        self.assertEqual([(r['kind'],r['id']) for r in data['tasks']],[('local','0')])
        body=dict(kind='local',id='0',action='cancel',confirmed=True)
        self.assertEqual(self.c.post('/api/v5/tasks/action',json=body).status_code,200)
        self.assertEqual(self.c.post('/api/v5/tasks/action',json=body).status_code,409)
        self.assertEqual(self.c.get('/api/v5/tasks').get_json()['tasks'],[])

    def test_video_pause_sets_worker_and_project_flags(self):
        p=self.st.create('text_story','视频',15)
        lease=self.st.jobs._reserve('v5_generate',p['id'])
        body=dict(kind='video',project=p['id'],id=p['id'],action='pause',confirmed=True)
        self.assertEqual(self.c.post('/api/v5/tasks/action',json=body).status_code,200)
        self.assertTrue(self.st.jobs.current(p['id'])['stop_requested'])
        self.assertTrue(self.st.store.get(p['id'])['pause'])
        self.st.jobs._release(lease)
        self.assertEqual(self.c.get('/api/v5/tasks').get_json()['tasks'],[])
        self.get.assert_not_called();self.post.assert_not_called()

    def test_exact_cancel_wait_releases_pending_and_prefers_raced_success(self):
        client=self.st.comfy;self.assertTrue(client.cancel_job('mine'))
        self.get.return_value={}
        with self.assertRaises(ComfyCancelled):client.wait('mine')
        self.assertTrue(client.cancel_job('mine'))
        success={'mine':{'status':{'status_str':'success'}}}
        self.get.side_effect=[{}, {},success]
        self.assertEqual(client.wait('mine'),success)
        self.assertNotIn('mine',client._cancelled)

    def test_image_worker_preserves_cancel_and_releases_lease(self):
        r=self.run_record('a'*32,'running','mine')
        with patch.object(self.s.runner,'reconcile',side_effect=ComfyCancelled('stopped')):
            self.s.runner._dispatch()
        self.assertEqual(self.s.store.get('runs',r['id'])['state'],'cancelled')
        self.assertFalse(self.st.jobs.is_busy());self.assertTrue(self.s.runner.gpu_guard('v5_generate','other'))

    def test_closing_unknown_on_network_failure_changes_nothing(self):
        r=self.run_record('a'*32,'unknown','old-prompt')
        self.get.side_effect=ComfyError('offline')
        self.assertEqual(self.action(r['id'],'close',confirmed=True).status_code,409)
        self.assertEqual(self.s.store.get('runs',r['id']),r)
        self.wake.assert_not_called()

    def test_dispatcher_cannot_resurrect_record_closed_before_reservation(self):
        r=self.run_record('a'*32,'unknown','old-prompt')
        reserve=self.st.jobs._reserve
        def close_then_reserve(*args,**kwargs):
            self.assertEqual(self.action(r['id'],'close',confirmed=True).status_code,200)
            return reserve(*args,**kwargs)
        with patch.object(self.st.jobs,'_reserve',side_effect=close_then_reserve),patch.object(self.s.runner,'reconcile') as reconcile:
            self.s.runner._dispatch()
        reconcile.assert_not_called()
        self.assertEqual(self.s.store.get('runs',r['id'])['state'],'cancelled')

    def test_stop_before_video_worker_enters_chain_is_not_reset(self):
        p=self.st.create('text_story','准备中的视频',15)
        lease=self.st.jobs._reserve('v5_generate',p['id'])
        self.c.post('/api/v5/tasks/action',json=dict(kind='video',project=p['id'],id=p['id'],action='pause',confirmed=True))
        with patch.object(self.st,'generate_one') as generate:
            self.st.run_chain(p['id'],0,False)
        generate.assert_not_called();self.assertTrue(self.st.store.get(p['id'])['pause'])
        self.st.jobs._release(lease)

    def test_story_stop_keeps_first_internal_result_without_submitting_next(self):
        p=self.st.create('text_story','内部任务停止边界',15)
        self.st.store.mutate(p['id'],lambda q:q['segments'][0].update(prompt='隔离检查的人工正文'))
        tasks=[dict(id='t1',status='draft',attempts=[]),dict(id='t2',status='draft',attempts=[])]
        def view(pid):return {**self.st.store.get(pid),'segments':tasks}
        def first(pid,index):
            tasks[index].update(status='done',selected='kept')
            self.st.store.mutate(pid,lambda q:q.update(pause=True))
        worker=SimpleNamespace(store=SimpleNamespace(get=view),generate_one=Mock(side_effect=first))
        with patch('h3ui.studio_story.task_segments',return_value=tasks),patch.object(self.st,'previous',return_value=None),patch.object(self.st,'worker',return_value=worker):
            self.st.generate_story(p['id'],0)
        worker.generate_one.assert_called_once_with(p['id'],0)
        self.assertEqual(tasks[0]['selected'],'kept');self.assertEqual(tasks[1]['status'],'draft')
        self.assertIn('用户已停止后续执行',self.st.store.get(p['id'])['error'])

    def test_cancel_during_video_recovery_removes_uncertain_occupancy(self):
        p=self.st.create('text_story','恢复中的视频',15)
        def recorded(q):
            q.update(storyboard_version=0)
            q['segments'][0].update(status='interrupted',attempts=[dict(id='attempt',prompt_id='mine',status='interrupted',created=1)])
        self.st.store.mutate(p['id'],recorded)
        with patch('h3ui.generation.recovery.resolve_submission',return_value=('mine',{},True)),patch.object(self.st.comfy,'wait',side_effect=ComfyCancelled('用户停止')):
            self.st.recover(p['id'],0)
        self.assertEqual(self.st.store.get(p['id'])['segments'][0]['attempts'][0]['status'],'failed')
        self.assertEqual(self.c.get('/api/v5/tasks').get_json()['tasks'],[])


if __name__=='__main__':unittest.main()
