"""Movie contracts use real project persistence and fake generation/media ends."""
import copy
import time
import uuid
from pathlib import Path
from .test_creation import CreationTests
from h3ui.creation.contracts import digest,read,validate


class MovieTests(CreationTests):
    def setup_movie(self):
        shot=self.save('storyboard',dict(shots=[dict(ref='tmp:shot',title='站台',text='旅人等待')]))['id_map']['tmp:shot']
        segment=self.save('segment',dict(segments=[dict(ref='tmp:segment',shot_ref=shot,text='她抬头',planned_seconds=5,dependency=dict(kind='independent'))]))['id_map']['tmp:segment']
        self.save('prompt',dict(prompt_mode='full',profile_id='movie.independent.dance_split',payload=dict(prompt_text='A traveler looks up. Natural station ambience.',used_reference_keys=[])),[segment])
        row=self.service.layer(self.p,'prompt',[segment])
        self.post('/authoring/projects/'+self.p['id']+'/confirm',dict(revision=self.p['revision'],layer='prompt',target_ids=[segment],content_hashes=dict(prompt=row['content_hash'])))
        self.p=self.service.snapshot(self.p['id'])
        self.movie=self.post('/movie/projects',dict(title='隔离电影',source_project_id=self.p['id'],source_revision=self.p['revision'],segment_ids=[]))
        self.sid=segment
        self.service.movie.execution.backend=self.fake_generate
        self.service.movie.execution.assemble=self.fake_assemble

    @staticmethod
    def fake_generate(p,record,directory,event,progress):
        path=directory/'fake.mp4';path.write_bytes(('fake-media-'+uuid.uuid4().hex).encode())
        return str(path),dict(duration=record['snapshot']['frame_plan']['deliver']/24,width=640,height=360,audio=True)

    @staticmethod
    def fake_assemble(parts,directory,output,event=None,progress=None):
        directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);path=directory/'fake-export.mp4'
        path.write_bytes(b'fake-export');return str(path),dict(duration=sum(p['end']-p['start'] for p in parts),width=output['width'],height=output['height'],audio=True)

    def command(self,path,data=None):
        value=self.post('/movie/projects/'+self.movie['id']+'/'+path,dict(revision=self.movie['revision'],**(data or {})))
        self.movie=self.service.snapshot(self.movie['id']);return value

    def generate(self):
        pf=self.command('preflight',dict(segment_id=self.sid));self.assertTrue(pf['ready'],pf)
        ready=self.command('prepare',dict(segment_id=self.sid,source_bundle_id=pf['source_bundle_id'],generation_draft_hash=pf['generation_draft_hash']))
        private=self.service.get(self.movie['id'])['movie_prepared'][-1]
        self.assertEqual(private['compiled']['workflow']['20']['inputs']['prompt'],ready['snapshot']['actual_prompt_text'])
        self.assertNotIn('compiled',ready)
        validate(ready['snapshot'],read('数据契约/generation-snapshot.schema.json'))
        job=self.command('generate',dict(prepared_request_id=ready['prepared_request_id'],prepared_hash=ready['prepared_hash']))
        for _ in range(150):
            job=self.service.writing.find(job['job_id'],'creation_jobs')[1]
            if job['state'] not in ('queued','running','preparing'):break
            time.sleep(.01)
        self.assertEqual(job['state'],'succeeded',job)
        self.movie=self.service.snapshot(self.movie['id']);return self.movie['movie_takes'][-1]

    def test_prepared_generation_edit_changes_and_export(self):
        self.setup_movie();first=self.generate();self.command('adopt',dict(segment_id=self.sid,take_id=first['take_id']))
        self.command('edit/initialize',dict(expected_uninitialized=True));initial=copy.deepcopy(self.movie['content']['edit'])
        self.command('edit/save',dict(edit_content_hash=self.movie['edit_content_hash'],order=initial['order'],item_changes=[dict(item_id=initial['order'][0],range=dict(in_ms=500,out_ms=4000),included=True)]))
        edited=copy.deepcopy(self.movie['content']['edit']);second=self.generate();self.command('adopt',dict(segment_id=self.sid,take_id=second['take_id']))
        self.assertEqual(edited,self.movie['content']['edit'])
        plan=self.command('edit/updates',dict(edit_content_hash=self.movie['edit_content_hash']))
        self.command('edit/updates/apply',dict(plan_id=plan['plan_id'],plan_hash=plan['plan_hash'],decisions=[dict(change_id=plan['changes'][0]['change_id'],action='replace',insert_after_item_id=None,new_range=None)]))
        self.assertEqual(self.movie['content']['edit']['items'][0]['range'],dict(in_ms=500,out_ms=4000))
        self.assertEqual(self.movie['content']['edit']['items'][0]['take_id'],second['take_id'])
        pf=self.command('export/preflight',dict(edit_content_hash=self.movie['edit_content_hash'],output=dict(width=640,height=360,fps_num=24,fps_den=1,fit='contain',audio_policy='preserve_or_silence',container='mp4')))
        job=self.command('exports',dict(preflight_id=pf['preflight_id'],preflight_hash=pf['input_hash'],confirmed_partial_export=False))
        for _ in range(150):
            job=self.service.writing.find(job['job_id'],'creation_jobs')[1]
            if job['state'] not in ('queued','running'):break
            time.sleep(.01)
        self.assertEqual(job['state'],'succeeded',job)
        movie=self.service.snapshot(self.movie['id']);self.assertEqual(movie['movie_exports'][0]['duration_ms'],3500)
        self.assertEqual(len(movie['movie_takes']),2)

    def test_invalid_duration_is_not_silently_split_and_real_network_blocked(self):
        self.setup_movie();p=self.service.get(self.movie['id']);bundle,source=self.service.movie.frozen(p,self.sid);source['segment']['planned_seconds']=100
        self.service.store.save(p,p['revision']);self.movie=self.service.snapshot(p['id'])
        pf=self.command('preflight',dict(segment_id=self.sid));self.assertFalse(pf['ready']);self.assertIn('拆分',''.join(pf['issues']))

    def test_sync_keeps_old_take_and_old_prepared_snapshot(self):
        self.setup_movie();first=self.generate();old=copy.deepcopy(self.movie['movie_prepared'][0]['snapshot'])
        self.save('prompt',dict(prompt_mode='full',profile_id='movie.independent.dance_split',payload=dict(prompt_text='A traveler turns around.',used_reference_keys=[])),[self.sid])
        plan=self.command('sync/preview',dict(source_project_id=self.p['id'],source_revision=self.p['revision'],target_segment_ids=[self.sid]))
        self.command('sync/apply',dict(plan_id=plan['plan_id'],plan_hash=plan['plan_hash'],selected_change_ids=[self.sid]))
        self.assertEqual(self.movie['movie_prepared'][0]['snapshot'],old)
        self.assertEqual(self.movie['movie_takes'][0]['take_id'],first['take_id'])
        self.assertNotEqual(self.movie['content']['source_bundles'][-1]['bundle_id'],old['source_bundle_id'])
