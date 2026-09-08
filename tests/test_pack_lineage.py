"""Two independent temporary libraries; no generation, production state or migrations."""
import copy
import io
import json
import unittest
import zipfile
from unittest.mock import Mock, patch
import test_asset_library as fixtures
from h3ui.asset_library.service import Library
from h3ui.asset_library.packs import Packs
from h3ui.asset_library.origins import AssetOrigins
from h3ui.asset_library.descendants import descendants
from h3ui.asset_library.generation_records import parameter_records


class PackLineageTests(unittest.TestCase):
    setUp=fixtures.LibraryTests.setUp

    def pair(self):
        parent=self.lib.ingest(self.image,'原素材',provenance=dict(type='local'))
        m=parent['snapshot']['media'][0]
        ref=dict(asset=parent['id'],version=parent['snapshot']['id'],media=m['id'],hash=m['hash'])
        child=self.lib.ingest(self.image,'派生素材',provenance=dict(type='derived',parent=ref))
        return parent,child

    def bundle(self,assets,**options):
        plan=Packs(self.lib).preview(dict(assets=[dict(asset=a['id'],version=a['snapshot']['id']) for a in assets],**options),AssetOrigins(self.lib,Mock()))
        Packs(self.lib).export(plan,lambda *a:None)
        return (self.lib.root/'exports'/(plan['token']+'.zip')).read_bytes()

    def restore(self,raw,name='receiver'):
        lib=Library(self.root/name)
        token=Packs(lib).stage(io.BytesIO(raw))
        result=Packs(lib).import_pack(token,lambda *a:None)
        return lib,token,[lib.store.get(a['id']) for a in result['assets']]

    def read(self,lib,item):
        origins=AssetOrigins(lib,Mock())
        return origins.read(item['id'],item['snapshot']['id'],item['snapshot']['media'][0]['id'])

    def rewrite(self,raw,change):
        buf=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(raw)) as source,zipfile.ZipFile(buf,'w') as dest:
            manifest=json.loads(source.read('manifest.json'));change(manifest)
            for name in source.namelist():dest.writestr(name,json.dumps(manifest) if name=='manifest.json' else source.read(name))
        return buf.getvalue()

    def test_independent_ids_exact_links_reverse_lookup_and_repeat_after_edit(self):
        a,b=self.pair();lib,token,items=self.restore(self.bundle([b,a]))
        parent=next(x for x in items if x['name']=='原素材');child=next(x for x in items if x['name']=='派生素材')
        self.assertNotEqual(parent['id'],a['id'])
        row=next(r for r in self.read(lib,child)['lineage']['rows'] if r['kind']=='asset')
        self.assertEqual((row['asset'],row['version']),(parent['id'],parent['snapshot']['id']))
        refs=descendants(AssetOrigins(lib,Mock()),parent['id'],parent['snapshot']['id'],parent['snapshot']['media'][0]['id'])
        self.assertEqual([x['asset'] for x in refs['rows']],[child['id']])
        updated=lib.update(parent['id'],parent['revision'],dict(name='修改后的名称'))
        Packs(lib).import_pack(token,lambda *a:None)
        self.assertEqual(lib.store.get(parent['id'])['snapshot']['id'],updated['snapshot']['id'])
        row=next(r for r in self.read(lib,child)['lineage']['rows'] if r['kind']=='asset')
        self.assertEqual(row['version'],parent['snapshot']['id'])
        self.assertEqual(lib.query({})['total'],2)

    def test_partial_retry_uses_first_imported_version_for_dependency(self):
        a,b=self.pair();raw=self.bundle([b,a]);lib=Library(self.root/'retry');token=Packs(lib).stage(io.BytesIO(raw))
        original=lib.store.save
        def fail_child(data,**kw):
            if data['name']=='派生素材':raise RuntimeError('interrupted')
            return original(data,**kw)
        with patch.object(lib.store,'save',side_effect=fail_child):
            with self.assertRaises(RuntimeError):Packs(lib).import_pack(token,lambda *a:None)
        parent=lib.store.get(lib.query({})['items'][0]['id'])
        lib.update(parent['id'],parent['revision'],dict(name='后来修改'))
        result=Packs(lib).import_pack(token,lambda *a:None)
        child=lib.store.get(next(x['id'] for x in result['assets'] if x['name']=='派生素材'))
        row=next(r for r in self.read(lib,child)['lineage']['rows'] if r['kind']=='asset')
        self.assertEqual(row['version'],parent['snapshot']['id'])

    def test_outside_source_does_not_auto_collect_or_link_sender_ids(self):
        a,b=self.pair();lib,_,items=self.restore(self.bundle([b]))
        data=self.read(lib,items[0]);self.assertEqual(lib.query({})['total'],1)
        self.assertFalse(any(r['kind']=='asset' for r in data['lineage']['rows']))
        self.assertTrue(any(r['state']=='external' for r in data['lineage']['rows']))
        self.assertIsNone(data['chain'][0]['project'])

    def test_opt_out_and_legacy_records_never_resolve_external_projects(self):
        a=self.lib.ingest(self.image,'外部作品',provenance=dict(type='generated',project='same-id',records=dict(manifest=dict(settings=dict(steps=19)))))
        for n,version in enumerate([1,2]):
            raw=self.rewrite(self.bundle([a],workflows=True,lineage=False),lambda m:m.update(version=version))
            lib,_,items=self.restore(raw,str(n));data=self.read(lib,items[0])
            self.assertIsNone(data['chain'][0]['project']);self.assertEqual(data['lineage']['rows'][0]['state'],'external')
        # Old import implementation kept raw generated provenance on the media.
        snap=copy.deepcopy(a['snapshot']);snap['media'][0]['provenance']=snap['provenance'];snap['provenance']=dict(type='portable_pack')
        legacy=self.lib.store.save(snap)
        self.assertIsNone(self.read(self.lib,legacy)['chain'][0]['project'])

    def test_reexport_remaps_only_current_package_assets(self):
        a,b=self.pair();lib,_,items=self.restore(self.bundle([b,a]))
        self.lib=lib
        third,_,restored=self.restore(self.bundle(items),'third')
        child=next(x for x in restored if x['name']=='派生素材');parent=next(x for x in restored if x['name']=='原素材')
        rows=self.read(third,child)['lineage']['rows']
        self.assertEqual([r['asset'] for r in rows if r['kind']=='asset'],[parent['id']])

    def test_tampered_identity_and_combined_cycle_rejected_before_registration(self):
        a,b=self.pair();raw=self.bundle([b,a]);lib=Library(self.root/'bad')
        for key in ['asset','version','media','hash']:
            def change(m):m['assets'][0]['media'][0]['portable_lineage']['links'][0]['reference'][key]='invalid'
            with self.assertRaisesRegex(ValueError,'不匹配'):Packs(lib).stage(io.BytesIO(self.rewrite(raw,change)))
        def cycle(m):
            child,parent=m['assets'];parent['bindings']=[dict(asset=child['asset_id'],version=child['id'],purpose='prop')]
        with self.assertRaisesRegex(ValueError,'循环'):Packs(lib).stage(io.BytesIO(self.rewrite(raw,cycle)))
        self.assertEqual(lib.query({})['total'],0)

    def test_wrapped_image_parameters_are_saved_values_and_bounded(self):
        origin=dict(type='generated_image',records=dict(seed=42,snapshot=dict(submode='text',settings=dict(steps=19,cfg=2),models=dict(unet='saved.safetensors'))))
        expected=parameter_records(origin);self.assertTrue(expected)
        for _ in range(3):origin=dict(type='portable_pack',records=origin)
        self.assertEqual(parameter_records(origin),expected)
        for _ in range(20):origin=dict(type='portable_pack',records=origin)
        self.assertEqual(parameter_records(origin),[])


if __name__=='__main__':unittest.main()
