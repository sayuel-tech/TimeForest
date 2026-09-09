"""Shared results in five actual UI adapters; synthetic media, isolated APIs, no generation."""
import argparse, copy, json, sys, threading
from pathlib import Path
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from wsgiref.simple_server import make_server, WSGIRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.image_parameter_ui_fixture import Handler, RealImageFixture
from tests.workspace_navigation_ui_fixture import capture
from tests.test_video_assembly_track import TrackTests
from h3ui.studio_records import image_visibility

SCRIPT=r'''<script type="module">
const pause=()=>new Promise(r=>setTimeout(r,40)),assert=(v,m)=>{if(!v)throw Error(m)};
const wait=async fn=>{for(let i=0;i<400;i++){if(await fn())return;await pause()}throw Error('UI wait: '+fn)};
const click=async s=>{await wait(()=>document.querySelector(s)&&!document.querySelector(s).disabled);document.querySelector(s).click();await pause()};
const q=new URLSearchParams(location.search),assembly=q.has('assembly'),pid=assembly?q.get('pid'):location.hash.split('/p/')[1];
const get=()=>fetch('/api/v5/projects/'+pid).then(r=>r.json());
const selected=p=>assembly?p.assembly.clips[0].extensions[0].selected:p.kind==='image'?p.outputs.find(o=>o.selected)?.id:p.segments[0].selected;
let workspace;
try{
 const initial=await get(),image=initial.kind==='image';
 if(assembly){const {mountWorkspace}=await import('/static/studio/modes/video-assembly/workspace.js');workspace=mountWorkspace(document.querySelector('#root'),initial,await fetch('/api/v5/assembly/catalog').then(r=>r.json()))}
 await wait(()=>document.querySelector('[data-workspace-step]'));
 await click('[data-workspace-step="'+(assembly?'1':image?'results':'review')+'"]');
 if(assembly)await click('[data-extension]');
 if(!image&&!assembly)await click('[data-property-tab="runs"]');
 let target,remove,restore,ingest;
 if(image){
   const outputs=(await get()).outputs;target=outputs[0].id;
   await click('[data-output="'+target+'"]');
   assert(!selected(await get()),'viewing selected an image');
   assert(document.querySelector('[data-output="'+target+'"] .candidate-state').textContent.includes('正在查看'),'view marker missing');
   ingest='#image-quick-ingest';remove='[data-record-remove="'+outputs[0].run+'"]';restore='[data-record-restore="'+outputs[0].run+'"]';
 }else if(assembly){
   target='result-a';await click('[data-run-view="'+target+'"]');
   assert(!selected(await get()),'viewing selected continuation');
   ingest='[data-ingest="'+target+'"]';remove='[data-remove-run="'+target+'"]';restore='[data-restore-run="'+target+'"]';
 }else{
   target='candidate-a';document.querySelector('.attempt').open=true;
   assert(selected(await get())===initial.segments[0].selected,'opening history changed selected');
   assert(document.querySelector('.attempt [data-select-attempt]').textContent==='选用并合成','hidden final auto-export meaning');
   ingest='[data-publish-candidate="'+target+'"]';remove='[data-record-remove="'+target+'"]';restore='[data-record-restore="'+target+'"]';
 }
 const currentStep=()=>document.querySelector('[data-workspace-step][aria-current="step"]').dataset.workspaceStep;
 const step=currentStep(),beforeSelected=selected(await get());
 if(!image){
   const box=assembly?document.querySelector('[data-media-player]'):document.querySelector('.attempt [data-media-player]');
   const video=box.querySelector('video');video.muted=true;await wait(()=>video.readyState>=1);
   box.querySelector('[data-media-play]').click();await wait(()=>!video.paused);box.querySelector('[data-media-play]').click();await wait(()=>video.paused);
   const seek=box.querySelector('[data-media-seek]');seek.value='.5';seek.dispatchEvent(new Event('input',{bubbles:true}));await wait(()=>Math.abs(video.currentTime-.5)<.15);
   await wait(()=>box.querySelector('[data-media-status]').textContent.includes('暂停'));
   // A missing-media response uses the common retry control, without changing the selected result.
   video.src='/missing-fixture.mp4';video.load();await wait(()=>!box.querySelector('[data-media-retry]').hidden);
   assert(selected(await get())===beforeSelected,'playback failure changed selection');
   video.src='/fixture-video.mp4';box.querySelector('[data-media-retry]').click();await wait(()=>video.readyState>=1&&!video.paused);video.pause();
   if(assembly){await click('[data-play-tail]');const main=document.querySelector('[data-media-player] video');await wait(()=>!main.paused);assert([...document.querySelectorAll('.assembly-thumb')].filter(v=>v.tagName==='VIDEO').every(v=>v.paused),'tail action played rail thumbnail');main.pause()}
 }
 await click(ingest);
 if(!image&&!assembly){
   await wait(()=>document.querySelector('#save-library-result'));
   await click('#save-library-result button.primary');
   await wait(()=>document.querySelector('#save-library-status a'));
   await click('#save-library-close');
 }
 await wait(()=>document.querySelector('.result-collect a[href^="#/assets/"]'));
 assert(selected(await get())===beforeSelected&&currentStep()===step,'collection changed selection/step');
 if(!image&&!assembly)document.querySelector('.attempt').open=true;
 await click(remove);await click('#yes');await wait(()=>document.querySelector(restore));
 const history=document.querySelector('.removed-records');history.open=true;
 assert(history.textContent.includes('回收站'),'restore location missing');await click(restore);await click('#yes');
 await wait(()=>!document.querySelector(restore));
 assert(selected(await get())===beforeSelected,'restore implicitly selected');
 if(assembly){
   await click('[data-run-view="result-a"]');await click('[data-select="result-a"]');
   await wait(()=>document.querySelectorAll('[data-track]').length===2);
   await click('[data-run-view="result-b"]');assert(selected(await get())==='result-a','viewing replaced track');
   await click('[data-select="result-b"]');await wait(async()=>selected(await get())==='result-b');
   assert(document.querySelectorAll('[data-track]').length===2,'replacement duplicated track');
 }else if(image){
   await click('[data-output="'+target+'"]');await click('#image-select');await wait(async()=>selected(await get())===target);
   await click('[data-workspace-step="results"]');
   const other=(await get()).outputs.find(o=>o.id!==target);await click('[data-output="'+other.id+'"]');
   assert(selected(await get())===target,'viewing changed selected image');
 }else{
   document.querySelector('.attempt').open=true;await click('[data-select-attempt="candidate-a"]');
   assert(document.querySelector('#dialog').textContent.includes('自动合成'),'selection confirmation hides export');
   await click('#no');assert(selected(await get())===beforeSelected,'cancelled selection changed project');
   await click('#reroll');assert(document.querySelector('#dialog').textContent.includes('旧候选'),'reroll fails to explain history');await click('#no');
 }
 if(assembly)assert((await get()).assembly.runs.filter(r=>r.kind!=='import').length===2,'generated unexpectedly');
 else {const state=await fetch('/__fixture/state').then(r=>r.json());assert(state.generation_requests===0&&!state.engine_attempts?.length,'generation called')}
 await wait(()=>!document.querySelector('#toast.show'));await document.fonts.ready;
 assert(document.documentElement.scrollWidth<=innerWidth+1,'horizontal overflow');
 const actions=document.querySelector('.result-actions');assert(actions?.querySelector('.result-collect'),'collection grouping missing');
 if(!image&&!assembly){document.querySelector('.attempt').open=true;document.querySelector('.attempt').scrollIntoView({block:'start'})}
 else document.querySelector('.result-actions').scrollIntoView({block:'end'});
 await new Promise(r=>setTimeout(r,300));
 document.body.dataset.check=JSON.stringify({passed:true,mode:assembly?'video_assembly':initial.mode,width:innerWidth,checks:['view vs select','collect keeps step and selection','remove/restore',...(image?['image selection']:['playback/pause/seek/error/retry']),...(assembly?['assembly replacement slot']:image?[]:['original confirmation semantics'])]});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.message,stack:e.stack})}
</script>'''

