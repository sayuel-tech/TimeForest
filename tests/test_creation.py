"""Real Flask/StudioStore integration; all external sockets are denied."""
import json
import socket
import tempfile
import unittest
import uuid
import time
from pathlib import Path
from unittest.mock import patch
from h3ui import create_app
from h3ui.creation.contracts import digest,read,validate,loads


class CreationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.network=patch.object(socket.socket,'connect',side_effect=AssertionError('External network forbidden'))
        self.network.start();self.addCleanup(self.network.stop)
        cfg=dict(studio_data_dir=str(self.root/'projects'),data_dir=str(self.root/'legacy'),asset_library_dir=str(self.root/'library'),prompt_library_dir=str(self.root/'prompts'),
                 comfy_base_dir=str(self.root/'comfy'),comfy_input_dir=str(self.root/'input'),comfy_output_dir=str(self.root/'output'),comfy_url='http://127.0.0.1:1',
                 studio_disable_generation=True,studio_progress_disabled=True,image_assets_enabled=True,open_browser=False)
        file=self.root/'config.json';file.write_text(json.dumps(cfg),encoding='utf-8')
        self.app=create_app(str(file),recover_tasks=False);self.c=self.app.test_client();self.service=self.app.config['CREATION']
        self.p=self.post('/authoring/projects',dict(title='隔离剧本'))

    def post(self,path,data):
        r=self.c.post('/api/v5'+path,json={'request_key':uuid.uuid4().hex,**data})
        self.assertEqual(r.status_code,200,r.get_json());return r.get_json()

    def save(self,layer,content,targets=None):
        row=next((x for x in self.p['content']['layers'] if x['layer']==layer and x['target_ids']==(targets or [])),None)
        r=self.post('/authoring/projects/'+self.p['id']+'/save',dict(revision=self.p['revision'],layer=layer,target_ids=targets or [],base_content_hash=row['content_hash'] if row else None,update_mode='replace_scope',removed_target_ids=[],content=content))
        self.p=self.c.get('/api/v5/projects/'+self.p['id']).get_json();return r

    def test_create_save_reopen_conflict_and_movie_container(self):
        self.save('intent',dict(story_text='只写好一半',target_duration_seconds=90,reference_ids=[],preferences=''))
        self.assertEqual(self.p['content']['layers'][0]['content']['story_text'],'只写好一半')
        self.assertEqual(self.service.store.get(self.p['id'])['duration'],90)
        old=self.p['revision']
        self.save('screenplay',dict(blocks=[dict(ref='tmp:block',heading='开头',text='在林间醒来。')]))
        self.assertEqual(len(self.p['content']['layers'][1]['content']['blocks'][0]['ref']),32)
        r=self.c.post('/api/v5/authoring/projects/'+self.p['id']+'/confirm',json=dict(request_key='conflict',revision=old,layer='screenplay',target_ids=[],content_hashes={}))
        self.assertEqual(r.status_code,409)
        movie=self.post('/movie/projects',dict(title='先试开头',source_project_id=self.p['id'],source_revision=self.p['revision'],segment_ids=[]))
        self.assertEqual(movie['kind'],'movie');self.assertEqual(movie['content']['source_project_id'],self.p['id'])
        listing=self.c.get('/api/v5/projects').get_json();self.assertEqual({p['kind'] for p in listing['projects']},{'authoring','movie'})

    def test_stable_ids_dependency_cycle_and_idempotence(self):
        receipt=self.save('storyboard',dict(shots=[dict(ref='tmp:shot',title='林间',text='等待')]))
        shot=receipt['id_map']['tmp:shot']
        a,b='tmp:a','tmp:b'
        receipt=self.save('segment',dict(segments=[dict(ref=a,shot_ref=shot,text='A'),dict(ref=b,shot_ref=shot,text='B')]))
        a,b=receipt['id_map'][a],receipt['id_map'][b]
        previous=self.p['revision']
        data=dict(request_key='same',revision=previous,layer='intent',target_ids=[],base_content_hash=None,update_mode='replace_scope',removed_target_ids=[],content=dict(story_text='',target_duration_seconds=None,reference_ids=[],preferences=''))
        first=self.post('/authoring/projects/'+self.p['id']+'/save',data)
        self.assertEqual(first,self.post('/authoring/projects/'+self.p['id']+'/save',data))
        self.p=self.service.snapshot(self.p['id'])
        with self.assertRaises(ValueError):
            p=self.service.get(self.p['id']);row=self.service.layer(p,'segment');row['content']['segments'][0]['dependency']=dict(kind='upstream_tail',upstream_ref=b);row['content']['segments'][1]['dependency']=dict(kind='upstream_tail',upstream_ref=a);self.service.check_relationships(p)

    def configure_fake(self,text=None,finish='stop'):
        config=self.service.writing.providers.list()[0];config['enabled']=True
        self.post('/authoring/providers/save',dict(config=config))
        self.post('/authoring/providers/credential',dict(config_id=config['config_id'],secret='fixture-only-key'))
        calls=[]
        class Fake:
            def send(self,config,secret,payload=None,resource=None):
                calls.append((config,payload));return dict(choices=[dict(message=dict(content=text),finish_reason=finish)])
        self.service.writing.providers.transport=Fake();return calls

    def start_writing(self):
        context=self.service.writing.context(self.p['id'],'screenplay_draft',instruction='写出故事开头')
        job=self.post('/authoring/jobs',dict(provider_config_id='deepseek_authoring',context=context,source_revision=self.p['revision'],return_context=None))
        for _ in range(150):
            job=self.c.get('/api/v5/authoring/jobs/'+job['job_id']).get_json()
            if job['state'] not in ('queued','running'):break
            time.sleep(.01)
        return job

    def test_fake_chat_to_real_candidate_apply_and_capture(self):
        sample=Path('tests/fixtures/creation/llm/screenplay_draft.ok.json').read_text(encoding='utf-8-sig')
        calls=self.configure_fake(sample);job=self.start_writing()
        self.assertEqual(job['state'],'succeeded',job)
        self.assertEqual(calls[0][1]['model'],'deepseek-v4.1-flash-expires-on-0910')
        self.assertEqual(len(calls),1)
        self.p=self.service.snapshot(self.p['id']);candidate=self.p['candidates'][0]
        self.post('/authoring/projects/'+self.p['id']+'/candidates/apply',dict(revision=self.p['revision'],candidate_id=candidate['candidate_id'],base_content_hash=candidate['base_content_hash'],edited_payload=None))
        self.p=self.service.snapshot(self.p['id'])
        self.assertTrue(self.p['content']['layers'][0]['content']['blocks'])
        self.assertNotIn('fixture-only-key',json.dumps(self.c.get('/api/v5/authoring/providers').get_json()))
        self.assertTrue(self.app.config['PROMPT_LIBRARY'].items(self.p))

    def test_truncated_response_and_reserved_provider_do_not_retry(self):
        calls=self.configure_fake('{"partial":',finish='length');job=self.start_writing()
        self.assertEqual(job['failure_code'],'RESPONSE_TRUNCATED');self.assertEqual(len(calls),1)
        config=self.service.writing.providers.list()[0];config['provider_kind']='lm_studio';config['enabled']=True
        saved=self.post('/authoring/providers/save',dict(config=config));self.assertFalse(saved['enabled'])
        r=self.c.post('/api/v5/authoring/providers/discover',json=dict(request_key='reserved',config_id=config['config_id'],read_only=True))
        self.assertEqual(r.get_json()['code'],'PROVIDER_NOT_IMPLEMENTED');self.assertEqual(len(calls),1)

    def test_all_bundled_response_contracts_and_duplicate_json(self):
        for fixture in Path('tests/fixtures/creation/llm').glob('*.json'):
            contract=fixture.name.rsplit('.',2)[0]
            validate(loads(fixture.read_text(encoding='utf-8-sig')),read('数据契约/llm/'+contract+'.schema.json'))
        with self.assertRaises(ValueError):loads('{"payload":1,"payload":2}')


if __name__=='__main__':unittest.main()
