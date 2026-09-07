"""Key image boundaries only. All engine network methods are forbidden."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from h3ui import create_app
from h3ui.comfy import ComfyClient
from h3ui.image_studio import compiler
from h3ui.image_studio.inputs import execution_inputs


class ImageStudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        cfg=json.loads(Path('config.example.json').read_text(encoding='utf-8'))
        cfg.update(studio_data_dir=str(self.root/'projects'),data_dir=str(self.root/'legacy'),
                   asset_library_dir=str(self.root/'library'),comfy_input_dir=str(self.root/'input'),
                   comfy_output_dir=str(self.root/'output'),studio_disable_generation=True,
                   studio_progress_disabled=True,studio_auto_recover=False,image_assets_enabled=True,open_browser=False)
        config=self.root/'config.json';config.write_text(json.dumps(cfg),encoding='utf-8')
        for name in ('_get','_post'):
            mock=patch.object(ComfyClient,name,side_effect=AssertionError('No engine calls permitted'))
            mock.start();self.addCleanup(mock.stop)
        self.app=create_app(str(config));self.client=self.app.test_client();self.s=self.app.config['IMAGE_STUDIO']
        self.p=self.s.create('图片隔离检查');self.pid=self.p['id']

    def picture(self,pid=None):
        stream=io.BytesIO();Image.new('RGB',(80,120),'#9aaf90').save(stream,'PNG');stream.seek(0)
        return self.client.post(f'/api/v5/image-projects/{pid or self.pid}/inputs',data={'file':(stream,'A.png')}).get_json()

    def save(self,p):
        plan=self.s.plan(p['id'],p);self.s.store.apply(p['id'],plan['token']);return self.s.snapshot(p['id'])

    def test_four_graphs_and_mask_geometry(self):
        for mode in ('single','dual','region','outpaint'):
            graph,out=compiler.compile_graph(mode,'编辑这个区域',{'A':'A.png','B':'B.png'},{'seed':42})
            self.assertEqual(graph[out]['class_type'],'SaveImage')
            for n in graph.values():
                for value in n['inputs'].values():
                    if isinstance(value,list):self.assertIn(value[0],graph)
            enc=[n['inputs'] for n in graph.values() if n['class_type']=='Krea2EditGroundedEncode']
            self.assertEqual(sorted(x['prompt'] for x in enc),['','编辑这个区域'])
            self.assertEqual(sum('image_b' in x for x in enc),2 if mode=='dual' else 0)
        a=self.picture();p=self.p;p['tasks'][0].update(A=a['id'],submode='region',prompt='填充')
        mask=Image.new('L',(80,120));mask.paste(255,(0,0,20,40));buf=io.BytesIO();mask.save(buf,'PNG');buf.seek(0)
        m=self.client.post(f'/api/v5/image-projects/{self.pid}/inputs',data={'source':a['id'],'file':(buf,'mask.png')}).get_json()
        p['tasks'][0]['mask']=m['id'];p=self.save(p)
        paths=execution_inputs(self.s.store,self.pid,p['tasks'][0],self.root/'execution')
        with Image.open(paths['A']) as image:
            self.assertEqual(image.getpixel((0,0))[3],0);self.assertEqual(image.getpixel((70,100))[3],255)
        g=compiler.geometry('outpaint',80,120,{'left':64,'right':128,'top':0,'bottom':32})
        self.assertEqual(g['canvas'],[g['work'][0]+192,g['work'][1]+32])

    def test_save_conflict_idempotence_and_video_compatibility(self):
        video=self.app.config['STUDIO'].create('text_story','旧模式',15)
        p=self.p;p['name']='保存后';plan=self.s.plan(self.pid,p)
        self.s.store.apply(self.pid,plan['token']);self.s.store.apply(self.pid,plan['token'])
        self.assertEqual(self.s.snapshot(self.pid)['revision'],2)
        with self.assertRaises(ValueError):self.s.plan(self.pid,p)
        listing=self.client.get('/api/v5/projects').get_json()['projects']
        self.assertEqual(len(listing),2)
        self.assertEqual(self.client.get('/api/v5/projects/'+video['id']).status_code,200)
        with self.s.store.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM projects').fetchone()[0],1)

    def test_submission_dedup_and_gpu_guard_without_network(self):
        a=self.picture();p=self.p;p['tasks'][0].update(A=a['id'],prompt='改变服装');p=self.save(p)
        self.s.cfg['studio_disable_generation']=False
        with patch.object(self.s.runner,'wake'):
            run=self.s.runner.submit(self.pid,p['current_task'],p['revision'],'one')
            self.assertEqual(self.s.runner.submit(self.pid,p['current_task'],p['revision'],'one')['id'],run['id'])
            with self.assertRaises(ValueError):self.s.runner.submit(self.pid,p['current_task'],p['revision'],'two')
        self.s.runner.update(run,state='unknown')
        self.assertIsNone(self.s.st.jobs._reserve('v5_generate','another'))
        self.assertEqual(self.s.store.get('runs',run['id'])['state'],'unknown')
        self.assertFalse((self.root/'input').exists())

    def test_video_reference_preview_and_primary_version(self):
        lib=self.app.config['ASSET_LIBRARY'];st=self.app.config['STUDIO']
        path=self.root/'picture.png';Image.new('RGB',(80,120),'green').save(path)
        asset=lib.ingest(path,'角色',provenance={'type':'generated_image','tool':'single'})
        old_version=asset['version'];old_hash=asset['snapshot']['media'][0]['hash']
        Image.new('RGB',(80,120),'blue').save(path)
        asset=lib.ingest(path,'角色',provenance={'type':'generated_image','tool':'dual'},aid=asset['id'],revision=asset['revision'],primary=True)
        self.assertEqual(lib.query({'image_tool':'dual'})['total'],1)
        self.assertEqual(lib.store.get(asset['id'],old_version)['snapshot']['media'][0]['hash'],old_hash)
        primary=next(m for m in asset['snapshot']['media'] if m['role']=='primary')
        self.assertNotEqual(primary['hash'],old_hash)
        for mode in ('swap','image_story','text_story'):
            p=st.create(mode,mode,15)
            if mode=='swap':
                p=st.store.mutate(p['id'],lambda q:q['segments'].append(st.new_segment(dict(index=0,raw=124,head=0,deliver=124,tail=0,start=0,duration=124/24,boundary='new_scene'))))
            before=st.store.get(p['id'])
            plan=lib.project_import.plan(p['id'],dict(revision=p['revision'],asset=asset['id'],version=asset['version'],segment=p['segments'][0]['id'],subject='1'))
            self.assertTrue(plan['ready'],plan)
            self.assertEqual(st.store.get(p['id']),before)
            lib.project_import.apply({'project':p['id'],'token':plan['token']},lambda *args:None)
            self.assertEqual(st.store.assets(p['id'])[0]['library_reference']['version'],asset['version'])

    def test_trusted_output_library_roundtrip(self):
        a=self.picture();p=self.p;p['tasks'][0].update(A=a['id'],prompt='编辑');p=self.save(p)
        self.s.cfg['studio_disable_generation']=False
        with patch.object(self.s.runner,'wake'):
            run=self.s.runner.submit(self.pid,p['current_task'],p['revision'],'output')
        self.s.runner.update(run,state='running',prompt_id='owned',output_node='27',graph_hash='fixture')
        directory=self.s.store.directory(self.pid)/'image_runs'/run['id'];directory.mkdir(parents=True)
        output=self.root/'output';output.mkdir();size=compiler.geometry('single',80,120)['output']
        Image.new('RGB',size,'green').save(output/'exact.png')
        history={'owned':{'status':{'status_str':'success'},'outputs':{'27':{'images':[{'filename':'exact.png','subfolder':'','type':'output'}]}}}}
        run=self.s.store.get('runs',run['id']);self.s.runner.finish(run,history)
        asset=self.s.ingest(self.pid,run['id'],{})
        self.assertEqual(self.s.ingest(self.pid,run['id'],{})['id'],asset['id'])
        ref=self.s.library_input(self.pid,{'asset':asset['id'],'version':asset['version'],'media':asset['snapshot']['media'][0]['id']})
        self.assertEqual(ref['provenance']['version'],asset['version'])
        self.assertNotIn('prompt',ref['provenance'])
        before=self.app.config['ASSET_LIBRARY'].store.get(asset['id'])
        self.s.trash(self.pid,{'revision':p['revision']})
        self.assertEqual(self.app.config['ASSET_LIBRARY'].store.get(asset['id'])['version'],before['version'])

if __name__=='__main__':unittest.main()
