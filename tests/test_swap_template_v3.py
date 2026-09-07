import unittest
import test_director_v3 as fixture
from h3ui.studio_prompts import build
from h3ui.studio_recipes import defaults

class SwapTemplateV3(unittest.TestCase):
    def setUp(self):
        fixture.DirectorV3.setUp(self);self.p['swap_prompt']['version']=3
    def test_descriptions_reach_each_real_swap_graph(self):
        self.seg.update(staging='a woman with long brown hair and a gray knit dress',beats='The replacement walks across the frame and raises her right hand.',prompt='Keep the dress hem visible.')
        for recipe in ['official_swap','dance_split']:
            self.p['settings']=defaults(recipe);text=build(self.p,self.seg,[self.image]);g=self.recipes.compile(self.p,self.seg,[self.image],text)
            self.assertEqual(g['workflow']['20']['inputs']['prompt'],text)
            self.assertIn(self.seg['staging'],text);self.assertIn(self.seg['beats'],text)
            self.assertNotIn('<Picture 2>',text);self.assertNotIn('<Subject 2>',text)
            self.assertEqual(g['prompt_template_version'],3)
            self.assertEqual(g['workflow']['400']['inputs']['image'],'ref.png')
    def test_optional_descriptions_never_guess_appearance_or_layout(self):
        text=build(self.p,self.seg,[self.image])
        self.assertIn('If it contains several views',text);self.assertNotIn('Several views within this image depict',text)
        self.assertNotIn('gray knit dress',text);self.assertNotIn('SHOULD NOT LEAK',text)
        self.assertEqual(text.count('subject_definitions:'),1)
    def test_native_voice_music_and_no_source_audio_fiction(self):
        self.p['settings']['audio_policy']='native';self.seg.update(voice='Warm and measured.',music='Soft instrumental piano.',speaker_order='1')
        audio=dict(id='a',kind='audio',purpose='voice',subject='1',input_name='voice.wav',duration=2)
        text=build(self.p,self.seg,[self.image,audio])
        self.assertIn('<Subject 1> (S1)',text);self.assertIn('Soft instrumental piano.',text);self.assertIn('Warm and measured.',text)
        self.assertNotIn('fully_copy',text);self.assertNotIn('<Audio 2>',text)
    def test_source_track_is_postprocessing_and_new_speech_conflicts(self):
        self.p['settings']['audio_policy']='source';text=build(self.p,self.seg,[self.image])
        self.assertIn('overall_soundscape:\nN/A',text);self.assertNotIn('<Audio',text)
        self.seg['prompt']='<d>[Chinese]你好。</d>'
        with self.assertRaisesRegex(ValueError,'原声'):build(self.p,self.seg,[self.image])
    def test_complete_custom_remains_exact(self):
        self.seg.update(swap_prompt_mode='custom',swap_custom_prompt='<Picture 1> replaces the person in <Video 1>.',staging='MUST NOT APPEND',beats='MUST NOT APPEND')
        self.assertEqual(build(self.p,self.seg,[self.image]),self.seg['swap_custom_prompt'])
    def test_subject_id_and_voice_reference_agree(self):
        image={**self.image,'subject':'5'};self.p['settings']['audio_policy']='native';self.seg['speaker_order']='5'
        audio=dict(id='a',kind='audio',purpose='voice',subject='5',input_name='v.wav',duration=2)
        self.assertIn('<Subject 5> (S1)',build(self.p,self.seg,[image,audio]))
        audio['subject']='2'
        with self.assertRaisesRegex(ValueError,'目标角色5'):build(self.p,self.seg,[image,audio])

    def test_missing_character_is_actionable_error(self):
        with self.assertRaisesRegex(ValueError,'角色图'):build(self.p,self.seg,[])
