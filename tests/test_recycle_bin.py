import json
import subprocess
import unittest
import uuid
from pathlib import Path
from PIL import Image
from tests import test_task_center as fixtures


class RecycleBinTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.TaskCenterTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.c=self.f.c;self.st=self.f.st;self.images=self.f.s;self.lib=self.f.app.config['ASSET_LIBRARY']

    def listing(self,category,**args):
        r=self.c.get('/api/v5/recycle-bin',query_string=dict(category=category,**args));self.assertEqual(r.status_code,200);return r.json

    def removed_image(self):
        run=self.f.run_record(uuid.uuid4().hex,'success')
        response=self.c.post('/api/v5/projects/'+self.f.pid+'/records/visibility',json=dict(record=run['id'],revision=self.images.store.project(self.f.pid)['revision'],removed=True))
        self.assertEqual(response.status_code,200);return run

    def restore_from_frontend(self,data,index=0):
        script="""import {restoreRequest,recycleView} from './static/studio/pages/asset-library/recycle-bin.js';
let raw='';for await(const chunk of process.stdin)raw+=chunk;const {data,index}=JSON.parse(raw);
if(!recycleView(data).includes('data-recycle-restore'))throw Error('restore control missing');
process.stdout.write(JSON.stringify(restoreRequest(data.items[index])));"""
        result=subprocess.run(['node','--input-type=module','-e',script],input=json.dumps(dict(data=data,index=index)),text=True,capture_output=True,check=True)
        request=json.loads(result.stdout)
        return self.c.post('/api/v5'+request['path'],json=request['body'])

    def test_asset_listing_and_real_frontend_restore_preserve_media(self):
        path=self.images.store.root/'fixture.png';Image.new('RGB',(8,8),'green').save(path)
        asset=self.lib.ingest(path,'角色资产');before=self.lib.store.get(asset['id'])
        self.c.post('/api/v5/library/assets/'+asset['id']+'/trash',json={'revision':asset['revision']})
        data=self.listing('assets');self.assertEqual(data['counts'],dict(assets=1,projects=0,generations=0))
        self.assertIn('/library/media/',data['items'][0]['preview'])
        self.assertEqual(self.restore_from_frontend(data).status_code,200)
        self.assertEqual(self.listing('assets')['total'],0)
        self.assertEqual(self.lib.store.get(asset['id'])['snapshot'],before['snapshot']);self.assertTrue(path.exists())

    def test_all_project_types_and_legacy_restore_without_generation(self):
        ids=[]
        for mode in ['swap','image_story','text_story']:
            p=self.st.create(mode,'回收 '+mode,15);ids.append(p['id'])
            self.c.post('/api/v5/projects/'+p['id']+'/trash',json={'revision':p['revision']})
        self.c.post('/api/v5/projects/'+self.f.pid+'/trash',json={'revision':self.f.p['revision']})
        pid=uuid.uuid4().hex;self.st.ctx['projects'].create(dict(id=pid,name='旧版作品',status='idle',segments=[]))
        self.c.post('/api/v5/legacy/'+pid+'/trash',json={})
        data=self.listing('projects');self.assertEqual(data['total'],5)
        self.assertEqual({p['type'] for p in data['items']},{'project','legacy_project'})
        for _ in range(5):self.assertEqual(self.restore_from_frontend(self.listing('projects')).status_code,200)
        self.assertEqual(self.listing('projects')['total'],0)
        self.f.get.assert_not_called();self.f.post.assert_not_called();self.f.wake.assert_not_called()

    def test_parent_restore_does_not_restore_removed_generation(self):
        run=self.removed_image();p=self.images.store.project(self.f.pid)
        self.c.post('/api/v5/projects/'+self.f.pid+'/trash',json={'revision':p['revision']})
        data=self.listing('generations');self.assertTrue(data['items'][0]['parent_deleted']);self.assertIn('先',data['items'][0]['blocked_reason'])
        self.assertEqual(self.restore_from_frontend(self.listing('projects')).status_code,200)
        data=self.listing('generations');self.assertEqual(data['total'],1);self.assertFalse(data['items'][0]['parent_deleted'])
        self.assertEqual(self.restore_from_frontend(data).status_code,200)
        self.assertFalse(self.images.store.get('runs',run['id'])['removed_at'])

    def test_generated_records_cover_three_video_modes_and_no_output_images(self):
        self.removed_image()
        for mode in ['swap','image_story','text_story']:
            p=self.st.create(mode,mode,15)
            def seed(q):
                if not q['segments']:q['segments']=[self.st.new_segment(dict(index=0))]
                q['segments'][0]['attempts']=[dict(id=uuid.uuid4().hex,status='failed',seed=0,removed_at=123)]
            self.st.store.mutate(p['id'],seed)
        data=self.listing('generations');self.assertEqual(data['total'],4)
        for _ in range(4):self.assertEqual(self.restore_from_frontend(self.listing('generations')).status_code,200)
        self.assertEqual(self.listing('generations')['total'],0)

    def test_index_is_read_only_paged_searchable_and_counts_ignore_search(self):
        for i in range(26):
            r=self.f.run_record(uuid.uuid4().hex,'failed');self.images.store.mutate('runs',r['id'],lambda r:r.update(removed_at=100+i,seed=i))
        with self.images.store.connect() as db:before=list(db.iterdump())
        first=self.listing('generations');second=self.listing('generations',page=2)
        self.assertEqual((len(first['items']),len(second['items'])),(24,2))
        self.assertFalse({r['id'] for r in first['items']} & {r['id'] for r in second['items']})
        self.assertEqual(self.listing('generations',q='missing')['counts']['generations'],26)
        self.assertEqual(self.listing('generations',q='missing')['total'],0)
        with self.images.store.connect() as db:self.assertEqual(list(db.iterdump()),before)
        self.f.get.assert_not_called();self.f.post.assert_not_called()

    def test_stale_restore_and_busy_project_use_existing_guards(self):
        self.removed_image();data=self.listing('generations')
        self.images.store.mutate('projects',self.f.pid,lambda p:p.update(revision=p['revision']+1))
        self.assertEqual(self.restore_from_frontend(data).status_code,409)
        self.f.run_record(uuid.uuid4().hex,'unknown')
        self.assertIn('待确认',self.listing('generations')['items'][0]['blocked_reason'])
        self.assertEqual(self.c.get('/api/v5/recycle-bin?category=invalid').status_code,400)


if __name__=='__main__':unittest.main()
