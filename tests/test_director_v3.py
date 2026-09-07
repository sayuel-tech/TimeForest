"""V3 input/prompt contracts: compile only, no engine submission or model load."""
import copy,tempfile,unittest
from pathlib import Path
from h3ui.studio_inputs import inventory,validate,validate_tags
from h3ui.studio_prompts import build
from h3ui.studio_recipes import Recipes,defaults
from h3ui.studio_speakers import speakers

class DirectorV3(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.recipes=Recipes(None,Path(self.tmp.name)/'catalog.json')
        self.p=dict(id='project',input_prompt_version=2,mode='swap',settings=defaults('dance_split'),swap_prompt=dict(mode='template',custom='',version=2))
        self.seg=dict(index=0,id='s',raw=124,head=0,deliver=124,tail=0,prompt='',seed_mode='fixed',seed='0',input_name='source.mp4')
        self.image=dict(id='image',name='角色四视图.png',kind='image',purpose='character',subject='1',sha256='hash',input_name='ref.png',record_prompt='<Picture 9> SHOULD NOT LEAK')
    def test_single_reference_tags_and_real_loader_match(self):
        text=build(self.p,self.seg,[self.image]);g=self.recipes.compile(self.p,self.seg,[self.image],text)
        self.assertIn('<Picture 1>',text);self.assertNotIn('<Subject 2>',text);self.assertNotIn('SHOULD NOT LEAK',text)
        self.assertEqual(g['workflow']['400']['inputs']['image'],'ref.png')
        for row in g['input_inventory']:
            self.assertIn(row['conditioning_input'],g['workflow']['20']['inputs'])
        self.assertEqual(g['workflow']['20']['inputs']['prompt'],text)
        self.assertEqual(g['prompt_template_version'],2)
    def test_old_template_stays_readable_and_custom_missing_picture_fails(self):
        self.p['swap_prompt']['version']=1;text=build(self.p,self.seg,[self.image]);self.assertIn('<Subject 2>',text)
        self.p['swap_prompt'].update(mode='custom',custom='<Picture 1> and <Picture 2> replace <Video 1>')
        with self.assertRaisesRegex(ValueError,'Picture'):build(self.p,self.seg,[self.image])
    def test_other_modes_retain_multiple_references(self):
        for mode in ['image_story','text_story']:
            self.p['mode']=mode;self.seg['prompt']='Two people walk into a forest.'
            assets=[self.image,{**self.image,'id':'second','subject':'2','input_name':'second.png'}]
            text=build(self.p,self.seg,assets);g=self.recipes.compile(self.p,self.seg,assets,text)
            self.assertIn('<Picture 2>',text);self.assertEqual(len(g['input_inventory']),2)
            self.assertEqual(g['workflow']['401']['inputs']['image'],'second.png')
    def test_subject_two_can_speak_first(self):
        self.p['mode']='image_story';self.seg.update(prompt='Two people speak.',speaker_order='2,1')
        audio=dict(id='voice',kind='audio',purpose='voice',subject='2',input_name='voice.wav',sha256='voicehash',duration=2)
        text=build(self.p,self.seg,[self.image,audio]);self.assertIn('<Subject 2> (S1)',text);self.assertNotIn('<Subject 2> (S2)',text)
        self.seg['speaker_order']='';text=build(self.p,self.seg,[self.image,audio]);self.assertNotIn('(S2)',text)
        self.assertEqual(speakers(dict(speaker_order='2,1'),'official_image'),{'2':1,'1':2})
    def test_none_and_inherited_assets_do_not_create_phantom_ordinals(self):
        self.p['mode']='image_story';self.seg.update(head=22,prompt='Continue walking.',asset_mode='none')
        text=build(self.p,self.seg,[]);self.assertNotIn('<Picture',text);self.assertNotIn('<Audio',text)
        with self.assertRaisesRegex(ValueError,'图片'):validate(self.p|{'mode':'swap'},self.seg,[self.image,self.image])
    def test_source_audio_is_not_an_audio_reference(self):
        rows=inventory(self.p,self.seg,[self.image]);self.assertEqual([r['kind'] for r in rows],['image','video'])
        with self.assertRaisesRegex(ValueError,'Audio'):validate_tags('<Audio 1>',rows)
    def test_voice_cannot_be_silently_submitted_to_pure_text(self):
        self.p.update(mode='text_story',settings=defaults('official_text'))
        with self.assertRaisesRegex(ValueError,'参考声音'):validate(self.p,self.seg,[dict(kind='audio',id='a',duration=2)])
