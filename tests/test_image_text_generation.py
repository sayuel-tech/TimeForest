"""Native Krea text branch: offline graph, real temporary save, fake output recovery."""
import copy
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from h3ui.image_studio import compiler,inputs


class ImageTextGenerationTests(unittest.TestCase):
    def setUp(self):
        from tests.test_image_parameters import ImageParameterTests
        self.f=ImageParameterTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=self.f.s;self.c=self.f.client

    def test_text_graph_uses_native_loaders_and_real_dimensions_without_edit_nodes(self):
        params=dict(seed=0,steps=19,cfg=2.5,sampler_name='heun',scheduler='normal',ratio='16:9',megapixels=.75)
        models={key:'custom/'+key+'.safetensors' for key in compiler.MODELS}
        graph,out=compiler.compile_graph('text','山间木屋',{},params,models,prefix='fixture/text')
        kinds={n['class_type'] for n in graph.values()}
        self.assertEqual(kinds,{'UNETLoader','CLIPLoader','VAELoader','CLIPTextEncode','EmptySD3LatentImage','KSampler','VAEDecode','SaveImage'})
        sampler=graph['30']['inputs'];self.assertEqual((sampler['steps'],sampler['seed'],sampler['cfg']),(19,0,2.5))
        self.assertEqual(graph['36']['inputs']['text'],'山间木屋');self.assertEqual(graph['34']['inputs']['text'],'')
        self.assertEqual(graph['35']['inputs']['unet_name'],models['unet'])
        self.assertEqual(graph['40']['inputs']['type'],'krea2');self.assertEqual(graph[out]['inputs']['filename_prefix'],'fixture/text')
        w,h=compiler.geometry('text',0,0,params)['output'];self.assertEqual((graph['28']['inputs']['width'],graph['28']['inputs']['height']),(w,h))
        self.assertEqual(graph['28']['inputs']['batch_size'],1)
        for node in graph.values():
            for value in node['inputs'].values():
                if isinstance(value,list):self.assertIn(value[0],graph)
        self.assertEqual(compiler.required_nodes('text'),kinds)
        self.assertEqual(inputs.execution_inputs(None,None,{'submode':'text','A':'nonexistent'},'unused'),{})

    def test_real_create_save_preflight_and_missing_prompt(self):
        response=self.c.post('/api/v5/projects',json={'mode':'image_assets','submode':'text','name':'文生图隔离'})
        self.assertEqual(response.status_code,200,response.get_json());p=response.get_json();tid=p['current_task']
        base='/api/v5/image-projects/'+p['id']
        self.assertFalse(self.c.get(base+'/tasks/'+tid+'/preflight').get_json()['ready'])
        p['tasks'][0]['prompt']='一只坐在窗边的猫';p['tasks'][0]['settings'].update(seed=0,ratio='3:2',megapixels=.5)
        plan=self.c.post(base+'/change-plan',json=p).get_json();saved=self.c.post(base+'/apply',json={'token':plan['token']}).get_json()
        pre=self.c.get(base+'/tasks/'+tid+'/preflight').get_json();self.assertTrue(pre['ready'],pre)
        self.assertIsNone(saved['tasks'][0]['A']);self.assertEqual(saved['inputs'],[])
        geom=self.c.post(base+'/geometry',json={'submode':'text','settings':saved['tasks'][0]['settings']}).get_json()
        self.assertEqual(geom,pre['geometry'])
        catalog=self.s.catalog();self.assertEqual(catalog['text_to_image_version'],1)
        keys={f['key'] for f in catalog['parameters']['text']}
        self.assertTrue({'unet','clip','vae','seed','steps','megapixels','ratio'}<=keys)
        self.assertFalse(keys&{'lora','strength_model','ref_boost','ref_boost_a','grounding_px','fit_mode','left','output_mp'})

    def test_empty_input_snapshot_and_synthetic_output_ingest_continue(self):
        p=self.s.create('纯文字','text');p['tasks'][0].update(prompt='绿色纸张')
        p['tasks'][0]['settings'].update(seed=0,megapixels=.25)
        p=self.f.save(p);self.s.cfg['studio_disable_generation']=False
        with patch.object(self.s.runner,'wake') as wake:
            run=self.s.runner.submit(p['id'],p['current_task'],p['revision'],'text-fixture');wake.assert_called_once()
        self.assertEqual(run['snapshot']['inputs'],{});self.assertEqual(run['snapshot']['adapter_revision'],1)
        self.assertEqual(run['seed'],0)
        self.s.runner.update(run,state='running',prompt_id='synthetic',output_node='27',graph_hash='offline-test')
        directory=self.s.store.directory(p['id'])/'image_runs'/run['id'];directory.mkdir(parents=True)
        output=self.f.root/'comfy/output';output.mkdir(parents=True,exist_ok=True)
        Image.new('RGB',run['geometry']['output'],'green').save(output/'synthetic.png')
        self.s.runner.finish(self.s.store.get('runs',run['id']),{'synthetic':{'status':{'status_str':'success'},'outputs':{'27':{'images':[{'filename':'synthetic.png','subfolder':'','type':'output'}]}}}})
        asset=self.s.ingest(p['id'],run['id'],{'select_output':False});self.assertIn('text',str(asset['snapshot']))
        ordinary=self.f.root/'ordinary.png';Image.new('RGB',(24,24),'blue').save(ordinary)
        self.s.lib.ingest(ordinary,'普通上传')
        filtered=self.c.get('/api/v5/library/assets?image_tool=text').get_json()
        self.assertEqual(filtered['total'],1);self.assertEqual(filtered['items'][0]['id'],asset['id'])
        continued=self.s.continue_output(p['id'],run['id'],self.s.snapshot(p['id'])['revision'])
        task=next(t for t in continued['tasks'] if t['id']==continued['current_task'])
        self.assertEqual(task['submode'],'single');self.assertTrue(task['A'])
        self.f.engine_get.assert_not_called()

    def test_native_node_catalog_does_not_require_edit_plugin_for_text(self):
        native={k:{} for k in compiler.required_nodes('text')}
        for kind,key in [('UNETLoader','unet_name'),('CLIPLoader','clip_name'),('VAELoader','vae_name')]:
            native[kind]={'input':{'required':{key:[['fake.safetensors']]}}}
        self.f.engine_get.side_effect=None;self.f.engine_get.return_value=native
        catalog=self.s.catalog(sync=True)
        self.assertEqual(catalog['missing_by_tool']['text'],[])
        self.assertIn('Krea2EditModelPatch',catalog['missing_by_tool']['single'])
        self.assertNotIn('lora',compiler.model_roles('text'))


if __name__=='__main__':unittest.main()
