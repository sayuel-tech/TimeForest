"""Cross-mode registration uses committed references, never picker/import drafts."""
import copy
from unittest.mock import patch
from PIL import Image
from tests.test_video_assembly import AssemblyTests


class LibraryUsageTests(AssemblyTests):
    def library_asset(self, video=False):
        path=self.silent if video else self.root/'role.png'
        if not video: Image.new('RGB',(128,128),(70,120,80)).save(path)
        self.lib=self.app.config['ASSET_LIBRARY']
        return self.lib.ingest(path,'Synthetic asset')

    def identity(self,item):
        return dict(asset=item['id'],version=item['version'],media=item['snapshot']['media'][0]['id'])

    def usage(self,item):
        with self.lib.store.connect() as db:
            return db.execute('SELECT count(*) FROM refs WHERE asset=?',(item['id'],)).fetchone()[0],self.lib.store.get(item['id'])['used']

    def test_assembly_import_registers_video_and_reference_and_preserves_versions(self):
        video=self.library_asset(True);image=self.library_asset()
        self.s.import_video(self.pid,self.p['revision'],reference=self.identity(video));self.refresh()
        self.assertEqual(self.usage(video)[0],1);self.assertIsNotNone(self.usage(video)[1])
        self.post('extensions',clip=self.p['assembly']['clips'][0]['id'])
        eid=self.p['assembly']['clips'][0]['extensions'][0]['id']
        self.s.import_reference(self.pid,dict(revision=self.p['revision'],extension=eid,reference=self.identity(image)))
        self.assertEqual(self.usage(image)[0],1);self.assertIsNotNone(self.usage(image)[1])
        detail=self.c.get('/api/v5/library/assets/'+image['id']).get_json()
        self.assertEqual(detail['references'],[dict(project=self.pid,version=image['version'])])
        with self.lib.store.connect() as db: before=db.execute('SELECT used FROM assets WHERE id=?',(image['id'],)).fetchone()[0]
        self.s.sync_library_usage(self.s.get(self.pid))
        self.assertEqual(self.usage(image),(1,before),'registration retry must not move recently used')

    def test_assembly_registration_failure_retries_on_save_without_duplicate_import(self):
        item=self.library_asset(True)
        with patch.object(self.lib,'record_usage',side_effect=OSError('isolated registration failure')):
            failed=self.c.post('/api/v5/assembly/'+self.pid+'/import',json=dict(revision=self.p['revision'],reference=self.identity(item)))
            self.assertEqual(failed.status_code,503);self.assertEqual(failed.get_json()['code'],'LIBRARY_USAGE_PENDING')
        self.refresh();self.assertEqual(len(self.p['assembly']['clips']),1)
        self.assertEqual(self.usage(item),(0,None))
        self.s.save(self.pid,dict(revision=self.p['revision'],clips=self.p['assembly']['clips'],output=self.p['assembly']['output']))
        self.refresh();self.assertEqual(len(self.p['assembly']['clips']),1)
        self.assertEqual(self.usage(item)[0],1)

    def test_image_import_only_registers_after_confirmed_save_and_retry_is_idempotent(self):
        item=self.library_asset();images=self.app.config['IMAGE_STUDIO'];p=images.create('Image usage')
        ref=images.library_input(p['id'],self.identity(item))
        self.assertEqual(self.usage(item),(0,None),'preparing an input is not using it')
        p['tasks'][0]['A']=ref['id']
        plan=images.plan(p['id'],p)
        self.assertEqual(self.usage(item),(0,None),'planning or cancelling must not record usage')
        response=self.c.post('/api/v5/image-projects/'+p['id']+'/apply',json=dict(token=plan['token']))
        self.assertEqual(response.status_code,200,response.get_json())
        recorded=self.usage(item);self.assertEqual(recorded[0],1);self.assertIsNotNone(recorded[1])
        response=self.c.post('/api/v5/image-projects/'+p['id']+'/apply',json=dict(token=plan['token']))
        self.assertEqual(response.status_code,200);self.assertEqual(self.usage(item),recorded)

    def test_failed_project_commit_does_not_record_usage(self):
        item=self.library_asset();images=self.app.config['IMAGE_STUDIO'];p=images.create('Failed save')
        ref=images.library_input(p['id'],self.identity(item));p['tasks'][0]['A']=ref['id'];plan=images.plan(p['id'],p)
        with patch.object(images.store,'apply',side_effect=OSError('isolated disk failure')):
            response=self.c.post('/api/v5/image-projects/'+p['id']+'/apply',json=dict(token=plan['token']))
        self.assertNotEqual(response.status_code,200);self.assertEqual(self.usage(item),(0,None))

    def test_usage_retry_after_library_failure_uses_committed_image_plan(self):
        item=self.library_asset();images=self.app.config['IMAGE_STUDIO'];p=images.create('Retry usage')
        ref=images.library_input(p['id'],self.identity(item));p['tasks'][0]['A']=ref['id'];plan=images.plan(p['id'],p)
        with patch.object(self.lib,'record_usage',side_effect=OSError('isolated library unavailable')):
            failed=self.c.post('/api/v5/image-projects/'+p['id']+'/apply',json=dict(token=plan['token']))
            self.assertEqual(failed.status_code,503);self.assertEqual(failed.get_json()['code'],'LIBRARY_USAGE_PENDING')
        self.assertEqual(images.snapshot(p['id'])['tasks'][0]['A'],ref['id'])
        response=self.c.post('/api/v5/image-projects/'+p['id']+'/apply',json=dict(token=plan['token']))
        self.assertEqual(response.status_code,200);self.assertEqual(self.usage(item)[0],1)
