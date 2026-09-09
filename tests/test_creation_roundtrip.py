"""Focused API boundaries and source preservation; no model or external socket."""
import copy
import json
import time
import uuid
from unittest.mock import patch
from pathlib import Path
from PIL import Image
from .test_creation_movie import MovieTests
from h3ui.creation.contracts import read,validate,digest


class RoundtripTests(MovieTests):
    def wait_job(self,jid):
        for _ in range(200):
            p,j=self.service.writing.find(jid,'creation_jobs')
            if j['state'] not in ('queued','running','preparing'):return p,j
            time.sleep(.01)
        self.fail('isolated worker did not finish')

    def test_scoped_rewrite_and_changed_basis(self):
        self.save('screenplay',dict(blocks=[dict(ref='tmp:a',text='第一段'),dict(ref='tmp:b',text='第二段')]))
        blocks=self.service.layer(self.p,'screenplay')['content']['blocks'];first,second=blocks
        self.configure_fake(Path('tests/fixtures/creation/llm/local_rewrite.ok.json').read_text(encoding='utf-8-sig'))
        context=self.service.writing.context(self.p['id'],'local_rewrite',[first['ref']],'只改第一段',layer='screenplay')
        job=self.post('/authoring/jobs',dict(provider_config_id='deepseek_authoring',context=context,source_revision=self.p['revision'],return_context=None))
        p,job=self.wait_job(job['job_id']);self.assertEqual(job['state'],'succeeded',job);candidate=p['candidates'][-1]
        self.post('/authoring/projects/'+p['id']+'/candidates/apply',dict(revision=p['revision'],candidate_id=candidate['candidate_id'],base_content_hash=candidate['base_content_hash'],edited_payload=None))
        p=self.service.get(p['id']);changed=self.service.layer(p,'screenplay')['content']['blocks'];self.assertEqual(changed[1],second);self.assertEqual(changed[0]['ref'],first['ref']);self.assertNotEqual(changed[0]['text'],first['text'])
        self.p=self.service.snapshot(p['id']);self.configure_fake(Path('tests/fixtures/creation/llm/screenplay_draft.ok.json').read_text(encoding='utf-8-sig'));job=self.start_writing()
        self.p=self.service.snapshot(p['id']);self.save('intent',dict(story_text='新故事依据',target_duration_seconds=30,reference_ids=[],preferences=''))
        # Existing basis text changed, not just a task progress revision.
        row=self.service.layer(self.p,'screenplay');body=copy.deepcopy(row['content']);body['blocks'][1]['text']='新第二段';self.save('screenplay',body)
        c=self.p['candidates'][-1];response=self.c.post('/api/v5/authoring/projects/'+p['id']+'/candidates/apply',json=dict(request_key=uuid.uuid4().hex,revision=self.p['revision'],candidate_id=c['candidate_id'],base_content_hash=c['base_content_hash'],edited_payload=None));self.assertEqual(response.status_code,409)

    def test_image_handoff_return_is_explicit_and_fixed(self):
        self.save('intent',dict(story_text='林间车站',target_duration_seconds=30,reference_ids=[],preferences=''))
        image=self.root/'fixture.png';Image.new('RGB',(32,24),'white').save(image)
        asset=self.service.library.ingest(image,'隔离参考',key='fixture-image');fixed=asset['snapshot'];m=fixed['media'][0]
        self.post('/authoring/projects/'+self.p['id']+'/references',dict(revision=self.p['revision'],asset=asset['id'],version=fixed['id'],media=m['id'],purpose='scene',subject=''))
        self.p=self.service.snapshot(self.p['id']);ref=self.p['creation_references'][0]
        result=self.post('/authoring/projects/'+self.p['id']+'/image-handoffs',dict(revision=self.p['revision'],target=dict(project_id=self.p['id'],layer='intent',target_ids=[]),source_content_hash=self.service.layer_hash(self.p,'intent'),reference_purpose='composition',image_prompt_text='车站的一张构图研究',reference_ids=[ref['id']],return_context=None))
        h=result['handoff'];images=self.app.config['IMAGE_STUDIO'];task=images.store.get('tasks',h['image_task_id'],h['image_project_id']);self.assertTrue(task['A']);self.assertEqual(task['prompt'],'车站的一张构图研究');self.assertEqual(images.store.all('runs',h['image_project_id']),[])
        self.assertEqual(self.c.get('/api/v5/projects/'+h['image_project_id']).status_code,200)
        self.p=self.service.snapshot(self.p['id']);before=copy.deepcopy(self.p['content']);plan=self.post('/authoring/projects/'+self.p['id']+'/image-bind/preflight',dict(revision=self.p['revision'],handoff_id=h['handoff_id'],asset_ref=asset['id'],asset_version=fixed['id'],mode='replace_active'))
        self.assertEqual(before,self.service.get(self.p['id'])['content'])
        self.post('/authoring/projects/'+self.p['id']+'/image-bind/apply',dict(revision=self.p['revision'],plan_id=plan['plan_id'],plan_hash=plan['plan_hash'],selected_change_ids=[plan['changes'][0]['change_id']]))
        p=self.service.get(self.p['id']);v=self.service.layer(p,'visual_references')['content']['references'][0];self.assertEqual(v['asset_version'],fixed['id']);self.assertTrue(v['active'])

    def test_twelve_contracts_needs_input_keep_prose(self):
        self.setup_movie();self.p=self.service.snapshot(self.p['id'])
        calls=[]
        for spec in read('配套清单/llm-task-registry.json')['tasks']:
            task=spec['task_type'];mode=spec.get('prompt_mode');targets=[self.sid] if task in ('h3_prompt','local_rewrite') else []
            sample=Path('tests/fixtures/creation/llm')/(spec['contract_key']+'.needs_input.json')
            calls=self.configure_fake(sample.read_text(encoding='utf-8-sig'))
            before=copy.deepcopy(self.service.get(self.p['id'])['content']['layers'])
            context=self.service.writing.context(self.p['id'],task,targets,'隔离检查',mode,'segment' if task=='local_rewrite' else None)
            p=self.service.get(self.p['id']);job=self.post('/authoring/jobs',dict(provider_config_id='deepseek_authoring',context=context,source_revision=p['revision'],return_context=None));p,j=self.wait_job(job['job_id'])
            self.assertEqual(j['state'],'succeeded',(spec['contract_key'],j));self.assertFalse(p['candidates'][-1]['applicable']);self.assertEqual(p['content']['layers'],before);self.assertEqual(len(calls),1)

    def test_take_removal_recycle_and_unknown_never_replays(self):
        self.setup_movie();take=self.generate();pid=self.movie['id']
        data=dict(revision=self.movie['revision'],record=take['take_id'],removed=True)
        self.post('/projects/'+pid+'/records/visibility',data);self.movie=self.service.snapshot(pid)
        index=self.c.get('/api/v5/recycle-bin?category=generations').get_json();self.assertTrue(any(r['id']==take['take_id'] for r in index['items']))
        self.post('/projects/'+pid+'/records/visibility',dict(data,revision=self.movie['revision'],removed=False));self.movie=self.service.snapshot(pid);self.assertEqual(self.movie['movie_takes'][0]['state'],'available')
        self.command('adopt',dict(segment_id=self.sid,take_id=take['take_id']));response=self.c.post('/api/v5/projects/'+pid+'/records/visibility',json=dict(data,revision=self.movie['revision']));self.assertEqual(response.status_code,409)
        p=self.service.get(pid);job=p['creation_jobs'][-1];job.update(state='submission_unknown',provider_request_id='unverified');self.service.store.save(p,p['revision'])
        self.service.movie.execution.resolve_unknown(job['job_id'],close=True);self.assertEqual(self.service.writing.find(job['job_id'],'creation_jobs')[1]['state'],'cancelled')
        self.assertEqual(len(self.service.get(pid)['movie_takes']),1)

    def test_downstream_uses_fixed_upstream_and_never_follows_new_adoption(self):
        self.setup_movie();a=self.sid;first=self.generate()
        self.p=self.service.snapshot(self.p['id']);segments=copy.deepcopy(self.service.layer(self.p,'segment')['content']['segments'])
        segments.append(dict(ref='tmp:tail',shot_ref=segments[0]['shot_ref'],text='她继续前行',planned_seconds=5,dependency=dict(kind='upstream_tail',upstream_ref=a)))
        b=self.save('segment',dict(segments=segments))['id_map']['tmp:tail']
        self.save('prompt',dict(prompt_mode='full',profile_id='movie.tail.dance_split',payload=dict(prompt_text='She continues walking. Station ambience.',used_reference_keys=[])),[b])
        row=self.service.layer(self.p,'prompt',[b]);self.post('/authoring/projects/'+self.p['id']+'/confirm',dict(revision=self.p['revision'],layer='prompt',target_ids=[b],content_hashes=dict(prompt=row['content_hash'])))
        self.p=self.service.snapshot(self.p['id']);plan=self.command('sync/preview',dict(source_project_id=self.p['id'],source_revision=self.p['revision'],target_segment_ids=[b]));self.command('sync/apply',dict(plan_id=plan['plan_id'],plan_hash=plan['plan_hash'],selected_change_ids=[b]))
        draft=self.service.movie.draft(self.service.get(self.movie['id']),b);draft.update(upstream_take_id=first['take_id'],upstream_range=dict(in_ms=0,out_ms=5000));self.command('generation-draft',draft)
        def fake_tail(file,start,end,directory,width,height,input_root):
            video=directory/'context.mp4';audio=directory/'context.wav';video.write_bytes(b'fake-video-tail');audio.write_bytes(b'fake-audio-tail')
            from h3ui.studio_media import digest as file_hash
            return dict(kind='external_decoded_av',frame_count=22,audio_frames=24,video=video.relative_to(input_root).as_posix(),audio=audio.relative_to(input_root).as_posix(),video_sha256=file_hash(video),audio_sha256=file_hash(audio))
        self.service.movie.execution.tail=fake_tail;self.sid=b;tail=self.generate();frozen=copy.deepcopy(self.service.get(self.movie['id'])['artifacts'][tail['snapshot_id']]);self.assertEqual(frozen['upstream_take_id'],first['take_id'])
        self.sid=a;second=self.generate();self.command('adopt',dict(segment_id=a,take_id=second['take_id']))
        self.assertEqual(self.service.get(self.movie['id'])['artifacts'][tail['snapshot_id']],frozen)
        self.assertEqual(self.service.movie.draft(self.service.get(self.movie['id']),b)['upstream_take_id'],first['take_id'])
        self.command('adopt',dict(segment_id=b,take_id=tail['take_id']));self.command('edit/initialize',dict(expected_uninitialized=True))
        pf=self.command('export/preflight',dict(edit_content_hash=self.movie['edit_content_hash'],output=dict(width=640,height=360,fps_num=24,fps_den=1,fit='contain',audio_policy='preserve_or_silence',container='mp4')))
        self.assertEqual(len(pf['seam_warnings']),1)
        denied=self.c.post('/api/v5/movie/projects/'+self.movie['id']+'/exports',json=dict(request_key=uuid.uuid4().hex,revision=self.movie['revision'],preflight_id=pf['preflight_id'],preflight_hash=pf['input_hash'],confirmed_partial_export=False));self.assertEqual(denied.status_code,400)
        job=self.command('exports',dict(preflight_id=pf['preflight_id'],preflight_hash=pf['input_hash'],confirmed_partial_export=False,accepted_seams=[pf['seam_warnings'][0]['id']]))
        p,j=self.wait_job(job['job_id']);self.assertEqual(j['state'],'succeeded');self.assertEqual(len(p['movie_exports'][-1]['manifest']['export_manifest']['accepted_seams']),1)

    def test_movie_collection_provenance_and_both_descendant_views(self):
        from h3ui.asset_library.origins import AssetOrigins
        from h3ui.asset_library.descendants import descendants
        from h3ui.asset_library.generation_descendants import generation_descendants
        from h3ui.prompt_library.records import project_records,asset_records
        image=self.root/'source.png';Image.new('RGB',(24,24),'white').save(image);asset=self.service.library.ingest(image,'来源参考',key='source-reference');version=asset['snapshot']['id'];medium=asset['snapshot']['media'][0]
        self.save('visual_references',dict(references=[dict(id='tmp:visual',scope_target_id=self.p['id'],purpose='composition',asset_ref=asset['id'],asset_version=version,intent_text='',control_data_artifact_id=None,active=True)]))
        self.setup_movie();take=self.generate();pid=self.movie['id']
        with patch('h3ui.asset_library.media.inspect',return_value=dict(kind='video',mime='video/mp4',extension='.mp4',duration=5,width=640,height=360)),patch('h3ui.asset_library.media.preview'):
            first=self.command('ingest',dict(result_id=take['take_id'],asset_title='隔离电影候选'))
            again=self.command('ingest',dict(result_id=take['take_id'],asset_title='隔离电影候选'))
        self.assertEqual(first['changed_ids'],again['changed_ids']);created=self.service.library.store.get(first['changed_ids'][0]);mid=created['snapshot']['media'][0]['id']
        origins=AssetOrigins(self.service.library,self.service.st,self.app.config['IMAGE_STUDIO']);view=origins.read(created['id'],created['snapshot']['id'],mid)
        self.assertTrue(view['parameters']);self.assertEqual(view['chain'][0]['project']['id'],pid)
        self.assertTrue(any(r.get('asset')==asset['id'] for r in view['lineage']['rows']))
        self.assertTrue(descendants(origins,asset['id'],version,medium['id'])['rows'])
        self.assertTrue(generation_descendants(origins,asset['id'],version,medium['id'])['rows'])
        self.assertTrue(project_records(self.app.config,pid,{'run':take['take_id']}))
        prompts=asset_records(self.app.config,created['id'],created['snapshot']['id'],mid);self.assertEqual(prompts[0]['source']['family'],'h3')
