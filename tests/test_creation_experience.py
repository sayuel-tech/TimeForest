"""Real project and asset APIs, bounded authoring scope tests; external sockets denied."""
import copy
import io
import json
import unittest
import uuid
from pathlib import Path
from PIL import Image
from tests import test_creation
from h3ui.creation.bindings import resolve
from h3ui.creation.contracts import digest


class CreationExperienceTests(unittest.TestCase):
    def setUp(self):
        self.case=test_creation.CreationTests();self.case.setUp();self.addCleanup(self.case.doCleanups)

    def tree(self):
        c=self.case
        result=c.save('storyboard',{'shots':[{'ref':'tmp:s','title':'修车铺','text':'两人见面'},{'ref':'tmp:t','title':'归家','text':'离开'}]})
        shot=result['id_map']['tmp:s'];other=result['id_map']['tmp:t']
        result=c.save('segment',{'segments':[{'ref':'tmp:a','shot_ref':shot,'text':'相遇','planned_seconds':5},{'ref':'tmp:b','shot_ref':other,'text':'离开','planned_seconds':5}]})
        return shot,result['id_map']['tmp:a'],result['id_map']['tmp:b']

    def dialogue(self,layer,targets,draft,base=None):
        c=self.case;p=c.service.snapshot(c.p['id']);key=layer+':'+','.join(targets)
        return c.post('/authoring/projects/'+p['id']+'/conversation',dict(revision=p['revision'],layer=layer,target_ids=targets,base_hash=base or p['writing_draft_hashes'].get(key),draft=draft))

    def test_scoped_conversation_edited_basis_and_conflicts(self):
        c=self.case;shot,clip,other=self.tree()
        draft=dict(instruction='保留人物关系',basis_candidate_id=None,include_images=False)
        self.dialogue('storyboard',[shot],draft);self.dialogue('prompt',[clip],dict(draft,instruction='不要配乐'))
        current=c.service.snapshot(c.p['id']);self.assertEqual(current['writing_drafts']['storyboard:'+shot]['instruction'],'保留人物关系')
        context=c.service.writing.context(c.p['id'],'h3_prompt',[other],'编写',prompt_mode='full')
        self.assertFalse(any('不要配乐' in r['content'] for r in context['materials']))
        c.configure_fake(Path('tests/fixtures/creation/llm/screenplay_draft.ok.json').read_text(encoding='utf-8-sig'));c.p=current
        job=c.start_writing();self.assertEqual(job['state'],'succeeded');c.p=c.service.snapshot(c.p['id']);candidate=c.p['candidates'][-1]
        edited=copy.deepcopy(candidate['payload']);edited['blocks'][0]['text']='用户未确认的改稿'
        value=dict(draft,basis_candidate_id=candidate['candidate_id'],edited_candidate=dict(id=candidate['candidate_id'],payload=edited))
        self.dialogue('screenplay',[],value)
        context=c.service.writing.context(c.p['id'],'screenplay_draft',instruction='再改结尾')
        self.assertIn('用户未确认的改稿',next(m['content'] for m in context['materials'] if m['reference_key'].startswith('basis:')))
        p=c.service.snapshot(c.p['id']);old=p['writing_draft_hashes']['screenplay:'];self.dialogue('screenplay',[],dict(value,instruction='新要求'))
        p=c.service.snapshot(c.p['id']);response=c.c.post('/api/v5/authoring/projects/'+p['id']+'/conversation',json=dict(revision=p['revision'],request_key=uuid.uuid4().hex,layer='screenplay',target_ids=[],base_hash=old,draft=value))
        self.assertEqual(response.status_code,409)
        with self.assertRaises(AssertionError):self.dialogue('prompt',[clip],value)

    def asset(self,color,need):
        c=self.case;buffer=io.BytesIO();Image.new('RGB',(32,32),color).save(buffer,format='PNG');buffer.seek(0)
        response=c.c.post('/api/v5/library/uploads',data={'file':(buffer,'reference.png'),'key':uuid.uuid4().hex},content_type='multipart/form-data')
        self.assertEqual(response.status_code,200,response.get_json());item=response.get_json();p=c.service.snapshot(c.p['id'])
        receipt=c.post('/authoring/projects/'+p['id']+'/references',dict(revision=p['revision'],asset=item['id'],version=item['snapshot']['id'],media=item['snapshot']['media'][0]['id'],purpose='character',subject='1',binding_need_ref=need))
        c.p=c.service.snapshot(p['id']);return item,receipt['changed_ids'][0]

    def test_effective_sources_exact_references_and_frozen_movie(self):
        c=self.case;shot,clip,other=self.tree()
        receipt=c.save('asset_bindings',dict(needs=[dict(ref='tmp:n',kind='character',name='张三',description='主角',source_refs=[],media_need='recommended',suggested_asset_refs=[])],bindings=[]))
        need=receipt['id_map']['tmp:n'];root,root_ref=self.asset('red',need);local,local_ref=self.asset('blue',need)
        data=copy.deepcopy(c.service.layer(c.p,'asset_bindings')['content'])
        def binding(key,kind,target,item,ref):return dict(id='tmp:'+key,need_ref=need,scope_kind=kind,scope_ids=[target],usage='character',state='bound',source='independent',asset_ref=item['id'],asset_version=item['snapshot']['id'],reference_id=ref,text_override='')
        data['bindings']=[binding('root','project',c.p['id'],root,root_ref),binding('shot','shot',shot,local,local_ref)]
        c.save('asset_bindings',data);data=copy.deepcopy(c.service.layer(c.p,'asset_bindings')['content'])
        self.assertEqual(resolve(c.service,c.p,clip)[0]['asset_ref'],local['id'])
        data['policies']={clip:'project'};c.save('asset_bindings',data)
        context=c.service.writing.context(c.p['id'],'h3_prompt',[clip],'写',prompt_mode='full')
        keys={m['reference_key'] for m in context['materials']};self.assertIn(root_ref,keys);self.assertNotIn(local_ref,keys)
        preview=c.service.movie.authoring_preview(c.p['id'],clip,False);self.assertEqual([s['reference_key'] for s in preview['input_contract']['slots']],[root_ref])
        movie=c.post('/movie/projects',dict(title='未完剧本试拍',source_project_id=c.p['id'],source_revision=c.p['revision'],segment_ids=[clip]))
        _,frozen=c.service.movie.frozen(c.service.get(movie['id']),clip);self.assertEqual(frozen['references'][0]['id'],root_ref);before=copy.deepcopy(frozen)
        data=copy.deepcopy(c.service.layer(c.p,'asset_bindings')['content']);data['policies'][clip]='independent';c.save('asset_bindings',data)
        self.assertEqual(resolve(c.service,c.p,clip)[0]['state'],'pending');self.assertEqual(c.service.movie.authoring_preview(c.p['id'],clip,False)['input_contract']['slots'],[])
        self.assertEqual(c.service.movie.frozen(c.service.get(movie['id']),clip)[1],before)
        data=copy.deepcopy(c.service.layer(c.p,'asset_bindings')['content']);data['policies'][clip]='parent';data['bindings'].append(dict(id='tmp:clip',need_ref=need,scope_kind='segment',scope_ids=[clip],usage='character',state='inherit',source='project',asset_ref=None,asset_version=None,text_override=''));c.save('asset_bindings',data)
        self.assertEqual(resolve(c.service,c.p,clip)[0]['asset_ref'],root['id'])
        # Changing only usage text retains the exact character image reference.
        source=copy.deepcopy(c.service.layer(c.p,'asset_bindings')['content']);source['bindings'][-1].update(state='bound',source='independent',asset_ref=local['id'],asset_version=local['snapshot']['id'],reference_id=root_ref)
        with self.assertRaises(AssertionError):c.save('asset_bindings',source)

    def test_local_confirmation_does_not_confirm_or_invalidate_other_clip(self):
        c=self.case;shot,clip,other=self.tree()
        c.save('screenplay',dict(blocks=[dict(ref='tmp:script',text='完整剧本')]))
        current=c.service.layer(c.p,'screenplay');c.post('/authoring/projects/'+c.p['id']+'/confirm',dict(revision=c.p['revision'],layer='screenplay',target_ids=[],content_hashes={'screenplay':current['content_hash']}));c.p=c.service.snapshot(c.p['id'])
        c.save('asset_bindings',dict(needs=[],bindings=[]))
        self.assertEqual(next(r for r in c.p['content']['confirmations'] if r['layer']=='screenplay')['review_state'],'current')
        for sid in (clip,other):
            current=c.service.layer(c.p,'segment',[sid]);c.post('/authoring/projects/'+c.p['id']+'/confirm',dict(revision=c.p['revision'],layer='segment',target_ids=[sid],content_hashes={'segment':current['content_hash']}));c.p=c.service.snapshot(c.p['id'])
        content=copy.deepcopy(c.service.layer(c.p,'segment')['content']);content['segments'][0]['text']='更改相遇的动作';c.save('segment',content)
        states={r['target_id']:r['review_state'] for r in c.p['content']['confirmations']}
        self.assertEqual(states[clip],'review_required');self.assertEqual(states[other],'current')


if __name__=='__main__':unittest.main()
