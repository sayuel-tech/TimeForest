"""Capability and conflict contracts; all data isolated and GPU submit forbidden."""
from test_studio import StudioAcceptance
from h3ui.studio_recipes import defaults

class CapabilityContracts(StudioAcceptance):
    def test_ref_conditioning_rejects_fl_only_model(self):
        p=self.new();p['settings']=defaults('dance_split')
        p['settings']['model']=defaults('official_text')['model']
        with self.assertRaisesRegex(ValueError,'Ref2VA'):
            self.st.edit_plan(p['id'],p)
    def test_capability_matches_compiler(self):
        catalog=self.st.recipes.catalog()
        self.assertEqual(catalog['contract_version'],1)
        for recipe in catalog['recipes']:
            keys={f['key'] for f in recipe['parameters']}
            self.assertEqual(recipe['capabilities']['native_fps'],24)
            self.assertEqual(recipe['capabilities']['lora_slots'],0 if recipe['official'] else 3)
            if recipe['id']=='dance_split':
                self.assertIn('split_step',keys);self.assertNotIn('refine_denoise',keys)
            if not recipe['two_pass']:self.assertNotIn('scale',keys)
        for mode in ['swap','image_story','text_story']:
            self.assertTrue(any(r['official'] and mode in r['modes'] for r in catalog['recipes']))

    def test_image_reference_switch_requires_confirmation(self):
        p=self.new();p['settings']=defaults('official_text');p=self.commit(p)
        image=self.asset(p);p['segments'][0]['assets']=[image['id']]
        plan=self.st.edit_plan(p['id'],p)
        self.assertTrue(plan['requires_confirmation']);self.assertEqual(plan['settings']['recipe'],'text_ref')
        self.assertEqual(self.st.store.get(p['id'])['settings']['recipe'],'official_text')
        accepted=self.st.store.apply(p['id'],plan['token'])
        report=self.st.preflight(p['id']);self.assertTrue(report['ready'],report['errors'])
        workflow=report['segments'][0]['compiled']['workflow']
        self.assertEqual(workflow['20']['class_type'],'MiniMaxH3ReferenceToVideo')
        self.assertIn('ref_images.ref_image_0',workflow['20']['inputs'])
