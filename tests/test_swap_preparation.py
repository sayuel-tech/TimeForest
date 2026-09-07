"""Isolated FFmpeg fixtures and workflow compilation. GPU submission is forbidden."""
import copy
from pathlib import Path
from unittest.mock import patch
from test_studio import StudioAcceptance
from werkzeug.datastructures import FileStorage
from h3ui.studio_recipes import defaults
from h3ui.studio_source import source_signature,source_options
from h3ui import studio_prompts,studio_media as av

class SwapPreparation(StudioAcceptance):
    def commit(self,p):
        plan=self.st.edit_plan(p['id'],p)
        return self.st.store.apply(p['id'],plan['token'])
    def draft(self):
        p=self.st.create('swap','隔离源视频检查')
        p['settings']=defaults('dance_split');p['settings'].update(size_mode='custom',width=128,height=128)
        return self.st.store.save(p,p['revision'])
    def video(self,p):
        file=self.root/'source.mp4'
        if not file.exists():av.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','testsrc2=s=128x128:r=24:d=7','-f','lavfi','-i','sine=frequency=440:sample_rate=32000:duration=7','-c:v','libx264','-c:a','aac','-shortest',file])
        with file.open('rb') as stream:return self.st.upload(p['id'],FileStorage(stream,filename='source.mp4'),'video','source','')
    def test_source_signature_only_tracks_input_geometry_and_effective_cut_rules(self):
        s=defaults('dance_split');a=source_signature(s)
        other={**s,'scale':2,'steps':30,'export_fps':60}
        self.assertEqual(a,source_signature(other))
        self.assertNotEqual(a,source_signature({**s,'megapixels':.5}))
        self.assertEqual(source_signature(s,{'segment_seconds':15})['raw'],345)
        self.assertEqual(source_signature({**s,'render_cap':8},{'segment_seconds':15})['raw'],192)
        with self.assertRaises(ValueError):source_options({'segment_seconds':float('nan')})
    def test_prepare_versions_matching_failure_and_archival(self):
        p=self.draft();a=self.video(p)
        p=self.st.prepare_source(p['id'],a['id']);self.assertEqual(len(p['segments']),2)
        oldfile=Path(p['source_normalized']);oldbytes=oldfile.read_bytes();oldids=[s['id'] for s in p['segments']]
        p['segments'][0]['assets']=[self.asset(p)['id']]
        p['segments'][0]['prompt']='first time range';p['segments'][1]['swap_prompt_mode']='custom';p['segments'][1]['swap_custom_prompt']='second time range'
        p=self.st.store.save(p,p['revision'])
        with patch('h3ui.studio_source.media.slice_segment',side_effect=RuntimeError('fixture disk failure')):
            with self.assertRaises(RuntimeError):self.st.prepare_source(p['id'],a['id'])
        self.assertEqual(self.st.store.get(p['id'])['source_normalized'],str(oldfile));self.assertEqual(oldfile.read_bytes(),oldbytes)
        p=self.st.prepare_source(p['id'],a['id'])
        self.assertEqual(p['segments'][1]['swap_custom_prompt'],'second time range')
        self.assertNotEqual(p['source_normalized'],str(oldfile));self.assertTrue(p['source_history'])
        p['source_options']={'segment_seconds':15,'detect_cuts':False,'cut_threshold':.45}
        p=self.commit(p);self.assertFalse(p['source_ready'])
        p=self.st.prepare_source(p['id'],a['id'])
        self.assertEqual(len(p['segments']),1);self.assertEqual(sum(s['deliver'] for s in p['segments']),168)
        self.assertEqual(p['segments'][0]['prompt'],'');self.assertTrue(p['segments'][0]['assets'])
        self.assertTrue(any(s.get('swap_custom_prompt')=='second time range' for s in p['removed_drafts']))
        self.assertEqual(oldfile.read_bytes(),oldbytes)
        progress=self.st.source_progress(p['id']);self.assertEqual(progress['phase'],'源视频准备完成');self.assertFalse(progress['active'])
    def test_only_second_pass_change_keeps_source_ready(self):
        p=self.draft();p['source_ready']=True;p=self.st.store.save(p,p['revision'])
        p['settings']['scale']=2;p=self.commit(p);self.assertTrue(p['source_ready'])
        p['settings']['width']=192;p=self.commit(p);self.assertFalse(p['source_ready'])
    def test_templates_and_custom_are_real_compiled_inputs(self):
        p=self.draft();p['source_ready']=True
        p['segments']=[self.st.new_segment(dict(index=0,start=0,raw=124,head=0,deliver=124,tail=0,boundary='new_scene',duration=124/24,input_name='source.mp4'))]
        p['segments'][0]['assets']=[self.asset(p)['id']];p=self.st.store.save(p,p['revision'])
        assets=self.st.resolve(p,p['segments'][0])
        dance=studio_prompts.build(p,p['segments'][0],assets)
        p['settings']=defaults('official_swap');official=studio_prompts.build(p,p['segments'][0],assets)
        self.assertNotEqual(dance,official)
        text='subject_definitions:\n<Picture 1> defines the replacement.\nsummary:\nReplace the performer in <Video 1>. Preserve the camera. CUSTOM_SENTINEL'
        p['swap_prompt']={'mode':'custom','custom':text};p=self.commit(p)
        self.assertEqual(studio_prompts.build(p,p['segments'][0],assets),text)
        graph=self.st.preflight(p['id'])['segments'][0]['compiled']['workflow']
        self.assertEqual(graph['20']['inputs']['prompt'],text)
        self.assertIn('ref_videos.ref_video_0',graph['20']['inputs'])
        self.assertIn('ref_images.ref_image_0',graph['20']['inputs'])
        p['segments'][0].update(swap_prompt_mode='template',prompt='LOCAL_SUPPLEMENT')
        self.assertIn('LOCAL_SUPPLEMENT',studio_prompts.build(p,p['segments'][0],assets))
        p['segments'][0].update(swap_prompt_mode='custom',swap_custom_prompt=text+' <d>new words</d>')
        with self.assertRaises(ValueError):studio_prompts.build(p,p['segments'][0],assets)
    def test_project_template_does_not_repeat_first_segment_timing(self):
        p=self.draft()
        endpoint=f"/api/v5/projects/{p['id']}/swap-template"
        project=self.client.post(endpoint,json={'scope':'project'}).get_json()['prompt']
        segment=self.client.post(endpoint,json={'scope':'segment'}).get_json()['prompt']
        self.assertNotEqual(project,segment)
        self.assertNotIn('124',project)
        self.assertIn('<Video 1>',project)
        self.assertIn('<Picture 1>',project)
    def test_background_failure_retains_candidate_and_old_version_for_retry(self):
        p=self.draft();a=self.video(p)
        p=self.st.prepare_source(p['id'],a['id']);old=p['source_normalized'];jobs=[]
        with patch.object(self.st.jobs,'start',side_effect=lambda kind,pid,work: jobs.append(work) or True):
            self.st.start_source(p['id'],a['id'],p['revision'],'edit')
        self.assertEqual(self.st.store.get(p['id'])['status'],'preparing')
        with patch.object(self.st,'prepare_source',side_effect=RuntimeError('fixture failure')):jobs[0]()
        failed=self.st.store.get(p['id']);progress=self.st.source_progress(p['id'])
        self.assertEqual(failed['source_candidate'],a['id'])
        self.assertEqual(failed['source_normalized'],old)
        self.assertTrue(Path(old).is_file())
        self.assertEqual(progress['phase'],'准备失败');self.assertFalse(progress['active'])
        self.assertEqual(progress['continue_to'],'edit')
