"""CPU-only fixtures exercise original timebases, derivations, collection and portable packs."""
import copy
import io
import json
import os
import time
import unittest
import zipfile
from pathlib import Path

from test_asset_library import LibraryTests
from h3ui.asset_library.collect import scan, import_scan
from h3ui.asset_library.derive import derive
from h3ui.asset_library.media import command, digest, inspect
from h3ui.asset_library.packs import Packs
from h3ui.asset_library.service import Library


class MediaToolsTests(unittest.TestCase):
    setUp = LibraryTests.setUp

    def video(self):
        path=self.root/'motion.mp4'
        command(['ffmpeg','-y','-v','error','-f','lavfi','-i','testsrc2=size=160x120:rate=30000/1001',
                 '-f','lavfi','-i','sine=frequency=420:sample_rate=48000','-t','3.5','-c:v','libx264','-c:a','aac',path])
        return path,self.lib.ingest(path,'原视频',{'categories':['video']})

    def test_timestamp_video_clip_audio_and_frame_preserve_original(self):
        path,asset=self.video();sha=digest(path);m=asset['snapshot']['media'][0]
        for operation,params,kind in [('clip',dict(start=.7,end=2.7),'video'),('audio',dict(start=1,end=3),'audio'),('frame',dict(start=1),'image')]:
            result=derive(self.lib,dict(asset=asset['id'],version=asset['version'],media=m['id'],operation=operation,params=params),lambda *args:None)
            meta=result['snapshot']['media'][0]['meta']
            self.assertEqual(meta['kind'],kind)
            self.assertEqual(result['snapshot']['provenance']['parent']['hash'],sha)
            if kind!='image':self.assertAlmostEqual(meta['duration'],2,delta=.06)
            if kind=='video':self.assertTrue(meta['has_audio']);self.assertEqual(meta['fps'],'30000/1001')
        self.assertEqual(digest(path),sha)
        self.assertEqual(self.lib.query({'category':'video'})['total'],2)

    def test_transparent_crop_rotate_resize_keeps_parent(self):
        asset=self.lib.ingest(self.image,'transparent');m=asset['snapshot']['media'][0]
        result=derive(self.lib,dict(asset=asset['id'],version=asset['version'],media=m['id'],operation='image_transform',
                                  params={'x':2,'y':2,'crop_width':40,'crop_height':60,'rotation':90,'width':120}),lambda *args:None)
        meta=result['snapshot']['media'][0]['meta']
        self.assertTrue(meta['alpha']);self.assertEqual((meta['width'],meta['height']),(120,80))
        self.assertNotEqual(meta['hash'],digest(self.image))

    def test_explicit_scan_skips_writing_files_and_import_is_pinned(self):
        source=self.root/'input';source.mkdir();file=source/'role.png';file.write_bytes(self.image.read_bytes())
        first=scan(self.lib,{'directory':str(source)},lambda *args:None)
        self.assertFalse(first['items']);self.assertEqual(len(first['skipped']),1)
        old=time.time()-10;os.utime(file,(old,old))
        second=scan(self.lib,{'directory':str(source)},lambda *args:None)
        self.assertEqual(len(second['items']),1)
        imported=import_scan(self.lib,{'file':second['items'][0]['id']},lambda *args:None)
        file.write_bytes(b'changed')
        with self.assertRaises(ValueError):import_scan(self.lib,{'file':second['items'][0]['id']},lambda *args:None)
        self.assertEqual(imported['snapshot']['media'][0]['hash'],digest(self.image))

    def test_portable_package_roundtrip_redacts_environment_and_preserves_bindings(self):
        self.lib.store.category('动作参考')
        cid=next(x['id'] for x in self.lib.store.catalog()['categories'] if x['name']=='动作参考')
        child=self.lib.ingest(self.image,'配饰',{'categories':['prop',cid]},provenance={'type':'local','api_key':'secret-example','path':'D:/private/media.png'})
        parent=self.lib.ingest(self.image,'角色',{'categories':['character'],'record_prompt':'Recorded prompt'})
        parent=self.lib.update(parent['id'],parent['revision'],{'bindings':[dict(asset=child['id'],version=child['version'],purpose='prop',default=True)]})
        packs=Packs(self.lib)
        plan=packs.preview(dict(assets=[{'asset':parent['id'],'version':parent['version']}],bindings=True,documents=True,workflows=True))
        self.assertEqual(len(plan['assets']),2)
        output=packs.export({'token':plan['token']},lambda *args:None)
        archive=self.lib.root/'exports'/(plan['token']+'.zip')
        with zipfile.ZipFile(archive) as z:
            text=z.read('manifest.json').decode()
            self.assertNotIn('secret-example',text);self.assertNotIn('D:/private',text)
        other=Library(self.root/'restored');receiver=Packs(other)
        with archive.open('rb') as file:upload=receiver.stage(file)
        result=receiver.import_pack({'token':upload['token']},lambda *args:None)
        self.assertEqual(result['count'],2)
        restored=next(x for x in other.query({})['items'] if x['name']=='角色')
        self.assertNotEqual(restored['id'],parent['id'])
        binding=other.store.get(restored['id'])['snapshot']['bindings'][0]
        self.assertEqual(other.store.get(binding['asset'],binding['version'])['name'],'配饰')
        repeated=receiver.import_pack({'token':upload['token']},lambda *args:None)
        self.assertEqual(repeated['count'],2);self.assertEqual(other.query({})['total'],2)
        self.assertIn('动作参考',[x['name'] for x in other.store.catalog()['categories']])

    def test_pack_path_escape_rejected_before_asset_registration(self):
        packs=Packs(self.lib);bad=self.root/'bad.zip'
        manifest=dict(format='time-forest-assets',version=1,assets=[dict(id='a',name='bad',media=[dict(hash='0'*64)])],
                      files=[dict(path='../outside.png',bytes=1,hash='0'*64)])
        with zipfile.ZipFile(bad,'w') as z:z.writestr('manifest.json',json.dumps(manifest));z.writestr('../outside.png',b'x')
        with self.assertRaisesRegex(ValueError,'路径越界'):
            with bad.open('rb') as f:packs.stage(f)
        self.assertEqual(self.lib.query({})['total'],0)


if __name__=='__main__':unittest.main()
