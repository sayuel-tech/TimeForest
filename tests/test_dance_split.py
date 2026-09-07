"""Source-graph contracts plus isolated, non-GPU business execution."""
import copy,json,hashlib,math,shutil,time,unittest,wave
from pathlib import Path
from test_studio import StudioAcceptance
from h3ui.studio_recipes import defaults,RECIPES
from h3ui.studio_story import storyboard
from h3ui import studio_media as av


class DanceSplitTests(StudioAcceptance):
 def draft(self,mode='image_story',duration=30):
  p=self.st.create(mode,'原核心隔离检查',duration)
  if mode=='swap':
   p['segments']=[self.st.new_segment(s) for s in storyboard(duration)];p['source_ready']=True
   for s in p['segments']:s.update(input_name='source-fixture.mp4')
  if mode!='text_story':p['segments'][0]['assets']=[self.asset(p)['id']]
  for s in p['segments']:s['prompt']='角色缓步走入森林。<d>[Chinese]我们出发。</d>'
  return self.st.store.save(p,p['revision'])

 def test_a_source_contract(self):
  source=json.loads(Path('h3ui/studio_sources/dance.json').read_text(encoding='utf-8'))
  nodes={n['id']:n for n in source['nodes']};links={x[0]:x for x in source['links']}
  setters={n['widgets_values'][0]:n for n in source['nodes'] if n['type']=='SetNode'}
  def resolve(nid,slot):
   n=nodes[nid]
   if n['type']=='GetNode':
    s=setters[n['widgets_values'][0]];edge=links[s['inputs'][0]['link']];return resolve(edge[1],edge[2])
   if n['type']=='Reroute':
    edge=links[n['inputs'][0]['link']];return resolve(edge[1],edge[2])
   return nid,slot
  def input_link(nid,key):
   edge=links[next(x['link'] for x in nodes[nid]['inputs'] if x['name']==key)];return resolve(edge[1],edge[2])
  p=self.draft(duration=15);row=self.st.preflight(p['id'])['segments'][0]['tasks'][0];self.assertFalse(row['errors'],row['errors']);g=row['compiled']['workflow']
  mapping={261:'14',289:'289',226:'16',139:'216',140:'215',142:'217',144:'214',255:'13',256:'12',223:'15',265:'20'}
  for old,new,keys in [(226,'16',['noise','guider','sampler','sigmas','latent_image']),(139,'216',['av_latent']),(140,'215',['latent']),(142,'217',['video_latent','audio_latent']),(144,'214',['noise','guider','sampler','sigmas'])]:
   for key in keys:
    nid,slot=input_link(old,key);self.assertEqual(g[new]['inputs'][key],[mapping[nid],slot],(old,key))
  self.assertEqual(nodes[261]['widgets_values'],['beta',12,1]);self.assertEqual(g['14']['inputs']['steps'],12)
  self.assertEqual(nodes[289]['widgets_values'],[8]);self.assertEqual(g['289']['inputs']['step'],8)
  scale_node,_=input_link(140,'mode.scale');self.assertEqual(g['215']['inputs']['mode.scale'],nodes[scale_node]['widgets_values'][0])
  self.assertEqual(sum(n['class_type']=='SamplerCustomAdvanced' for n in g.values()),2)
  self.assertNotIn('222',g);self.assertNotIn('221',g)
  self.assertEqual(g['17']['inputs']['samples'],['214',1]);self.assertEqual(g['23']['inputs']['samples'],['214',1]);self.assertEqual(g['393']['inputs']['latent'],['214',1])
  self.assertEqual(g['202']['inputs']['model'],['201',0]);self.assertNotIn('200',g)

 def test_b_modes_scenes_assets(self):
  for mode in ['swap','image_story','text_story']:
   self.assertTrue(any(r['official'] and mode in r['modes'] for r in RECIPES.values()))
   for audio in [False,True]:
    p=self.draft(mode)
    if audio:p['segments'][0]['assets'].append(self.asset(p,'audio')['id'])
    if mode=='image_story':p['segments'][0]['assets'] += [self.asset(p,subject='2')['id'],self.asset(p,subject='',purpose='palette')['id']]
    p=self.st.store.save(p,p['revision'])
    for boundary in ['continue','new_scene']:
     p['segments'][1]['boundary']=boundary
     if mode=='swap':
      p['segments'][1]['head']=22 if boundary=='continue' else 0
      p=self.st.store.save(p,p['revision']) # simulated source-cut planner result
     p=self.commit(p)
     report=self.st.preflight(p['id']);self.assertTrue(report['ready'],(mode,audio,boundary,report['errors']))
     if mode=='text_story' and not audio:self.assertIn('integrated_multimodal_description:',report['segments'][0]['tasks'][0]['prompt'])
     a,b=[(s['tasks'][0] if s.get('tasks') else s)['compiled']['workflow'] for s in report['segments']]
     self.assertEqual(a['20']['class_type'],'MiniMaxH3ReferenceToVideo')
     self.assertEqual('ref_audios.ref_audio_0' in a['20']['inputs'],audio)
     if mode=='swap':self.assertEqual(a['20']['inputs']['ref_videos.ref_video_0'],['49',0])
     if boundary=='continue':
      self.assertEqual(b['105']['inputs']['context_audio'],['645',0]);self.assertEqual(b['220']['inputs']['conditioning'],['20',0]);self.assertEqual(b['101']['class_type'],'LoadVideo')
     else:self.assertNotIn('105',b);self.assertEqual(b['214']['inputs']['guider'],['15',0])

 def test_c_parameters_and_migration(self):
  p=self.draft();p['settings'].update(steps=16,split_step=10,scale=1.3,megapixels=.4)
  p['settings']['loras'][2]['bypass']=True;p=self.commit(p)
  self.assertEqual(p['settings']['refine_steps'],6);self.assertFalse(p['settings']['acceleration'])
  g=self.st.preflight(p['id'])['segments'][0]['tasks'][0]['compiled']['workflow'];self.assertEqual(g['289']['inputs']['step'],10);self.assertEqual(g['14']['inputs']['steps'],16);self.assertEqual(g['215']['inputs']['mode.scale'],1.3);self.assertNotIn('202',g)
  bad=copy.deepcopy(p['settings']);bad['split_step']=16
  with self.assertRaises(ValueError):self.st.recipes.normalize(bad,p['mode'])
  old=self.new();before=self.st.store.get(old['id']);request={**old,'settings':defaults('dance_split')}
  plan=self.st.edit_plan(old['id'],request);self.assertTrue(plan['requires_confirmation']);self.assertEqual(self.st.store.get(old['id']),before)
  changed=self.st.store.apply(old['id'],plan['token']);self.assertEqual(changed['settings']['split_step'],8)

 def test_d_two_storyboards_approved_tail_and_audio(self):
  p=self.draft();p['segments'][0].update(seed_mode='fixed',seed='881');p['segments'][1].update(seed_mode='fixed',seed='882');p=self.st.store.save(p,p['revision'])
  calls=[];histories={};original_submit,original_wait=self.st.comfy.submit,self.st.comfy.wait
  def submit(g,client):
   calls.append(g);n=g['20']['inputs']['length'];prefix=g['19']['inputs']['filename_prefix'];dst=self.st.output/(prefix+'.mp4');dst.parent.mkdir(parents=True,exist_ok=True)
   av.run(['ffmpeg','-y','-v','error','-f','lavfi','-i',f'color=c=gray:s=128x128:r=24:d={n/24:.9f}','-f','lavfi','-i',f'sine=frequency=330:sample_rate=32000:duration={n/24:.9f}','-frames:v',str(n),'-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',dst])
   context=self.st.output/(g['393']['inputs']['filename_prefix']+'_00001.safetensors');header=json.dumps({'video':{},'audio':{}}).encode();context.write_bytes(len(header).to_bytes(8,'little')+header)
   from PIL import Image
   def item(path):
    rel=path.relative_to(self.st.output);return dict(filename=rel.name,subfolder=rel.parent.as_posix(),type='output')
   images=[]
   for i in range(g['394']['inputs']['length']):
    out=dst.parent/f'context_{i:02d}.png';Image.new('RGB',(128,128),(i*10,20,30)).save(out);images.append(item(out))
   audio=dst.parent/'lossless.flac';av.run(['ffmpeg','-y','-v','error','-f','lavfi','-i',f'sine=frequency=550:sample_rate=32000:duration={n/24:.9f}','-ac','2','-c:a','flac',audio])
   key=f'fake-{len(calls)}';histories[key]={key:{'status':{'status_str':'success'},'outputs':{'19':{'images':[item(dst)]},'395':{'images':images},'396':{'audio':[item(audio)]}}}};return key
  self.st.comfy.submit=submit;self.st.comfy.wait=lambda k:histories[k]
  try:
   self.st.run_chain(p['id'],None,True);p=self.st.store.get(p['id']);self.assertEqual(p['segments'][0]['status'],'needs_review',p.get('error'));self.assertEqual(len(calls),1)
   with self.assertRaises(ValueError):self.st.previous(p,p['segments'][1])
   self.st.approve(p['id'],0);self.st.run_chain(p['id'],None,True);p=self.st.store.get(p['id']);self.assertEqual(p['segments'][1]['status'],'needs_review',p.get('error'));self.assertEqual(len(calls),2)
   first=p['segments'][0]['attempts'][0];tail=first['tail_context'];self.assertEqual(calls[1]['101']['inputs']['file'],tail['video']);self.assertEqual(calls[1]['645']['inputs']['audio'],tail['audio'])
   self.assertEqual(calls[0]['12']['inputs']['noise_seed'],881);self.assertEqual(calls[1]['12']['inputs']['noise_seed'],882)
   self.assertEqual(tail['audio_samples'],32000)
   raw=av.run(['ffmpeg','-v','error','-i',self.st.input/tail['video'],'-f','framemd5','-'])
   self.assertEqual(len([line for line in raw.splitlines() if not line.startswith('#')]),22)
   self.st.approve(p['id'],1);deadline=time.time()+25
   while self.st.jobs.is_busy() and time.time()<deadline:time.sleep(.05)
   p=self.st.store.get(p['id']);self.assertEqual(p['status'],'complete',p.get('error'));self.assertEqual(p['export']['report']['frames'],668)
   # Corrupting the carried media must not silently use an unrelated tail.
   path=self.st.input/tail['audio'];path.write_bytes(b'bad')
   with self.assertRaises(ValueError):self.st.previous(p,p['segments'][1])
  finally:self.st.comfy.submit,self.st.comfy.wait=original_submit,original_wait

 def test_e_audio_grid_rounding(self):
  from h3ui.studio_tail import save_tail
  from PIL import Image
  p=self.draft(duration=6.58);seg=p['segments'][0];folder=self.st.output/'grid';folder.mkdir()
  images=[]
  for i in range(22):
   file=folder/f'{i}.png';Image.new('RGB',(32,32)).save(file);images.append(dict(filename=file.name,subfolder='grid'))
  audio=folder/'native.flac';av.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','sine=frequency=220:sample_rate=32000:duration=6.575','-ac','2','-c:a','flac',audio])
  history={'id':{'outputs':{'395':{'images':images},'396':{'audio':[dict(filename=audio.name,subfolder='grid')]}}}}
  compiled=dict(tail_image_node='395',tail_audio_node='396',geometry={})
  result=save_tail(self.st,p,seg,'grid',self.root/'grid-result',history,'id',compiled)
  self.assertEqual(result['audio_grid_padding_samples'],267);self.assertEqual(result['audio_samples'],32000)
  with wave.open(str(self.st.input/result['audio']),'rb') as f:self.assertEqual(f.getnframes(),32000)

if __name__=='__main__':
 suite=unittest.TestSuite(DanceSplitTests(n) for n in unittest.defaultTestLoader.getTestCaseNames(DanceSplitTests) if n.startswith(('test_a_','test_b_','test_c_','test_d_','test_e_')))
 result=unittest.TextTestRunner(verbosity=2).run(suite);raise SystemExit(not result.wasSuccessful())
