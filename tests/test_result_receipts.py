"""Actual immutable media -> import operation -> fresh API receipt, isolated stores."""
import copy
import unittest
from PIL import Image
from tests import test_local_server

class ReceiptTests(unittest.TestCase):
    setUp=test_local_server.LocalServerTests.setUp

    def test_three_modes_reopen_receipt_without_project_writes_and_reject_changed_file(self):
        lib=self.app.config['ASSET_LIBRARY']
        for mode in ('swap','image_story','text_story'):
            with self.subTest(mode=mode):
                p=self.st.create(mode,'isolated receipts',15)
                directory=self.st.store.directory(p['id'])/'receipt';directory.mkdir()
                media=directory/'result.png';Image.new('RGB',(32,32),'green').save(media)
                def seed(q):
                    if not q['segments']:q['segments']=[self.st.new_segment(dict(index=0,raw=124,head=0,deliver=124,tail=0,start=0,duration=124/24,boundary='new_scene'))]
                    q['segments'][0]['attempts']=[dict(id='candidate',status='complete',delivery=str(media),directory=str(directory))]
                    q['export']=dict(file=str(media),created=123)
                p=self.st.store.mutate(p['id'],seed);before=copy.deepcopy(self.st.store.get(p['id']))
                url='/api/v5/library/projects/'+p['id']+'/outputs'
                outputs=self.client.get(url).get_json()['items'];self.assertEqual(len(outputs),2)
                for output in outputs:
                    self.assertNotIn('asset',output)
                    item=lib.results.import_result(dict(output=output['id']),lambda *a:None)
                    provenance=item['snapshot']['media'][0]['provenance']
                    if provenance.get('composite'):
                        self.assertEqual(provenance['export_created'],123)
                    fresh=self.app.test_client().get(url).get_json()['items']
                    found=next(x for x in fresh if x['id']==output['id']);self.assertEqual(found['asset'],item['id'])
                    lib.store.trash(item['id'],item['revision'])
                    self.assertTrue(next(x for x in self.client.get(url).get_json()['items'] if x['id']==output['id'])['asset_removed'])
                self.assertEqual(before,self.st.store.get(p['id']))
                Image.new('RGB',(40,40),'blue').save(media)
                self.assertTrue(all('asset' not in x for x in self.client.get(url).get_json()['items']))

    def test_incomplete_or_missing_asset_receipts_are_not_claimed(self):
        lib=self.app.config['ASSET_LIBRARY']
        with lib.store.connect() as db:
            db.execute('INSERT INTO operations VALUES(?,?,?,?,?)',('x','import','running','{"asset":"absent"}',0))
            db.execute('INSERT INTO operations VALUES(?,?,?,?,?)',('y','import','done','{"asset":"absent"}',0))
        self.assertEqual(lib.store.import_receipts(['x','y']),{})
