"""Isolated prompt library/save/record checks. No engine, real media or user data."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_video_assembly as fixtures
from h3ui.prompt_library.store import Store
from h3ui.prompt_library.records import prompt_records


class PromptLibraryTests(unittest.TestCase):
    setUp=fixtures.AssemblyTests.setUp

    def post(self,path,data):
        r=self.c.post('/api/v5'+path,json=data)
        self.assertEqual(r.status_code,200,r.get_json());return r.get_json()

    def test_library_versions_categories_and_protection(self):
        branch=self.post('/prompt-library/model-branches',dict(purpose='video',name='Wan',family='wan'))
        entry=self.post('/prompt-library/entries',dict(title='散步',purpose='video',branch=branch['id'],content=dict(type='text',text='慢慢走'),request_id='create-once'))
        again=self.post('/prompt-library/entries',dict(request_id='create-once'))
        self.assertEqual(entry['id'],again['id'])
        moved=self.post('/prompt-library/entries/'+entry['id'],dict(revision=entry['revision'],branch='video:general',favorite=True))
        self.assertEqual(moved['version'],1)
        updated=self.post('/prompt-library/entries/'+entry['id'],dict(revision=moved['revision'],content=dict(type='text',text='继续走')))
        self.assertEqual(updated['version'],2)
        self.assertEqual(self.c.get('/api/v5/prompt-library/entries/'+entry['id']+'/versions/1').get_json()['content']['text'],'慢慢走')
        self.assertEqual(self.c.post('/api/v5/prompt-library/entries/'+entry['id'],json=dict(revision=1,title='错')).status_code,409)
        self.assertEqual(self.c.post('/api/v5/prompt-library/entries/'+entry['id'],json=dict(revision=updated['revision'],branch='image:krea2')).status_code,400)
        removed=self.post('/prompt-library/entries/'+entry['id'],dict(revision=updated['revision'],removed=True))
        self.assertEqual(self.c.get('/api/v5/prompt-library/entries?trash=1').get_json()['total'],1)
        self.post('/prompt-library/entries/'+entry['id'],dict(revision=removed['revision'],removed=False))
        self.assertEqual(self.c.get('/api/v5/prompt-library/entries').get_json()['total'],1)
        backup=self.c.get('/api/v5/prompt-library/backup');self.assertTrue(backup.data.startswith(b'SQLite format 3'))

    def save_video(self,mode):
        p=self.st.create(mode,'提示词 '+mode,5)
        if not p['segments']:
            from h3ui.studio_story import storyboard
            p['segments']=[self.st.new_segment(x) for x in storyboard(5)]
            p=self.st.store.save(p,p['revision'])
        p['segments'][0]['prompt']='穿过森林'
        p['segments'][0]['prompt_sources']={'prompt':dict(entry='a',version=1,text='穿过森林')}
        plan=self.post('/projects/'+p['id']+'/change-plan',p)
        self.assertEqual(self.c.get('/api/v5/prompt-library/entries').get_json()['total'],0)
        return self.post('/projects/'+p['id']+'/apply',dict(token=plan['token']))

    def test_five_modes_real_save_collection(self):
        library=self.app.config['PROMPT_LIBRARY']
        for mode in ('swap','image_story','text_story'):
            # Use a new prompt DB per mode to verify plan-only creates nothing.
            library._store=Store(self.root/('prompts-'+mode))
            p=self.save_video(mode)
            self.assertEqual(p['prompt_collection']['state'],'collected')
            self.assertEqual(p['segments'][0]['prompt_sources']['prompt']['entry'],'a')
            rows=library.store.list({})['items'];self.assertTrue(rows);self.assertTrue(all(r['branch']=='video:h3' for r in rows))
            old=rows[0];plan=self.post('/projects/'+p['id']+'/change-plan',p);self.post('/projects/'+p['id']+'/apply',dict(token=plan['token']))
            self.assertEqual(library.store.get(old['id'])['version'],old['version'])
        library._store=Store(self.root/'prompts-image')
        p=self.post('/projects',dict(mode='image_assets',name='图片提示词',submode='text'))
        p['tasks'][0]['prompt']='森林';p['tasks'][0]['prompt_sources']={'prompt':dict(entry='a',version=1,text='森林')}
        plan=self.post('/image-projects/'+p['id']+'/change-plan',p);saved=self.post('/image-projects/'+p['id']+'/apply',dict(token=plan['token']))
        self.assertEqual(saved['prompt_collection']['state'],'collected');self.assertEqual(library.store.list({})['items'][0]['branch'],'image:krea2')
        self.assertEqual(saved['tasks'][0]['prompt_sources']['prompt']['entry'],'a')
        library._store=Store(self.root/'prompts-assembly')
        from h3ui.studio_recipes import defaults
        ext=dict(id='ext',prompt='沿结尾继续',seconds=5,recipe='dance_split',configurations={k:defaults(k) for k in ('dance_split','official_image')},seed_mode='random',seed='0',sound='native',references=[])
        def init(p):p['assembly']['clips']=[dict(id='clip',name='源视频',start=0,end=2,meta=dict(duration=2),file=str(self.s.store.directory(self.pid)/'fake.mp4'),extensions=[ext])]
        self.s.store.mutate(self.pid,init)
        p=self.s.snapshot(self.pid)
        saved=self.post('/assembly/'+self.pid+'/save',dict(revision=p['revision'],name=p['name'],output=p['assembly']['output'],clips=p['assembly']['clips']))
        self.assertEqual(saved['prompt_collection']['state'],'collected');self.assertEqual(library.store.list({})['items'][0]['branch'],'video:h3')

    def test_pending_retry_frozen_snapshot_and_manual_organization(self):
        lib=self.app.config['PROMPT_LIBRARY'];store=lib.store
        p=dict(id='project',name='项目',mode='image_assets',kind='image',revision=1,updated=1,tasks=[dict(id='task',name='指令',submode='text',prompt='旧正文',models=dict(unet='krea2_turbo_int8_convrot.safetensors'))])
        with patch.object(store,'collect',side_effect=OSError('模拟库写入失败')):failed=lib.capture(p)
        self.assertEqual(failed['state'],'pending')
        p['tasks'][0]['prompt']='尚未保存的新正文'
        result=lib.retry(failed['receipt']);self.assertEqual(result['state'],'collected')
        entry=store.get(result['entries'][0]);self.assertEqual(entry['content']['text'],'旧正文')
        moved=store.save(dict(revision=entry['revision'],branch='image:general',removed=True),entry['id'])
        p.update(revision=2,updated=2);lib.capture(p)
        current=store.get(entry['id']);self.assertEqual(current['branch'],'image:general');self.assertTrue(current['deleted_at']);self.assertEqual(current['version'],2)
        self.assertEqual(lib.retry(failed['receipt'])['state'],'collected')
        with self.assertRaises(ValueError):store.save(dict(revision=current['revision'],content=dict(type='text',text='覆盖')),entry['id'])

    def test_family_unknown_not_default_and_registered_extension(self):
        lib=self.app.config['PROMPT_LIBRARY']
        self.assertEqual(lib.family('qwen3vl_4b_fp8_scaled.safetensors','image')['family'],None)
        self.assertEqual(lib.family('custom.safetensors','video')['family'],None)
        lib.cfg['prompt_model_families']=[dict(purpose='video',model='wan-custom.safetensors',family='wan',evidence='author model card')]
        self.assertEqual(lib.family('wan-custom.safetensors','video')['family'],'wan')

    def test_fixed_records_image_assembly_composite_and_external(self):
        image=dict(type='generated_image',project='p',snapshot=dict(submode='text',prompt='旧图指令',models=dict(unet='krea2_turbo_int8_convrot.safetensors')))
        self.assertEqual(prompt_records(image)[0]['content']['text'],'旧图指令')
        self.assertEqual(prompt_records(image)[0]['source']['family'],'krea2')
        video=dict(actual_prompt='旧视频指令',manifest=dict(settings=dict(model='minimax_h3_ref2va_pruned_int8_convrot.safetensors')))
        composite=dict(records=dict(selected_runs=[dict(records=video),dict(records={**video,'actual_prompt':'第二段'})]))
        self.assertEqual(len(prompt_records(composite)),2)
        self.assertTrue(all(not r['source'].get('project') for r in prompt_records(dict(type='portable_pack',records=image))))
        self.assertEqual(prompt_records(dict(prompt={'nodes':'不是正文'})),[])
        response=self.post('/prompt-library/check-tags',dict(text='<Picture 2>',rows=[dict(kind='image')]))
        self.assertTrue(response['warnings'])

    def test_saved_favorite_draft_receipt_and_structured_binding(self):
        p=self.save_video('text_story');lib=self.app.config['PROMPT_LIBRARY'];entry=lib.store.list({})['items'][0]
        payload=dict(content=entry['content'],origin={k:entry['source'][k] for k in ('project','target','scope','model')})
        found=self.post('/prompt-library/favorite-current',payload)['entry']
        self.assertTrue(found['favorite']);self.assertEqual(found['id'],entry['id']);self.assertEqual(lib.store.list({})['total'],1)
        payload['content']['fields']['prompt']='未保存正文'
        self.assertIsNone(self.post('/prompt-library/favorite-current',payload)['entry'])
        draft=copy.deepcopy(p);draft['segments'][0].update(prompt='完整正文示例',prompt_mode='full',soundscape='保留声音字段',speaker_order='2,1')
        saved=self.post('/projects/'+p['id']+'/draft',dict(revision=0,body=draft))
        self.assertEqual(saved['prompt_collection']['state'],'collected')
        self.assertNotEqual(self.st.store.get(p['id'])['segments'][0]['prompt'],'完整正文示例')
        self.assertEqual(lib.store.get(entry['id'])['content']['fields']['prompt'],'完整正文示例')
        self.assertEqual(lib.store.get(entry['id'])['content']['fields']['speaker_order'],'2,1')
        from h3ui.studio_prompts import build
        text=build(draft,draft['segments'][0],[])
        self.assertEqual(text,'完整正文示例')  # Full body is not wrapped a second time.
        issue=self.post('/prompt-library/check-tags',dict(text='<Subject 3> (S2)',rows=[],segment=dict(speaker_order='2,1')))
        self.assertTrue(issue['warnings'])

    def test_exact_record_apis_ignore_current_prompt_and_keep_export_order(self):
        p=self.st.create('text_story','记录',10);root=self.st.store.directory(p['id']);root.mkdir(parents=True,exist_ok=True)
        from h3ui.studio_story import storyboard
        if len(p['segments'])<2:p['segments']=[self.st.new_segment(x) for x in storyboard(20)]
        for i,seg in enumerate(p['segments'][:2]):
            directory=root/('fixed'+str(i));directory.mkdir();(directory/'prompt.txt').write_text('旧正文'+str(i),encoding='utf-8')
            (directory/'manifest.json').write_text(json.dumps(dict(settings=p['settings'])),encoding='utf-8')
            seg.update(prompt='后来改过',attempts=[dict(id='run'+str(i),directory=str(directory))])
        export=root/'export';export.mkdir();(export/'manifest.json').write_text(json.dumps(dict(selected=[dict(attempt='run1'),dict(attempt='run0')])))
        p['export']=dict(created=123,file=str(export/'final.mp4'));self.st.store.save(p,p['revision'])
        get=lambda query:self.c.get('/api/v5/prompt-library/records/'+p['id']+query).get_json()['items']
        self.assertEqual(get('?run=run0')[0]['content']['text'],'旧正文0')
        self.assertEqual([r['content']['text'] for r in get('?final=123')],['旧正文1','旧正文0'])
        self.assertEqual(self.c.get('/api/v5/prompt-library/records/'+p['id']+'?run=missing').status_code,404)
        images=self.app.config['IMAGE_STUDIO'];image=images.create('图记录','text');task=image['tasks'][0]
        snap=copy.deepcopy(task);snap['prompt']='当时的图片';images.store.put('runs',dict(id='image-run',project=image['id'],task=task['id'],snapshot=snap))
        images.store.mutate('tasks',task['id'],lambda t:t.update(prompt='新图草稿'))
        records=self.c.get('/api/v5/prompt-library/records/'+image['id']+'?run=image-run').get_json()['items']
        self.assertEqual(records[0]['content']['text'],'当时的图片')
        from h3ui.studio_recipes import defaults
        snap=dict(extension=dict(recipe='dance_split',prompt='旧续接',configurations={'dance_split':defaults('dance_split')}))
        def init(q):q['assembly']['runs']=[dict(id='continuation',kind='generate',snapshot=snap),dict(id='export',kind='export',snapshot=dict(parts=[dict(candidate='continuation')]))]
        self.s.store.mutate(self.pid,init)
        rows=self.c.get('/api/v5/prompt-library/records/'+self.pid+'?run=export').get_json()['items']
        self.assertEqual(rows[0]['content']['text'],'旧续接');self.assertIn('片段 1',rows[0]['title'])
        saved=self.post('/prompt-library/entries',dict(title='续接记录副本',purpose='video',branch='video:h3',content=rows[0]['content'],source=rows[0]['source']))
        self.assertIn('origin_run=continuation',saved['source_project']['url'])
        self.assertEqual(self.c.get('/api/v5/prompt-library/asset-records/unknown?media=m').status_code,400)

if __name__=='__main__':unittest.main()
