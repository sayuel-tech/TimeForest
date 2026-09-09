"""Real ES modules + Flask + temporary projects, with fake model/media ends."""
import argparse
import html
import json
import re
import subprocess
import sys
import threading
from pathlib import Path
from wsgiref.simple_server import make_server,WSGIRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_creation_movie import MovieTests

PAGE=r'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/studio/style.css"><main id="root"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div>
<script type="module">
import {mountWorkspace as script} from '/static/studio/modes/authoring/workspace.js';
import {mountWorkspace as movie} from '/static/studio/modes/movie/workspace.js';
import {readReturnContext,returnHref} from '/static/studio/features/shot-segment-tree/return-context.js';
const q=new URLSearchParams(location.search),pid=q.get('pid'),root=document.querySelector('#root');
const pause=()=>new Promise(r=>setTimeout(r,50)),assert=(v,m)=>{if(!v)throw Error(m);};
const get=()=>fetch('/api/v5/projects/'+pid).then(r=>r.json());
async function wait(check){for(let i=0;i<250;i++){if(await check())return;await pause();}throw Error('Timed out');}
async function click(sel){const el=document.querySelector(sel);assert(el,'Missing '+sel);assert(!el.disabled,'Disabled '+sel);el.click();await pause();}
function input(sel,value){const el=document.querySelector(sel);assert(el,'Missing '+sel);el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));}
let workspace;
try{
 const p=await get();workspace=(p.kind==='authoring'?script:movie)(root,p);const settled=()=>!workspace.session.working&&!workspace.session.actionPending;
 if(p.kind==='authoring'){
   input('[data-text="intent"]','浏览器填写故事开头');await click('[data-save]');await wait(settled);assert((await get()).content.layers.find(r=>r.layer==='intent').content.story_text==='浏览器填写故事开头','intent not saved');
   await click('[data-next]');root.querySelector('[data-text=screenplay]').closest('details').open=true;input('[data-text="screenplay"]','旅人走向车站。');await click('[data-save]');await wait(settled);
   const id=(await get()).content.layers.find(r=>r.layer==='screenplay').content.blocks[0].ref;
   input('[data-text=screenplay]','旅人走向车站。\n列车到站。');await click('[data-save]');await wait(settled);
   assert((await get()).content.layers.find(r=>r.layer==='screenplay').content.blocks[0].ref===id,'block identity changed');
   await click('#authoring-settings');await wait(()=>document.querySelector('[data-config="model_id"]'));assert(document.querySelector('[data-config="model_id"]').value==='deepseek-v4.1-flash-expires-on-0910','model id');input('[data-config="model_id"]','cancelled-model');await click('[data-settings-action="cancel"]');assert(!workspace.session.dirty,'cancel dirtied project');
   const revision=(await get()).revision;input('[data-text="screenplay"]','尚未保存的改写');await click('[data-create-image-task]');await wait(()=>document.querySelector('.choice-dialog[open]'));assert(!document.querySelector('[data-image-prompt]'),'unexpected instruction form');await click('.choice-dialog[open] .dialog-close');await wait(settled);assert((await get()).revision===revision,'cancel handoff saved project');assert(workspace.session.dirty,'cancel handoff lost draft');await click('[data-save]');await wait(settled);
   for(const choice of ['discard','save']){
     const before=await get(),oldText=before.content.layers.find(r=>r.layer==='screenplay').content.blocks[0].text;
     input('[data-text="screenplay"]','补图跳转 '+choice);await click('[data-create-image-task]');await wait(()=>document.querySelector('.choice-dialog[open]'));
     await click('.choice-dialog[open] [data-choice="'+(choice==='save'?1:0)+'"]');await wait(settled);assert(!workspace.ctx.error,workspace.ctx.error?.message);
     const after=await get(),handoff=after.image_handoffs.at(-1);assert(handoff,'missing image link');assert(location.hash==='#/p/'+handoff.image_project_id,'not routed to image workspace');assert(!workspace.session.dirty,'duplicate leave guard');
     assert(after.content.layers.find(r=>r.layer==='screenplay').content.blocks[0].text===(choice==='save'?'补图跳转 save':oldText),'save/discard mismatch');
     const image=await fetch('/api/v5/projects/'+handoff.image_project_id).then(r=>r.json());assert(image.kind==='image'&&image.tasks[0].prompt==='','not a blank image workspace');assert(image.authoring_handoff.script_project_id===pid,'lost script relation');
     workspace.dispose();workspace=script(root,after);await click('[data-next]');await wait(settled);
   }
   root.querySelector('[data-view-key="image-handoffs"]').open=true;
   const links=[...root.querySelectorAll('.image-handoff-item')];assert(links.length===2,'existing handoffs missing');for(const item of links){const a=item.querySelector('a').getBoundingClientRect(),b=item.querySelector('button').getBoundingClientRect();assert(b.top>=a.bottom,'handoff actions overlap');}

 }else{
   await click('#movie-settings');await wait(()=>document.querySelector('[data-param="steps"]'));input('[data-param="steps"]',16);await click('#cancel-settings');assert(!workspace.session.dirty,'settings cancel changed movie');
   await click('[data-preflight]');await wait(settled);assert(!workspace.ctx.error,workspace.ctx.error?.message);
   await click('[data-generate]');await wait(settled);assert(!workspace.ctx.error,workspace.ctx.error?.message);await wait(async()=>{const next=await get();return next.movie_takes?.length>0;});workspace.session.receive(await get());
   await click('[data-adopt]');await wait(settled);await click('[data-edit-next]');await click('[data-initialize]');await wait(settled);assert(root.querySelector('.movie-track-item'),'no timeline');
   input('[data-range="in_ms"]',500);input('[data-range="out_ms"]',4000);await click('[data-save]');await wait(settled);assert((await get()).content.edit.items[0].range.in_ms===500,'edit range not saved');
   assert(root.querySelector('[data-return-generation]'),'generation return missing');const returnShot=new URLSearchParams(root.querySelector('a[href*="step=3"]').getAttribute('href').split('?')[1]).get('target');assert(returnShot===(await get()).content.source_bundles.at(-1).shot_id,'return link points to clip instead of parent shot');
   await click('[data-preview-edit]');await wait(()=>document.querySelector('[data-preview-label]'));assert(document.querySelector('dialog[open] video'),'preview missing native player');await click('dialog[open] [data-close]');await wait(settled);
   const source=root.querySelector('a[href*="step=3"]');source.click();const back=readReturnContext(new URLSearchParams(location.hash.split('?')[1]));assert(back,'actual project identity rejected');assert(back.origin_item_id===(await get()).content.edit.order[0],'source return lost item');assert(back.origin_page==='editing','source return lost page');assert(returnHref(back).startsWith('#/p/'+pid+'?step=1&'),'return route lost project/page');
 }
 const action=root.querySelector('[data-export]')||root.querySelector('[data-next]');if(innerWidth<=850){action.scrollIntoView({block:'center',behavior:'instant'});}const rect=action.getBoundingClientRect();assert(rect.width>0&&rect.top>=0&&rect.bottom<=innerHeight+2,'primary action not reachable '+JSON.stringify({top:rect.top,bottom:rect.bottom,scrollY,height:innerHeight}));assert(rect.left>=0&&rect.right<=innerWidth,'primary action clipped horizontally');
 workspace.dispose();window.scrollTo({top:0,left:0,behavior:'instant'});await pause();document.body.dataset.check=JSON.stringify({passed:true});
}catch(error){workspace?.dispose();document.body.dataset.check=JSON.stringify({passed:false,error:error.stack});}
</script>'''

class Quiet(WSGIRequestHandler):
    def log_message(self,*args):pass

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);parser.add_argument('--width',type=int,default=1440);args=parser.parse_args();out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    case=MovieTests();case.setUp();case.setup_movie()
    def app(environ,start):
        if environ['PATH_INFO']=='/creation-fixture':start('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [PAGE.encode()]
        return case.app(environ,start)
    server=make_server('127.0.0.1',0,app,handler_class=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start();checks=[]
    try:
        for mode,pid in [('authoring',case.p['id']),('movie',case.movie['id'])]:
            if mode=='authoring':
                p=case.service.create('authoring',dict(title='UI 隔离剧本',request_key='ui-create'));pid=p['id']
            result=subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--no-first-run','--disable-background-networking',f'--user-data-dir={out/("profile-"+mode)}',f'--window-size={args.width},1000','--virtual-time-budget=20000',f'--screenshot={out/(mode+".png")}','--dump-dom',f'http://127.0.0.1:{server.server_port}/creation-fixture?pid={pid}'],capture_output=True,timeout=50)
            dom=result.stdout.decode('utf-8','replace');(out/(mode+'.html')).write_text(dom,encoding='utf-8');match=re.search(r'data-check="([^"]+)"',dom)
            data=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='No browser completion marker')
            checks.append(dict(mode=mode,**data));print(json.dumps(checks[-1],ensure_ascii=False),flush=True)
    finally:
        server.shutdown();server.server_close();case.doCleanups();(out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)

if __name__=='__main__':main()
