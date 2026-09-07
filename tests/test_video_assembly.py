"""Actual temporary API/media/compiler tests. Engine calls are forbidden by default."""
import copy
import io
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from h3ui import create_app
from h3ui.comfy import ComfyClient
from h3ui.studio_recipes import defaults
from h3ui.studio_store import Conflict
from h3ui.video_assembly import compiler,media


class AssemblyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media_temp=tempfile.TemporaryDirectory();cls.media_root=Path(cls.media_temp.name)
        cls.silent=cls.media_root/'无声横屏.mp4';cls.sound=cls.media_root/'声音竖屏.mp4'
        media.command(['ffmpeg','-nostdin','-y','-v','error','-f','lavfi','-i','color=c=red:s=160x96:r=30:d=2','-c:v','libx264','-pix_fmt','yuv420p',cls.silent])
        media.command(['ffmpeg','-nostdin','-y','-v','error','-f','lavfi','-i','color=c=blue:s=96x160:r=25:d=2','-f','lavfi','-i','sine=frequency=440:duration=2','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',cls.sound])

    @classmethod
    def tearDownClass(cls): cls.media_temp.cleanup()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        cfg=dict(studio_data_dir=str(self.root/'projects'),data_dir=str(self.root/'legacy'),asset_library_dir=str(self.root/'library'),
                 comfy_base_dir=str(self.root/'comfy'),comfy_input_dir=str(self.root/'input'),comfy_output_dir=str(self.root/'output'),
                 comfy_url='http://127.0.0.1:1',studio_disable_generation=True,studio_progress_disabled=True,image_assets_enabled=True,open_browser=False)
        file=self.root/'config.json';file.write_text(json.dumps(cfg),encoding='utf-8')
        for method in ('_get','_post'):
            stub=patch.object(ComfyClient,method,side_effect=AssertionError('No engine network'))
            stub.start();self.addCleanup(stub.stop)
        self.app=create_app(str(file),recover_tasks=False);self.c=self.app.test_client();self.s=self.app.config['VIDEO_ASSEMBLY'];self.st=self.s.st
        response=self.c.post('/api/v5/projects',json=dict(mode='video_assembly',name='隔离拼接'))
        self.assertEqual(response.status_code,200,response.get_json());self.p=response.get_json();self.pid=self.p['id']

    def refresh(self): self.p=self.c.get('/api/v5/projects/'+self.pid).get_json();return self.p

    def post(self,endpoint,**data):
        response=self.c.post('/api/v5/assembly/'+self.pid+'/'+endpoint,json={'revision':self.p['revision'],**data})
        self.assertEqual(response.status_code,200,response.get_json());self.refresh();return response.get_json()

    def upload(self,path=None):
        file=path or self.silent
        r=self.c.post('/api/v5/assembly/'+self.pid+'/import',data=dict(revision=str(self.p['revision']),file=(io.BytesIO(file.read_bytes()),file.name)))
        self.assertEqual(r.status_code,200,r.get_json());self.p=r.get_json();return self.p['assembly']['clips'][-1]

    def extension(self):
        clip=self.upload();self.post('extensions',clip=clip['id']);return self.p['assembly']['clips'][0]['extensions'][0]

    def payload(self):
        return dict(name=self.p['name'],output=self.p['assembly']['output'],clips=[{**c,'extensions':[e for e in c['extensions'] if not e.get('removed_at')]} for c in self.p['assembly']['clips'] if not c.get('removed_at')])

    def test_two_real_graphs_external_tail_nondefault_bindings_and_old_graph_unchanged(self):
        context=dict(kind='external_decoded_av',frame_count=22,video='tail.mkv',audio='tail.wav')
        for key in compiler.RECIPES:
            s=defaults(key);p=dict(id='test',mode='image_story',settings=s);part=compiler.plan(2)[0]
            segment=dict(id='s',assets=[],inherit_ids=[],index=0,seed='0',**part)
            previous=dict(video='tail.mkv',audio='tail.wav',frame_count=22)
            original=self.st.recipes.compile(p,segment,[],'向前走',previous=previous)
            changed=copy.deepcopy(s);changed.update(steps=16,model='custom.safetensors',size_mode='custom',width=320,height=192)
            result=compiler.compile_tail(self.st.recipes,'test','s',changed,part,0,'向前走',context,'r')
            self.assertEqual(result['issues'],[])
            g=result['workflow'];self.assertEqual(g['12']['inputs']['noise_seed'],0)
            self.assertEqual(g['20']['inputs']['prompt'],'向前走');self.assertEqual(g['20']['inputs']['width'],320)
            self.assertEqual(g['105']['inputs']['context_audio'],['645',0]);self.assertEqual(g['645']['inputs']['audio'],'tail.wav')
            self.assertEqual(g['101']['inputs']['file'],'tail.mkv');self.assertEqual(g['1']['inputs']['unet_name'],'custom.safetensors')
            self.assertFalse(any('ref_video' in k for k in g['20']['inputs']))
            self.assertEqual(original,self.st.recipes.compile(p,segment,[],'向前走',previous=previous))

    def test_frame_planner_first_task_has_context_exact_added_length(self):
        for seconds in (1,5,15,30,120):
            parts=compiler.plan(seconds)
            self.assertEqual(sum(p['deliver'] for p in parts),seconds*24)
            self.assertTrue(all(p['head']==22 and p['raw']%17==5 and 124<=p['raw']<=345 for p in parts))

    def test_save_both_recipe_drafts_seed_zero_and_revision(self):
        self.extension();e=self.p['assembly']['clips'][0]['extensions'][0]
        e.update(prompt='继续行走',seed_mode='fixed',seed='0',recipe='official_image')
        e['configurations']['dance_split']['steps']=16;e['configurations']['official_image']['steps']=24
        payload=self.payload();old=self.p['revision'];self.post('save',**payload)
        e=self.p['assembly']['clips'][0]['extensions'][0];self.assertEqual(e['seed'],'0')
        self.assertEqual(e['configurations']['dance_split']['steps'],16);self.assertEqual(e['configurations']['official_image']['steps'],24)
        result=self.c.post('/api/v5/assembly/'+self.pid+'/save',json={**payload,'revision':old});self.assertEqual(result.status_code,409)
        check=self.c.get(f'/api/v5/assembly/{self.pid}/preflight/{e["id"]}');self.assertEqual(check.status_code,200,check.get_json())
        self.assertEqual(check.get_json()['issues'],[])

    def test_actual_mixed_media_export_keeps_sources_and_can_ingest(self):
        a=self.upload();b=self.upload(self.sound);hashes=[media.digest(a['file']),media.digest(b['file'])]
        self.p['assembly']['clips'].reverse();self.p['assembly']['clips'][0]['start']=.5
        self.post('save',**self.payload());self.post('export')
        self.wait_done();run=self.p['assembly']['runs'][-1]
        self.assertEqual(run['state'],'success',run.get('error'));self.assertAlmostEqual(run['report']['duration'],3.5,delta=.05)
        self.assertTrue(run['report']['audio']);self.assertEqual([media.digest(a['file']),media.digest(b['file'])],hashes)
        for second,channel in ((.25,2),(2.5,0)):
            rgb=self.root/f'pixel-{channel}.rgb'
            media.command(['ffmpeg','-nostdin','-y','-v','error','-ss',second,'-i',run['file'],'-vf','crop=2:2:iw/2:ih/2,format=rgb24','-frames:v','1','-f','rawvideo',rgb])
            pixel=rgb.read_bytes()[:3];self.assertGreater(pixel[channel],200)
        wav=self.root/'sound-check.wav'
        media.command(['ffmpeg','-nostdin','-y','-v','error','-i',run['file'],'-vn','-ar','32000','-ac','1','-c:a','pcm_s16le',wav])
        import wave,array
        with wave.open(str(wav)) as stream:samples=array.array('h',stream.readframes(stream.getnframes()))
        self.assertGreater(sum(abs(v) for v in samples[16000:19200])/3200,100)
        self.assertLess(sum(abs(v) for v in samples[80000:83200])/3200,10)
        self.assertEqual(self.c.get('/api/v5/tasks').get_json()['active_count'],0)
        result=self.post('ingest',run=run['id']);self.assertIn('asset',result)
        result2=self.post('ingest',run=run['id']);self.assertEqual(result['asset'],result2['asset'])
        self.post('visibility',kind='run',id=run['id'],removed=True)
        trash=self.c.get('/api/v5/recycle-bin?category=generations').get_json();self.assertEqual(trash['items'][0]['type'],'assembly_run')
        self.post('visibility',kind='run',id=run['id'],removed=False)
        self.assertTrue(Path(run['file']).exists())

    def wait_done(self):
        for _ in range(200):
            self.refresh()
            if not self.st.jobs.is_busy(self.pid) and not any(r['state'] in ('preparing','submitting','running') for r in self.p['assembly']['runs']): return
            time.sleep(.05)
        self.fail('worker did not finish')

    def test_external_tail_actual_frame_audio_and_short_clip(self):
        directory=self.st.input/'test'
        context=media.tail(self.silent,0,2,directory,160,96,self.st.input)
        self.assertTrue(context['silent_source']);video=self.st.input/context['video'];audio=self.st.input/context['audio']
        count=media.command(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=nb_read_frames','-of','csv=p=0',video]).strip()
        self.assertEqual(int(count),22)
        import wave
        with wave.open(str(audio)) as w:self.assertEqual(w.getnframes(),32000)
        with self.assertRaises(ValueError):media.tail(self.silent,0,.5,directory,160,96,self.st.input)

    def test_remove_restore_zero_clips_and_protect_running_unknown(self):
        clip=self.upload();self.post('visibility',kind='clip',id=clip['id'],removed=True)
        self.assertFalse([c for c in self.p['assembly']['clips'] if not c.get('removed_at')])
        item=self.c.get('/api/v5/recycle-bin?category=projects').get_json()['items'][0]
        self.assertEqual(item['type'],'assembly_clip');self.post('visibility',kind='clip',id=clip['id'],removed=False)
        self.st.store.mutate(self.pid,lambda p:p['assembly']['runs'].append(dict(id='uncertain',kind='generate',state='unknown',created=1,snapshot={},tasks=[])))
        self.refresh();response=self.c.post('/api/v5/projects/'+self.pid+'/trash',json=dict(revision=self.p['revision']))
        self.assertEqual(response.status_code,409)
        rows=self.c.get('/api/v5/tasks').get_json()['tasks'];self.assertEqual(rows[0]['kind'],'assembly');self.assertIn('recover',rows[0]['actions'])

    def test_library_video_fixed_version_and_source_protection(self):
        item=self.s.lib.ingest(self.sound,'固定视频')
        entry=item['snapshot']['media'][0]
        self.post('import',reference=dict(asset=item['id'],version=item['snapshot']['id'],media=entry['id']))
        clip=self.p['assembly']['clips'][0]
        self.assertEqual(clip['provenance']['version'],item['snapshot']['id']);self.assertEqual(media.digest(clip['file']),media.digest(self.sound))
        response=self.c.post('/api/v5/projects/'+self.pid+'/change-plan',json={});self.assertEqual(response.status_code,400)

    def test_cancel_owns_child_and_does_not_publish_partial(self):
        self.upload();entered=threading.Event()
        def waiting(parts,directory,output,cancel,progress):
            entered.set();cancel.wait(3)
            if cancel.is_set():raise media.Cancelled('已停止')
            raise RuntimeError('cancel missing')
        with patch('h3ui.video_assembly.media.assemble',side_effect=waiting):
            self.post('export');self.assertTrue(entered.wait(1));run=self.p['assembly']['runs'][-1]
            self.post('control',run=run['id'],action='stop',confirmed=True);self.wait_done()
        run=self.p['assembly']['runs'][-1];self.assertEqual(run['state'],'cancelled');self.assertNotIn('file',run)

    def test_real_child_cancellation_and_vfr_rotation_normalization(self):
        import sys
        stop=threading.Event();timer=threading.Timer(.25,stop.set);timer.start()
        before=time.monotonic()
        try:
            with self.assertRaises(media.Cancelled):media.command([sys.executable,'-c','import time;time.sleep(30)'],stop)
        finally:timer.cancel()
        self.assertLess(time.monotonic()-before,5)
        vfr=self.root/'variable.mp4'
        media.command(['ffmpeg','-nostdin','-y','-v','error','-i',self.silent,'-vf',r'setpts=N/(if(lt(N\,30)\,30\,20)*TB)',
                       '-fps_mode','vfr','-c:v','libx264',vfr])
        rotated=self.root/'rotated.mp4'
        media.command(['ffmpeg','-nostdin','-y','-v','error','-display_rotation:v:0','90','-i',self.sound,'-c','copy',rotated])
        self.assertEqual(media.inspect(rotated)['width'],160)
        a=self.upload(vfr);self.upload(rotated);self.post('export');self.wait_done()
        r=self.p['assembly']['runs'][-1];self.assertEqual(r['state'],'success',r.get('error'))
        self.assertAlmostEqual(r['report']['duration'],round(a['meta']['duration']*24)/24+2,delta=.05)

    def test_unknown_submit_never_retries_without_tracking_and_close_is_explicit(self):
        self.extension();eid=self.p['assembly']['clips'][0]['extensions'][0]['id']
        self.p['assembly']['clips'][0]['extensions'][0]['prompt']='继续行走';self.post('save',**self.payload())
        self.st.ctx['cfg']['studio_disable_generation']=False
        with patch.object(self.st.recipes,'connect',return_value={}),patch.object(self.st.comfy,'_get',return_value={}),patch.object(self.st.comfy,'submit',side_effect=RuntimeError('uncertain response')) as submit:
            self.post('generate',extension=eid);self.wait_done();r=self.p['assembly']['runs'][-1]
            self.assertEqual(r['state'],'unknown');self.assertEqual(submit.call_count,1)
            response=self.c.post('/api/v5/assembly/'+self.pid+'/generate',json=dict(revision=self.p['revision'],extension=eid));self.assertEqual(response.status_code,409)
            self.post('control',run=r['id'],action='close',confirmed=True)
            self.assertEqual(self.p['assembly']['runs'][-1]['state'],'cancelled');self.assertEqual(submit.call_count,1)

    def test_stop_checks_exact_engine_owner_and_active_import_is_listed(self):
        clip=self.upload();rid='owned';event=threading.Event();self.s.controls[rid]=event
        self.st.store.mutate(self.pid,lambda p:p['assembly']['runs'].append(dict(id=rid,kind='generate',state='running',created=1,seed=0,snapshot={},tasks=[],prompt_id='prompt',client_id='mine')))
        with patch.object(self.st.comfy,'_get',return_value={'queue_running':[[0,'prompt',{}, {'client_id':'someone-else'}]]}),patch.object(self.st.comfy,'cancel_job') as cancel:
            with self.assertRaises(Conflict):self.s.control(self.pid,rid,'stop')
            cancel.assert_not_called();self.assertFalse(event.is_set())
        self.s.controls.pop(rid)
        self.st.store.mutate(self.pid,lambda p:p['assembly']['runs'][-1].update(kind='import',state='preparing'))
        task=self.c.get('/api/v5/tasks').get_json()['tasks'][0];self.assertEqual(task['title'],'导入视频')

    def test_mutations_cannot_replace_source_or_remove_via_save(self):
        self.upload();payload=self.payload();payload['clips']=[]
        response=self.c.post('/api/v5/assembly/'+self.pid+'/save',json=dict(revision=self.p['revision'],**payload))
        self.assertEqual(response.status_code,409)
        payload=self.payload();source=payload['clips'][0]['file'];payload['clips'][0]['file']='C:/Windows/win.ini'
        self.post('save',**payload);self.assertEqual(self.p['assembly']['clips'][0]['file'],source)

    def test_background_progress_does_not_block_independent_draft_or_change_run_snapshot(self):
        self.extension();e=copy.deepcopy(self.p['assembly']['clips'][0]['extensions'][0]);base=self.p['assembly']['draft_revision']
        self.st.store.mutate(self.pid,lambda p:p['assembly']['runs'].append(dict(id='active',kind='generate',state='running',created=1,tasks=[],snapshot=dict(extension=e))))
        self.p['assembly']['clips'][0]['extensions'][0]['prompt']='下一次使用的描述'
        payload=self.payload();self.post('save',draft_revision=base,**payload)
        self.assertEqual(self.p['assembly']['clips'][0]['extensions'][0]['prompt'],'下一次使用的描述')
        self.assertEqual(self.p['assembly']['runs'][-1]['snapshot']['extension']['prompt'],'')
        response=self.c.post('/api/v5/assembly/'+self.pid+'/save',json={**payload,'revision':self.p['revision'],'draft_revision':base})
        self.assertEqual(response.status_code,409)

    def test_two_recipe_fake_engine_complete_run_then_select(self):
        self.extension();eid=self.p['assembly']['clips'][0]['extensions'][0]['id']
        self.reference_upload(eid);self.reference_upload(eid,'audio')
        raw=self.root/'output.mp4'
        media.command(['ffmpeg','-nostdin','-y','-v','error','-f','lavfi','-i','color=c=green:s=160x96:r=24:d=6',
                       '-f','lavfi','-i','sine=frequency=660:duration=6','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',raw])
        for recipe in compiler.RECIPES:
            self.refresh();e=self.p['assembly']['clips'][0]['extensions'][0];e.update(prompt='继续行走',seconds=2,recipe=recipe,seed_mode='fixed',seed='0')
            self.post('save',**self.payload());graphs=[]
            self.st.ctx['cfg']['studio_disable_generation']=False
            def submit(graph,client_id):graphs.append(copy.deepcopy(graph));return 'fake-prompt'
            with patch.object(self.st.recipes,'connect',return_value={}),patch.object(self.st.comfy,'_get',return_value={}),patch.object(self.st.comfy,'submit',side_effect=submit),patch.object(self.st.comfy,'wait',return_value={}),patch.object(self.st.comfy,'first_video',return_value=raw):
                self.post('generate',extension=eid);self.wait_done()
            self.st.ctx['cfg']['studio_disable_generation']=True
            run=self.p['assembly']['runs'][-1];self.assertEqual(run['state'],'success',run.get('error'))
            self.assertEqual(run['snapshot']['tail_preparation'],media.TAIL_PREPARATION)
            prepared=self.st.input/graphs[0]['101']['inputs']['file']
            self.assertEqual((media.inspect(prepared)['width'],media.inspect(prepared)['height']),(160,96))
            self.assertEqual(len(graphs),1);self.assertEqual(graphs[0]['12']['inputs']['noise_seed'],0)
            self.assertTrue((self.st.input/graphs[0]['400']['inputs']['image']).is_file())
            self.assertTrue((self.st.input/graphs[0]['401']['inputs']['audio']).is_file())
            self.assertEqual(len(run['snapshot']['assets']),2)
            self.assertAlmostEqual(run['report']['duration'],2,delta=.05)
            self.post('select',extension=eid,run=run['id'])
            response=self.c.post('/api/v5/assembly/'+self.pid+'/visibility',json=dict(revision=self.p['revision'],kind='run',id=run['id'],removed=True));self.assertEqual(response.status_code,409)
        self.p['assembly']['clips'][0]['end']=1.5;self.post('save',**self.payload())
        self.assertIsNone(self.p['assembly']['clips'][0]['extensions'][0]['selected'])


    def reference_upload(self,eid,kind='image'):
        from PIL import Image
        import wave
        stream=io.BytesIO()
        if kind=='image':Image.new('RGB',(32,48),'orange').save(stream,format='PNG');name='角色.png'
        else:
            with wave.open(stream,'wb') as audio:
                audio.setparams((1,2,32000,0,'NONE','not compressed'));audio.writeframes(b'\0'*128000)
            name='参考声音.wav'
        response=self.c.post('/api/v5/assembly/'+self.pid+'/references',data=dict(revision=str(self.p['revision']),extension=eid,kind=kind,file=(io.BytesIO(stream.getvalue()),name)))
        self.assertEqual(response.status_code,200,response.get_json());self.p=response.get_json()
        return self.p['assembly']['references'][-1]

    def test_reference_inputs_both_graphs_and_tail_are_independent(self):
        e=self.extension();eid=e['id'];self.reference_upload(eid);self.reference_upload(eid,'audio')
        for recipe in compiler.RECIPES:
            e=self.p['assembly']['clips'][0]['extensions'][0];e.update(recipe=recipe,prompt='<Picture 1>角色继续行走，<Audio 1>提供音色。')
            self.post('save',**self.payload());result=self.s.preflight(self.pid,eid)
            self.assertEqual([a['tag'] for a in result['input_inventory']],['<Picture 1>','<Audio 1>'])
            assets=self.s.reference_assets(self.s.get(self.pid),e)
            compiled=compiler.compile_tail(self.st.recipes,self.pid,eid,e['configurations'][recipe],compiler.plan(2)[0],0,e['prompt'],dict(kind='external_decoded_av',frame_count=22,video='tail.mkv',audio='tail.wav'),'r',assets)
            graph=compiled['workflow'];self.assertEqual(graph['20']['inputs']['ref_images.ref_image_0'],['400',0]);self.assertEqual(graph['20']['inputs']['ref_audios.ref_audio_0'],['401',0])
            self.assertEqual(graph['400']['inputs']['image'],assets[0]['input_name']);self.assertEqual(graph['645']['inputs']['audio'],'tail.wav')
            self.assertEqual(graph['105']['inputs']['context_frames'],['103',0])
        self.p['assembly']['clips'][0]['extensions'][0]['prompt']='<Picture 2>不存在';self.post('save',**self.payload())
        with self.assertRaisesRegex(ValueError,'引用不存在'):self.s.preflight(self.pid,eid)

    def test_reference_save_removal_snapshot_and_foreign_id(self):
        e=self.extension();eid=e['id'];self.reference_upload(eid);e=self.p['assembly']['clips'][0]['extensions'][0];e['prompt']='继续';self.post('save',**self.payload())
        self.st.ctx['cfg']['studio_disable_generation']=False
        with patch.object(self.st.jobs,'start',return_value=False):
            self.c.post('/api/v5/assembly/'+self.pid+'/generate',json=dict(revision=self.p['revision'],extension=eid))
        self.refresh();run=copy.deepcopy(self.p['assembly']['runs'][-1]);self.assertEqual(len(run['snapshot']['assets']),1)
        self.p['assembly']['clips'][0]['extensions'][0]['references']=[];self.post('save',**self.payload())
        self.assertEqual(self.p['assembly']['runs'][-1]['snapshot'],run['snapshot']);self.assertTrue(Path(run['snapshot']['assets'][0]['path']).exists())
        self.p['assembly']['clips'][0]['extensions'][0]['references']=[dict(id='foreign',purpose='character',subject='1')]
        response=self.c.post('/api/v5/assembly/'+self.pid+'/save',json=dict(revision=self.p['revision'],**self.payload()));self.assertEqual(response.status_code,400)

    def test_reference_library_fixed_version_and_metadata_are_not_prompt(self):
        e=self.extension();aid=self.reference_upload(e['id']);source=self.s.get(self.pid)['assembly']['references'][0]
        item=self.s.lib.ingest(Path(source['path']),'固定角色',key='fixture-reference')
        fixed=self.s.lib.store.get(item['id']);m=fixed['snapshot']['media'][0]
        self.post('references',extension=e['id'],reference=dict(asset=item['id'],version=fixed['snapshot']['id'],media=m['id']))
        ref=self.s.get(self.pid)['assembly']['references'][-1];self.assertEqual(ref['library_reference']['version'],fixed['snapshot']['id']);self.assertEqual(self.p['assembly']['clips'][0]['extensions'][0]['prompt'],'')
        self.assertNotEqual(ref['path'],source['path']);self.assertEqual(ref['sha256'],source['sha256'])


if __name__=='__main__':unittest.main()
