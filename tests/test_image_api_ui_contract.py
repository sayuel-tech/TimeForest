"""Actual image HTTP contract -> actual UI draft -> actual save/compile bridge.

No listening HTTP server or browser is launched. SQLite, inputs and discoverable
model filenames are temporary. The fixture must not repair a deficient response.
"""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.image_parameter_ui_fixture import RealImageFixture, ROOT
from h3ui.image_studio import compiler


class ImageApiUiContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='image-api-ui-contract-')
        self.addCleanup(self.temp.cleanup)
        self.fixture = RealImageFixture(Path(self.temp.name))
        self.addCleanup(self.fixture.close)

    def test_real_catalog_reaches_ui_draft_and_persisted_execution(self):
        fixture = self.fixture
        status, catalog = fixture.request('GET', '/api/v5/image-projects/catalog', None)
        self.assertEqual(status, 200)
        self.assertEqual(catalog.get('parameter_contract_version'), 1)
        self.assertEqual(set(catalog.get('parameters', {})), set(compiler.TOOLS))
        self.assertEqual(catalog['local_models']['source'], 'filesystem')
        for role, filename in fixture.fake_model_names.items():
            self.assertIn(filename, catalog['choices'][role])
        status, project = fixture.request('GET', '/api/v5/projects/'+fixture.pid, None)
        self.assertEqual(status, 200)
        before = copy.deepcopy(project)
        # Consume serialized route JSON through the same JS exports as the real page.
        script = '''
import {readFileSync} from 'node:fs';
import {imageParameters, createImageSettingsDraft, renderImageQuickSettings}
  from './static/studio/features/image-settings/index.js';
const {project, catalog}=JSON.parse(readFileSync(0,'utf8'));
const fieldKeys=Object.fromEntries(project.tasks.map(task=>[task.submode,
  imageParameters(task,catalog).map(field=>field.scope+'.'+field.key)]));
const task=project.tasks.find(task=>task.submode==='single');
const draft=createImageSettingsDraft({task,catalog});
const fields=draft.fields();
draft.set(fields.find(field=>field.key==='steps'),'17');
draft.set(fields.find(field=>field.key==='unet'),catalog.choices.unet[0]);
draft.setSeedMode('fixed'); draft.setSeedValue('0');
process.stdout.write(JSON.stringify({fieldKeys,applied:await draft.apply(),
  quick:renderImageQuickSettings({task,catalog})}));
'''
        result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT,
                                input=json.dumps({'project': project, 'catalog': catalog}),
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        ui = json.loads(result.stdout)
        for tool in compiler.TOOLS:
            self.assertIn('models.unet', ui['fieldKeys'][tool])
            self.assertIn('settings.steps', ui['fieldKeys'][tool])
            self.assertIn('settings.seed', ui['fieldKeys'][tool])
        self.assertIn('data-setting="megapixels"', ui['quick'])
        task = next(t for t in project['tasks'] if t['submode']=='single')
        task.update(ui['applied'])
        # Applying the UI draft cannot have persisted anything before this real transaction.
        self.assertEqual(fixture.image_service.snapshot(fixture.pid), before)
        base = '/api/v5/image-projects/'+fixture.pid
        status, plan = fixture.request('POST', base+'/change-plan', project)
        self.assertEqual(status, 200, plan)
        status, saved = fixture.request('POST', base+'/apply', {'token': plan['token']})
        self.assertEqual(status, 200, saved)
        status, reopened = fixture.request('GET', '/api/v5/projects/'+fixture.pid, None)
        self.assertEqual(reopened, saved)
        current = next(t for t in reopened['tasks'] if t['id']==task['id'])
        self.assertEqual(current['settings']['steps'], 17)
        self.assertEqual(current['settings']['seed'], 0)
        self.assertEqual(current['models']['unet'], catalog['choices']['unet'][0])
        self.assertEqual(reopened['outputs'], before['outputs'])
        graph, output = compiler.compile_graph('single', current['prompt'], {'A':'A.png'},
                                                current['settings'], current['models'])
        self.assertEqual(graph[output]['class_type'], 'SaveImage')
        sampler = next(node['inputs'] for node in graph.values() if node['class_type']=='KSampler')
        self.assertEqual((sampler['steps'], sampler['seed']), (17, 0))
        model = next(node['inputs'] for node in graph.values() if node['class_type']=='UNETLoader')
        self.assertEqual(model['unet_name'], catalog['choices']['unet'][0])
        status, _ = fixture.request('POST', base+'/tasks/'+task['id']+'/generate', {})
        self.assertEqual(status, 403)
        self.assertEqual(fixture.engine_attempts, [])

    def test_missing_catalog_parameters_are_not_synthesized_by_fixture(self):
        deficient = {'sentinel': 'actual route response lacks parameters'}
        with patch.object(self.fixture.image_service, 'catalog', return_value=deficient) as actual:
            status, received = self.fixture.request('GET', '/api/v5/image-projects/catalog', None)
        self.assertEqual(status, 200)
        self.assertEqual(received, deficient)
        self.assertNotIn('parameters', received)
        actual.assert_called_once_with()
        self.assertEqual(self.fixture.real_api_calls[-1]['path'], '/api/v5/image-projects/catalog')
        script = '''
import {readFileSync} from 'node:fs';
import {createImageSettingsDraft} from './static/studio/features/image-settings/index.js';
const catalog=JSON.parse(readFileSync(0,'utf8'));
try {
  createImageSettingsDraft({task:{submode:'single',settings:{},models:{}},catalog});
  process.stdout.write(JSON.stringify({accepted:true}));
} catch(error) {
  process.stdout.write(JSON.stringify({code:error.code,message:error.message}));
}
'''
        result = subprocess.run(['node', '--input-type=module', '-e', script], cwd=ROOT,
                                input=json.dumps(received), capture_output=True, text=True,
                                encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        failure = json.loads(result.stdout)
        self.assertEqual(failure.get('code'), 'IMAGE_PARAMETER_CONTRACT_MISMATCH', failure)

    def test_all_tools_restore_real_defaults_save_and_compile(self):
        f=self.fixture
        _,catalog=f.request('GET','/api/v5/image-projects/catalog',None)
        self.assertTrue(catalog['quick_ingest_preserves_selection'])
        _,project=f.request('GET','/api/v5/projects/'+f.pid,None)
        before=copy.deepcopy(project)
        script='''
import {readFileSync} from 'node:fs';
import {createImageSettingsDraft} from './static/studio/features/image-settings/index.js';
const {project,catalog}=JSON.parse(readFileSync(0,'utf8'));
for(const task of project.tasks){
 const draft=createImageSettingsDraft({task,catalog});
 for(const field of draft.fields())if(field.type==='model')draft.set(field,'changed.safetensors');
 draft.set(draft.fields().find(f=>f.key==='steps'),'29');draft.setSeedMode('fixed');draft.setSeedValue('0');
 draft.resetDefaults();Object.assign(task,await draft.apply());
}
process.stdout.write(JSON.stringify(project));
'''
        result=subprocess.run(['node','--input-type=module','-e',script],cwd=ROOT,input=json.dumps({'project':project,'catalog':catalog}),capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr);draft=json.loads(result.stdout)
        self.assertEqual(f.image_service.snapshot(f.pid),before)
        base='/api/v5/image-projects/'+f.pid
        status,plan=f.request('POST',base+'/change-plan',draft);self.assertEqual(status,200,plan)
        status,saved=f.request('POST',base+'/apply',{'token':plan['token']});self.assertEqual(status,200,saved)
        for task,original in zip(saved['tasks'],before['tasks']):
            for field in catalog['parameters'][task['submode']]:
                source=catalog['models' if field['scope']=='models' else 'defaults']
                self.assertEqual(task[field['scope']][field['key']],source[field['key']])
            for key in ('id','A','B','mask','prompt'):self.assertEqual(task[key],original[key])
            # Bind a known execution seed to inspect the graph without generating a random value.
            graph,_=compiler.compile_graph(task['submode'],task['prompt'],{'A':'A.png','B':'B.png'},{**task['settings'],'seed':0},task['models'])
            sampler=next(n['inputs'] for n in graph.values() if n['class_type']=='KSampler')
            self.assertEqual(sampler['steps'],catalog['defaults']['steps']);self.assertEqual(sampler['seed'],0)
            model=next(n['inputs'] for n in graph.values() if n['class_type']=='UNETLoader')
            self.assertEqual(model['unet_name'],catalog['models']['unet'])
        self.assertEqual(saved['outputs'],before['outputs']);self.assertEqual(f.engine_attempts,[])


if __name__ == '__main__':
    unittest.main()
