"""Candidate removal is reversible metadata, exercised through real isolated APIs."""
import unittest
import json
import subprocess
from pathlib import Path
from unittest.mock import patch
from tests import test_task_center as fixtures


class CandidateRecordsTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.TaskCenterTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=self.f.s;self.st=self.f.st;self.c=self.f.c

    def change(self,pid,rid,removed=True,revision=None,segment=None):
        if revision is None:
            revision=(self.s.store.project(pid) if self.s.store.exists(pid) else self.st.store.get(pid))['revision']
        return self.c.post('/api/v5/projects/'+pid+'/records/visibility',json=dict(record=rid,removed=removed,revision=revision,segment=segment))

    def image(self,selected=False):
        run=self.f.run_record('a'*32,'success')
        path=self.s.store.directory(self.f.pid)/'test-result.png';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'original fixture bytes')
        out=dict(id=run['id'],run=run['id'],project=self.f.pid,task=run['task'],path=str(path),selected=selected,library={'asset':'existing','version':'fixed'})
        self.s.store.put('outputs',out);return run,out,path

    def test_image_remove_restore_preserves_files_snapshot_and_library(self):
        run,out,path=self.image()
        self.assertEqual(self.change(self.f.pid,run['id']).status_code,200)
        data=self.c.get('/api/v5/projects/'+self.f.pid).get_json()
        self.assertTrue(data['runs'][0]['removed_at']);self.assertTrue(data['outputs'][0]['removed_at'])
        self.assertEqual(data['outputs'][0]['library'],out['library']);self.assertEqual(data['runs'][0]['snapshot'],run['snapshot'])
        self.assertEqual(path.read_bytes(),b'original fixture bytes')
        self.assertEqual(self.s.summaries()[0]['outputs'],0)
        self.assertEqual(self.change(self.f.pid,run['id'],False).status_code,200)
        self.assertFalse(self.s.store.get('outputs',out['id']).get('removed_at'))
        self.f.get.assert_not_called();self.f.post.assert_not_called()

    def test_selected_running_unknown_and_revision_conflicts_rejected(self):
        run,out,path=self.image(selected=True)
        self.assertEqual(self.change(self.f.pid,run['id']).status_code,409)
        self.s.store.mutate('outputs',out['id'],lambda o:o.update(selected=False))
        self.assertEqual(self.change(self.f.pid,run['id'],revision=0).status_code,409)
        for state in ('running','unknown','waiting'):
            self.s.store.mutate('runs',run['id'],lambda r:r.update(state=state))
            self.assertEqual(self.change(self.f.pid,run['id']).status_code,409)
        self.assertEqual(path.read_bytes(),b'original fixture bytes')

    def test_removed_image_cannot_be_selected_or_reused(self):
        run,out,_=self.image();self.assertEqual(self.change(self.f.pid,run['id']).status_code,200)
        for action,body in [('select',{}),('continue',{'revision':self.s.store.project(self.f.pid)['revision']}),('library',{})]:
            response=self.c.post(f'/api/v5/image-projects/{self.f.pid}/outputs/{out["id"]}/{action}',json=body)
            self.assertEqual(response.status_code,409)

    def test_video_three_modes_remove_restore_and_selected_protection(self):
        for mode in ('swap','image_story','text_story'):
            p=self.st.create(mode,'历史清理',15)
            def seed(q):
                if not q['segments']:q['segments']=[self.st.new_segment(dict(index=0))]
                q['segments'][0].update(attempts=[dict(id='old',status='complete',seed=0,created=1),dict(id='kept',status='complete',created=2)],selected='kept')
            p=self.st.store.mutate(p['id'],seed);segment=p['segments'][0]['id']
            self.assertEqual(self.change(p['id'],'kept',segment=segment).status_code,409)
            self.assertEqual(self.change(p['id'],'old',segment=segment).status_code,200)
            after=self.st.store.get(p['id']);self.assertEqual(after['segments'][0]['selected'],'kept')
            self.assertEqual(len(after['segments'][0]['attempts']),2)
            self.assertTrue(after['segments'][0]['attempts'][0]['removed_at'])
            with self.assertRaisesRegex(ValueError,'候选已移除'):
                self.st.approve(p['id'],0,attempt='old')
            self.assertEqual(self.change(p['id'],'old',False,segment=segment).status_code,200)

    def test_video_busy_and_uncertain_refuse_cleanup(self):
        p=self.st.create('text_story','不要清理执行中记录',15)
        p=self.st.store.mutate(p['id'],lambda q:q['segments'][0].update(attempts=[dict(id='old',status='interrupted')]))
        segment=p['segments'][0]['id']
        self.assertEqual(self.change(p['id'],'old',segment=segment).status_code,409)
        lease=self.st.jobs._reserve('v5_generate',p['id'])
        self.assertEqual(self.change(p['id'],'old',segment=segment).status_code,409)
        self.st.jobs._release(lease)

    def test_stale_video_library_token_cannot_publish_removed_candidate(self):
        p=self.st.create('text_story','结果入库边界',15)
        path=self.st.store.directory(p['id'])/'old.mp4';path.write_bytes(b'original result')
        p=self.st.store.mutate(p['id'],lambda q:q['segments'][0].update(attempts=[dict(id='old',status='complete',seed=0,created=1,delivery=str(path))]))
        results=self.f.app.config['ASSET_LIBRARY'].results
        token=results.outputs(p['id'])[0]['id']
        self.assertEqual(self.change(p['id'],'old',segment=p['segments'][0]['id']).status_code,200)
        self.assertEqual(results.outputs(p['id']),[])
        with patch.object(results.lib,'ingest') as ingest:
            with self.assertRaisesRegex(ValueError,'候选已移除'):results.import_result({'output':token},lambda *args:None)
            ingest.assert_not_called()
        self.assertEqual(path.read_bytes(),b'original result')

    def test_wrong_project_and_stale_restore_cannot_change_records(self):
        run,out,_=self.image();other=self.s.create('另一个项目')
        self.assertEqual(self.change(other['id'],run['id']).status_code,409)
        initial=self.s.store.project(self.f.pid)['revision']
        self.assertEqual(self.change(self.f.pid,run['id']).status_code,200)
        self.assertEqual(self.change(self.f.pid,run['id'],False,revision=initial).status_code,409)
        self.assertTrue(self.s.store.get('runs',run['id'])['removed_at'])

    def test_real_image_api_renderer_and_save_keep_removal(self):
        run,out,_=self.image();self.change(self.f.pid,run['id'])
        project=self.c.get('/api/v5/projects/'+self.f.pid).get_json()
        script="""
import {chosenOutput,imageRecordHistory} from './static/studio/features/image-results/workspace-view.js';
let raw='';for await(const chunk of process.stdin)raw+=chunk;
const p=JSON.parse(raw),task=p.tasks[0];
if(chosenOutput(p,task))throw Error('removed candidate still chosen');
if(!imageRecordHistory(p,task).includes('data-record-restore'))throw Error('restore missing');
p.name='saved after removal';process.stdout.write(JSON.stringify(p));
"""
        rendered=subprocess.run(['node','--input-type=module','-e',script],input=json.dumps(project),text=True,capture_output=True,check=True)
        edited=json.loads(rendered.stdout)
        plan=self.c.post('/api/v5/image-projects/'+self.f.pid+'/change-plan',json=edited)
        self.assertEqual(plan.status_code,200)
        saved=self.c.post('/api/v5/image-projects/'+self.f.pid+'/apply',json={'token':plan.get_json()['token']})
        self.assertEqual(saved.status_code,200)
        self.assertEqual(saved.get_json()['name'],'saved after removal')
        self.assertTrue(saved.get_json()['outputs'][0]['removed_at'])
        self.assertEqual(saved.get_json()['runs'][0]['snapshot'],run['snapshot'])
        self.assertEqual(self.change(self.f.pid,run['id'],False).status_code,200)
        self.assertFalse(self.s.snapshot(self.f.pid)['outputs'][0]['selected'])


if __name__=='__main__':unittest.main()
