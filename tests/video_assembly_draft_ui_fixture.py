"""Regression for idle polling followed by authoring and generate click.

Real browser, temporary API/store/compiler; jobs.start is captured, never run.
ComfyClient remains forbidden by AssemblyTests. No production files are read.
"""
import argparse
import html
import json
import re
import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import patch
from wsgiref.simple_server import make_server, WSGIRequestHandler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.test_video_assembly import AssemblyTests

PAGE = r'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="/static/studio/style.css"><main id="root"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div>
<script type="module">
import {mountWorkspace} from '/static/studio/modes/video-assembly/workspace.js';
const query=new URLSearchParams(location.search),pid=query.get('pid'),scenario=query.get('scenario'),root=document.querySelector('#root');
const pause=ms=>new Promise(r=>setTimeout(r,ms||40));
const assert=(v,m)=>{if(!v)throw Error(m)};
async function wait(fn){for(let i=0;i<350;i++){if(await fn())return;await pause()}throw Error('Timed out')}
const nativeFetch=window.fetch.bind(window);let polls=0,workspace,releasePoll;
window.fetch=async(url,options)=>{const r=await nativeFetch(url,options);if(String(url)==='/api/v5/projects/'+pid&&options?.signal){await r.clone().text();polls++;if(polls===1&&scenario?.startsWith('inflight'))await new Promise(resolve=>releasePoll=resolve);}return r;};
const get=()=>nativeFetch('/api/v5/projects/'+pid).then(r=>r.json());
const click=async s=>{const el=document.querySelector(s);assert(el&&!el.disabled,'Unavailable '+s);el.click();await pause()};
const input=(s,v)=>{const el=document.querySelector(s);el.value=v;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};
try{
 const p=await get(),catalog=await nativeFetch('/api/v5/assembly/catalog').then(r=>r.json());workspace=mountWorkspace(root,p,catalog);
 await click('[data-step="1"]');await click('[data-extension]');
 // A normal user reads the imported material before typing, allowing an idle poll.
 if(scenario?.startsWith('inflight')){
  // A real, newer server revision arrives after editing or opening a modal.
  await nativeFetch('/fixture/bump?pid='+pid,{method:'POST'});
  await wait(()=>releasePoll);
  if(scenario==='inflight-dialog'){
   await click('#settings');await click('[data-settings-section="sampling"]');input('[data-param="steps"]',16);
   releasePoll();await pause(150);await click('[data-apply]');await wait(()=>!document.querySelector('#dialog').open);
  }else if(scenario==='inflight-focus'){
   const field=root.querySelector('[data-seconds]');field.focus();releasePoll();await pause(150);
   assert(root.querySelector('[data-seconds]')===field&&document.activeElement===field,'Late poll replaced focused input before change');field.blur();
  }else if(scenario==='inflight-playing'){
   await click('[data-step="0"]');const video=root.querySelector('video');video.muted=true;video.loop=true;await video.play();
   const before=workspace.session.project;releasePoll();await pause(150);
   assert(workspace.session.project===before&&!video.paused,'Poll detached controls during playback');
   video.pause();await wait(()=>workspace.session.project.revision>before.revision);
   await click('[data-step="1"]');await click('[data-extension]');
  }else{input('[data-prompt]','编辑中的草稿');releasePoll();await pause(150);assert(root.querySelector('[data-prompt]').value==='编辑中的草稿','Late poll replaced active draft');}
 }else if(!query.has('fast')){await wait(()=>polls>=1);await pause(150);}
 input('[data-prompt]','<Picture 1>继续向前走，保留风声。');
 input('[data-seconds]','7');await click('[data-reference-edit]');input('[data-reference-purpose]','costume');input('[data-reference-subject]','2');await click('[data-reference-apply]');
 await click('[data-generate]');await wait(()=>!workspace.session.working);
 if(scenario==='save-error'){
  assert(root.querySelector('[data-error]').textContent.includes('隔离保存冲突'),'Missing save failure');
  assert(workspace.session.dirty&&root.querySelector('[data-prompt]').value==='<Picture 1>继续向前走，保留风声。','Save failure discarded draft');
  assert(!(await get()).assembly.runs.some(r=>r.kind==='generate'),'Generate continued after failed save');
  await click('[data-generate]');await wait(()=>!workspace.session.working);
 }
 const saved=await get(),e=saved.assembly.clips[0].extensions[0],r=saved.assembly.runs.find(r=>r.kind==='generate');
 const state={prompt:e.prompt,seconds:e.seconds,references:e.references,error:root.querySelector('[data-error]')?.textContent,queued:Boolean(r),polls};
 assert(e.prompt==='<Picture 1>继续向前走，保留风声。','Prompt lost on generate: '+JSON.stringify(state));
 assert(e.seconds===7&&e.references[0].purpose==='costume'&&e.references[0].subject==='2','Other draft fields lost');
 assert(r?.snapshot.extension.prompt===e.prompt&&r.snapshot.assets.length===1,'Run snapshot not bound');
 if(scenario==='inflight-dialog')assert(e.configurations.dance_split.steps===16,'Late poll discarded parameter edits');
 assert(!root.querySelector('[data-error]').textContent.trim(),'Unexpected operation error');
 document.body.dataset.check=JSON.stringify({passed:true,...state});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.message,stack:e.stack});}
