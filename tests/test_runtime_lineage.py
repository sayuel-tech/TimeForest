"""Temporary stores and guarded execution entrypoints; no engine/network/model."""
import copy
import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_asset_lineage as fixtures
from h3ui.generation.source_lineage import capture
from h3ui.studio_story import TaskStore,storyboard


class RuntimeLineageTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.LineageTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.LineageTests.tearDownClass.__func__)
    setUp=fixtures.LineageTests.setUp
    asset=fixtures.LineageTests.asset
    ref=fixtures.LineageTests.ref
    read=fixtures.LineageTests.read
    assembly_chain=fixtures.LineageTests.assembly_chain
    image_chain=fixtures.LineageTests.image_chain

    def video(self,mode='image_story'):
        p=self.st.create(mode,'来源记录测试',30)
        if len(p['segments'])<2:p['segments']=[self.st.new_segment(s) for s in storyboard(30)]
        for s in p['segments']:s['prompt']='继续走入森林。'
        p['segments'][1]['head']=22
        p['segments'][0]['selected']='p1'
        p['segments'][0]['attempts']=[dict(id='p1',status='complete',created=1,source_lineage=dict(version=1,inputs=[],previous=None,previous_recorded=True))]
        return p

    def test_capture_keeps_fixed_refs_tags_and_selected_identity_without_mutation(self):
        for mode in ('swap','image_story','text_story'):
            p=self.video(mode);base=self.asset(dict(type='local'));ref=self.ref(base)
            inputs=[dict(id='i',kind='image',library_reference=ref),dict(id='a',kind='audio')]
            before=copy.deepcopy((p,inputs));snap=capture(self.st,p,p['segments'][1],inputs,'context')
            self.assertEqual(snap['previous'],dict(project=p['id'],segment=p['segments'][0]['id'],run='p1'))
            self.assertEqual(snap['inputs'][0]['reference'],ref)
            self.assertEqual([r['tag'] for r in snap['inputs'][:2]],['<Picture 1>','<Audio 1>'])
            inputs[0]['library_reference']['version']='changed'
            self.assertNotEqual(snap['inputs'][0]['reference']['version'],'changed')
            self.assertEqual(before[0],p)
            self.assertIsNone(capture(self.st,p,p['segments'][1],[],None)['previous'])

    def test_story_capture_and_taskstore_keep_outer_and_internal_identity(self):
        p=self.video();self.st.store.save(p,p['revision'])
        with patch.object(self.st,'previous',return_value='context'),patch.object(self.st,'continue_story'):
            self.st.generate_story(p['id'],1)
        saved=self.st.store.get(p['id']);outer=saved['segments'][1]['attempts'][-1]
        manifest=json.loads((Path(outer['directory'])/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['source_lineage'],outer['source_lineage'])
        task_store=TaskStore(self.st.store,p['id'],1,outer['id']);view=task_store.get(p['id'])
        task=view['segments'][0]
        snap=capture(self.st,view,task,[],'context')
        self.assertEqual(snap['previous']['run'],'p1')
        second=copy.deepcopy(task);second.update(id='internal-2',index=1)
        view['segments']=[dict(task,selected='internal-1',attempts=[dict(id='internal-1')]),second]
        snap=capture(self.st,view,second,[],'internal-context')
        self.assertEqual(snap['previous']['run'],outer['id'])
        self.assertEqual(snap['previous']['internal_run'],'internal-1')
        self.assertEqual(snap['previous']['segment'],saved['segments'][1]['id'])
        view.pop('_story_source_lineage')
        self.assertFalse(capture(self.st,view,task,[],'legacy-context')['previous_recorded'])

    def test_legacy_execution_writes_same_graph_and_additive_metadata(self):
        p=self.video('text_story');p['storyboard_version']=0
        p['segments'][1].update(seed_mode='fixed',seed='0')
        self.st.store.save(p,p['revision'])
        graph=dict(issues=[],workflow={'node':{'class_type':'fixture','inputs':{'seed':0}}})
        with patch.object(self.st,'previous',return_value='context'),patch.object(self.st,'resolve',return_value=[]),patch.object(self.st,'prepare_execution_inputs'),patch.object(self.st.recipes,'compile',return_value=copy.deepcopy(graph)),patch('h3ui.studio.ProgressWatch'),patch.object(self.st.comfy,'submit',side_effect=RuntimeError('isolated stop before engine')) as submit:
            self.st.generate_one(p['id'],1)
        run=self.st.store.get(p['id'])['segments'][1]['attempts'][-1]
        directory=Path(run['directory']);manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(json.loads((directory/'workflow.json').read_text(encoding='utf-8')),graph['workflow'])
        self.assertEqual(submit.call_args.args[0],graph['workflow'])
        self.assertEqual(run['seed'],'0');self.assertEqual(manifest['previous'],'context')
        self.assertEqual(run['source_lineage'],manifest['source_lineage'])
        self.assertEqual(run['source_lineage']['previous']['run'],'p1')

    def video_chain(self,mode='image_story'):
        p=self.video(mode);base=self.asset(dict(type='local'))
        p['segments'][0]['attempts'][0]['source_lineage']['inputs']=[dict(kind='image',reference=self.ref(base))]
        parent=dict(project=p['id'],segment=p['segments'][0]['id'],run='p1')
        p['segments'][1]['attempts']=[dict(id='p2',status='complete',created=2,source_lineage=dict(version=1,inputs=[],previous=parent,previous_recorded=True))]
        self.st.store.save(p,p['revision'])
        origin=dict(type='generated',project=p['id'],records=dict(source_lineage=p['segments'][1]['attempts'][0]['source_lineage']))
        return p,base,origin

    def test_saved_video_chain_links_actual_previous_and_fixed_asset(self):
        p,base,origin=self.video_chain();item=self.asset(origin)
        rows=self.read(item)['lineage']['rows']
        self.assertEqual([r['kind'] for r in rows],['video','asset'])
        self.assertEqual(rows[1]['asset'],base['id'])
        self.st.store.mutate(p['id'],lambda p:p['segments'][0].update(selected='different'))
        self.assertEqual(rows,self.read(item)['lineage']['rows'])
        self.st.store.mutate(p['id'],lambda p:p['segments'][0]['attempts'][0].update(removed_at=1))
        self.assertEqual(self.read(item)['lineage']['rows'][0]['state'],'removed')

    def test_internal_identity_is_not_an_outer_self_cycle(self):
        p,base,origin=self.video_chain();run=p['segments'][1]['attempts'][0]
        run['tasks']=[dict(id='t1',attempts=[dict(id='i1',source_lineage=copy.deepcopy(p['segments'][0]['attempts'][0]['source_lineage']))])]
        p=self.st.store.get(p['id']);p['segments'][1]['attempts'][0]=run;self.st.store.save(p,p['revision'])
        origin['records']['source_lineage']['previous']=dict(project=p['id'],segment=p['segments'][1]['id'],run='p2',internal_segment='t1',internal_run='i1')
        rows=self.read(self.asset(origin))['lineage']['rows']
        self.assertEqual(rows[0]['run'],'i1');self.assertIn('origin_run=p2',rows[0]['project']['url'])
        self.assertEqual(rows[1]['asset'],base['id'])

    def page(self,item,**args):
        ref=self.ref(item)
        r=self.c.get('/api/v5/library/assets/'+item['id']+'/generation-descendants',query_string=dict(version=ref['version'],media=ref['media'],**args))
        self.assertEqual(r.status_code,200,r.get_json());return r.get_json()

    def test_uncollected_video_and_image_results_reverse_read_only(self):
        p,base,_=self.video_chain();before=self.st.store.get(p['id'])
        page=self.page(base)
        self.assertEqual({r['run'] for r in page['rows']},{'p1','p2'})
        self.assertTrue(all('origin_asset='+base['id'] in r['project']['url'] for r in page['rows']))
        self.assertEqual(before,self.st.store.get(p['id']))
        images,pid,base,_,_=self.image_chain()
        page=self.page(base)
        self.assertEqual([r['output'] for r in page['rows']],['o1'])
        images.store.mutate('tasks',images.store.get('outputs','o1',pid)['task'],lambda t:t.update(discarded_at=1))
        self.assertTrue(self.page(base)['rows'][0]['removed'])

    def test_assembly_generation_and_export_results_are_visible(self):
        base,_=self.assembly_chain()
        def finish(p):
            for run in p['assembly']['runs']:run.update(state='success',kind='generate',created=1)
            p['assembly']['runs'].append(dict(id='export',state='success',kind='export',created=2,snapshot=dict(parts=[dict(candidate='P111')])))
        self.st.store.mutate(self.pid,finish)
        self.assertEqual({r['run'] for r in self.page(base)['rows']},{'P11','P111','export'})

    def test_paging_cutoff_missing_identity_and_removed_project(self):
        p,base,_=self.video_chain()
        def many(q):
            q['deleted_at']=1
            template=q['segments'][0]['attempts'][0]
            q['segments'][0]['attempts']=[dict(copy.deepcopy(template),id='r'+str(i)) for i in range(28)]
        self.st.store.mutate(p['id'],many)
        first=self.page(base);self.assertIsNotNone(first['cursor'])
        self.assertTrue(all(r['project']['state']=='removed' for r in first['rows']))
        final=self.page(base,cursor=first['cursor'],before=first['before'])
        self.assertIsNone(final['cursor'])
        self.assertEqual(len(first['rows'])+len(final['rows']),28)
        self.assertGreater(first['incomplete']+final['incomplete'],0)  # p2 points at the now missing p1
        self.assertEqual(final,self.page(base,cursor=first['cursor'],before=first['before']))

    def test_export_and_old_layout_keep_saved_source_identity(self):
        p,base,_=self.video_chain()
        path=self.st.store.directory(p['id'])/'export';path.mkdir()
        (path/'manifest.json').write_text(json.dumps(dict(selected=[dict(attempt='p2')])),encoding='utf-8')
        p=self.st.store.get(p['id']);p['export']=dict(file=str(path/'output.mp4'),created=3)
        p['previous_layouts']=[copy.deepcopy(p['segments'])];p['segments']=[]
        self.st.store.save(p,p['revision'])
        data=self.page(base)
        self.assertEqual({r['run'] for r in data['rows']},{'p1','p2','final:3'})
        self.assertTrue(next(r for r in data['rows'] if r['run']=='p1')['historical'])
        self.assertIn('origin_final=3',next(r for r in data['rows'] if r['run']=='final:3')['project']['url'])

    def test_source_video_reference_and_library_collection_keep_capture(self):
        p,base,origin=self.video_chain('swap')
        source=dict(id='source',project=p['id'],kind='video',library_reference=self.ref(base))
        self.st.store.add_asset(p['id'],source);p['source_asset']='source'
        captured=capture(self.st,p,p['segments'][1],[],'context')
        self.assertEqual(captured['inputs'][0]['reference'],self.ref(base))
        # Read ResultImports' actual registered immutable payload without collecting.
        p=self.st.store.get(p['id']);run=p['segments'][0]['attempts'][0]
        directory=self.st.store.directory(p['id'])/'test-run';directory.mkdir()
        delivery=directory/'delivery.mp4';delivery.write_bytes(self.silent.read_bytes())
        run.update(directory=str(directory),delivery=str(delivery));self.st.store.save(p,p['revision'])
        # Remove the synthetic source record: it lacks a real project media path.
        with self.st.store.connect() as db:db.execute('DELETE FROM assets WHERE id=?',('source',))
        from h3ui.asset_library.results import ResultImports
        outputs=ResultImports(self.s.lib,self.st).outputs(p['id'])
        selected=next(r for r in outputs if r['kind']=='candidate')
        with self.s.lib.store.connect() as db:
            body=json.loads(db.execute('SELECT body FROM operations WHERE key=?',(selected['id'],)).fetchone()[0])
        self.assertEqual(body['provenance']['records']['source_lineage'],run['source_lineage'])

    def test_new_results_after_scan_cutoff_and_invalid_cursor(self):
        p,base,_=self.video_chain();first=self.page(base)
        def future(q):q['segments'][0]['attempts'].append(dict(copy.deepcopy(q['segments'][0]['attempts'][0]),id='future',created=first['before']+100))
        self.st.store.mutate(p['id'],future)
        self.assertNotIn('future',[r['run'] for r in self.page(base,before=first['before'])['rows']])
        q=dict(version=base['snapshot']['id'],media=base['snapshot']['media'][0]['id'],cursor='broken')
        self.assertEqual(self.c.get('/api/v5/library/assets/'+base['id']+'/generation-descendants',query_string=q).status_code,400)

    def test_finishing_a_pending_run_does_not_shift_paging_offset(self):
        p,base,_=self.video_chain()
        def seed(q):
            template=q['segments'][0]['attempts'][0]
            q['segments'][0]['attempts']=[dict(copy.deepcopy(template),id='r'+str(i)) for i in range(28)]
            q['segments'][0]['attempts'][0]['status']='submitted'
            q['segments'][1]['attempts']=[]
        self.st.store.mutate(p['id'],seed)
        first=self.page(base)
        self.st.store.mutate(p['id'],lambda q:q['segments'][0]['attempts'][0].update(status='complete',completed=first['before']+1))
        rest=self.page(base,cursor=first['cursor'],before=first['before'])
        ids=[r['run'] for r in first['rows']+rest['rows']]
        self.assertEqual(len(ids),27);self.assertEqual(len(set(ids)),27);self.assertNotIn('r0',ids)


if __name__=='__main__':unittest.main()
