"""Media URLs and stale telemetry are checked without a model or ComfyUI."""
import json,tempfile,unittest
from pathlib import Path
from h3ui.studio_progress import snapshot_runtime

class SourcePreview(unittest.TestCase):
    def test_new_source_segments_do_not_adopt_previous_completion(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root,'live-progress.json').write_text(json.dumps(dict(phase='本次渲染已完成',prompt_id='old',finished=10)))
            p=dict(id='p',status='draft',segments=[dict(status='draft',attempts=[],selected=None)])
            self.assertEqual(snapshot_runtime(p,root),{'active':False})

    def test_unrelated_prompt_telemetry_is_not_current(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root,'live-progress.json').write_text(json.dumps(dict(phase='完成',prompt_id='old')))
            p=dict(id='p',status='draft',segments=[dict(status='draft',attempts=[dict(id='new',prompt_id='new')],selected=None)])
            self.assertEqual(snapshot_runtime(p,root),{'active':False})
