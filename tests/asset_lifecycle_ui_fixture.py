"""Five actual controllers and temporary real APIs; no production data or engine."""
import argparse,json,sys,threading
from pathlib import Path
from werkzeug.serving import make_server,WSGIRequestHandler
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_video_assembly import AssemblyTests
from tests.workspace_navigation_ui_fixture import capture
from h3ui.studio_recipes import defaults

SCRIPT=r'''<script type="module">
const sleep=ms=>new Promise(r=>setTimeout(r,ms)),assert=(v,m)=>{if(!v)throw Error(m)};
const wait=async fn=>{for(let i=0;i<500;i++){if(await fn())return;await sleep(30)}throw Error('UI timeout: '+fn)};
const click=async s=>{await wait(()=>document.querySelector(s)&&!document.querySelector(s).disabled);document.querySelector(s).click();await sleep(40)};
const q=new URLSearchParams(location.search),pid=q.get('pid'),aid=q.get('aid'),mode=q.get('mode'),root=document.querySelector('#root');
const nativeFetch=window.fetch.bind(window);let writes=0;
window.fetch=(url,options={})=>{if(options.method&&options.method!=='GET')writes++;return nativeFetch(url,options)};
const read=()=>nativeFetch('/api/v5/projects/'+pid).then(r=>r.json());
const lib=()=>nativeFetch('/api/v5/library/assets/'+aid).then(r=>r.json());
const input=(selector,value)=>{const e=document.querySelector(selector);e.value=value;e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}))};
let workspace;
const watchdog=setTimeout(()=>{document.body.dataset.check=JSON.stringify({passed:false,error:"unfinished interaction",visible:document.body.innerText.slice(-1800)})},35000);
try{
 const initial=await read();location.hash='#/p/'+pid;
 if(mode==='video_assembly'){
  const {mountWorkspace}=await import('/static/studio/modes/video-assembly/workspace.js');workspace=mountWorkspace(root,initial,await nativeFetch('/api/v5/assembly/catalog').then(r=>r.json()));
  await click('[data-workspace-step="1"]');await click('[data-extension]');
  input('[data-prompt]','未保存续接正文');const before=await read();
  await click('[data-reference-library]');await click('.picker-cancel');assert(JSON.stringify(await read())===JSON.stringify(before),'picker cancel saved assembly');
  await click('[data-reference-library]');await click('[data-pick="'+aid+'"]');await wait(()=>document.querySelector('[data-reference-apply]'));
  input('[data-reference-purpose]','palette');assert(document.querySelector('[data-reference-subject]').disabled,'palette still needs character');
  await click('[data-reference-cancel]');assert(JSON.stringify(await read())===JSON.stringify(before),'metadata cancel saved assembly');
  await click('[data-reference-library]');await click('[data-pick="'+aid+'"]');await wait(()=>document.querySelector('[data-reference-apply]'));
  input('[data-reference-purpose]','costume');input('[data-reference-subject]','2');await click('[data-reference-apply]');
  await wait(()=>root.querySelector('[data-reference-edit]')&&!workspace.session.working);
  let saved=await read(),e=saved.assembly.clips[0].extensions[0];assert(e.prompt==='未保存续接正文','assembly prompt lost');assert(e.references[0].purpose==='costume'&&e.references[0].subject==='2','assembly metadata lost');
  await click('[data-reference-edit]');input('[data-reference-purpose]','scene');await click('[data-reference-cancel]');assert(!workspace.session.dirty,'edit cancellation dirtied assembly');
  await click('[data-reference-edit]');input('[data-reference-purpose]','palette');await click('[data-reference-apply]');assert(workspace.session.dirty,'edit not in draft');await click('[data-save]');await wait(()=>!workspace.session.working&&!workspace.session.dirty);
  assert((await read()).assembly.clips[0].extensions[0].references[0].subject==='','palette persisted character');
  await click('[data-reference-remove]');await click('[data-save]');await wait(()=>!workspace.session.working&&!workspace.session.dirty);
  assert((await read()).assembly.clips[0].extensions[0].references.length===0,'assembly reference not removed');
 }else if(mode==='image_assets'){
  const {mountWorkspace}=await import('/static/studio/app/image-workspace-controller.js');workspace=mountWorkspace(root,initial,await nativeFetch('/api/v5/image-projects/catalog').then(r=>r.json()));
  input('#image-prompt','未保存图片正文');let before=await read();const count=writes;
  await click('[data-library="A"]');await click('.picker-cancel');await wait(()=>!workspace.session.actionPending);assert(writes===count,'image picker cancellation sent write');
  await click('[data-library="A"]');await click('[data-pick="'+aid+'"]');await wait(()=>root.querySelector('[data-remove-input="A"]')&&!workspace.session.actionPending);
  assert(workspace.session.project.tasks[0].prompt==='未保存图片正文','image prompt lost');await workspace.session.save();
  before=await read();await click('[data-remove-input="A"]');await click('#no');await wait(()=>!workspace.session.actionPending);assert(JSON.stringify(await read())===JSON.stringify(before),'cancel removed image');
  await click('[data-remove-input="A"]');await click('#yes');await wait(()=>!workspace.session.actionPending);assert(workspace.session.project.tasks[0].A===null,'image reference not removed');await workspace.session.save();
  assert((await read()).tasks[0].A===null,'image removal not saved');assert((await read()).inputs.length>0,'image removal deleted file record');
 }else{
  const {getMode}=await import('/static/studio/app/mode-registry.js'),definition=getMode(mode),view=await definition.load(),{mountWorkspace}=await import('/static/studio/app/workspace-controller.js');workspace=mountWorkspace(root,initial,await nativeFetch('/api/v5/catalog').then(r=>r.json()),definition,view);
  const ctx=workspace.ctx;ctx.tab='edit';ctx.shot=0;ctx.project.segments[0].prompt='未保存视频正文';ctx.setDirty();ctx.renderProject();const before=await read();
  let pending=ctx.useLibrary(ctx.project.segments[0].id);await click('.picker-cancel');await pending;assert(JSON.stringify(await read())===JSON.stringify(before),'picker cancel saved video');assert(workspace.session.dirty,'picker cancel lost draft');
  pending=ctx.useLibrary(ctx.project.segments[0].id);await click('[data-pick="'+aid+'"]');await click('#use-check');await wait(()=>!document.querySelector('#use-apply').disabled);await click('#use-cancel');await pending;
  assert(JSON.stringify(await read())===JSON.stringify(before),'preview cancel saved video');assert(!(await lib()).used,'preview marked asset used');
  pending=ctx.useLibrary(ctx.project.segments[0].id);await click('[data-pick="'+aid+'"]');await click('#use-check');await wait(()=>!document.querySelector('#use-apply').disabled);await click('#use-apply');await pending;
  let saved=await read();assert(saved.segments[0].prompt==='未保存视频正文','atomic import lost prompt');assert(saved.segments[0].assets.length===1,'import missing');
  const id=saved.segments[0].assets[0],sid=saved.segments[0].id;
  pending=ctx.editAsset(sid,id);await wait(()=>document.querySelector('[data-reference-apply]'));input('[data-reference-purpose]','palette');await click('[data-reference-cancel]');await pending;assert(!workspace.session.dirty,'edit cancel dirtied video');
  pending=ctx.editAsset(sid,id);await wait(()=>document.querySelector('[data-reference-apply]'));input('[data-reference-purpose]','costume');input('[data-reference-subject]','2');await click('[data-reference-apply]');await pending;await workspace.session.save(async()=>true);
  const changed=ctx.project.asset_library.find(a=>a.id===ctx.project.segments[0].assets[0]);assert(changed.purpose==='costume'&&changed.subject==='2','video edit metadata lost');
  const removing=ctx.removeAsset(sid,changed.id);if(document.querySelector('#dialog').open)await click('#yes');await removing;await workspace.session.save(async()=>true);assert((await read()).segments[0].assets.length===0,'video reference not removed');
 }
 // Local files use the same purpose confirmation, with no upload on cancellation.
 const file=new File([await nativeFetch('/fixture-image.png').then(r=>r.blob())],'local-costume.png',{type:'image/png'});
 const fileEvent=selector=>{const node=root.querySelector(selector),transfer=new DataTransfer();transfer.items.add(file);node.files=transfer.files;node.dispatchEvent(new Event('change',{bubbles:true}));};
 if(mode==='video_assembly'){
  const before=await read(),count=writes;
  fileEvent('[data-reference-file="image"]');await wait(()=>document.querySelector('#dialog').open);await click('[data-reference-cancel]');assert(writes===count,'local reference cancel uploaded');
  fileEvent('[data-reference-file="image"]');await wait(()=>document.querySelector('#dialog').open);input('[data-reference-purpose]','scene');await click('[data-reference-apply]');await wait(()=>root.querySelector('[data-reference-edit]')&&!workspace.session.working);
  assert((await read()).assembly.clips[0].extensions[0].references[0].purpose==='scene','local assembly purpose missing');
 }else if(mode==='image_assets'){
  fileEvent('[data-upload="A"]');await wait(()=>!workspace.session.actionPending&&workspace.session.project.tasks[0].A);await workspace.session.save();assert((await read()).tasks[0].A,'local image not saved');
  await click('[data-tool="dual"]');await wait(()=>!workspace.session.actionPending&&root.querySelector('[data-library="B"]'));const sourceA=workspace.session.project.tasks[0].A;
  await click('[data-library="B"]');await click('[data-pick="'+aid+'"]');await wait(()=>!workspace.session.actionPending&&root.querySelector('[data-remove-input="B"]'));
  await click('[data-remove-input="B"]');await click('#yes');await wait(()=>!workspace.session.actionPending);await workspace.session.save();
  const current=(await read()).tasks[0];assert(current.A===sourceA&&current.B===null,'removing B changed A');
 }else{
  const ctx=workspace.ctx,element={files:[file],dataset:{upload:'image',segment:ctx.project.segments[0].id},value:'fixture'},count=writes;
  let adding=ctx.uploadAssets(element);await wait(()=>document.querySelector('#dialog').open);await click('[data-reference-cancel]');await adding;assert(writes===count,'local video reference cancel uploaded');
  adding=ctx.uploadAssets(element);await wait(()=>document.querySelector('#dialog').open);input('[data-reference-purpose]',mode==='swap'?'character':'scene');await click('[data-reference-apply]');await adding;await workspace.session.save(async()=>true);assert((await read()).segments[0].assets.length===1,'local video reference missing');
 }
 const asset=await lib();assert(!asset.deleted&&asset.references.some(r=>r.project===pid),'removal lost library or historical usage');
 assert(JSON.stringify((await read()).settings||{})===JSON.stringify(initial.settings||{})||mode==='text_story','unexpected settings change');
 assert(document.documentElement.scrollWidth<=innerWidth+1,'horizontal overflow');await document.fonts.ready;
 clearTimeout(watchdog);document.body.dataset.check=JSON.stringify({passed:true,mode,width:innerWidth,checks:['picker cancellation','metadata/removal cancellation','real API library/local add/save/remove','prompt preservation','fixed asset and usage retained','no overflow']});
}catch(e){clearTimeout(watchdog);document.body.dataset.check=JSON.stringify({passed:false,error:e.message,stack:e.stack})}
</script>'''

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--evidence-dir',required=True);args=parser.parse_args();out=Path(args.evidence_dir);out.mkdir(parents=True,exist_ok=True);checks=[]
 AssemblyTests.setUpClass()
 try:
  for mode in ['swap','image_story','text_story','image_assets','video_assembly']:
   for width in [1280,760]:
    case=AssemblyTests();case.setUp()
    try:
     image=case.root/'costume.png';Image.new('RGB',(96,128),'green').save(image);asset=case.s.lib.ingest(image,'隔离服装',{'categories':['character']})
     if mode=='video_assembly':case.extension();pid=case.pid
     else:
      p=case.c.post('/api/v5/projects',json=dict(mode=mode,name='素材流程隔离检查')).get_json();pid=p['id']
      if mode=='swap':
       def seed(q):
        q['settings']=defaults('official_swap');q['source_ready']=True;q['segments']=[case.st.new_segment(dict(index=0,raw=124,head=0,deliver=124,tail=0,start=0,duration=124/24,boundary='new_scene'))]
       case.st.store.mutate(pid,seed)
     page='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/studio/style.css"><main id="root"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div>'+SCRIPT
     def app(environ,start_response):
      if environ.get('PATH_INFO')=='/lifecycle-check':start_response('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [page.encode()]
      if environ.get('PATH_INFO')=='/fixture-image.png':start_response('200 OK',[('Content-Type','image/png')]);return [image.read_bytes()]
      return case.app(environ,start_response)
     class Quiet(WSGIRequestHandler):
      def log(self,*args,**kwargs):pass
     server=make_server('127.0.0.1',0,app,threaded=True,request_handler=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start()
     try:checks.append(capture(out,mode+'-'+str(width),f'http://127.0.0.1:{server.server_port}/lifecycle-check?mode={mode}&pid={pid}&aid={asset["id"]}',width))
     finally:server.shutdown();server.server_close()
    finally:case.doCleanups()
 finally:AssemblyTests.tearDownClass()
 (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
 if not all(c['passed'] for c in checks):raise SystemExit(1)

if __name__=='__main__':main()
