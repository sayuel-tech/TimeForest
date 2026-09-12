"""Nine real isolated inputs through save, immutable snapshot and graph; no GPU."""
import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace, ModuleType
from unittest import TestCase
from unittest.mock import patch

from tests import test_image_studio as image_tests
from h3ui.image_studio import compiler
from h3ui.image_studio.inputs import execution_inputs


class MultiReferenceTests(TestCase):
    setUp = image_tests.ImageStudioTests.setUp
    picture = image_tests.ImageStudioTests.picture
    save = image_tests.ImageStudioTests.save

    def test_nine_inputs_save_snapshot_and_compile(self):
        p = self.p
        task = p['tasks'][0]
        task.update(submode='dual', prompt='图 A 保留场景，图 I 提供服装', settings={'seed': 42})
        for slot in compiler.IMAGE_SLOTS:
            task[slot] = self.picture()['id']
        plan = self.client.post(f'/api/v5/image-projects/{self.pid}/change-plan', json=p)
        self.assertEqual(plan.status_code, 200)
        saved = self.client.post(f'/api/v5/image-projects/{self.pid}/apply', json={'token': plan.json['token']})
        self.assertEqual(saved.status_code, 200)
        p = saved.json
        self.s.cfg['studio_disable_generation'] = False
        with patch.object(self.s.runner, 'wake'):
            run = self.s.runner.submit(self.pid, task['id'], p['revision'], 'nine-inputs')
        snap = run['snapshot']
        self.assertEqual(list(snap['inputs']), list(compiler.IMAGE_SLOTS))
        self.assertEqual(snap['multi_reference_revision'], 1)
        # A missing companion fails before copying inputs or submitting a prompt.
        catalog = dict(node_catalog={'error': None}, missing=[], missing_by_tool={'dual': []},
                       multi_reference_nodes_missing=sorted(compiler.MULTIREF_NODES))
        with patch.object(self.s.st.comfy, '_get', return_value={}), patch.object(self.s, 'catalog', return_value=catalog), patch.object(self.s.st.comfy, 'submit') as submit:
            with self.assertRaisesRegex(ValueError, '3—9图编辑'):
                self.s.runner.execute(run)
            submit.assert_not_called()
        paths = execution_inputs(self.s.store, self.pid, snap, self.root/'execution')
        self.assertEqual(set(paths), set(compiler.IMAGE_SLOTS))
        graph, output = compiler.compile_graph('dual', snap['prompt'], {k: str(v) for k, v in paths.items()}, snap['settings'])
        self.assertEqual(sum(n['class_type']=='LoadImage' for n in graph.values()), 9)
        self.assertEqual(graph[output]['class_type'], 'SaveImage')
        for node in graph.values():
            if node['class_type'] in compiler.MULTIREF_NODES:
                self.assertEqual({k for k in node['inputs'] if k.startswith('image_')}, {'image_'+x.lower() for x in compiler.IMAGE_SLOTS})
        # Editing current inputs cannot mutate the prior run.
        p['tasks'][0]['I'] = None
        self.save(p)
        self.assertEqual(self.s.store.get('runs', run['id'], self.pid)['snapshot']['I'], task['I'])

    def test_sparse_slots_legacy_and_limits(self):
        p = self.p
        task = p['tasks'][0]
        a, b, i = [self.picture()['id'] for _ in range(3)]
        task.update(submode='dual', A=a, B=b, I=i, C=None, prompt='test')
        p = self.save(p)
        self.assertIn('C', p['tasks'][0])
        graph, _ = compiler.compile_graph('dual', 'test', {'A':'a.png','B':'b.png','I':'i.png','C':None}, {'seed':1})
        self.assertEqual(sum(n['class_type']=='LoadImage' for n in graph.values()), 3)
        p['tasks'][0]['J'] = i
        with self.assertRaisesRegex(ValueError, '9张'): self.s.plan(self.pid, p)
        del p['tasks'][0]['J']
        other = self.s.create('other')
        p['tasks'][0]['I'] = self.picture(other['id'])['id']
        with self.assertRaises((ValueError, KeyError)): self.s.plan(self.pid, p)
        graph, _ = compiler.compile_graph('dual', 'legacy', {'A':'a.png','B':'b.png'}, {'seed':1})
        self.assertFalse(compiler.MULTIREF_NODES & {n['class_type'] for n in graph.values()})
        self.assertEqual(sum(n['class_type']=='Krea2EditGroundedEncode' for n in graph.values()), 2)


