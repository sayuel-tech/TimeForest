"""Result collection uses real temporary API/storage and synthetic files, no engine."""
import copy
import hashlib
import unittest
from PIL import Image


class ImageResultActionsTests(unittest.TestCase):
    def setUp(self):
        from tests.test_image_studio import ImageStudioTests
        self.f=ImageStudioTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=self.f.s;self.c=self.f.client;self.pid=self.f.pid
        self.task=self.f.p['tasks'][0]
        for index in (1,2):
            oid=str(index)*32
            path=self.s.store.directory(self.pid)/f'candidate-{index}.png'
            Image.new('RGB',(80,120),'green' if index==1 else 'blue').save(path)
            self.s.store.put('runs',dict(id=oid,project=self.pid,task=self.task['id'],state='success',seed=0,
                snapshot=copy.deepcopy(self.task),source_hash='fixture-source',graph_hash='fixture-graph',plugin_version='fixture',created=index))
            self.s.store.put('outputs',dict(id=oid,project=self.pid,task=self.task['id'],run=oid,path=str(path),
                hash=hashlib.sha256(path.read_bytes()).hexdigest(),width=80,height=120,selected=index==1))
        self.base=f'/api/v5/image-projects/{self.pid}/outputs/'+'2'*32+'/library'

    def test_quick_collection_preserves_selection_and_is_idempotent(self):
        before=self.s.snapshot(self.pid)
        response=self.c.post(self.base,json={'select_output':False,'name':'收藏候选'})
        self.assertEqual(response.status_code,200,response.get_json());asset=response.get_json()
        repeated=self.c.post(self.base,json={'select_output':False}).get_json()
        self.assertEqual((asset['id'],asset['version']),(repeated['id'],repeated['version']))
        after=self.s.snapshot(self.pid)
        self.assertEqual([(o['id'],o['selected']) for o in after['outputs']],[(o['id'],o['selected']) for o in before['outputs']])
        self.assertEqual(after['tasks'],before['tasks']);self.assertEqual(after['runs'],before['runs'])
        self.assertEqual(after['revision'],before['revision'])
        collected=next(o for o in after['outputs'] if o['id']=='2'*32)
        self.assertEqual(collected['library'],{'asset':asset['id'],'version':asset['version']})
        self.assertIn('fixture-graph',str(asset['snapshot']));self.assertIn('generated_image',str(asset['snapshot']))

    def test_original_collection_still_selects_and_invalid_flag_writes_nothing(self):
        before=self.s.snapshot(self.pid)
        response=self.c.post(self.base,json={'select_output':'false'})
        self.assertEqual(response.status_code,400);self.assertEqual(self.s.snapshot(self.pid),before)
        self.assertEqual(self.s.lib.query({})['total'],0)
        response=self.c.post(self.base,json={});self.assertEqual(response.status_code,200,response.get_json())
        outputs=self.s.snapshot(self.pid)['outputs']
        self.assertEqual([o['id'] for o in outputs if o['selected']],['2'*32])


if __name__=='__main__':unittest.main()
