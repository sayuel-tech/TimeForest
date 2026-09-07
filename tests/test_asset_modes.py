"""Reference policy contracts; graph compilation only, never GPU generation."""
from test_studio import StudioAcceptance
from h3ui.studio_recipes import defaults
from h3ui.studio_story import task_segments


class AssetModes(StudioAcceptance):
    def draft(self, recipe='dance_split', mode='image_story'):
        p=self.st.create(mode,'素材策略隔离检查',30)
        p['settings']=defaults(recipe)
        p['segments'][0]['assets']=[self.asset(p)['id'],self.asset(p,'audio')['id']]
        for s in p['segments']:s['prompt']='Continue walking through the forest. Speak only the new dialogue.'
        return self.st.store.save(p,p['revision'])

    def test_continuation_omits_references_but_keeps_av_context(self):
        for recipe in ['dance_split','dance_av','official_image','wenxi_av']:
            p=self.draft(recipe)
            self.assertEqual(len(self.st.resolve(p,p['segments'][1])),2)
            p['segments'][1]['asset_mode']='none'
            p=self.commit(p)
            self.assertEqual(p['segments'][1]['asset_mode'],'none')
            self.assertEqual(self.st.resolve(p,p['segments'][1]),[])
            tasks=task_segments(self.st,p,p['segments'][1])
            self.assertTrue(all(t['asset_mode']=='none' for t in tasks))
            report=self.st.preflight(p['id'])
            self.assertTrue(report['ready'],(recipe,report['errors']))
            graph=report['segments'][1]['tasks'][0]['compiled']['workflow']
            self.assertFalse(any(k.startswith(('ref_images.','ref_audios.')) for k in graph['20']['inputs']))
            self.assertIn('105',graph)
            self.assertEqual(graph['15']['inputs']['conditioning'],['105',0])
            self.assertTrue('context_audio' in graph['105']['inputs'] or 'context_latent' in graph['105']['inputs'])
            if recipe=='dance_split':
                self.assertEqual(graph['105']['inputs']['context_audio'],['645',0])
                self.assertEqual(graph['23']['inputs']['samples'],['214',1])
            with self.assertRaises(ValueError):self.st.previous(p,p['segments'][1])

    def test_custom_selection_and_new_scene_requirements(self):
        p=self.draft();audio=p['segments'][0]['assets'][1]
        p['segments'][1].update(asset_mode='custom',inherit_ids=[audio])
        p=self.commit(p)
        self.assertEqual([a['id'] for a in self.st.resolve(p,p['segments'][1])],[audio])
        p['segments'][1].update(asset_mode='none',boundary='new_scene')
        p=self.commit(p)
        report=self.st.preflight(p['id'])
        self.assertFalse(report['ready'])
        self.assertTrue(any('新场景' in e for e in report['errors']))

    def test_text_reference_can_continue_without_resending_voice(self):
        p=self.draft('text_ref','text_story')
        p['segments'][1]['asset_mode']='none';p=self.commit(p)
        report=self.st.preflight(p['id'])
        self.assertTrue(report['ready'],report['errors'])
        graph=report['segments'][1]['tasks'][0]['compiled']['workflow']
        self.assertIn('105',graph)
        self.assertNotIn('ref_audios.ref_audio_0',graph['20']['inputs'])

    def test_unknown_policy_is_rejected(self):
        p=self.draft();p['segments'][1]['asset_mode']='typo'
        with self.assertRaises(ValueError):self.commit(p)

    def test_legacy_auto_default_does_not_invalidate_results(self):
        p=self.draft()
        for s in p['segments']:
            s.pop('asset_mode',None)
            s.update(status='accepted',selected='legacy-result')
        p=self.st.store.save(p,p['revision'])
        p=self.commit(p)
        self.assertTrue(all(s['selected']=='legacy-result' for s in p['segments']))
