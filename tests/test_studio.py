"""Non-generation acceptance. Fixtures are isolated; Comfy submit is forbidden."""
import copy,io,json,math,os,sys,tempfile,time,unittest,wave
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from werkzeug.datastructures import FileStorage
from h3ui import create_app
from h3ui.studio_plan import story_plan,geometry
from h3ui.studio_recipes import defaults,RECIPES
from h3ui import studio_media as av
from h3ui.studio_store import Conflict

class StudioAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='time_forest_v5_checks_');cls.root=Path(cls.tmp.name)
        cfg=json.loads(Path('config.example.json').read_text(encoding='utf-8'));cfg.update(studio_data_dir=str(cls.root/'v5'),data_dir=str(cls.root/'legacy'),asset_library_dir=str(cls.root/'library'),comfy_url='http://127.0.0.1:1',comfy_input_dir=str(cls.root/'input'),comfy_output_dir=str(cls.root/'output'),open_browser=False)
        cfg['studio_progress_disabled']=True
        config=cls.root/'config.json';config.write_text(json.dumps(cfg),encoding='utf-8')
        cls.app=create_app(str(config));cls.st=cls.app.config['STUDIO'];cls.client=cls.app.test_client()
        cls.st.recipes.info=json.loads(Path('h3ui/studio_sources/object_info.json').read_text(encoding='utf-8'))
        cls.st.recipes.offline=False;cls.st.recipes.refresh=lambda:None
        cls.st.comfy.submit=lambda *a,**k: (_ for _ in ()).throw(AssertionError('REAL GPU SUBMISSION FORBIDDEN'))
        cls.image=io.BytesIO();Image.new('RGB',(120,220),'#ada087').save(cls.image,format='PNG');cls.image=cls.image.getvalue()
        out=io.BytesIO()
        with wave.open(out,'wb') as f:
            f.setparams((1,2,32000,64000,'NONE','not compressed'))
            f.writeframes(b''.join(int(5000*math.sin(i*2*math.pi*220/32000)).to_bytes(2,'little',signed=True) for i in range(64000)))
        cls.sound=out.getvalue()
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def new(self,mode='text_story'):
        p=self.st.create(mode,'隔离验收')
        # Retain explicit coverage of pre-storyboard v5 projects.
        p['storyboard_version']=0
        p['settings']=defaults('dance_av')
        p['segments']=[self.st.new_segment(x) for x in story_plan(30)]
        for s in p['segments']:s['prompt']='A character quietly walks into a forest. <d>[Chinese]你好。</d>'
        return self.st.store.save(p,p['revision'])
    def asset(self,p,kind='image',subject='1',purpose='character'):
        return self.st.upload(p['id'],FileStorage(stream=io.BytesIO(self.image if kind=='image' else self.sound),filename='ref.png' if kind=='image' else 'voice.wav'),kind,purpose,subject)
    def commit(self,p):
        plan=self.st.edit_plan(p['id'],dict(revision=p['revision'],name=p['name'],duration=p['duration'],settings=p['settings'],segments=p['segments'],review=p['review']))
        return self.st.store.apply(p['id'],plan['token'])
    def test_01_frame_plan(self):
        for seconds in [1,3,5,8,14.37,15,16,30,31,47,60,3599.5,3600]:
            segs=story_plan(seconds)
            self.assertEqual(sum(s['deliver'] for s in segs),int(math.floor(seconds*24+.5)))
            self.assertTrue(all(s['raw']<=345 and s['raw']%17==5 for s in segs))
            self.assertTrue(all(s['tail']==0 for s in segs[:-1]))
        self.assertEqual(len(story_plan(15)),2)
        self.assertTrue(all(s['head']==0 for s in story_plan(30,boundaries={1:'new_scene',2:'new_scene'})))
    def test_02_asset_inheritance_and_audio(self):
        p=self.new('image_story');a=self.asset(p);b=self.asset(p,subject='2');palette=self.asset(p,subject='',purpose='palette');audio=self.asset(p,'audio',purpose='voice')
        p['segments'][0]['assets']=[a['id'],b['id'],palette['id'],audio['id']];p=self.commit(p)
        self.assertEqual(len(self.st.resolve(p,p['segments'][1])),4)
        report=self.st.preflight(p['id']);self.assertTrue(report['ready'],report['errors'])
        g=report['segments'][1]['compiled']['workflow'];self.assertIn('ref_audios.ref_audio_0',g['20']['inputs']);self.assertEqual(g['220']['inputs']['conditioning'],['20',0]);self.assertEqual(g['15']['inputs']['conditioning'],['105',0]);self.assertEqual(g['23']['inputs']['samples'],['16',0]);self.assertEqual(g['393']['inputs']['latent'],['16',0])
        p['segments'][1]['assets']=[audio['id']];p=self.commit(p)
        self.assertEqual(len(self.st.resolve(p,p['segments'][1])),1)
        self.assertFalse(self.st.preflight(p['id'])['ready'])
    def test_03_conflict_atomicity(self):
        p=self.new();p['settings']=defaults('official_text');p=self.commit(p);a=self.asset(p,'audio',purpose='voice');old=self.st.store.get(p['id'])
        p['segments'][0]['assets']=[a['id']];plan=self.st.edit_plan(p['id'],p)
        self.assertTrue(plan['requires_confirmation']);self.assertEqual(plan['settings']['recipe'],'text_ref');self.assertEqual(self.st.store.get(p['id']),old)
        p=self.st.store.apply(p['id'],plan['token']);self.assertEqual(p['settings']['model'],defaults('text_ref')['model'])
        with self.assertRaises(Conflict):self.st.store.apply(p['id'],plan['token'])
        plan=self.st.edit_plan(p['id'],p);self.st.store.mutate(p['id'],lambda x:x.update(name='并发修改'))
        with self.assertRaises(Conflict):self.st.store.apply(p['id'],plan['token'])
    def test_04_all_recipes_and_parameter_bindings(self):
        for rid,r in RECIPES.items():
            mode=r['modes'][0];p=self.new('image_story' if mode=='swap' else mode);p['mode']=mode;p['settings']=defaults(rid)
            if mode!='text_story':a=self.asset(p);p['segments'][0]['assets']=[a['id']]
            if rid=='text_ref':a=self.asset(p,'audio',purpose='voice');p['segments'][0]['assets']=[a['id']]
            p['settings']['size_mode']='custom';p['settings']['width']=512;p['settings']['height']=768
            p['settings']['head_chunks']=8;p['settings']['ff_chunks']=8
            p['settings']=self.st.recipes.normalize(p['settings'],mode)
            if mode=='swap':p['source_ready']=True
            p=self.st.store.save(p,p['revision']);report=self.st.preflight(p['id'])
            self.assertTrue(report['ready'],(rid,report['errors']))
            for row in report['segments']:
                graph=row['compiled']['workflow'];self.assertEqual(graph['20']['inputs']['width'],512);self.assertEqual(graph['211']['inputs']['head_chunks'],8);self.assertEqual(graph['18']['inputs']['audio'],['23',0])
        p=self.new();p['settings']['loras']=[dict(file='',strength=0,bypass=True) for _ in range(3)];p=self.commit(p);g=self.st.preflight(p['id'])['segments'][0]['compiled']['workflow'];self.assertFalse(any(n['class_type'].endswith('LoRA') or n['class_type']=='LoraLoaderModelOnly' for n in g.values()))
    def test_05_media_trim_export(self):
        src=self.root/'fixture.mp4';av.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','testsrc2=s=128x128:r=24:d=3','-f','lavfi','-i','sine=frequency=440:sample_rate=32000:duration=3','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',src])
        a=self.root/'a/delivery.mp4';b=self.root/'b/delivery.mp4';av.av_trim(src,a,0,24);av.av_trim(src,b,22,24)
        for fps in [24,30,60]:
            output,report=av.assemble([dict(delivery=str(a),deliver=24),dict(delivery=str(b),deliver=24)],self.root/f'export{fps}',fps)
            self.assertEqual(report['frames'],2*fps);self.assertEqual(report['audio_rate'],32000);self.assertAlmostEqual(report['duration'],2,places=2)
    def test_06_no_legacy_mutations(self):
        response=self.client.post('/api/projects',data={});self.assertEqual(response.status_code,409)
    def test_07_official_acceleration(self):
        p=self.new();p['settings']=defaults('official_text');p['settings']['acceleration']=True;p=self.commit(p)
        c=self.st.preflight(p['id'])['segments'][0]['compiled'];self.assertEqual(c['effective_steps'],8)
        p['settings']['accel_strength']=0;p=self.commit(p);c=self.st.preflight(p['id'])['segments'][0]['compiled'];self.assertEqual(c['effective_steps'],20);self.assertNotIn('200',c['workflow'])
    def test_08_simulated_queue_review_and_recovery(self):
        p=self.new();p['duration']=15;p=self.commit(p);calls=[];records={}
        old_submit=self.st.comfy.submit;old_wait=self.st.comfy.wait
        def fake_submit(graph,client):
            calls.append(graph);n=graph['20']['inputs']['length'];prefix=graph['19']['inputs']['filename_prefix'];movie=self.st.output/(prefix+'.mp4');movie.parent.mkdir(parents=True,exist_ok=True)
            av.run(['ffmpeg','-y','-v','error','-f','lavfi','-i',f'color=c=gray:s=128x128:r=24:d={n/24:.9f}','-f','lavfi','-i',f'sine=frequency=330:sample_rate=32000:duration={n/24:.9f}','-frames:v',str(n),'-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',movie])
            context=self.st.output/(graph['393']['inputs']['filename_prefix']+'_00001.safetensors');header=json.dumps({'video':{},'audio':{}}).encode();context.write_bytes(len(header).to_bytes(8,'little')+header)
            key=f'simulated-{len(calls)}';rel=movie.relative_to(self.st.output);records[key]={key:{'status':{'status_str':'success'},'outputs':{'19':{'images':[{'filename':rel.name,'subfolder':rel.parent.as_posix()}]}}}};return key
        self.st.comfy.submit=fake_submit;self.st.comfy.wait=lambda key:records[key]
        try:
            self.st.run_chain(p['id'],None,True);p=self.st.store.get(p['id']);self.assertEqual(len(calls),1);self.assertEqual(p['segments'][0]['status'],'needs_review',p.get('error'))
            original_get=self.st.comfy._get
            self.st.comfy._get=lambda endpoint: {'queue_running':[],'queue_pending':[]} if endpoint=='/queue' else records[endpoint.split('/')[-1]]
            try:
                self.st.store.mutate(p['id'],lambda q:q['segments'][0].update(status='interrupted'))
                self.st.recover(p['id'],0)
                self.assertEqual(len(calls),1)
                recovered=self.st.store.get(p['id']);self.assertEqual(recovered['segments'][0]['status'],'needs_review');self.assertEqual(recovered['segments'][0]['attempts'][0]['qa']['audio_rate'],32000)
            finally:self.st.comfy._get=original_get
            self.st.approve(p['id'],0);self.st.run_chain(p['id'],None,True);p=self.st.store.get(p['id']);self.assertEqual(len(calls),2);self.assertEqual(calls[1]['101']['inputs']['latent_path'],p['segments'][0]['attempts'][0]['context'])
            self.st.approve(p['id'],1)
            deadline=time.time()+15
            while self.st.jobs.is_busy() and time.time()<deadline:time.sleep(.05)
            p=self.st.store.get(p['id']);self.assertEqual(p['status'],'complete',p.get('error'));self.assertEqual(p['export']['report']['frames'],360)
            # Seed mode is next-run configuration and must not discard an accepted candidate.
            selected=p['segments'][0]['selected'];p['segments'][0].update(seed_mode='fixed',seed=p['segments'][0]['last_seed']);p=self.commit(p);self.assertEqual(p['segments'][0]['selected'],selected)
            p['settings']['steps']+=1;p=self.commit(p);self.assertIsNone(p['segments'][0]['selected']);self.assertIsNone(p['export'])
        finally:self.st.comfy.submit=old_submit;self.st.comfy.wait=old_wait

if __name__=='__main__':unittest.main(verbosity=2)
