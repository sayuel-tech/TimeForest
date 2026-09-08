"""Exact-version origin reads through temporary real API; no engine or user data."""
import unittest
from urllib.parse import parse_qs
from PIL import Image
from tests import test_video_assembly as fixtures
from h3ui.asset_library.generation_records import parameter_records


class OriginTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.AssemblyTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.AssemblyTests.tearDownClass.__func__)
    setUp = fixtures.AssemblyTests.setUp

    def asset(self, origin, aid=None, revision=None):
        path=self.root/'origin.png'; Image.new('RGB',(32,32),'red').save(path)
        return self.s.lib.ingest(path,'来源测试',provenance=origin,aid=aid,revision=revision)

    def read(self, item, mid=None):
        snap=item['snapshot']
        response=self.c.get(f"/api/v5/library/assets/{item['id']}/origin",query_string=dict(version=snap['id'],media=mid or snap['media'][0]['id']))
        self.assertEqual(response.status_code,200,response.get_json())
        return response.get_json()

    def test_all_five_project_modes_resolve_without_mutating_projects(self):
        for mode in ['swap','image_story','text_story','image_assets','video_assembly']:
            p=self.c.post('/api/v5/projects',json=dict(mode=mode,name='制作项目 '+mode)).get_json()
            self.assertIn('id',p)
            before=self.c.get('/api/v5/projects/'+p['id']).get_json()
            item=self.asset(dict(type='generated_image' if mode=='image_assets' else 'generated',project=p['id'],project_name='制作时名称'))
            data=self.read(item)
            self.assertEqual(data['chain'][0]['project']['name'],'制作项目 '+mode)
            self.assertEqual(data['chain'][0]['project']['url'],'#/p/'+p['id'])
            self.assertEqual(data['parameters'],[])
            self.assertEqual(self.c.get('/api/v5/projects/'+p['id']).get_json(),before)

    def test_removed_missing_project_and_local_asset(self):
        item=self.asset(dict(type='generated',project=self.pid))
        self.s.store.mutate(self.pid,lambda p:p.update(deleted_at=1))
        project=self.read(item)['chain'][0]['project']
        self.assertEqual(project['state'],'removed')
        self.assertEqual(project['url'],'#/assets?view=trash&recycle=projects')
        missing=self.read(self.asset(dict(type='generated',project='not-present',project_name='历史项目')))
        self.assertEqual(missing['chain'][0]['project']['name'],'历史项目')
        self.assertNotIn('url',missing['chain'][0]['project'])
        self.assertIsNone(self.read(self.asset(dict(type='local')))['chain'][0]['project'])

    def test_exact_origin_identity_is_encoded_with_return_asset_version(self):
        item=self.asset(dict(type='generated_image',project=self.pid,task='task 1',run='run&a',output='output+1'))
        url=self.read(item)['chain'][0]['project']['url']
        route,query=url.split('?',1)
        self.assertEqual(route,'#/p/'+self.pid)
        self.assertEqual(parse_qs(query),dict(origin_task=['task 1'],origin_run=['run&a'],origin_output=['output+1'],
            origin_asset=[item['id']],origin_version=[item['snapshot']['id']],origin_media=[item['snapshot']['media'][0]['id']]))
        for extra,expected in [(dict(export_created=123.5),'123.5'),({},'unknown')]:
            final=self.asset(dict(type='generated',project=self.pid,composite=True,**extra))
            link=self.read(final)['chain'][0]['project']['url']
            self.assertEqual(parse_qs(link.split('?',1)[1])['origin_final'],[expected])

    def test_exact_alternate_and_derived_parent_not_latest_or_wrong_media(self):
        first=self.asset(dict(type='generated',project=self.pid))
        second=self.asset(dict(type='local'),first['id'],first['revision'])
        self.assertIsNone(self.read(second,second['snapshot']['media'][-1]['id'])['chain'][0]['project'])
        m=first['snapshot']['media'][0]
        derived=self.asset(dict(type='derived',parent=dict(asset=first['id'],version=first['snapshot']['id'],media=m['id'],hash=m['hash']),operation='image_transform'))
        data=self.read(derived)
        self.assertEqual(len(data['chain']),2)
        self.assertEqual(data['chain'][1]['version'],first['snapshot']['id'])
        self.assertEqual(data['chain'][1]['project']['id'],self.pid)
        self.assertEqual(data['parameters'],[])
        bad=self.asset(dict(type='derived',parent=dict(asset=first['id'],version=first['snapshot']['id'],media=m['id'],hash='wrong')))
        self.assertIn('不存在',self.read(bad)['notice'])
        self.assertEqual(self.c.get(f"/api/v5/library/assets/{first['id']}/origin").status_code,400)
        self.assertEqual(self.c.get(f"/api/v5/library/assets/{first['id']}/origin",query_string=dict(version=first['snapshot']['id'],media='foreign')).status_code,400)

    def test_saved_image_fields_only_actual_seed_zero_and_no_plugin_dump(self):
        origin=dict(type='generated_image',project=self.pid,actual_prompt='制作时正文',records=dict(seed=0,snapshot=dict(submode='text',settings=dict(steps=19,cfg=2,secret='hidden'),models=dict(unet='custom.safetensors',lora='not-used'))))
        data=self.read(self.asset(origin)); fields={f['key']:f['value'] for f in data['parameters'][0]['fields']}
        self.assertEqual(fields['steps'],19);self.assertEqual(fields['seed'],0)
        self.assertEqual(fields['unet'],'custom.safetensors')
        self.assertNotIn('secret',fields);self.assertNotIn('lora',fields)
        self.assertEqual(data['prompt'],'制作时正文')
        self.assertEqual(parameter_records({}),[])

    def test_continuation_and_composite_saved_order_no_paths(self):
        origin=dict(type='generated',project=self.pid,candidate='p111',snapshot=dict(source=dict(origin=dict(candidate='p11')),parts=[dict(file='private/path',candidate='p11',start=0,end=5),dict(file='private/original',start=1,end=3)]))
        data=self.read(self.asset(origin))
        self.assertEqual(data['chain'][0]['previous_run'],'p11')
        self.assertEqual(data['parts'][0]['run'],'p11')
        self.assertNotIn('private',str(data))

    def test_usage_project_is_separate_from_generation_origin(self):
        item=self.asset(dict(type='local'))
        m=item['snapshot']['media'][0]
        self.s.lib.record_usage(self.pid,[dict(id='usage',reference=dict(asset=item['id'],version=item['version'],media=m['id'],hash=m['hash']))],'origin-test',used_at=1)
        self.assertIsNone(self.read(item)['chain'][0]['project'])
        detail=self.c.get('/api/v5/library/assets/'+item['id']).get_json()
        self.assertEqual(detail['asset_origin_version'],1)
        self.assertEqual(detail['reference_projects'][self.pid]['name'],self.p['name'])
        self.assertEqual(detail['references'],[dict(project=self.pid,version=item['version'])])


if __name__=='__main__':unittest.main()
