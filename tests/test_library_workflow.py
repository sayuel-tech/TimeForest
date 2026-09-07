"""Media-only library snapshots must reach actual compiler nodes in all three modes."""
import copy
import io
import unittest
import wave

from PIL import Image
from test_local_server import LocalServerTests
from h3ui.asset_library.bindings import expand
from h3ui.studio_recipes import defaults


class LibraryWorkflowTests(unittest.TestCase):
    setUp = LocalServerTests.setUp

    def setup_assets(self):
        self.lib = self.app.config['ASSET_LIBRARY']
        self.image = self.root / 'role.png'
        Image.new('RGBA', (128, 128), (60, 90, 100, 130)).save(self.image)
        first = self.lib.ingest(self.image, '角色一', {'categories': ['character'], 'record_prompt': 'SHOULD NEVER ENTER GENERATION'})
        self.audio = self.root / 'voice.wav'
        with wave.open(str(self.audio), 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes(bytes(48000 * 2 * 3))
        voice = self.lib.ingest(self.audio, '角色一声线', {'categories': ['voice']})
        first = self.lib.update(first['id'], first['revision'], {'bindings': [dict(asset=voice['id'], version=voice['version'], purpose='voice', default=True)]})
        return first, voice

    def apply_plan(self, p, asset, **extra):
        data = dict(revision=p['revision'], asset=asset['id'], version=asset['version'], owner='role-one',
                    subject='1', segment=p['segments'][0]['id'], **extra)
        report = self.lib.project_import.plan(p['id'], data)
        self.assertTrue(report['ready'], report)
        self.lib.project_import.apply({'project': p['id'], 'token': report['token']}, lambda *args: None)
        return self.st.store.get(p['id']), report

    def test_image_mode_uses_real_nodes_and_document_changes_are_inert(self):
        role, voice = self.setup_assets()
        p = self.st.create('image_story', 'integration', 15)
        p = self.st.store.mutate(p['id'], lambda q: q['segments'][0].update(prompt='A dancer walks through a forest.'))
        before = copy.deepcopy(p)
        data = dict(revision=p['revision'], asset=role['id'], version=role['version'], owner='role-one', subject='1', segment=p['segments'][0]['id'])
        preview = self.lib.project_import.plan(p['id'], data)
        self.assertEqual(self.st.store.get(p['id']), before)
        self.assertEqual(self.st.store.assets(p['id']), [])
        self.lib.project_import.apply({'project': p['id'], 'token': preview['token']}, lambda *args: None)
        report = self.st.preflight(p['id'])
        self.assertTrue(report['ready'], report['errors'])
        compiled = report['segments'][0]['tasks'][0]['compiled']
        graph = compiled['workflow']
        self.assertEqual(graph['400']['class_type'], 'LoadImage')
        self.assertEqual(graph['401']['class_type'], 'LoadAudio')
        self.assertEqual(graph['20']['inputs']['ref_audios.ref_audio_0'], ['401', 0])
        self.assertNotIn('SHOULD NEVER', graph['20']['inputs']['prompt'])
        self.assertIn('<Subject 1>', graph['20']['inputs']['prompt'])
        self.assertEqual(compiled['asset_map'][1]['library_reference']['asset'], voice['id'])
        from h3ui.studio_prompts import build
        def same_run_graph():
            project=self.st.store.get(p['id']);segment=project['segments'][0]
            assets=self.st.resolve(project,segment)
            return self.st.recipes.compile(project,segment,assets,build(project,segment,assets),attempt='same-run')
        compiled=same_run_graph()
        self.lib.update(role['id'], role['revision'], {'record_prompt': 'CHANGED DOCUMENT', 'description': '<Picture 99>'})
        self.lib.store.trash(role['id'], role['revision'] + 1)
        after = same_run_graph()
        self.assertEqual(compiled, after)
        self.assertFalse((self.root / 'engine-input').exists())

    def test_official_text_switch_requires_apply_and_preserves_written_prompt(self):
        role, voice = self.setup_assets()
        p = self.st.create('text_story', 'text', 15)
        p = self.st.store.mutate(p['id'], lambda q: (q.update(settings=defaults('official_text')), q['segments'][0].update(prompt='A new spoken sentence, not the voice reference transcript.')))
        before = copy.deepcopy(p)
        data = dict(revision=p['revision'], asset=voice['id'], version=voice['version'], segment=p['segments'][0]['id'])
        preview = self.lib.project_import.plan(p['id'], data)
        self.assertTrue(preview['ready'], preview)
        self.assertEqual(preview['settings']['recipe'], 'text_ref')
        self.assertEqual(self.st.store.get(p['id']), before)
        self.lib.project_import.apply({'project': p['id'], 'token': preview['token']}, lambda *args: None)
        after = self.st.store.get(p['id'])
        self.assertEqual(after['settings']['recipe'], 'text_ref')
        self.assertEqual(after['segments'][0]['prompt'], before['segments'][0]['prompt'])
        report = self.st.preflight(p['id'])
        self.assertTrue(report['ready'], report['errors'])

    def test_swap_conflict_does_not_silently_remove_image_or_change_sound_policy(self):
        role, voice = self.setup_assets()
        second = self.lib.ingest(self.image, '额外服装', {'categories': ['costume']})
        role = self.lib.update(role['id'], role['revision'], {'bindings': role['snapshot']['bindings'] + [dict(asset=second['id'], version=second['version'], purpose='costume', default=True)]})
        p = self.st.create('swap', 'swap')
        p = self.st.store.mutate(p['id'], lambda q: (q.update(settings=defaults('official_swap')), q['segments'].append(self.st.new_segment(dict(index=0, raw=124, head=0, deliver=124, tail=0, start=0, duration=124/24, boundary='new_scene')))))
        data = dict(revision=p['revision'], asset=role['id'], version=role['version'], owner='role-one', segment=p['segments'][0]['id'])
        preview = self.lib.project_import.plan(p['id'], data)
        self.assertFalse(preview['ready'])
        self.assertTrue(any('最多1张' in e for e in preview['errors']))
        self.assertTrue(any('原声' in e for e in preview['errors']))
        bundle = expand(self.lib, role['id'], role['version'], 'role-one')
        entries = {x['key']: {'selected': False} for x in bundle['entries'] if x['purpose'] == 'costume'}
        data.update(entries=entries, audio_policy='native')
        preview = self.lib.project_import.plan(p['id'], data)
        self.assertTrue(preview['ready'], preview)
        self.assertEqual(self.st.store.get(p['id'])['settings']['audio_policy'], 'source')
        self.lib.project_import.apply({'project': p['id'], 'token': preview['token']}, lambda *args: None)
        self.assertEqual(self.st.store.get(p['id'])['settings']['audio_policy'], 'native')
        self.assertEqual(len(self.st.store.assets(p['id'])), 2)

    def test_two_role_bindings_and_version_update_keep_ownership_independent(self):
        role, voice = self.setup_assets()
        role2 = self.lib.ingest(self.image, '角色二', {'categories':['character']})
        role2 = self.lib.update(role2['id'],role2['revision'], {'bindings':role['snapshot']['bindings']})
        p=self.st.create('image_story','two roles',30)
        p=self.st.store.mutate(p['id'],lambda q:q['segments'][0].update(prompt='Two characters talk in a forest.'))
        p,_=self.apply_plan(p,role)
        data=dict(revision=p['revision'],asset=role2['id'],version=role2['version'],owner='role-two',subject='2',segment=p['segments'][0]['id'])
        plan=self.lib.project_import.plan(p['id'],data);self.assertTrue(plan['ready'],plan)
        self.lib.project_import.apply({'project':p['id'],'token':plan['token']},lambda *a:None)
        p=self.st.store.get(p['id']);refs=self.st.resolve(p,p['segments'][0])
        self.assertEqual({a['subject'] for a in refs if a['kind']=='audio'},{'1','2'})
        self.assertEqual(len({a['id'] for a in refs}),4)
        newer=self.lib.update(role['id'],role['revision'],{'name':'角色一新版'})
        old_ids=[a['id'] for a in refs if a['owners']==['role-one']]
        report=self.lib.project_import.plan(p['id'],dict(revision=p['revision'],asset=newer['id'],version=newer['version'],owner='role-one',subject='1',segment=p['segments'][0]['id'],replace=old_ids))
        self.assertTrue(report['ready'],report)
        self.lib.project_import.apply({'project':p['id'],'token':report['token']},lambda *a:None)
        q=self.st.store.get(p['id']);updated=self.st.resolve(q,q['segments'][0])
        self.assertEqual([a['id'] for a in updated if a['owners']==['role-two']],[a['id'] for a in refs if a['owners']==['role-two']])
        self.assertTrue(any(a['library_reference']['root_version']==newer['version'] for a in updated))
        # An explicit no-assets continuation must not be repopulated from P1's role bindings.
        q['segments'][1].update(asset_mode='none',assets=[],inherit_ids=[])
        self.assertEqual(self.st.resolve(q,q['segments'][1]),[])

    def test_control_reference_is_stored_but_not_masquerading_as_character(self):
        role, _ = self.setup_assets()
        mask = self.lib.ingest(self.image, '透明遮罩', {'categories': ['control']})
        p = self.st.create('image_story', 'mask')
        report = self.lib.project_import.plan(p['id'], dict(revision=p['revision'], asset=mask['id'], segment=p['segments'][0]['id']))
        self.assertFalse(report['ready'])
        self.assertEqual(report['entries'][0]['state'], 'unsupported')
        self.assertEqual(self.st.store.assets(p['id']), [])


if __name__ == '__main__':
    unittest.main()
