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
   await click('[data-adopt]');await wait(settled);
   if(q.has('q3')){
     const adopted=(await get()).movie_takes.find(t=>t.currently_adopted).take_id;
     await click('[data-generate]');await wait(settled);await wait(async()=> (await get()).movie_takes.length===2);workspace.session.receive(await get());
     const second=(await get()).movie_takes.find(t=>t.take_id!==adopted).take_id,before=(await get()).revision;
     await click('[data-run-view="'+second+'"]');
     assert((await get()).revision===before,'view wrote project');assert((await get()).movie_takes.find(t=>t.currently_adopted).take_id===adopted,'view changed adoption');
     assert(root.querySelector('.movie-viewing-heading').textContent.includes('查看不会替换'),'view/adoption distinction missing');
     await click('[data-ingest]');await wait(settled);assert(!workspace.ctx.error,workspace.ctx.error?.message);
     const collected=await get();assert(collected.movie_takes.find(t=>t.take_id===second).library_asset,'ingest receipt absent');assert(collected.movie_takes.find(t=>t.currently_adopted).take_id===adopted,'ingest implicitly adopted');
     await click('[data-adopt]');await wait(settled);assert((await get()).movie_takes.find(t=>t.currently_adopted).take_id===second,'explicit adoption failed');
     await click('[data-run-view="'+adopted+'"]');assert(root.querySelector('.movie-viewing-heading').textContent.includes('当前采用候选 2'),'adopted identity stale');
     const player=root.querySelector('.desk-canvas > .media-player');assert(player.getBoundingClientRect().height>=160,'primary player collapsed');assert(root.querySelector('.candidate-tile').getBoundingClientRect().width<=200,'candidate tile dominates primary player');
   }else{
   if(q.has('edit')){
     const second=(await get()).content.segment_order[1];workspace.ctx.selected=second;
     await click('[data-generate]');await wait(settled);await wait(async()=> (await get()).movie_takes.some(t=>t.movie_segment_id===second));workspace.session.receive(await get());
     await click('[data-adopt]');await wait(settled);
   }
   await click('[data-edit-next]');await click('[data-initialize]');await wait(settled);assert(root.querySelector('.movie-track-item'),'no timeline');
   if(q.has('edit')){
     const order=(await get()).content.edit.order;assert(order.length===2,'two clips not imported');
     assert(root.querySelector('[data-move="-1"]').disabled,'first clip can move before beginning');
     await click('[data-move="1"]');assert(workspace.ctx.selectedItem===order[0],'move changed selected identity');
     assert(root.querySelector('.movie-item-heading').textContent.includes('轨道 2'),'track position stale');
     await click('[data-save]');await wait(settled);assert((await get()).content.edit.order[1]===order[0],'order not persisted');
     await click('[data-move="-1"]');await click('[data-save]');await wait(settled);
   }
   if(root.querySelector('.timecode-display')){const video=root.querySelector('.media-player video');await wait(()=>video.readyState>0);video.currentTime=.75;await wait(()=>Math.abs(video.currentTime-.75)<.05);await click('[data-playhead=in_ms]');assert(Number(root.querySelector('[data-range=in_ms]').value)===750,'playhead read the wrong video');input('.timecode-display','00:bad');await click('[data-save]');await wait(settled);assert(workspace.ctx.error,'invalid time accepted');assert(root.querySelector('.timecode-display').value==='00:bad','invalid time draft lost after save failure');input('.timecode-display','00:00.500');}
   input('[data-range="in_ms"]',500);input('[data-range="out_ms"]',4000);await click('[data-save]');await wait(settled);assert((await get()).content.edit.items[0].range.in_ms===500,'edit range not saved');
   assert(root.querySelector('[data-return-generation]'),'generation return missing');const returnShot=new URLSearchParams(root.querySelector('a[href*="step=3"]').getAttribute('href').split('?')[1]).get('target');assert(returnShot===(await get()).content.source_bundles.at(-1).shot_id,'return link points to clip instead of parent shot');
   await click('[data-preview-edit]');await wait(()=>document.querySelector('[data-preview-label]'));assert(document.querySelector('dialog[open] video'),'preview missing native player');await click('dialog[open] [data-close]');await wait(settled);
   const source=root.querySelector('a[href*="step=3"]');source.click();const back=readReturnContext(new URLSearchParams(location.hash.split('?')[1]));assert(back,'actual project identity rejected');assert(back.origin_item_id===(await get()).content.edit.order[0],'source return lost item');assert(back.origin_page==='editing','source return lost page');assert(returnHref(back).startsWith('#/p/'+pid+'?step=1&'),'return route lost project/page');
   }
 }
 const action=root.querySelector('[data-export]')||root.querySelector('[data-next]')||root.querySelector('[data-edit-next]');if(innerWidth<=850){action.scrollIntoView({block:'center',behavior:'instant'});}const rect=action.getBoundingClientRect();assert(rect.width>0&&rect.top>=0&&rect.bottom<=innerHeight+2,'primary action not reachable '+JSON.stringify({top:rect.top,bottom:rect.bottom,scrollY,height:innerHeight}));assert(rect.left>=0&&rect.right<=innerWidth,'primary action clipped horizontally');
 root.querySelector('.desk-canvas').scrollTop=0;if(innerWidth>=1200&&innerHeight>=768&&root.querySelector('.timecode-display'))assert([...root.querySelectorAll('.timecode-display')].every(e=>e.getBoundingClientRect().bottom<=root.querySelector('.savebar').getBoundingClientRect().top),'range controls below first viewport');workspace.dispose();window.scrollTo({top:0,left:0,behavior:'instant'});await pause();document.body.dataset.check=JSON.stringify({passed:true});
}catch(error){workspace?.dispose();document.body.dataset.check=JSON.stringify({passed:false,error:error.stack});}
</script>'''

class Quiet(WSGIRequestHandler):
    def log_message(self,*args):pass

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);parser.add_argument('--width',type=int,default=1440);parser.add_argument('--r1',action='store_true');parser.add_argument('--q3',action='store_true');parser.add_argument('--edit',action='store_true');parser.add_argument('--height',type=int);args=parser.parse_args();out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    case=MovieTests();case.setUp();case.setup_movie()
    if args.edit:
        shot=case.service.layer(case.p,'storyboard',[])['content']['shots'][0]['ref']
        original=case.service.layer(case.p,'segment',[])['content']['segments']
        second=case.save('segment',dict(segments=original+[dict(ref='tmp:second',shot_ref=shot,text='列车驶入站台',planned_seconds=5,dependency=dict(kind='independent'))]))['id_map']['tmp:second']
        case.save('prompt',dict(prompt_mode='full',profile_id='movie.independent.dance_split',payload=dict(prompt_text='A train arrives.',used_reference_keys=[])),[second])
        row=case.service.layer(case.p,'prompt',[second])
        case.post('/authoring/projects/'+case.p['id']+'/confirm',dict(revision=case.p['revision'],layer='prompt',target_ids=[second],content_hashes=dict(prompt=row['content_hash'])))
        case.p=case.service.snapshot(case.p['id'])
        case.movie=case.post('/movie/projects',dict(title='剪辑顺序检查',source_project_id=case.p['id'],source_revision=case.p['revision'],segment_ids=[]))
    if args.r1:
        from h3ui.video_assembly import media
        sample=case.root/'uiux-playable.mp4'
        media.command(['ffmpeg','-nostdin','-y','-v','error','-loop','1','-i',Path('static/assets/movie/empty-edit.webp').resolve(),'-t','5','-vf','scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2','-r','24','-c:v','libx264','-pix_fmt','yuv420p',sample])
        def fake_playable(project,record,directory,event,progress):
            import shutil
            target=directory/'fixture.mp4';shutil.copy2(sample,target)
            return str(target),dict(duration=5,width=640,height=360,audio=False)
        case.service.movie.execution.backend=fake_playable
    page=PAGE
    if args.r1:
        from tests.uiux_r1_shell import application_shell
        page=application_shell(page)
    def app(environ,start):
        if environ['PATH_INFO']=='/creation-fixture':start('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [page.encode()]
        return case.app(environ,start)
    server=make_server('127.0.0.1',0,app,handler_class=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start();checks=[]
    try:
        for mode,pid in [('authoring',case.p['id']),('movie',case.movie['id'])]:
            if (args.q3 or args.edit) and mode=='authoring':continue
            if mode=='authoring':
                p=case.service.create('authoring',dict(title='UI 隔离剧本',request_key='ui-create'));pid=p['id']
            url=f'http://127.0.0.1:{server.server_port}/creation-fixture?pid={pid}'+('&q3=1' if args.q3 else '')+('&edit=1' if args.edit else '')
            if args.r1:
                command=[sys.executable,str(Path(__file__).with_name('uiux_browser_capture.py')),url,str(out/(mode+'.png')),str(args.width),str(args.height or (960 if args.width==1440 else 900))]
            else:
                command=['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--no-first-run','--disable-background-networking',f'--user-data-dir={out/("profile-"+mode)}',f'--window-size={args.width},1000','--virtual-time-budget=20000',f'--screenshot={out/(mode+".png")}','--dump-dom',url]
            result=subprocess.run(command,capture_output=True,timeout=60)
            dom=result.stdout.decode('utf-8','replace');(out/(mode+'.html')).write_text(dom,encoding='utf-8');match=re.search(r'data-check="([^"]+)"',dom)
            data=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='No browser completion marker')
            checks.append(dict(mode=mode,**data));print(json.dumps(checks[-1],ensure_ascii=False),flush=True)
    finally:
        server.shutdown();server.server_close();case.doCleanups();(out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)

if __name__=='__main__':main()