class ResultFixture(RealImageFixture):
    def reset(self):
        super().reset();self.collected=set()
    def seed_results(self):
        for p in self.projects.values():
            if p.get('kind')=='image':continue
            p['segments'][0].update(status='needs_review',selected='candidate-b',delivery_url='/fixture-video.mp4',attempts=[dict(id='candidate-'+x,status='complete',seed=i,created=1,delivery_url='/fixture-video.mp4',directory='fixture') for i,x in enumerate(['a','b'])])
        outputs=self.image_service.store.all('outputs',self.pid)
        second=outputs[1];run=copy.deepcopy(self.image_service.store.get('runs',second['run'],self.pid));run['id']='separate-result-run';self.image_service.store.put('runs',run);second['run']=run['id'];self.image_service.store.put('outputs',second)

    def request(self,method,path,body):
        parts=path.strip('/').split('/')
        if path.startswith('/api/v5/library/projects/') and path.endswith('/outputs'):
            pid=parts[4];return 200,dict(result_receipts_version=1,items=[dict(id='token-'+a['id'],kind='candidate',result_id=a['id'],name=a['id'],**(dict(asset='fixture-collected') if 'token-'+a['id'] in self.collected else {})) for a in self.projects[pid]['segments'][0]['attempts'] if not a.get('removed_at')])
        if path=='/api/v5/library/catalog':return 200,dict(categories=[dict(id='video',name='视频')])
        if path=='/api/v5/library/project-results':
            self.collected.add(body['output']);return 200,dict(id='fixture-task',state='done',note='受控入库确认',result=dict(id='fixture-collected'))
        if path.endswith('/records/visibility'):
            pid=parts[3]
            if pid==self.pid:return 200,image_visibility(self.image_service,pid,body)
            p=self.projects[pid];a=next(a for a in p['segments'][0]['attempts'] if a['id']==body['record']);a['removed_at']=1 if body['removed'] else None;p['revision']+=1;return 200,dict(ok=True)
        return super().request(method,path,body)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence-dir',required=True);parser.add_argument('--only',choices=['original','assembly']);parser.add_argument('--modes',default='swap,image_story,text_story,image_assets');args=parser.parse_args();out=Path(args.evidence_dir);out.mkdir(parents=True,exist_ok=True);checks=[]
    TrackTests.setUpClass()
    try:
        if args.only!='assembly':
            class Checked(Handler):
                def send(self,status,body,content_type='application/json; charset=utf-8'):
                    if self.path.startswith('/?') and content_type.startswith('text/html'):body=body.replace(b'</body>',SCRIPT.encode()+b'</body>')
                    super().send(status,body,content_type)
                def do_GET(self):
                    if self.path=='/fixture-video.mp4':
                        data=TrackTests.sound.read_bytes();start=0;end=len(data)-1;partial=self.headers.get('Range')
                        if partial:
                            low,high=partial.removeprefix('bytes=').split('-',1);start=int(low or 0);end=min(int(high) if high else end,end)
                        self.send_response(206 if partial else 200);self.send_header('Content-Type','video/mp4');self.send_header('Accept-Ranges','bytes');self.send_header('Content-Length',str(end-start+1))
                        if partial:self.send_header('Content-Range',f'bytes {start}-{end}/{len(data)}')
                        self.end_headers();self.wfile.write(data[start:end+1]);return
                    super().do_GET()
            fixture=ResultFixture(out);server=ThreadingHTTPServer(('127.0.0.1',0),Checked);server.fixture=fixture;threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                for mode in ['swap','image_story','text_story','image_assets']:
                    if mode not in args.modes.split(','):continue
                    for width in [1280,760]:
                        fixture.reset();fixture.seed_results();pid=next(k for k,p in fixture.projects.items() if p['mode']==mode)
                        checks.append(capture(out,mode+'-'+str(width),f'http://127.0.0.1:{server.server_port}/?check=1#/p/{pid}',width))
            finally:server.shutdown();server.server_close();fixture.close()
        if args.only!='original':
            for width in [1280,760]:
                case=TrackTests();case.setUp();e=case.extension();case.candidate(e['id'],'result-a');case.candidate(e['id'],'result-b')
                page='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/studio/style.css"><main id="root"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div>'+SCRIPT
                def app(environ,start_response):
                    path=environ.get('PATH_INFO')
                    if path=='/result-check':start_response('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [page.encode()]
                    if path=='/fixture-video.mp4':start_response('200 OK',[('Content-Type','video/mp4')]);return [case.sound.read_bytes()]
                    return case.app(environ,start_response)
                class Quiet(WSGIRequestHandler):
                    def log_message(self,*args):pass
                server=make_server('127.0.0.1',0,app,handler_class=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start()
                try:checks.append(capture(out,'video_assembly-'+str(width),f'http://127.0.0.1:{server.server_port}/result-check?assembly=1&pid={case.pid}',width))
                finally:server.shutdown();server.server_close();case.doCleanups()
    finally:
        TrackTests.tearDownClass();(out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)

if __name__=='__main__':main()
