import copy,unittest
import test_studio as fixture

class InputRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.StudioAcceptance.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):fixture.StudioAcceptance.tearDownClass.__func__(cls)
    def test_preview_resolves_draft_ids_without_saving(self):
        p=self.st.create('image_story','输入草稿',30)
        a=fixture.StudioAcceptance.asset(self,p)
        p=self.st.store.get(p['id']);draft=copy.deepcopy(p['segments']);draft[0]['assets']=[a['id']]
        r=self.client.post(f"/api/v5/projects/{p['id']}/input-preview",json=dict(segment=draft[0]['id'],segments=draft,settings=p['settings']))
        self.assertEqual(r.status_code,200,r.json);self.assertEqual(r.json['inputs'][0]['asset_id'],a['id'])
        self.assertEqual(r.json['inputs'][0]['tag'],'<Picture 1>')
        self.assertEqual(self.st.store.get(p['id']),p)
        draft[0]['assets']=['foreign-id']
        r=self.client.post(f"/api/v5/projects/{p['id']}/input-preview",json=dict(segment=draft[0]['id'],segments=draft))
        self.assertEqual(r.status_code,400);self.assertEqual(self.st.store.get(p['id']),p)
    def test_template_without_reference_is_only_placeholder(self):
        p=self.st.create('swap','无素材示例');r=self.client.post(f"/api/v5/projects/{p['id']}/swap-template",json={})
        self.assertEqual(r.status_code,200,r.json);self.assertTrue(r.json['placeholder']);self.assertEqual(r.json['template_version'],3)
        self.assertEqual(self.st.store.get(p['id']),p)
        r=self.client.post(f"/api/v5/projects/{p['id']}/swap-template",json={'segments':[{'id':'stale'}]})
        self.assertEqual(r.status_code,400)
    def test_new_project_versions_are_explicit(self):
        for mode in ['swap','image_story','text_story']:
            r=self.client.post('/api/v5/projects',json=dict(mode=mode,name='版本核验',duration=15))
            self.assertEqual(r.status_code,200,r.json);self.assertEqual(r.json['input_prompt_version'],2)
            self.assertEqual(r.json['input_contract_version'],2)
            if mode=='swap':self.assertEqual(r.json['swap_prompt']['version'],3)

    def test_final_prompt_is_current_draft_without_saving_or_compiling(self):
        p=self.st.create('swap','最终正文')
        a=fixture.StudioAcceptance.asset(self,p)
        p=self.st.store.get(p['id'])
        p['segments']=[self.st.new_segment(dict(index=0,raw=124,head=0,tail=0,deliver=124))]
        p['segments'][0]['assets']=[a['id']]
        p=self.st.store.save(p,p['revision'])
        draft=copy.deepcopy(p['segments']);draft[0].update(swap_prompt_mode='custom',swap_custom_prompt='<Picture 1> replaces the performer in <Video 1>. Preserve motion.')
        payload=dict(revision=p['revision'],segment=draft[0]['id'],segments=draft,settings=p['settings'],swap_prompt=p['swap_prompt'])
        original_compile=self.st.recipes.compile
        self.st.recipes.compile=lambda *a,**k: (_ for _ in ()).throw(AssertionError('Preview must not compile or submit'))
        try:
            r=self.client.post(f"/api/v5/projects/{p['id']}/prompt-preview",json=payload)
            self.assertEqual(r.status_code,200,r.json);self.assertEqual(r.json['prompt'],draft[0]['swap_custom_prompt'])
            self.assertEqual(self.st.store.get(p['id']),p)
            draft[0].update(swap_prompt_mode='template',prompt='Keep the coat from the character reference.')
            r=self.client.post(f"/api/v5/projects/{p['id']}/prompt-preview",json=payload)
            self.assertIn(draft[0]['prompt'],r.json['prompt']);self.assertIn('subject_definitions:',r.json['prompt'])
            self.assertEqual(self.st.store.get(p['id']),p)
            payload['revision']-=1
            r=self.client.post(f"/api/v5/projects/{p['id']}/prompt-preview",json=payload)
            self.assertEqual(r.status_code,409)
        finally:self.st.recipes.compile=original_compile
