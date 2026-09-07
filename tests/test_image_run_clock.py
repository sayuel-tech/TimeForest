"""Durable image timing uses isolated stores; no generation or engine access."""
import unittest
from unittest.mock import patch
from tests import test_task_center as fixtures


class ImageRunClockTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.TaskCenterTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.runner=self.f.s.runner

    def test_engine_queue_wait_does_not_start_execution_clock(self):
        run=self.f.run_record('a'*32,'waiting')
        self.f.get.return_value={'queue_pending':[[0,'another-task']]}
        with patch('h3ui.image_studio.runner.time.sleep'),patch.object(self.f.s,'catalog') as catalog:
            self.runner.execute(run)
        catalog.assert_not_called()
        self.assertNotIn('started',self.f.s.store.get('runs',run['id']))

    def test_execution_start_and_terminal_time_survive_api_reload_and_later_notes(self):
        run=self.f.run_record('a'*32,'waiting')
        with patch('h3ui.image_studio.runner.time.time',return_value=120),patch.object(self.f.s,'catalog',side_effect=ValueError('isolated preparation failure')):
            with self.assertRaises(ValueError):self.runner.execute(run)
        with patch('h3ui.image_studio.runner.time.time',return_value=145):self.runner.update(run,state='failed')
        with patch('h3ui.image_studio.runner.time.time',return_value=190):self.runner.update(run,note='later note',state='failed')
        result=self.f.c.get('/api/v5/projects/'+self.f.pid).get_json()['runs'][0]
        self.assertEqual((result['created'],result['started'],result['finished']),(1,120,145))
        self.assertEqual(result['snapshot'],run['snapshot'])
        self.f.post.assert_not_called()

    def test_cancel_waiting_records_end_without_faking_execution_start(self):
        run=self.f.run_record('a'*32,'waiting')
        with patch('h3ui.image_studio.runner.time.time',return_value=170):self.runner.cancel(self.f.pid,run['id'])
        result=self.f.s.store.get('runs',run['id'])
        self.assertEqual(result['finished'],170);self.assertNotIn('started',result)
        self.f.get.assert_not_called();self.f.post.assert_not_called()


if __name__=='__main__':unittest.main()
