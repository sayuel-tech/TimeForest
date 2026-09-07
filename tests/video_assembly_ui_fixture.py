"""Headless real-browser checks against real APIs and temporary synthetic media.

Uses existing Chrome and the project Python, no engine, production configuration,
or user assets. Write evidence only to the explicitly supplied directory.
"""
import argparse
import html
import json
import re
import subprocess
import sys
import threading
from pathlib import Path
from wsgiref.simple_server import make_server, WSGIRequestHandler
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_video_assembly import AssemblyTests

PAGE=r'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="/static/studio/style.css"><main id="root"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div>
<script type="module">
import {mountWorkspace} from '/static/studio/modes/video-assembly/workspace.js';
const q=new URLSearchParams(location.search),pid=q.get('pid'),root=document.querySelector('#root');
const pause=()=>new Promise(r=>setTimeout(r,40));
const assert=(v,m)=>{if(!v)throw Error(m);};
async function wait(check){for(let i=0;i<350;i++){if(await check())return;await pause();}throw Error('Browser wait timed out');}
const get=()=>fetch('/api/v5/projects/'+pid).then(r=>r.json());
const click=async selector=>{const el=document.querySelector(selector);assert(el,'Missing '+selector);assert(!el.disabled,'Disabled '+selector);el.click();await pause();};
const input=(selector,value)=>{const el=document.querySelector(selector);assert(el,'Missing '+selector);el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};
let workspace;
try{
 const p=await get(),catalog=await fetch('/api/v5/assembly/catalog').then(r=>r.json());workspace=mountWorkspace(root,p,catalog);
 const settled=()=>!workspace.session.working;
 const direct=root.querySelector('[data-direct]'),next=root.querySelector('[data-next]');
 assert(direct.parentElement===next.parentElement&&direct.nextElementSibling===next,'primary action order');
 assert(root.querySelector('#property-import [data-library]')&&root.querySelector('#property-import [data-import]'),'import choices not together');
 if(innerWidth>900)assert(next.getBoundingClientRect().right>direct.getBoundingClientRect().right,'next must be rightmost');
 if(q.has('references')){
  await click('[data-step="1"]');await click('[data-add-extension]');await wait(()=>settled()&&root.querySelector('[data-reference-file]'));
  assert(root.querySelector('[data-property-tab="assets"]').getAttribute('aria-selected')==='true','new extension does not open assets');
  const canvas=document.createElement('canvas');canvas.width=32;canvas.height=48;canvas.getContext('2d').fillRect(0,0,32,48);
  const blob=await new Promise(resolve=>canvas.toBlob(resolve));const transfer=new DataTransfer();transfer.items.add(new File([blob],'测试角色.png',{type:'image/png'}));
  let inputFile=root.querySelector('[data-reference-file="image"]');inputFile.files=transfer.files;inputFile.dispatchEvent(new Event('change',{bubbles:true}));
  await wait(()=>settled()&&root.querySelector('[data-reference-purpose]'));
  input('[data-reference-purpose]','costume');input('[data-reference-subject]','2');input('[data-prompt]','<Picture 1>服装参考，继续向前行走');
  await click('[data-save]');await wait(settled);let saved=await get(),first=saved.assembly.clips[0].extensions[0];
  assert(first.references[0].purpose==='costume'&&first.references[0].subject==='2','reference draft not saved');
  let preflight=await fetch('/api/v5/assembly/'+pid+'/preflight/'+first.id).then(r=>r.json());assert(preflight.input_inventory[0].tag==='<Picture 1>','reference not bound');
  await click('#settings');await click('[data-settings-section="assets"]');input('[data-param="reference_size"]','max');await click('dialog [data-save]');await wait(()=>!document.querySelector('#dialog').open);
  assert((await get()).assembly.clips[0].extensions[0].configurations.dance_split.reference_size==='max','reference precision not saved');
  await click('[data-add-extension]');await wait(settled);await click('[data-reference-inherit]');await click('[data-save]');await wait(settled);
  assert((await get()).assembly.clips[0].extensions[1].references[0].id===first.references[0].id,'explicit inheritance failed');
  await click('[data-reference-remove]');await click('[data-save]');await wait(settled);
  assert((await get()).assembly.clips[0].extensions[1].references.length===0,'reference removal not saved');
  await click('[data-extension="'+first.id+'"]');
 }

 if(q.has('flow')){
  await click('[data-move="1"]');await wait(settled);await click('[data-save]');await wait(settled);assert((await get()).assembly.track_order[0]==='clip:'+p.assembly.clips[1].id,'track order not saved');
  await click('[data-step="1"]');await click('[data-add-extension]');await wait(()=>settled()&&root.querySelector('[data-prompt]'));
  input('[data-prompt]','继续缓慢向前，保留环境声音');await click('#settings');
  await click('[data-settings-section="sampling"]');input('[data-param="steps"]',16);document.querySelector('[data-refresh]').click();await click('[data-cancel]');
  await click('#settings');await get();await pause();await click('[data-settings-section="sampling"]');assert(Number(document.querySelector('[data-param="steps"]').value)===12,'cancel changed values');
  input('[data-param="steps"]',16);await click('[data-settings-section="core"]');input('[data-recipe]','official_image');
  await click('[data-settings-section="sampling"]');input('[data-param="steps"]',24);
  await click('[data-settings-section="core"]');input('[data-recipe]','dance_split');await click('[data-settings-section="sampling"]');assert(Number(document.querySelector('[data-param="steps"]').value)===16,'recipe draft lost');
  await click('[data-reset]');assert(Number(document.querySelector('[data-param="steps"]').value)===12,'reset failed');input('[data-param="steps"]',16);
  input('[data-seed-mode]','fixed');input('[data-seed]','0');await click('[data-refresh]');await wait(()=>!document.querySelector('[data-refresh]').disabled);assert(Number(document.querySelector('[data-param="steps"]').value)===16,'refresh reset values');
  await click('dialog [data-save]');await wait(()=>!document.querySelector('#dialog').open);
  let saved=await get(),e=saved.assembly.clips.flatMap(c=>c.extensions)[0];assert(e.prompt.includes('环境声音')&&e.seed==='0'&&e.seed_mode==='fixed','saved binding mismatch');assert(e.configurations.dance_split.steps===16&&e.configurations.official_image.steps===24,'recipe save mismatch');
  await click('[data-preflight]');await wait(settled);assert(!root.querySelector('.error-feedback'),'preflight failed');
  await click('[data-remove-extension]');await wait(()=>document.querySelector('#dialog').open);document.querySelector('#dialog .primary').click();await wait(()=>settled()&&!root.querySelector('[data-prompt]'));
  await click('[data-step="2"]');await click('[data-export]');await wait(settled);await wait(async()=>(await get()).assembly.runs.some(r=>r.kind==='export'&&r.state==='success'));await click('[data-reload]');await wait(settled);
  await click('[data-ingest]');await wait(settled);assert(root.textContent.includes('已入库'),'quick ingest failed');
  await click('[data-step="0"]');await click('[data-library]');await wait(()=>document.querySelector('.library-pick-card'));await click('.library-pick-card');await click('.picker-cancel');assert(workspace.session.project.assembly.clips.length===2,'picker cancel changed sequence');
  await click('[data-library]');await wait(()=>document.querySelector('.library-pick-card'));await click('.library-pick-card');await click('.picker-apply');await wait(()=>settled()&&workspace.session.project.assembly.clips.length===3);
 }
 if(q.has('settings')){await click('[data-step="1"]');await click('[data-add-extension]');await wait(settled);await click('#settings');await click('[data-settings-section="picture"]');}
 await document.fonts.ready;if(q.has('settings')){const dialog=document.querySelector('#dialog'),content=document.querySelector('.production-settings');assert(content,'shared dialog root');assert(getComputedStyle(content.querySelector('h2')).fontSize==='27px','shared heading style');assert(dialog.getBoundingClientRect().width>Math.min(1000,innerWidth*.8),'shared width');assert(content.querySelector('.settings-grid'),'shared field grid');}assert(document.documentElement.scrollWidth<=innerWidth+1,'horizontal overflow');
 document.body.dataset.check=JSON.stringify({passed:true,width:innerWidth,documentWidth:document.documentElement.scrollWidth,flow:q.has('flow')});
}catch(error){document.body.dataset.check=JSON.stringify({passed:false,error:error.message,stack:error.stack});}
</script>'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence-dir',required=True);args=parser.parse_args()
    out=Path(args.evidence_dir);out.mkdir(parents=True,exist_ok=True)
    AssemblyTests.setUpClass();case=AssemblyTests();case.setUp();app=case.app;checks=[]
    def fixture_app(environ,start_response):
        if environ.get('PATH_INFO')=='/assembly-check':
            start_response('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [PAGE.encode('utf-8')]
        return app(environ,start_response)
    class Quiet(WSGIRequestHandler):
        def log_message(self,*args):pass
    server=make_server('127.0.0.1',0,fixture_app,handler_class=Quiet)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        for name,width,height,query in [('wide',1280,720,''),('narrow',760,1000,''),('settings',760,1000,'&settings=1'),('settings-wide',1280,720,'&settings=1'),('settings-large',1920,1080,'&settings=1'),('references',1280,900,'&references=1'),('flow',1280,900,'&flow=1')]:
            case.p=case.s.create('视频拼接 · 隔离界面');case.pid=case.p['id'];case.refresh();case.upload();case.upload(case.sound)
            result=subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--no-first-run','--disable-background-networking',
                f'--user-data-dir={out/("profile-"+name)}',f'--window-size={width},{height}','--virtual-time-budget=25000',f'--screenshot={out/(name+".png")}',
                '--dump-dom',f'http://127.0.0.1:{server.server_port}/assembly-check?pid={case.pid}'+query],capture_output=True,timeout=50)
            dom=result.stdout.decode('utf-8','replace');(out/(name+'.html')).write_text(dom,encoding='utf-8')
            match=re.search(r'data-check="([^"]+)"',dom);data=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='No completion marker')
            checks.append(dict(case=name,**data));print(json.dumps(checks[-1],ensure_ascii=False),flush=True)
    finally:
        server.shutdown();server.server_close();case.doCleanups();AssemblyTests.tearDownClass()
        (out/'browser-checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)


if __name__=='__main__':main()
