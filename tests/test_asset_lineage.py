"""Real temporary stores/API, synthetic execution records; no model submission."""
import copy
import json
import unittest
from urllib.parse import parse_qs
from tests import test_asset_origins as fixtures


class LineageTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.OriginTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.OriginTests.tearDownClass.__func__)
    setUp=fixtures.OriginTests.setUp
    asset=fixtures.OriginTests.asset
    read=fixtures.OriginTests.read

    def ref(self,item):
        m=item['snapshot']['media'][0]
        return dict(asset=item['id'],version=item['snapshot']['id'],media=m['id'],hash=m['hash'])

    def assembly_chain(self):
        base=self.asset(dict(type='local'))
        runs=[dict(id='P11',extension='e1',snapshot=dict(source=dict(origin=self.ref(base)))),
              dict(id='P111',extension='e2',snapshot=dict(source=dict(origin=dict(candidate='P11'))))]
        self.s.store.mutate(self.pid,lambda p:p['assembly'].update(runs=copy.deepcopy(runs)))
        item=self.asset(dict(type='generated',mode='video_assembly',project=self.pid,candidate='P111',snapshot=runs[1]['snapshot']))
        return base,item

    def test_p1_p11_p111_reads_frozen_edges_and_exact_return_links(self):
        base,item=self.assembly_chain()
        before=self.s.store.get(self.pid,include_deleted=True)
        rows=self.read(item)['lineage']['rows']
        self.assertEqual([r['kind'] for r in rows],['assembly','asset'])
        self.assertEqual(rows[0]['run'],'P11')
        self.assertEqual(rows[1]['asset'],base['id'])
        self.assertEqual(rows[1]['parent'],1)
        query=parse_qs(rows[0]['project']['url'].split('?')[1])
        self.assertEqual(query['origin_run'],['P11'])
        self.assertEqual(query['origin_asset'],[item['id']])
        self.assertEqual(before,self.s.store.get(self.pid,include_deleted=True))
        # Track order/current selections cannot alter a saved execution edge.
        self.s.store.mutate(self.pid,lambda p:p['assembly'].update(track_order=['extension:unrelated']))
        self.assertEqual(rows,self.read(item)['lineage']['rows'])

    def test_removed_run_and_project_still_trace_without_restoring(self):
        base,item=self.assembly_chain()
        def remove(p):
            p['deleted_at']=1;p['assembly']['runs'][0]['removed_at']=1
        self.s.store.mutate(self.pid,remove)
        rows=self.read(item)['lineage']['rows']
        self.assertEqual(rows[0]['state'],'removed')
        self.assertEqual(rows[0]['project']['state'],'removed')
        self.assertEqual(rows[1]['asset'],base['id'])
        self.assertEqual(self.s.store.get(self.pid,include_deleted=True)['deleted_at'],1)

    def test_missing_run_does_not_use_another_run(self):
        _,item=self.assembly_chain()
        self.s.store.mutate(self.pid,lambda p:p['assembly']['runs'].pop(0))
        rows=self.read(item)['lineage']['rows']
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['state'],'missing')
        self.assertEqual(rows[0]['run'],'P11')

    def test_cycle_and_total_depth_limits(self):
        _,item=self.assembly_chain()
        self.s.store.mutate(self.pid,lambda p:p['assembly']['runs'][0]['snapshot']['source'].update(origin=dict(candidate='P111')))
        self.assertEqual(self.read(item)['lineage']['rows'][-1]['state'],'cycle')
        runs=[dict(id=str(i),snapshot=dict(source=dict(origin=dict(candidate=str(i+1))))) for i in range(30)]
        self.s.store.mutate(self.pid,lambda p:p['assembly'].update(runs=runs))
        item=self.asset(dict(type='generated',project=self.pid,snapshot=dict(source=dict(origin=dict(candidate='0')))))
        data=self.read(item)['lineage']
        self.assertTrue(data['truncated']);self.assertEqual(data['rows'][-1]['state'],'limit')
        self.assertLessEqual(len(data['rows']),17)

    def test_composite_order_branch_budget_and_no_local_path_leak(self):
        _,item=self.assembly_chain()
        source=self.asset(dict(type='generated',project=self.pid,snapshot=dict(parts=[dict(candidate='P111'),dict(origin=dict(type='local',name='private/path'))])))
        data=self.read(source)
        direct=[r for r in data['lineage']['rows'] if r['parent'] is None]
        self.assertEqual([r['relation'] for r in direct],['part_1','part_2'])
        self.assertNotIn('private/path',json.dumps(data))
        many=self.asset(dict(type='generated',project=self.pid,snapshot=dict(parts=[dict(candidate='P111')]*100)))
        data=self.read(many)['lineage']
        self.assertTrue(data['truncated']);self.assertEqual(len(data['rows']),64)

    def test_library_edges_require_exact_hash_and_old_version(self):
        old=self.asset(dict(type='local'));ref=self.ref(old)
        self.asset(dict(type='local'),old['id'],old['revision'])
        item=self.asset(dict(type='generated',project=self.pid,snapshot=dict(source=dict(origin=ref))))
        self.assertEqual(self.read(item)['lineage']['rows'][0]['version'],old['snapshot']['id'])
        for value,state in [(dict(ref,hash='wrong'),'missing'),({k:v for k,v in ref.items() if k!='hash'},'incomplete')]:
            bad=self.asset(dict(type='generated',project=self.pid,snapshot=dict(source=dict(origin=value))))
            self.assertEqual(self.read(bad)['lineage']['rows'][0]['state'],state)

    def image_chain(self):
        images=self.app.config['IMAGE_STUDIO']
        p=self.c.post('/api/v5/projects',json=dict(mode='image_assets',name='图片接续')).get_json()
        pid=p['id'];task=p['tasks'][0]
        base=self.asset(dict(type='local'))
        input_record=images.library_input(pid,self.ref(base))
        snapshot=dict(submode='single',inputs=dict(A=input_record),settings=dict(steps=19),models={})
        images.store.put('runs',dict(id='r1',project=pid,task=task['id'],state='success',snapshot=snapshot,seed=0))
        images.store.put('outputs',dict(id='o1',project=pid,run='r1',task=task['id'],path=input_record['path']))
        # Exercise the real continue action, then save the same immutable input
        # snapshot shape used by runner.submit; never invoke the runner here.
        after=images.continue_output(pid,'o1',p['revision'])
        second=images.store.get('tasks',after['current_task'],pid)
        frozen=dict(submode='single',parent_output='o1',inputs=dict(A=images.store.get('inputs',second['A'],pid)))
        item=self.asset(dict(type='generated_image',project=pid,output='o2',records=dict(snapshot=frozen)))
        return images,pid,base,item,frozen

    def test_image_continue_through_uncollected_output_to_fixed_asset(self):
        images,pid,base,item,_=self.image_chain()
        before=images.store.all('outputs',pid)
        rows=self.read(item)['lineage']['rows']
        self.assertEqual([r['kind'] for r in rows],['image','asset'])
        self.assertEqual(rows[0]['output'],'o1');self.assertEqual(rows[1]['asset'],base['id'])
        self.assertEqual(rows[0]['parameters'][0]['fields'][0]['value'],19)
        self.assertEqual(before,images.store.all('outputs',pid))
        images.store.mutate('outputs','o1',lambda o:o.update(removed_at=1))
        self.assertEqual(self.read(item)['lineage']['rows'][0]['state'],'removed')

    def test_replaced_A_does_not_follow_stale_task_parent_or_unused_inputs(self):
        _,pid,_,_,frozen=self.image_chain()
        frozen['inputs']['A']['provenance']={}
        frozen['inputs']['B']=dict(provenance=dict(parent_output='o1'))
        item=self.asset(dict(type='generated_image',project=pid,records=dict(snapshot=frozen)))
        rows=self.read(item)['lineage']['rows']
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['kind'],'local')
        frozen['submode']='text'
        item=self.asset(dict(type='generated_image',project=pid,records=dict(snapshot=frozen)))
        self.assertEqual(self.read(item)['lineage']['rows'],[])

    def test_image_role_branches_missing_and_foreign_identity(self):
        images,pid,base,_,frozen=self.image_chain()
        frozen.update(submode='dual')
        frozen['inputs']['B']=dict(provenance=self.ref(base))
        item=self.asset(dict(type='generated_image',project=pid,records=dict(snapshot=frozen)))
        rows=self.read(item)['lineage']['rows']
        self.assertEqual([r['relation'] for r in rows if r['parent'] is None],['image_A','image_B'])
        foreign=self.asset(dict(type='generated_image',project=self.pid,records=dict(snapshot=frozen)))
        self.assertEqual(self.read(foreign)['lineage']['rows'][0]['state'],'missing')
        images.store.mutate('runs','r1',lambda r:r['snapshot']['inputs']['A'].update(provenance=dict(parent_output='o1')))
        self.assertEqual(self.read(item)['lineage']['rows'][1]['state'],'cycle')

    def test_external_pack_never_links_colliding_local_ids(self):
        item=self.asset(dict(type='portable_pack',project=self.pid,records=dict(type='generated',project=self.pid),original_asset='same'))
        data=self.read(item)
        self.assertEqual(data['lineage']['rows'][0]['state'],'external')
        self.assertNotIn('#/p/',json.dumps(data))

    def downstream(self,item,**query):
        ref=self.ref(item)
        response=self.c.get('/api/v5/library/assets/'+item['id']+'/descendants',query_string=dict(version=ref['version'],media=ref['media'],**query))
        self.assertEqual(response.status_code,200,response.get_json())
        return response.get_json()

    def test_downstream_finds_transitive_video_and_image_without_usage_inference(self):
        base,video=self.assembly_chain()
        data=self.downstream(base)
        self.assertEqual([r['asset'] for r in data['rows']],[video['id']])
        _,_,base,image,_=self.image_chain()
        data=self.downstream(base)
        self.assertEqual([r['asset'] for r in data['rows']],[image['id']])
        local=self.asset(dict(type='local'))
        self.s.lib.record_usage(self.pid,[dict(id='usage',reference=self.ref(local))],'downstream-test',used_at=1)
        self.assertEqual(self.downstream(local)['rows'],[])

    def test_downstream_old_versions_removed_results_and_no_hash_guess(self):
        base=self.asset(dict(type='local'))
        derived=self.asset(dict(type='derived',parent=self.ref(base)))
        self.asset(dict(type='local'),derived['id'],derived['revision'])
        with self.s.lib.store.connect() as db: db.execute('UPDATE assets SET deleted=1 WHERE id=?',(derived['id'],))
        bad=self.asset(dict(type='derived',parent=dict(self.ref(base),hash='wrong')))
        data=self.downstream(base)
        self.assertTrue(data['rows'][0]['historical']);self.assertTrue(data['rows'][0]['removed'])
        self.assertNotIn(bad['id'],[r['asset'] for r in data['rows']]);self.assertGreater(data['incomplete'],0)
        self.assertEqual(data['rows'][0]['version'],derived['snapshot']['id'])

    def test_downstream_pagination_is_stable_and_read_only(self):
        base=self.asset(dict(type='local'))
        for _ in range(28):self.asset(dict(type='derived',parent=self.ref(base)))
        first=self.downstream(base)
        self.assertEqual(first['scanned'],25);self.assertIsNotNone(first['cursor'])
        newer=self.asset(dict(type='derived',parent=self.ref(base)))
        second=self.downstream(base,cursor=first['cursor'],upper=first['upper'])
        self.assertIsNone(second['cursor']);self.assertEqual(len(first['rows'])+len(second['rows']),28)
        self.assertNotIn(newer['id'],[r['asset'] for r in second['rows']])
        self.assertEqual(second,self.downstream(base,cursor=first['cursor'],upper=first['upper']))
        self.assertEqual(self.c.get('/api/v5/library/assets/'+base['id']+'/descendants').status_code,400)
        ref=self.ref(base)
        self.assertEqual(self.c.get('/api/v5/library/assets/'+base['id']+'/descendants',query_string=dict(version=ref['version'],media=ref['media'],cursor='bad')).status_code,400)

    def test_original_video_final_uses_saved_order_and_marks_old_context_boundary(self):
        records=dict(segments=dict(selected=[dict(attempt='v2'),dict(attempt='v1')]),selected_runs=[
            dict(segment='s1',candidate='v1',records=dict(manifest=dict(settings=dict(steps=11)))),
            dict(segment='s2',candidate='v2',records=dict(manifest=dict(settings=dict(steps=22),previous='private/checkpoint')))])
        item=self.asset(dict(type='generated',project=self.pid,composite=True,records=records))
        data=self.read(item)
        direct=[r for r in data['lineage']['rows'] if r['parent'] is None]
        self.assertEqual([r['run'] for r in direct],['v2','v1'])
        self.assertIn('origin_segment=s2',direct[0]['project']['url'])
        self.assertEqual(data['lineage']['rows'][1]['state'],'unrecorded')
        self.assertNotIn('private/checkpoint',json.dumps(data))


if __name__=='__main__':unittest.main()
