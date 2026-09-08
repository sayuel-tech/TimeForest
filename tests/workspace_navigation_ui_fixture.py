"""Five real workspace adapters, isolated API/media; never generate or use production data."""
import argparse
import base64
import json
import subprocess
import sys
import threading
import time
from urllib.request import urlopen
import websocket
from http.server import ThreadingHTTPServer
from pathlib import Path
from wsgiref.simple_server import make_server, WSGIRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.image_parameter_ui_fixture import Handler, RealImageFixture
from tests.test_video_assembly import AssemblyTests

SCRIPT=r'''<script type="module">
const pause=()=>new Promise(r=>setTimeout(r,40));
const assert=(v,m)=>{if(!v)throw Error(m)};
const wait=async fn=>{for(let i=0;i<400;i++){if(await fn())return;await pause()}throw Error('UI wait timed out: '+fn)};
const click=async selector=>{await wait(()=>document.querySelector(selector)&&!document.querySelector(selector).disabled);document.querySelector(selector).click();await pause()};
const q=new URLSearchParams(location.search),assembly=q.has('assembly'),pid=assembly?q.get('pid'):location.hash.split('/p/')[1];
const get=()=>fetch('/api/v5/projects/'+pid).then(r=>r.json());
let workspace;
try{
 const original=await get();
 if(assembly){const {mountWorkspace}=await import('/static/studio/modes/video-assembly/workspace.js');workspace=mountWorkspace(document.querySelector('#root'),original,await fetch('/api/v5/assembly/catalog').then(r=>r.json()))}
 await wait(()=>document.querySelector('[data-workspace-steps]'));
 const image=original.kind==='image',mode=assembly?'video_assembly':original.mode;
 const steps=()=>[...document.querySelectorAll('[data-workspace-step]')];
 const current=()=>steps().find(b=>b.getAttribute('aria-current')==='step').dataset.workspaceStep;
 const initial=current(),initialButtons=steps();
 assert(document.querySelectorAll('[data-workspace-header]').length===1,'duplicate/missing header');
 assert(document.querySelectorAll('.project-actions button').length===1,'parameter entry differs');
 initialButtons[0].focus();initialButtons[0].dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
 assert(document.activeElement===initialButtons[1]&&current()===initial,'arrow key navigated or failed to focus');
 initialButtons[1].dispatchEvent(new KeyboardEvent('keydown',{key:'End',bubbles:true}));assert(document.activeElement===initialButtons.at(-1),'End focus');
 // Enter/Space remain native button activation, with the original adapter's save gate.
 if(mode==='swap'){
  await click('[data-workspace-step="edit"]');await wait(()=>current()==='edit');
  const choice=document.querySelector('[data-swap-mode]');choice.value='custom';choice.dispatchEvent(new Event('change',{bubbles:true}));
 }
 if(assembly){await click('[data-workspace-step="1"]');await click('[data-add-extension]');await wait(()=>document.querySelector('[data-prompt]')&&!workspace.session.working)}
 const promptSelector=image?'#image-prompt':assembly?'[data-prompt]':mode==='swap'?'textarea[data-field="swap_custom_prompt"]':'textarea[data-field="prompt"]';
 await wait(()=>document.querySelector(promptSelector));
 const prompt=document.querySelector(promptSelector),text=prompt.value+(prompt.value?'\n':'')+'导航保留检查';
 prompt.value=text;prompt.dispatchEvent(new Event('input',{bubbles:true}));
 const editorStep=current(),other=image?'results':assembly?'2':mode==='swap'?'source':'review';
 await click('[data-workspace-step="'+other+'"]');await wait(()=>current()===other);
 await click('[data-workspace-step="'+editorStep+'"]');await wait(()=>current()===editorStep&&document.querySelector(promptSelector));
 assert(document.querySelector(promptSelector).value===text,'navigation lost edited prompt');
 const saveSelector=image?'#image-save':assembly?'.savebar [data-save]':'#save';
 await click(saveSelector);
 await wait(async()=>{const p=await get();return image?p.tasks.some(t=>t.prompt===text):assembly?p.assembly.clips.some(c=>c.extensions.some(e=>e.prompt===text)):p.segments.some(s=>Object.values(s).includes(text))});
 if(assembly){
  await click('[data-open-import]');await wait(()=>document.querySelector('#dialog').open);
  assert(current()==='1','plus left second step');
  document.querySelector('#dialog').dispatchEvent(new Event('cancel',{cancelable:true}));
  await wait(()=>!document.querySelector('#dialog').open);assert(current()==='1','cancel import changed step');
 }
 await click('.project-actions button');await wait(()=>document.querySelector('#dialog').open);
 await click(image||!assembly?'#cancel-settings':'[data-cancel]');await wait(()=>!document.querySelector('#dialog').open);
 assert(current()===editorStep,'parameter cancel navigated');
 const support=document.querySelector('.savebar .workspace-support'),actions=document.querySelector('.savebar .workspace-actions');
 assert(support.contains(document.querySelector(saveSelector)),'save not in support group');
 assert(actions.querySelector('.primary'),'primary missing');
 if(innerWidth>900)assert(support.getBoundingClientRect().right<=actions.getBoundingClientRect().left+1,'footer groups overlap');
 else assert(getComputedStyle(document.querySelector('.savebar')).position==='static','narrow footer covers editor');
 const title=document.querySelector('[data-workspace-header] h1');title.textContent='很长的项目名称与跨模式排版检查'.repeat(5);
 await document.fonts.ready;await pause();
 assert(title.scrollWidth>title.clientWidth&&getComputedStyle(title).textOverflow==='ellipsis','long title not truncated');
 assert(document.documentElement.scrollWidth<=innerWidth+1,'page horizontal overflow');
 const after=await get();
 if(assembly)assert(after.assembly.runs.every(r=>r.kind==='import'),'navigation generated/exported');
 else assert((await fetch('/__fixture/state').then(r=>r.json())).generation_requests===0,'navigation generated/prepared');
 await wait(()=>!document.querySelector('#toast.show'));
 const noSmooth=document.createElement('style');noSmooth.textContent='*{scroll-behavior:auto!important}';document.head.append(noSmooth);
 if(innerWidth<900)document.querySelector('.savebar').scrollIntoView({block:'end'});else window.scrollTo(0,0);
 await new Promise(r=>setTimeout(r,500));
 if(innerWidth<900)assert(document.querySelector('.savebar').getBoundingClientRect().bottom<=innerHeight+1,'footer inaccessible');
 document.body.dataset.check=JSON.stringify({passed:true,mode,width:innerWidth,checks:'shared header; keyboard focus only; step draft retention; save roundtrip; parameter cancel; footer placement/access; narrow/long title; no generation'});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.message,stack:e.stack})}
</script>'''

