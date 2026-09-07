import copy
import unittest
from tests import test_video_assembly as base
from h3ui.video_assembly.source_parameters import parameter_records,from_library


def origin(steps=16,seed=0):
    return dict(type='generated',seed=seed,records=dict(manifest=dict(settings={
        'recipe':'dance_split','model':'folder/model.safetensors','steps':steps,'split_step':8,
        'sampler':'euler','scheduler':'beta','low_vram':False,
        'loras':[dict(file='saved-lora.safetensors',strength=0,bypass=False)]},segment={})))


class SourceParameterTests(unittest.TestCase):
    setUpClass=classmethod(base.AssemblyTests.setUpClass.__func__)
    tearDownClass=classmethod(base.AssemblyTests.tearDownClass.__func__)
    setUp=base.AssemblyTests.setUp
    refresh=base.AssemblyTests.refresh
    post=base.AssemblyTests.post
    payload=base.AssemblyTests.payload

    def import_asset(self,item,media=None):
        reference=dict(asset=item['id'],version=item['snapshot']['id'],media=media or item['snapshot']['media'][0]['id'])
        return self.post('import',reference=reference)['assembly']['clips'][-1]

    def test_fixed_media_version_not_latest_cover_and_empty_alternate(self):
        lib=self.s.lib
        first=lib.ingest(self.sound,'first',provenance=origin())
        second=lib.ingest(self.sound,'second',provenance=origin(29),aid=first['id'],revision=first['revision'])
        a=self.import_asset(first);b=self.import_asset(second,second['snapshot']['media'][-1]['id'])
        fields=lambda c:{f['key']:f['value'] for f in c['source_parameters'][0]['fields']}
        self.assertEqual(fields(a)['steps'],16);self.assertEqual(fields(b)['steps'],29)
        self.assertEqual(fields(a)['actual_seed'],'0');self.assertFalse(fields(a)['low_vram'])
        self.assertEqual(fields(a)['lora_0_strength'],0);self.assertNotIn('scale',fields(a))
        self.assertEqual(next(f['label'] for f in a['source_parameters'][0]['fields'] if f['key']=='steps'),'总采样步数')
        local=lib.ingest(self.sound,'no records',provenance={'type':'local'},aid=first['id'],revision=second['revision'])
        self.assertEqual(self.import_asset(local,local['snapshot']['media'][-1]['id'])['source_parameters'],[])

    def test_import_freezes_source_and_old_import_is_read_only_without_source_identity_change(self):
        item=self.s.lib.ingest(self.sound,'saved',provenance=origin());c=self.import_asset(item)
        self.post('extensions',clip=c['id']);eid=self.p['assembly']['clips'][0]['extensions'][0]['id']
        before=self.s.source(self.p,eid)
        self.p['assembly']['clips'][0]['source_parameters']=[{'forged':True}]
        self.post('save',**self.payload())
        self.assertEqual(self.p['assembly']['clips'][0]['source_parameters'],c['source_parameters'])
        self.s.store.mutate(self.pid,lambda p:p['assembly']['clips'][0].pop('source_parameters'))
        stored=self.s.get(self.pid);self.refresh()
        self.assertEqual(self.s.get(self.pid),stored)
        self.assertEqual(self.p['assembly']['clips'][0]['source_parameters'],c['source_parameters'])
        self.assertEqual(self.s.source(self.p,eid),before)
        self.assertEqual(self.p['assembly_source_parameters_version'],1)

    def test_local_or_missing_exact_version_stays_empty(self):
        self.assertEqual(from_library(self.s.lib,dict(type='library',asset='x',media='y',hash='z')),[])
        item=self.s.lib.ingest(self.sound,'local');self.assertEqual(self.import_asset(item)['source_parameters'],[])
        self.assertEqual(from_library(self.s.lib,dict(type='library',asset=item['id'],version='missing',media='y',hash='z')),[])

    def test_selected_internal_tasks_and_composite_records_are_separate(self):
        selected=origin(20,7)['records'];wrong=origin(99,8)['records']
        payload=origin()
        payload['records']['tasks']=[dict(index=0,selected='chosen',runs=[dict(id='chosen',seed=7,records=selected),dict(id='old',seed=8,records=wrong)])]
        payload=dict(type='generated',composite=True,records=dict(selected_runs=[dict(candidate='a',records=payload['records']),dict(candidate='b',records=origin(24,9)['records'])]))
        rows=parameter_records(payload)
        self.assertEqual([next(f['value'] for f in r['fields'] if f['key']=='steps') for r in rows],[16,20,24])
        self.assertIn('内部任务 1',rows[1]['title']);self.assertIn('片段 2',rows[2]['title'])

    def test_assembly_snapshot_only_active_configuration_no_defaults_or_plugin_dump(self):
        saved=origin(18)['records']['manifest']['settings']
        payload=dict(seed=0,snapshot=dict(extension=dict(recipe='dance_split',seconds=7,sound='mute',seed_mode='random',configurations=dict(dance_split=saved,official_image={'steps':99}))))
        rows=parameter_records(payload);values={f['key']:f['value'] for f in rows[0]['fields']}
        self.assertEqual(values['steps'],18);self.assertEqual(values['seconds'],7);self.assertEqual(values['actual_seed'],'0')
        self.assertEqual(parameter_records({'snapshot':{'parts':[{'file':'private.mp4'}]}}),[])
        self.assertEqual(parameter_records({'records':{'prompt':{'node':{'inputs':{'secret':'x'}}}}}),[])
        self.assertEqual(parameter_records({'records':{'manifest':{'settings':None},'tasks':[{'runs':None}]}}),[])
        self.assertEqual(parameter_records(dict(type='portable_pack',records=origin())),parameter_records(origin()))


if __name__=='__main__':unittest.main()