class MultiReferenceNodeTests(TestCase):
    def test_all_references_reach_both_node_paths(self):
        path = Path('comfyui_nodes/timeforest_krea_multiref/__init__.py')
        spec = importlib.util.spec_from_file_location('multiref_test', path)
        node = importlib.util.module_from_spec(spec); spec.loader.exec_module(node)
        graph, _ = compiler.compile_graph('dual', 'test', {slot: slot+'.png' for slot in 'ABCDEFGHI'}, {'seed': 1})
        for entry in graph.values():
            if entry['class_type'] in node.NODE_CLASS_MAPPINGS:
                schema = node.NODE_CLASS_MAPPINGS[entry['class_type']].INPUT_TYPES()
                self.assertTrue(set(schema['required']) <= set(entry['inputs']))
                self.assertTrue(set(entry['inputs']) <= set(schema['required']) | set(schema['optional']))
        encoder = SimpleNamespace(_prep=lambda image, px: ('prepared', image),
            _template=lambda count, system: '<|vision_start|><|image_pad|><|vision_end|>'*count+'{}')
        calls = []
        clip = SimpleNamespace(tokenize=lambda prompt, **kwargs: calls.append((prompt, kwargs)) or 'tokens',
                               encode_from_tokens_scheduled=lambda tokens: tokens)
        fit_calls = []
        module = SimpleNamespace(_fit_encode_image=lambda image, vae, h, w, cache, key, fit:
                                 fit_calls.append(image) or image,
                                 _to_4d=lambda x: x,
                                 krea2_edit_forward=lambda *args, **kwargs: calls.append((args, kwargs)) or 'result')
        extension = ModuleType('comfy.patcher_extension')
        wrappers = []
        extension.WrappersMP = SimpleNamespace(DIFFUSION_MODEL='diffusion')
        extension.add_wrapper_with_key = lambda kind, key, wrapper, options: wrappers.append(wrapper)
        comfy = ModuleType('comfy'); comfy.patcher_extension = extension
        images = {'image_'+slot: slot.upper() for slot in node.SLOTS}
        with patch.object(node, 'upstream', return_value=(module, encoder)), patch.dict('sys.modules', {'comfy':comfy, 'comfy.patcher_extension':extension}):
            for prompt in ('edit', ''):
                node.TimeForestKreaMultiRefEncode().encode(clip, prompt, **images)
                self.assertEqual(len(calls[-1][1]['images']), 9)
                self.assertIn('Image I: ', calls[-1][1]['llama_template'])
            inner = SimpleNamespace(process_latent_in=lambda value: 'latent_'+value)
            model = SimpleNamespace(model=inner, clone=lambda: SimpleNamespace(model_options={}))
            node.TimeForestKreaMultiRefPatch().patch(model, object(), {'samples': SimpleNamespace(shape=(1,4,128,128))}, **images)
            self.assertEqual(fit_calls, list('ABCDEFGHI'))
            self.assertEqual(len(wrappers), 1)
            result = wrappers[0](SimpleNamespace(class_obj='dit'), SimpleNamespace(shape=(1,4,128,128)), 't', 'ctx', None, {})
            self.assertEqual(result, 'result')
            self.assertEqual(calls[-1][0][4], ['latent_'+slot for slot in 'ABCDEFGHI'])
            self.assertEqual(len(fit_calls), 9, 'must not VAE encode again during sampling')
            sparse = {'image_a':'A','image_b':'B','image_i':'I'}
            node.TimeForestKreaMultiRefEncode().encode(clip, 'use I', **sparse)
            self.assertIn('Image I: ', calls[-1][1]['llama_template'])
            with self.assertRaises(ValueError): node.references({**images, 'image_j':'J'})
