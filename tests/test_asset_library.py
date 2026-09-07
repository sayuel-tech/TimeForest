"""No model or engine requests: immutable originals, versions and backup contracts."""
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, PngImagePlugin

from h3ui.asset_library.service import Library
from h3ui.asset_library.media import digest
from h3ui.studio_store import Conflict


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.lib = Library(self.root / 'library')
        self.image = self.root / 'transparent.png'
        png = PngImagePlugin.PngInfo()
        png.add_text('prompt', json.dumps({'1': {'class_type': 'ExampleNode', 'inputs': {'text': 'original record'}}}))
        Image.new('RGBA', (64, 80), (90, 110, 130, 100)).save(self.image, pnginfo=png)

    def ingest(self, name='丹眉', **kw):
        return self.lib.ingest(self.image, name, **kw)

    def test_original_bytes_and_identity_are_separate(self):
        first = self.ingest(metadata={'categories': ['character', 'palette'], 'record_prompt': 'private original prompt'})
        second = self.ingest('另一个角色')
        self.assertNotEqual(first['id'], second['id'])
        m = first['snapshot']['media'][0]
        self.assertTrue(m['meta']['alpha'])
        self.assertEqual(m['hash'], digest(self.image))
        self.assertEqual(self.lib.storage()['objects'], 1)
        self.assertEqual(digest(self.lib.store.path(self.lib.store.object(m['hash'])['path'])), digest(self.image))
        self.assertIn('prompt', first['snapshot']['provenance']['records'])

    def test_versions_conflicts_and_idempotency(self):
        first = self.ingest(key='one-import')
        self.assertEqual(self.ingest(key='one-import')['id'], first['id'])
        updated = self.lib.update(first['id'], 1, {'record_prompt': 'documentation only', 'description': 'setting', 'name': '丹眉新版'})
        self.assertNotEqual(first['version'], updated['version'])
        self.assertEqual(self.lib.store.get(first['id'], first['version'])['snapshot']['name'], '丹眉')
        self.assertEqual(updated['snapshot']['provenance'], first['snapshot']['provenance'])
        with self.assertRaises(Conflict):
            self.lib.update(first['id'], 1, {'name': 'stale'})
        self.assertEqual(self.lib.query({})['total'], 1)

    def test_corrupt_disk_failure_and_path_escape_do_not_register_assets(self):
        corrupt = self.root / 'fake.png'
        corrupt.write_text('not an image', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.lib.ingest(corrupt, 'invalid')
        with patch('h3ui.asset_library.service.shutil.copyfile', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.ingest()
        self.assertEqual(self.lib.query({})['total'], 0)
        with self.assertRaises(ValueError):
            self.lib.store.path('../outside.txt')

    def test_document_revision_does_not_change_media_or_provenance(self):
        first = self.ingest()
        updated = self.lib.update(first['id'], 1, {'record_prompt': 'NOT a production prompt', 'description': 'Picture 100, voice 99'})
        self.assertEqual(first['snapshot']['media'], updated['snapshot']['media'])
        with self.assertRaises(ValueError):
            self.lib.update(first['id'], 2, {'provenance': {'seed': 1}})

    def test_bound_versions_and_cycles(self):
        one = self.ingest()
        two = self.ingest('声音的所有者')
        linked = self.lib.update(one['id'], 1, {'bindings': [dict(asset=two['id'], version=two['version'], purpose='voice', default=True)]})
        self.assertEqual(linked['snapshot']['bindings'][0]['version'], two['version'])
        with self.assertRaisesRegex(ValueError, '循环'):
            self.lib.update(two['id'], 1, {'bindings': [dict(asset=one['id'], version=linked['version'], purpose='character', default=True)]})

    def test_trash_restore_collections_and_consistent_backup(self):
        one = self.ingest(metadata={'categories': ['character'], 'tags': ['舞者']})
        collection = self.lib.store.collection('电影素材', items=[one['id']])
        self.assertEqual(self.lib.query({'collection': collection['id'], 'tag': '舞者'})['total'], 1)
        trashed = self.lib.store.trash(one['id'], one['revision'])
        self.assertEqual(self.lib.query({})['total'], 0)
        self.assertEqual(self.lib.query({'trash': '1'})['total'], 1)
        self.lib.store.trash(one['id'], trashed['revision'], restore=True)
        backup = self.lib.backup(self.root / 'backup')
        self.lib.verify_backup(backup['path'])
        restored = Library(backup['path'])
        self.assertEqual(restored.query({})['total'], 1)
        self.assertEqual(restored.store.get(one['id'])['snapshot']['id'], one['version'])
        self.assertEqual(self.lib.store.collection_items(collection['id']), [one['id']])


if __name__ == '__main__':
    unittest.main()
