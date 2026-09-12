"""Manual screenplay whitespace survives real save, render and confirmation; no model."""
import html,json,re,sys,threading,subprocess
from pathlib import Path
from werkzeug.serving import make_server,WSGIRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_creation import CreationTests
from tests.uiux_r1_shell import application_shell

SCRIPT=r'''<script type="module">
import {mountWorkspace} from '/static/studio/modes/authoring/workspace.js';
const root=document.querySelector('#root'),pid=new URLSearchParams(location.search).get('pid');
const get=()=>fetch('/api/v5/projects/'+pid).then(r=>r.json()),pause=()=>new Promise(r=>setTimeout(r,40));
const assert=(v,m)=>{if(!v)throw Error(m)};
async function wait(fn){for(let i=0;i<350;i++){if(fn())return;await pause()}throw Error('Timed out')}
let w;const text='\n\n清晨，林间一片寂静。\nThe camera stays still.\n\n';
const set=(selector,value)=>{const e=root.querySelector(selector);e.value=value;e.dispatchEvent(new Event('input',{bubbles:true}))};
const click=async selector=>{root.querySelector(selector).click();await wait(()=>!w.session.actionPending&&!w.session.working)};
try{
 w=mountWorkspace(root,await get());set('[data-text="intent"]',text);await click('[data-save]');
 assert((await get()).content.layers.find(r=>r.layer==='intent').content.story_text===text,'API changed intent');
 assert(root.querySelector('[data-text="intent"]').value===text,'render lost initial newline');
 await click('[data-nav-step="1"]');set('[data-text="screenplay"]',text);set('[data-ai-instruction]',text);await click('[data-save]');
 let p=await get(),row=p.content.layers.find(r=>r.layer==='screenplay'),ref=row.content.blocks[0].ref;
 assert(row.content.blocks[0].text===text,'API changed screenplay');
 w.dispose();w=mountWorkspace(root,p);
 assert(root.querySelector('[data-text="screenplay"]').value===text,'reopen changed screenplay');
 assert(root.querySelector('[data-ai-instruction]').value===text,'reopen changed communication');
 set('[data-text="screenplay"]',text+'续写一句。');await click('[data-confirm]');p=await get();
 row=p.content.layers.find(r=>r.layer==='screenplay');assert(row.content.blocks[0].text===text+'续写一句。','continue changed original');
 assert(row.content.blocks[0].ref===ref,'manual edit changed identity');
 assert(p.content.confirmations.some(c=>c.layer==='screenplay'),'manual confirmation missing');
 assert(p.creation_jobs.length===0&&p.candidates.length===0,'manual editing invoked AI');
 root.querySelector('[data-text="screenplay"]').closest('details').open=true;
 await document.fonts.ready;assert(document.documentElement.scrollWidth<=innerWidth+1,'overflow');
 document.body.dataset.check=JSON.stringify({passed:true,width:innerWidth,modelJobs:0});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.stack})}
</script>'''

def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True);checks=[]
    for width in [1366,430]:
        c=CreationTests();c.setUp();page=application_shell(SCRIPT)
        def app(env,start):
            if env['PATH_INFO']=='/manual':start('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [page.encode()]
            return c.app(env,start)
        class Quiet(WSGIRequestHandler):
            def log(self,*args,**kwargs):pass
        server=make_server('127.0.0.1',0,app,threaded=True,request_handler=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            result=subprocess.run([sys.executable,str(Path(__file__).with_name('uiux_browser_capture.py')),f'http://127.0.0.1:{server.server_port}/manual?pid={c.p["id"]}',str(out/f'{width}.png'),str(width),str(768 if width==1366 else 900)],capture_output=True,timeout=60)
            dom=result.stdout.decode('utf-8','replace')
            (out/f'{width}.html').write_text(dom,encoding='utf-8');match=re.search(r'data-check="([^"]+)"',dom)
            result=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='missing marker');checks.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
        finally:server.shutdown();server.server_close();c.doCleanups()
    (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8');assert all(c['passed'] for c in checks)

if __name__=='__main__':main()
