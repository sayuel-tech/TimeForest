"""Filesystem refresh and exact model binding; all ComfyUI requests are mocked."""
import json,unittest
from pathlib import Path
from unittest.mock import patch
import test_local_server as fixture
from h3ui.studio_recipes import defaults
from h3ui.comfy import ComfyError

class ModelSelectionTests(unittest.TestCase):
    def setUp(self):fixture.LocalServerTests.setUp(self)
    def test_refresh_detects_added_renamed_removed_files_and_extra_paths(self):
        base=self.root/'models'
        for folder in ['diffusion_models','unet','loras','vae','clip','text_encoders']:
            (base/folder).mkdir(parents=True)
            (base/folder/'new-model.safetensors').write_bytes(b'fixture')
        nested=base/'diffusion_models'/'新版本';nested.mkdir()
        (nested/'free-name.safetensors').write_bytes(b'fixture')
        extra=self.root/'external';extra.mkdir();(extra/'new-lora.pt').write_bytes(b'fixture')
        (self.root/'extra_model_paths.yaml').write_text('extra:\n  base_path: external\n  loras: |\n    .\n',encoding='utf-8')
        result=self.client.get('/api/v5/catalog').json
        self.assertIn(str(Path('新版本/free-name.safetensors')),result['models'])
        self.assertIn('new-model.safetensors',result['clips'])
        self.assertIn('new-model.safetensors',result['vaes'])
        self.assertIn('new-lora.pt',result['loras'])
        file=nested/'free-name.safetensors';file.rename(nested/'renamed.safetensors')
        (extra/'new-lora.pt').unlink()
        next=self.client.get('/api/v5/catalog').json
        self.assertNotIn(str(Path('新版本/free-name.safetensors')),next['models'])
        self.assertIn(str(Path('新版本/renamed.safetensors')),next['models'])
        self.assertNotIn('new-lora.pt',next['loras'])
        self.assertEqual(next['local_models']['source'],'filesystem')
    def test_arbitrary_model_files_saved_and_bound_without_correction(self):
        p=self.st.create('text_story','原样提交',15);s=defaults('official_text')
        s.update(model='unknown-ref-experiment.safetensors',clip='custom-encoder.pt',video_vae='decoder-a.pt',audio_vae='decoder-b.pt',acceleration=True,accel_file='custom-speed.safetensors')
        p['settings']=s;p['segments'][0]['prompt']='A quiet forest.'
        plan=self.st.edit_plan(p['id'],p);saved=self.st.store.apply(p['id'],plan['token'])
        self.assertEqual(saved['settings']['model'],s['model'])
        normalized=self.st.recipes.normalize(s,'text_story',online=True)
        for k in ['model','clip','video_vae','audio_vae','accel_file']:self.assertEqual(normalized[k],s[k])
        graph=self.st.recipes.compile(saved,saved['segments'][0],[],p['segments'][0]['prompt'])['workflow']
        for node,key,value in [('1','unet_name',s['model']),('2','clip_name',s['clip']),('3','vae_name',s['video_vae']),('4','vae_name',s['audio_vae']),('200','lora_name',s['accel_file'])]:
            self.assertEqual(graph[node]['inputs'][key],value)
    def test_dance_lora_files_preserved(self):
        s=defaults();s['model']='unrecognized-model.pt'
        for i,l in enumerate(s['loras']):l.update(file=f'custom-{i}.pt',bypass=False,strength=.42)
        p=self.st.create('text_story','三个自选LoRA',15);p['settings']=s
        normalized=self.st.recipes.normalize(s,'text_story',online=True)
        self.assertEqual(normalized['loras'],s['loras'])
        graph=self.st.recipes.compile(p,p['segments'][0],[],'A forest.')['workflow']
        for i,l in enumerate(s['loras']):self.assertEqual(graph[str(200+i)]['inputs']['lora_name'],l['file'])
    def test_comfy_error_reaches_project_and_attempt(self):
        p=self.st.create('text_story','错误回显',15)
        p['storyboard_version']=0;p['settings']=defaults('official_text');p['settings']['model']='unknown.safetensors'
        p['segments'][0]['prompt']='A forest.';p=self.st.store.save(p,p['revision'])
        message='ComfyUI /prompt HTTP 400: node 1 unet_name unknown.safetensors invalid'
        with patch.object(self.st.comfy,'submit',side_effect=ComfyError(message)) as submit:
            self.st.generate_one(p['id'],0)
        self.assertEqual(submit.call_args.args[0]['1']['inputs']['unet_name'],'unknown.safetensors')
        result=self.client.get('/api/v5/projects/'+p['id']).json
        self.assertEqual(result['error'],message)
        self.assertEqual(result['segments'][0]['attempts'][-1]['error'],message)

if __name__=='__main__':unittest.main()