finally{workspace?.dispose()}
</script>'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence-dir', required=True)
    parser.add_argument('--fast', action='store_true')
    parser.add_argument('--scenario', choices=['idle','inflight-edit','inflight-dialog','inflight-focus','inflight-playing','save-error'], default='idle')
    args = parser.parse_args()
    out = Path(args.evidence_dir); out.mkdir(parents=True, exist_ok=True)
    AssemblyTests.setUpClass(); case = AssemblyTests(); case.setUp()
    extension = case.extension()
    from PIL import Image
    import io
    stream = io.BytesIO(); Image.new('RGB', (32, 48), 'green').save(stream, format='PNG')
    response = case.c.post('/api/v5/assembly/'+case.pid+'/references', data={
        'revision': str(case.p['revision']), 'extension': extension['id'],
        'kind': 'image', 'file': (io.BytesIO(stream.getvalue()), 'reference.png')})
    assert response.status_code == 200, response.get_json()
    case.st.ctx['cfg']['studio_disable_generation'] = False

    save_failed = False
    def fixture(environ, start_response):
        nonlocal save_failed
        if environ.get('PATH_INFO') == '/draft-check':
            start_response('200 OK', [('Content-Type', 'text/html; charset=utf-8')]); return [PAGE.encode()]
        if environ.get('PATH_INFO') == '/fixture/bump':
            p = case.s.get(case.pid); case.s.store.save(p, p['revision'])
            start_response('200 OK', [('Content-Type', 'application/json')]); return [b'{}']
        if args.scenario == 'save-error' and environ.get('PATH_INFO', '').endswith('/save') and not save_failed:
            save_failed = True
            start_response('409 Conflict', [('Content-Type', 'application/json')])
            return [json.dumps({'error':'隔离保存冲突：请重试，草稿保留'}).encode()]
        return case.app(environ, start_response)

    class Quiet(WSGIRequestHandler):
        def log_message(self, *args): pass

    server = make_server('127.0.0.1', 0, fixture, handler_class=Quiet)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with patch.object(case.st.jobs, 'start', return_value=True) as queued:
            result = subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe',
                '--headless=new', '--disable-gpu', '--no-first-run', '--disable-background-networking',
                f'--user-data-dir={out/"profile"}', '--window-size=1280,900', '--virtual-time-budget=20000',
                f'--screenshot={out/"draft.png"}', '--dump-dom',
                f'http://127.0.0.1:{server.server_port}/draft-check?pid={case.pid}&scenario={args.scenario}'+('&fast=1' if args.fast else '')], capture_output=True, timeout=45)
            dom = result.stdout.decode('utf-8', 'replace'); (out/'draft.html').write_text(dom, encoding='utf-8')
            match = re.search(r'data-check="([^"]+)"', dom)
            check = json.loads(html.unescape(match[1])) if match else dict(passed=False, error='Missing completion marker')
            check['captured_jobs'] = queued.call_count
            (out/'check.json').write_text(json.dumps(check, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(check, ensure_ascii=False), flush=True)
            assert check['passed'] and queued.call_count == 1
    finally:
        server.shutdown(); server.server_close(); case.doCleanups(); AssemblyTests.tearDownClass()


if __name__ == '__main__': main()
