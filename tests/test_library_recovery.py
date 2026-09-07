import copy
import json
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from PIL import Image
from test_local_server import LocalServerTests
from h3ui.generation.recovery import resolve_submission, assert_no_uncertain_runs
from h3ui.studio_store import Conflict
from h3ui.comfy import ComfyClient, ComfyError

class RecoveryTests(unittest.TestCase):
    setUp = LocalServerTests.setUp

    def test_uncertain_submission_exact_identity_and_no_resubmit(self):
        attempt={'id':'run-one','directory':str(self.root)}
        client=Mock()
        client._get.side_effect=lambda path: {'queue_running':[[0,'job-one',{}, {'client_id':'time-forest-run-one'}]],'queue_pending':[]} if path=='/queue' else {}
        pid, history, queued=resolve_submission(client,attempt)
        self.assertEqual(pid,'job-one'); self.assertTrue(queued); client.submit.assert_not_called()
        client._get.side_effect=lambda path: {'queue_running':[], 'queue_pending':[]} if path=='/queue' else {'unrelated':{'prompt':[0,'unrelated',{}, {'client_id':'prefix-time-forest-run-one'}]}}
        with self.assertRaisesRegex(ValueError,'待确认'):resolve_submission(client,attempt)
        client.submit.assert_not_called()
        p={'segments':[{'attempts':[{'tasks':[{'attempts':[{'status':'submitted'}]}]}]}]}
        with self.assertRaisesRegex(ValueError,'待确认'):assert_no_uncertain_runs(p,[0])

    def test_draft_persists_without_mutating_running_snapshot(self):
        p=self.st.create('text_story','running',15);before=copy.deepcopy(p)
        lease=self.st.jobs._reserve('v5_generate',p['id'])
        try:
            p['segments'][0]['prompt']='Next run only';p['segments'][0]['attempts']=[{'illegal':'do not copy'}]
            response=self.client.post('/api/v5/projects/'+p['id']+'/draft',json={'revision':0,'body':p})
            self.assertEqual(response.status_code,200,response.json)
            self.assertNotIn('attempts',response.json['body']['segments'][0])
            self.assertEqual(self.st.store.get(p['id']),before)
            from h3ui.generation.drafts import DraftStore
            self.assertEqual(DraftStore(self.st.store).get(p['id'])['body']['segments'][0]['prompt'],'Next run only')
            with self.assertRaises(Conflict):self.st.drafts.save(p['id'],{'revision':0,'body':p})
        finally:self.st.jobs._release(lease)

    def test_active_poll_retries_reads_only(self):
        with patch.object(ComfyClient,'_get',side_effect=[ComfyError('offline'),ComfyError('offline'),{'existing':{'status':{'status_str':'success'}}}]),patch('h3ui.comfy.time.sleep') as sleep,patch.object(ComfyClient,'submit') as submit:
            result=self.st.comfy.wait('existing')
            self.assertIn('existing',result);self.assertEqual(sleep.call_count,2);submit.assert_not_called()

    def test_local_task_done_means_lease_released(self):
        lib=self.app.config['ASSET_LIBRARY'];jobs=self.st.jobs
        lib.tasks.handlers['fixture']=lambda d,progress:{'ok':True}
        task=lib.tasks.submit('fixture',{'project':'fixture-project'},'fixture')
        deadline=time.monotonic()+5
        while time.monotonic()<deadline and lib.tasks.get(task['id'])['state'] not in ('done','failed'):time.sleep(.02)
        self.assertEqual(lib.tasks.get(task['id'])['state'],'done');self.assertFalse(jobs.is_busy('fixture-project'))
        lib.tasks.stop_event.set()
        if lib.tasks.thread:lib.tasks.thread.join(2)

    def test_launcher_never_runs_on_read_and_rejects_unverified_paths(self):
        with patch('h3ui.generation.launcher.subprocess.Popen') as spawn:
            self.assertFalse(self.client.get('/api/v5/engine/launcher').json['enabled'])
            self.assertEqual(self.client.post('/api/v5/engine/launcher',json={'enabled':True,'python':'missing.exe','script':'main.py'}).status_code,400)
            spawn.assert_not_called()

class ResultTests(unittest.TestCase):
    setUp = LocalServerTests.setUp

    def test_exact_candidate_metadata_and_composite_sources_survive_import(self):
        lib=self.app.config['ASSET_LIBRARY'];p=self.st.create('text_story','result fixture',15)
        directory=self.st.store.directory(p['id'])/'segments'/'fixture';directory.mkdir(parents=True)
        media=directory/'chosen.png';Image.new('RGBA',(64,64),(40,50,60,70)).save(media)
        (directory/'workflow.json').write_text(json.dumps({'20':{'class_type':'ChosenNode','inputs':{'seed':123}}}),encoding='utf-8')
        (directory/'manifest.json').write_text(json.dumps({'selected':[{'attempt':'chosen'}]}),encoding='utf-8')
        (directory/'prompt.txt').write_text('ACTUAL RUN TEXT',encoding='utf-8')
        internal=directory/'inner';internal.mkdir();(internal/'workflow.json').write_text(json.dumps({'internal_sampler':{'seed':321}}),encoding='utf-8')
        self.st.store.mutate(p['id'],lambda q:(q['segments'][0].update(attempts=[{'id':'chosen','directory':str(directory),'delivery':str(media),'seed':123,'tasks':[{'index':0,'selected':'inner-run','attempts':[{'id':'inner-run','directory':str(internal),'seed':321}]}]}]),q.update(export={'file':str(media),'created':456})))
        outputs=lib.results.outputs(p['id']);candidate=next(x for x in outputs if x['kind']=='candidate')
        first=lib.results.import_result({'output':candidate['id']},lambda *a:None)
        self.assertEqual(first['snapshot']['provenance']['records']['prompt']['20']['inputs']['seed'],123)
        self.assertEqual(first['snapshot']['record_prompt'],'ACTUAL RUN TEXT')
        self.assertEqual(first['snapshot']['provenance']['records']['tasks'][0]['runs'][0]['records']['prompt']['internal_sampler']['seed'],321)
        changed=lib.update(first['id'],first['revision'],{'record_prompt':'DOCUMENT EDIT'})
        self.assertEqual(changed['snapshot']['provenance']['records'],first['snapshot']['provenance']['records'])
        self.assertEqual(lib.results.import_result({'output':candidate['id']},lambda *a:None)['id'],first['id'])
        alternate=lib.ingest(media,'alternate',provenance={'type':'generated','records':{'prompt':{'seed':789}}},aid=first['id'],revision=changed['revision'])
        self.assertEqual(alternate['snapshot']['media'][-1]['provenance']['records']['prompt']['seed'],789)
        self.assertEqual(alternate['snapshot']['provenance']['records']['prompt']['20']['inputs']['seed'],123)
        from h3ui.asset_library.bindings import expand
        self.assertNotIn('ACTUAL RUN TEXT',json.dumps(expand(lib,first['id'])))
        final=lib.results.import_result({'output':next(x for x in outputs if x['kind']=='final')['id']},lambda *a:None)
        self.assertTrue(final['snapshot']['provenance']['composite']);self.assertNotIn('seed',final['snapshot']['provenance'])
        self.assertIn('segments',final['snapshot']['provenance']['records'])
        self.assertEqual(final['snapshot']['provenance']['records']['selected_runs'][0]['candidate'],'chosen')
        media.write_bytes(b'changed result')
        with self.assertRaisesRegex(ValueError,'变化'):lib.results.import_result({'output':candidate['id']},lambda *a:None)

if __name__=='__main__':unittest.main()
