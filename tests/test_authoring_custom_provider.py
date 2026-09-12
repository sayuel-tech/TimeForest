"""Custom provider configuration reaches requests; no actual model or credentials."""
import copy,json,unittest
from pathlib import Path
from . import test_creation
from h3ui.creation.providers import endpoint

class CustomProviderTests(unittest.TestCase):
    def setUp(self):
        self.c=test_creation.CreationTests();self.c.setUp();self.addCleanup(self.c.doCleanups)

    def test_custom_endpoint_model_and_json_setting_reach_new_jobs(self):
        sample=Path('tests/fixtures/creation/llm/screenplay_draft.ok.json').read_text(encoding='utf-8-sig')
        self.c.configure_fake(sample);calls=[]
        class Fake:
            def send(self,config,secret,payload=None,resource=None):
                calls.append((copy.deepcopy(config),copy.deepcopy(payload)))
                return {'choices':[{'message':{'content':sample},'finish_reason':'stop'}]}
        self.c.service.writing.providers.transport=Fake()
        config=self.c.service.writing.providers.list()[0]
        config.update(provider_kind='openai_compatible',base_url='https://custom.invalid/gateway/v1/chat/completions',model_id='my-model-a',structured_mode='prompt_json',max_output_tokens=2048)
        self.c.post('/authoring/providers/save',{'config':config})
        job=self.c.start_writing();self.assertEqual(job['state'],'succeeded',job)
        self.assertEqual(calls[0][1]['model'],'my-model-a');self.assertNotIn('response_format',calls[0][1]);self.assertEqual(calls[0][1]['max_tokens'],2048)
        self.assertEqual(endpoint(calls[0][0]['base_url'],'chat/completions'),config['base_url'])
        frozen=copy.deepcopy(self.c.service.writing.find(job['job_id'],'creation_jobs')[1]['config'])
        config.update(model_id='my-model-b',structured_mode='json_object')
        self.c.post('/authoring/providers/save',{'config':config});self.c.p=self.c.service.snapshot(self.c.p['id'])
        self.assertEqual(self.c.start_writing()['state'],'succeeded')
        self.assertEqual(calls[1][1]['model'],'my-model-b');self.assertEqual(calls[1][1]['response_format'],{'type':'json_object'})
        self.assertEqual(self.c.service.writing.find(job['job_id'],'creation_jobs')[1]['config'],frozen)
        self.assertNotIn('fixture-only-key',json.dumps(self.c.c.get('/api/v5/authoring/providers').json))

    def test_deepseek_and_reserved_provider_rules_remain(self):
        config=self.c.service.writing.providers.list()[0];config.update(enabled=True,structured_mode='prompt_json')
        result=self.c.c.post('/api/v5/authoring/providers/save',json={'request_key':'bad','config':config})
        self.assertEqual(result.status_code,400)
        config.update(provider_kind='lm_studio',structured_mode='json_object')
        self.assertFalse(self.c.post('/authoring/providers/save',{'config':config})['enabled'])

if __name__=='__main__':unittest.main()
