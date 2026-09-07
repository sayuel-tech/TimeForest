"""One maintained UI and execution service, with historical result access intact."""
import unittest
from pathlib import Path
import test_local_server as fixture


class MaintenanceBoundaryTests(unittest.TestCase):
    def setUp(self):
        fixture.LocalServerTests.setUp(self)

    def test_one_ui_and_no_retired_engine_dependency(self):
        root = self.st.ctx['root']
        self.assertNotIn('engine', self.st.ctx)
        self.assertIs(self.st.comfy, self.st.ctx['comfy'])
        for url in ['/', '/static/studio/app.js', '/static/studio/style.css', '/api/health']:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            response.close()
        for name in ['engine.py', 'profiles.py', 'domain.py']:
            self.assertFalse((root / 'h3ui' / name).exists())
        for url in ['/static/index-v4.html', '/static/legacy-v3/index.html', '/static/studio/index.html', '/api/profiles']:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 404, url)
            response.close()

    def test_legacy_media_still_readable_and_execution_blocked(self):
        registry = self.st.ctx['projects']
        pid = 'a' * 32
        registry.create(dict(id=pid, name='历史结果', status='idle', segments=[]))
        result = registry.project_dir(pid) / 'result.txt'
        result.write_text('preserved result', encoding='utf-8')
        response = self.client.get('/api/projects/' + pid)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['name'], '历史结果')
        response = self.client.get('/api/projects/' + pid + '/outputs/result.txt')
        self.assertEqual(response.data, b'preserved result')
        response.close()
        for suffix in ['', '/generate-all', '/concat']:
            self.assertEqual(self.client.post('/api/projects/' + pid + suffix).status_code, 409)
        self.assertEqual(result.read_text(encoding='utf-8'), 'preserved result')


if __name__ == '__main__':
    unittest.main()
