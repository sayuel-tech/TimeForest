"""Telemetry checks only: no ComfyUI prompt submission."""
import json,tempfile,time,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from h3ui.studio_progress import ProgressWatch,read,snapshot_runtime,workflow_summary

class ProgressTests(unittest.TestCase):
 def test_events_and_prompt_isolation(self):
  with tempfile.TemporaryDirectory() as d:
   g={'16':{'class_type':'SamplerCustomAdvanced'},'215':{'class_type':'MinimaxH3LatentUpscaler3D'},'214':{'class_type':'SamplerCustomAdvanced'}}
   w=ProgressWatch('http://127.0.0.1:8000','unit-only',g,Path(d)/'attempt',d,1,0,2)
   w.submitted('expected')
   w.event({'type':'executing','data':{'prompt_id':'foreign','node':'214'}})
   self.assertIsNone(w.data['node'])
   w.event({'type':'executing','data':{'prompt_id':'expected','node':'16'}})
   w.event({'type':'progress','data':{'prompt_id':'expected','node':'16','value':4,'max':12}});w.publish()
   data=read(Path(d)/'live-progress.json');self.assertEqual(data['step'],4);self.assertEqual(data['step_total'],12);self.assertIn('第一采',data['phase'])
   w.event({'type':'executing','data':{'prompt_id':'expected','node':'215'}});self.assertIsNone(w.data['step']);self.assertIn('放大',w.data['phase'])
   w.event({'type':'executing','data':{'prompt_id':'expected','node':'214'}})
   w.event({'type':'progress','data':{'prompt_id':'expected','value':1,'max':4}});w.publish()
   self.assertEqual(w.data['step_total'],4);self.assertIn('第二采',w.data['phase']);self.assertEqual(w.data['nodes_done'],2)
   w.event({'type':'execution_error','data':{'prompt_id':'expected','exception_message':'unit failure'}})
   self.assertTrue(w.data['finished']);self.assertEqual(w.data['error'],'unit failure')
 def test_split_sampler_stage_names(self):
  with tempfile.TemporaryDirectory() as d:
   g={'289':{'inputs':{'step':8}},'14':{'inputs':{'steps':12}}}
   w=ProgressWatch('http://127.0.0.1:8000','unit-only',g,d,d,0)
   self.assertIn('前8步',w.phase('16'));self.assertIn('剩余4步',w.phase('214'))
 def test_snapshot_uses_actual_graph(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);g={'1':{'inputs':{'unet_name':'actual-model'}},'20':{'inputs':{'width':736,'height':416}},'14':{'inputs':{'steps':12,'denoise':1}},'214':{},'215':{'inputs':{'mode.scale':1.5}},'222':{'inputs':{'steps':4,'denoise':.3}}}
   (p/'workflow.json').write_text(json.dumps(g));(p/'qa.json').write_text(json.dumps(dict(width=1088,height=640)))
   result=workflow_summary(d);self.assertEqual(result['model'],'actual-model');self.assertEqual(result['refine_steps'],4);self.assertEqual(result['output_width'],1088)
   a=dict(id='run',directory=d,created=10,completed=20,status='complete',seed='7')
   project=dict(id='p',status='needs_review',segments=[dict(status='needs_review',selected='run',attempts=[a])])
   runtime=snapshot_runtime(project,d);self.assertFalse(runtime['active']);self.assertEqual(project['segments'][0]['execution_info']['runs'][0]['summary']['steps'],12)

if __name__=='__main__':unittest.main(verbosity=2)
