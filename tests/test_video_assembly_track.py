"""Real temporary API and media checks for independent delivery slots."""
import copy
import shutil
import unittest
from pathlib import Path
from tests import test_video_assembly as assembly_tests
from h3ui.video_assembly import media, track


class TrackTests(unittest.TestCase):
    setUpClass = classmethod(assembly_tests.AssemblyTests.setUpClass.__func__)
    tearDownClass = classmethod(assembly_tests.AssemblyTests.tearDownClass.__func__)
    setUp = assembly_tests.AssemblyTests.setUp
    refresh = assembly_tests.AssemblyTests.refresh
    post = assembly_tests.AssemblyTests.post
    upload = assembly_tests.AssemblyTests.upload
    extension = assembly_tests.AssemblyTests.extension
    payload = assembly_tests.AssemblyTests.payload
    wait_done = assembly_tests.AssemblyTests.wait_done

    def candidate(self, eid, rid='result'):
        self.refresh(); _, e = self.s.find_extension(self.p, eid)
        file = self.s.store.directory(self.pid)/(rid+'.mp4')
        shutil.copy2(self.sound, file)
        run = dict(id=rid, extension=eid, kind='generate', state='success', file=str(file),
                   created=1, started=1, finished=2, seed=0, tasks=[], note='隔离候选',
                   report=media.inspect(file), snapshot=dict(extension=copy.deepcopy(e),
                   source=self.s.source(self.p, eid), assets=[]))
        self.s.store.mutate(self.pid, lambda p:p['assembly']['runs'].append(run))
        self.refresh(); return run

    def test_select_appends_once_reselect_keeps_position_and_legacy_is_read_only(self):
        e = self.extension(); c = self.p['assembly']['clips'][0]
        a = self.candidate(e['id']); self.post('select', extension=e['id'], run=a['id'])
        keys = ['clip:'+c['id'], 'extension:'+e['id']]
        self.assertEqual(self.p['assembly']['track_order'], keys)
        self.post('select', extension=e['id'], run=a['id'])
        self.assertEqual(self.p['assembly']['track_order'], keys)
        self.post('save', track_order=keys[::-1], **self.payload())
        b = self.candidate(e['id'], 'replacement'); self.post('select', extension=e['id'], run=b['id'])
        self.assertEqual(self.p['assembly']['track_order'], keys[::-1])
        self.assertEqual(self.s.parts(self.p)[0]['candidate'], b['id'])
        self.assertTrue(Path(a['file']).is_file())
        self.s.store.mutate(self.pid, lambda p:p['assembly'].pop('track_order', None))
        before = self.s.get(self.pid); self.refresh()
        self.assertEqual(self.p['assembly']['track_order'], keys)
        self.assertEqual(self.s.get(self.pid), before)

    def test_real_export_follows_reordered_generated_and_original_slots(self):
        e = self.extension(); c = self.p['assembly']['clips'][0]
        r = self.candidate(e['id']); self.post('select', extension=e['id'], run=r['id'])
        source_before = self.s.source(self.p, e['id'])
        order = ['extension:'+e['id'], 'clip:'+c['id']]
        self.post('save', track_order=order, **self.payload())
        self.assertEqual(self.s.source(self.p, e['id']), source_before)
        self.post('export'); self.wait_done()
        result = self.p['assembly']['runs'][-1]
        self.assertEqual(result['state'], 'success', result.get('error'))
        self.assertEqual(result['snapshot']['parts'][0]['candidate'], r['id'])
        self.assertAlmostEqual(result['report']['duration'], 4, delta=.05)
        for seconds, channel in [(0.5, 2), (2.5, 0)]:
            raw = self.root/f'pixel-{channel}.rgb'
            media.command(['ffmpeg','-nostdin','-y','-v','error','-ss',seconds,'-i',result['file'],
                           '-vf','crop=2:2:iw/2:ih/2,format=rgb24','-frames:v','1','-f','rawvideo',raw])
            self.assertGreater(raw.read_bytes()[channel], 200)

    def test_invalid_duplicate_foreign_missing_and_stale_order_rejected(self):
        e = self.extension(); r = self.candidate(e['id']); self.post('select', extension=e['id'], run=r['id'])
        keys = self.p['assembly']['track_order']; before = self.s.get(self.pid)
        for order in [keys+keys[:1], keys[:1], keys+['clip:foreign'], '../file', [None]]:
            response = self.c.post('/api/v5/assembly/'+self.pid+'/save', json={
                'revision':self.p['revision'], 'track_order':order, **self.payload()})
            self.assertEqual(response.status_code, 400, response.get_json())
            self.assertEqual(self.s.get(self.pid), before)
        old_revision = self.p['revision']; self.post('save', track_order=keys[::-1], **self.payload())
        response = self.c.post('/api/v5/assembly/'+self.pid+'/save', json={
            'revision':old_revision, 'track_order':keys, **self.payload()})
        self.assertEqual(response.status_code, 409)

    def test_removed_and_invalidated_slots_do_not_export_or_duplicate_on_restore(self):
        e = self.extension(); r = self.candidate(e['id']); self.post('select', extension=e['id'], run=r['id'])
        self.post('visibility', kind='extension', id=e['id'], removed=True)
        self.assertEqual(len(track.order(self.p)), 1)
        self.post('visibility', kind='extension', id=e['id'], removed=False)
        self.assertEqual(len(track.order(self.p)), 1)
        self.post('select', extension=e['id'], run=r['id'])
        self.assertEqual(len(track.order(self.p)), 2)
        self.p['assembly']['clips'][0]['end']=1.5
        self.post('save', track_order=track.order(self.p), **self.payload())
        self.assertEqual(len(track.order(self.p)), 1)
        self.assertTrue(Path(r['file']).is_file())

    def test_continued_result_appends_without_reinterpreting_its_generation_source(self):
        e = self.extension(); c = self.p['assembly']['clips'][0]
        first = self.candidate(e['id']); self.post('select', extension=e['id'], run=first['id'])
        self.post('save', track_order=track.order(self.p)[::-1], **self.payload())
        self.post('extensions', clip=c['id']); second_e=self.p['assembly']['clips'][0]['extensions'][-1]
        second = self.candidate(second_e['id'], 'second'); self.post('select', extension=second_e['id'], run=second['id'])
        self.assertEqual(track.order(self.p), ['extension:'+e['id'], 'clip:'+c['id'], 'extension:'+second_e['id']])
        self.assertEqual(second['snapshot']['source']['origin']['candidate'], first['id'])
        replacement=self.candidate(e['id'], 'replacement'); self.post('select', extension=e['id'], run=replacement['id'])
        self.assertEqual(len(track.order(self.p)), 2)
        self.assertTrue(Path(second['file']).is_file())
        self.assertEqual(self.p['assembly']['runs'][-2]['snapshot']['source'], second['snapshot']['source'])
        self.assertEqual(self.c.get('/api/v5/health').get_json()['assembly_track_version'],1)


if __name__ == '__main__': unittest.main()