def capture(out,name,url,width):
    # Existing Chrome + existing websocket-client. CDP viewport capture avoids
    # Windows headless --screenshot clipping/blanking after scrollIntoView.
    profile=out/("profile-"+name);socket=None;serial=0
    process=subprocess.Popen(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--no-first-run','--disable-background-networking','--remote-debugging-port=0',f'--user-data-dir={profile}',f'--window-size={width},1000',url],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    def command(method,params=None):
        nonlocal serial
        serial+=1;socket.send(json.dumps(dict(id=serial,method=method,params=params or {})))
        while True:
            result=json.loads(socket.recv())
            if result.get('id')==serial:
                if 'error' in result:raise RuntimeError(result['error'])
                return result.get('result',{})
    def evaluate(expression):return command('Runtime.evaluate',dict(expression=expression,returnByValue=True))['result'].get('value')
    try:
        deadline=time.monotonic()+45
        while not (profile/'DevToolsActivePort').exists():
            if time.monotonic()>deadline:raise TimeoutError('Chrome startup')
            time.sleep(.05)
        port=(profile/'DevToolsActivePort').read_text().splitlines()[0]
        with urlopen(f'http://127.0.0.1:{port}/json/list') as response:tabs=json.load(response)
        socket=websocket.create_connection(next(t['webSocketDebuggerUrl'] for t in tabs if t['type']=='page'),suppress_origin=True,timeout=10)
        while not (marker:=evaluate('document.body?.dataset.check')):
            if time.monotonic()>deadline:raise TimeoutError('No UI completion')
            time.sleep(.1)
        data=json.loads(marker)
        (out/(name+'.html')).write_text(evaluate('document.documentElement.outerHTML'),encoding='utf-8')
        shot=command('Page.captureScreenshot',dict(format='png',captureBeyondViewport=False))
        (out/(name+'.png')).write_bytes(base64.b64decode(shot['data']))
        data['case']=name;print(json.dumps(data,ensure_ascii=False),flush=True);return data
    finally:
        if socket:
            try:command('Browser.close')
            except (websocket.WebSocketException,ConnectionError):pass
            socket.close()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence-dir',required=True);parser.add_argument('--only',choices=['original','assembly']);args=parser.parse_args()
    out=Path(args.evidence_dir);out.mkdir(parents=True,exist_ok=True);checks=[]
    if args.only!='assembly':
        class Checked(Handler):
            def send(self,status,body,content_type='application/json; charset=utf-8'):
                if self.path.startswith('/?') and content_type.startswith('text/html'):body=body.replace(b'</body>',SCRIPT.encode()+b'</body>')
                super().send(status,body,content_type)
        fixture=RealImageFixture(out);server=ThreadingHTTPServer(('127.0.0.1',0),Checked);server.fixture=fixture
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            for pid,p in fixture.projects.items():
                for width in [1280,760]:checks.append(capture(out,p['mode']+'-'+str(width),f'http://127.0.0.1:{server.server_port}/?check=1#/p/{pid}',width))
        finally:server.shutdown();server.server_close();fixture.close()
    if args.only!='original':
        AssemblyTests.setUpClass();case=AssemblyTests();case.setUp()
        page='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/studio/style.css"><main id="root"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div>'+SCRIPT
        def application(environ,start_response):
            if environ.get('PATH_INFO')=='/navigation-check':
                start_response('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [page.encode()]
            return case.app(environ,start_response)
        class Quiet(WSGIRequestHandler):
            def log_message(self,*args):pass
        server=make_server('127.0.0.1',0,application,handler_class=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            for width in [1280,760]:
                case.p=case.s.create('导航隔离检查');case.pid=case.p['id'];case.refresh();case.upload()
                checks.append(capture(out,'video_assembly-'+str(width),f'http://127.0.0.1:{server.server_port}/navigation-check?assembly=1&pid={case.pid}',width))
        finally:server.shutdown();server.server_close();case.doCleanups();AssemblyTests.tearDownClass()
    (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)

if __name__=='__main__':main()
