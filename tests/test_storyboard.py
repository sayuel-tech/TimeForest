"""Storyboard contracts. Comfy submit is replaced; no H3/model is run."""
import copy,json,math,time,unittest
from pathlib import Path
from test_studio import StudioAcceptance
from h3ui.studio_story import storyboard,task_segments
from h3ui.studio_recipes import defaults
from h3ui import studio_media as av

class StoryboardAcceptance(StudioAcceptance):
    # Old v5 regression cases remain in test_studio; do not rerun them here.
    def test_09_story_counts(self):
        for seconds,count in [(8,1),(15,1),(30,2),(40,3),(.0+1,1),(3600,240)]:
            for cap in [6,10,15]:
                plan=storyboard(seconds,cap,timing_mode='exact')
                self.assertEqual(len(plan),count)
                self.assertEqual(sum(s['deliver'] for s in plan),round(seconds*24))
                for s in plan:
                    self.assertLessEqual(s['deliver'],360)
                    self.assertEqual(sum(t['deliver'] for t in s['task_plan']),s['deliver'])
                    self.assertTrue(all(t['raw']<=cap*24 and t['raw']%17==5 for t in s['task_plan']))
                    self.assertTrue(all(t['tail']==0 for t in s['task_plan'][:-1]))
        natural=storyboard(30)
        self.assertEqual(len(natural),2)
        self.assertTrue(all(len(s['task_plan'])==1 for s in natural))
        self.assertEqual([s['deliver'] for s in natural],[345,323])
        self.assertEqual(storyboard(8)[0]['deliver'],192)
        self.assertEqual(len(storyboard(15,6)[0]['task_plan']),3)

    def test_10_preview_save_and_legacy(self):
        p=self.st.create('image_story','30秒两段',30)
        self.assertEqual(len(p['segments']),2)
        before=self.st.store.get(p['id'])
        incoming=copy.deepcopy(p['segments']);incoming[1]['prompt']='不得丢弃的第二分镜'
        response=self.client.post(f'/api/v5/projects/{p["id"]}/preview',json=dict(duration=15,settings=p['settings'],segments=incoming))
        self.assertEqual(response.status_code,200)
        d=response.json;self.assertEqual(len(d['segments']),1);self.assertEqual(d['removed'][0]['prompt'],incoming[1]['prompt'])
        self.assertEqual(self.st.store.get(p['id']),before)
        data={**p,'duration':15,'segments':d['segments'],'removed_drafts':d['removed']}
        plan=self.st.edit_plan(p['id'],data)
        self.assertTrue(plan['requires_confirmation']);self.assertEqual(self.st.store.get(p['id']),before)
        saved=self.st.store.apply(p['id'],plan['token'])
        self.assertEqual(saved['duration'],15);self.assertEqual(len(saved['segments']),1)
        self.assertTrue(any(s['prompt']==incoming[1]['prompt'] for s in saved['removed_drafts']))
        old=self.new();self.assertEqual(len(old['segments']),3)
        old['segments'][2]['prompt']='旧第三段'
        old=self.st.store.save(old,old['revision']);plan=self.st.edit_plan(old['id'],{**old,'storyboard_version':1})
        self.assertEqual(len(plan['segments']),2)
        old=self.st.store.apply(old['id'],plan['token']);self.assertEqual(old['previous_layouts'][0][2]['prompt'],'旧第三段')

    def test_11_task_binding_and_prompt(self):
        for rid in ['dance_av','official_image','official_text','text_ref','wenxi_av']:
            mode='text_story' if rid in ['official_text','text_ref'] else 'image_story'
            p=self.st.create(mode,'工作流检查',30);p['settings']=defaults(rid)
            p['timing_mode']='exact';p['segments']=[self.st.new_segment(x) for x in storyboard(30,timing_mode='exact')]
            if mode=='image_story':p['segments'][0]['assets']=[self.asset(p)['id']]
            if rid=='text_ref':p['segments'][0]['assets']=[self.asset(p,'audio')['id']]
            for s in p['segments']:s['prompt']='走入沙漠。停下脚步。<d>[Chinese]你好，世界。</d>';s.update(seed_mode='fixed',seed='123')
            p=self.st.store.save(p,p['revision']);r=self.st.preflight(p['id']);self.assertTrue(r['ready'],r['errors'])
            self.assertEqual(len(r['segments']),2)
            self.assertEqual(len(r['segments'][0]['tasks']),2)
            g=r['segments'][1]['tasks'][0]['compiled']['workflow']
            self.assertEqual(g['101']['class_type'],'LoadVideo');self.assertEqual(g['104']['inputs']['batch_index'],338)
            self.assertEqual(g['105']['inputs']['context_frames'],['103',0]);self.assertIn('context_audio',g['105']['inputs'])
            texts=[t['prompt'] for t in task_segments(self.st,p,p['segments'][0])]
            self.assertEqual(sum(t.count('<d>[Chinese]你好，世界。</d>') for t in texts),1)
            self.assertTrue(all(t['assets']==p['segments'][0]['assets'] for t in task_segments(self.st,p,p['segments'][1])))

    def test_12_simulated_story_review_recovery_and_export(self):
        p=self.st.create('text_story','30秒两分镜',30);p['settings']=defaults('official_text')
        p['timing_mode']='exact';p['segments']=[self.st.new_segment(x) for x in storyboard(30,timing_mode='exact')]
        for s in p['segments']:s.update(prompt='走进森林。看向远方。<d>[Chinese]你好。</d>',seed_mode='fixed',seed='123')
        p=self.st.store.save(p,p['revision']);calls=[];records={};fail_wait=[True]
        old_submit,old_wait,old_get=self.st.comfy.submit,self.st.comfy.wait,self.st.comfy._get
        def fake_submit(graph,client):
            calls.append(graph);n=graph['20']['inputs']['length'];prefix=graph['19']['inputs']['filename_prefix'];movie=self.st.output/(prefix+'.mp4');movie.parent.mkdir(parents=True,exist_ok=True)
            av.run(['ffmpeg','-y','-v','error','-f','lavfi','-i',f'color=c=gray:s=128x128:r=24:d={n/24:.9f}','-f','lavfi','-i',f'sine=frequency=330:sample_rate=32000:duration={n/24:.9f}','-frames:v',str(n),'-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',movie])
            context=self.st.output/(graph['393']['inputs']['filename_prefix']+'_00001.safetensors');header=json.dumps({'video':{},'audio':{}}).encode();context.write_bytes(len(header).to_bytes(8,'little')+header)
            key=f'fixture-{len(calls)}';rel=movie.relative_to(self.st.output);records[key]={key:{'status':{'status_str':'success'},'outputs':{'19':{'images':[{'filename':rel.name,'subfolder':rel.parent.as_posix()}]}}}};return key
        def fake_wait(key):
            if len(calls)==2 and fail_wait[0]:fail_wait[0]=False;raise TimeoutError('模拟回执中断')
            return records[key]
        self.st.comfy.submit=fake_submit;self.st.comfy.wait=fake_wait;self.st.comfy._get=lambda url: {'queue_running':[],'queue_pending':[]} if url=='/queue' else records[url.split('/')[-1]]
        try:
            self.st.run_chain(p['id'],None,True)
            q=self.st.store.get(p['id']);self.assertEqual(q['segments'][0]['status'],'interrupted',q.get('error'));self.assertEqual(len(calls),2)
            self.st.recover(p['id'],0);q=self.st.store.get(p['id'])
            self.assertEqual(len(calls),2);self.assertEqual(q['segments'][0]['status'],'needs_review',q.get('error'))
            a=q['segments'][0]['attempts'][0];self.assertEqual(a['qa']['frames'],360);self.assertEqual([t['last_seed'] for t in a['tasks']],['123','124'])
            self.st.approve(p['id'],0);self.st.run_chain(p['id'],None,True)
            q=self.st.store.get(p['id']);self.assertEqual(q['segments'][1]['status'],'needs_review',q.get('error'));self.assertEqual(len(calls),4)
            self.assertEqual(calls[2]['101']['class_type'],'LoadVideo')
            self.assertEqual(calls[2]['101']['inputs']['file'],a['delivery'])
            self.st.approve(p['id'],1)
            deadline=time.time()+25
            while self.st.jobs.is_busy() and time.time()<deadline:time.sleep(.05)
            q=self.st.store.get(p['id']);self.assertEqual(q['status'],'complete',q.get('error'));self.assertEqual(q['export']['report']['frames'],720)
            self.assertEqual(q['export']['report']['audio_rate'],32000)
        finally:self.st.comfy.submit,self.st.comfy.wait,self.st.comfy._get=old_submit,old_wait,old_get

    def test_13_natural_length_automatic(self):
        import shutil
        p=self.st.create('text_story','自然长度默认',30);p['settings']=defaults('official_text');p['review']='automatic'
        for s in p['segments']:s['prompt']='A person walks slowly through the desert.'
        p=self.st.store.save(p,p['revision']);graphs=[];records={}
        fixture=self.root/'natural.mp4'
        av.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=gray:s=128x128:r=24:d=14.375','-f','lavfi','-i','sine=frequency=220:sample_rate=32000:duration=14.375','-frames:v','345','-c:v','libx264','-c:a','aac',fixture])
        old_submit,old_wait=self.st.comfy.submit,self.st.comfy.wait
        def submit(g,client):
            graphs.append(g);dst=self.st.output/(g['19']['inputs']['filename_prefix']+'.mp4');dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(fixture,dst)
            context=self.st.output/(g['393']['inputs']['filename_prefix']+'_00001.safetensors');h=json.dumps({'video':{},'audio':{}}).encode();context.write_bytes(len(h).to_bytes(8,'little')+h)
            key=str(len(graphs));rel=dst.relative_to(self.st.output);records[key]={key:{'outputs':{'19':{'images':[{'filename':rel.name,'subfolder':rel.parent.as_posix()}]}}}};return key
        self.st.comfy.submit=submit;self.st.comfy.wait=lambda k:records[k]
        try:
            self.st.run_chain(p['id'],None,True);q=self.st.store.get(p['id'])
            self.assertEqual(q['status'],'complete',q.get('error'));self.assertEqual(len(graphs),2)
            self.assertEqual(q['duration'],30);self.assertEqual(q['export']['report']['frames'],668)
            self.assertEqual(graphs[1]['101']['class_type'],'MiniMaxH3MotionContextLoadLatent')
            self.assertNotEqual(graphs[0]['12']['inputs']['noise_seed'],graphs[1]['12']['inputs']['noise_seed'])
        finally:self.st.comfy.submit,self.st.comfy.wait=old_submit,old_wait

if __name__=='__main__':
    suite=unittest.TestSuite(StoryboardAcceptance(name) for name in unittest.defaultTestLoader.getTestCaseNames(StoryboardAcceptance) if name.startswith(('test_09','test_10','test_11','test_12','test_13')))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
