"""Render actual four existing workspace adapters with isolated fixture APIs."""
import argparse
import html
import json
import re
import subprocess
import sys
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.image_parameter_ui_fixture import Handler, RealImageFixture

SCRIPT=r'''<script type="module">
const pause=()=>new Promise(r=>setTimeout(r,40));
const assert=(v,m)=>{if(!v)throw Error(m)};
const wait=async fn=>{for(let i=0;i<450;i++){if(fn())return;await pause()}throw Error('UI wait timed out: '+fn)};
const click=async selector=>{await wait(()=>document.querySelector(selector)&&!document.querySelector(selector).disabled);document.querySelector(selector).click();await pause();};
const control=body=>fetch('/__fixture/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const pid=location.hash.split('/p/')[1];
const get=()=>fetch('/api/v5/projects/'+pid).then(r=>r.json());
const field=()=>document.querySelector('[data-param="steps"],[data-setting="steps"]');
const value=p=>p.kind==='image'?p.tasks.find(t=>t.id===p.current_task).settings.steps:p.settings.steps;
const set=n=>{field().value=String(n);field().dispatchEvent(new Event('input',{bubbles:true}));field().dispatchEvent(new Event('change',{bubbles:true}));};
const open=async()=>{await click('.project-actions button');await wait(field);};
const confirm=async yes=>{await click('.choice-dialog [data-choice="'+(yes?1:0)+'"]');};
try{
 await control({save_error:false});await wait(()=>document.querySelector('.project-actions button'));
 const original=value(await get());const next=original===30?29:original+1;
 await open();set(next);document.querySelector('#dialog').dispatchEvent(new Event('cancel',{cancelable:true}));
 await wait(()=>!document.querySelector('#dialog').open);await open();assert(Number(field().value)===original,'Esc changed outer draft');
 await click('[data-settings-action="reset"]');await click('#cancel-settings');await open();assert(Number(field().value)===original,'cancelled reset changed parameters');
 set(next);await click('#apply-settings');await wait(()=>!document.querySelector('#dialog').open);
 assert(value(await get())===original,'Apply unexpectedly persisted');await open();assert(Number(field().value)===next,'Apply did not update draft');
 await control({save_error:true});await click('#save-settings');await wait(()=>document.querySelector('#parameter-errors .error-feedback'));
 assert(Number(field().value)===next&&document.querySelector('#dialog').open,'save failure discarded dialog input');
 assert(value(await get())===original,'failed save changed stored version');
 await control({save_error:false});await click('#save-settings');
 if((await get()).kind!=='image'){
   await wait(()=>document.querySelector('.choice-dialog'));assert(document.querySelector('#dialog').open,'impact confirmation replaced parameter dialog');
   await confirm(false);await wait(()=>!document.querySelector('#save-settings').disabled);assert(document.querySelector('#dialog').open,'cancelled impact closed draft');
   await click('#save-settings');await confirm(true);
 }
 await wait(()=>!document.querySelector('#dialog').open);assert(value(await get())===next,'Save not persisted');
 await open();assert(Number(field().value)===next,'saved reopen mismatch');set(original);await click('#apply-settings');await wait(()=>!document.querySelector('#dialog').open);
 location.hash='#/archive';await wait(()=>document.querySelector('.choice-dialog'));await click('.choice-dialog [data-choice="0"]');
 assert(location.hash.includes(pid),'stay left project');
 location.hash='#/archive';await wait(()=>document.querySelector('.choice-dialog'));await control({save_error:true});await click('.choice-dialog [data-choice="2"]');
 await wait(()=>document.querySelector('.choice-dialog .error-feedback'));assert(location.hash.includes(pid),'failed leave-save left project');
 await control({save_error:false});await click('.choice-dialog [data-choice="2"]');
 if((await get()).kind!=='image'){await wait(()=>document.querySelectorAll('.choice-dialog').length===2);await click('.choice-dialog:last-of-type [data-choice="1"]');}
 await wait(()=>location.hash==='#/archive'&&!document.querySelector('.choice-dialog'));assert(value(await get())===original,'leave-save did not persist');
 location.hash='#/p/'+pid;await wait(()=>document.querySelector('.project-actions button'));await open();
 await document.fonts.ready;
 const root=document.querySelector('.production-settings'),dialog=document.querySelector('#dialog');
 assert(getComputedStyle(root.querySelector('h2')).fontSize===getComputedStyle(document.documentElement).getPropertyValue('--title-dialog').trim(),'heading style differs');
 assert(dialog.scrollWidth<=dialog.clientWidth+1,'horizontal overflow');
 const roles=[...root.querySelectorAll('[data-settings-action]')].map(b=>b.dataset.settingsAction);
 assert(roles.join(',')==='reset,cancel,apply,save','common action ordering differs');
 root.querySelector('.dialog-actions').scrollIntoView({block:'nearest'});await pause();
 assert(root.querySelector('.dialog-actions').getBoundingClientRect().bottom<=innerHeight,'actions inaccessible');
 root.querySelector('h2').scrollIntoView({block:'nearest'});
 const state=await fetch('/__fixture/state').then(r=>r.json());assert(state.generation_requests===0,'generation attempted');
 document.body.dataset.check=JSON.stringify({passed:true,mode:(await get()).mode,checks:'Esc/reset cancel; apply; failed save + retry; nested impact; leave stay/fail/save; width/actions',width:innerWidth});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.message,stack:e.stack})}
</script>'''

class ExperienceFixture(RealImageFixture):
    def request(self, method, path, body):
        status, result = super().request(method, path, body)
        if status == 200 and path.endswith('/change-plan') and path.startswith('/api/v5/projects/'):
            result['requires_confirmation'] = True
        return status, result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence-dir',required=True);args=parser.parse_args()
    out=Path(args.evidence_dir);out.mkdir(parents=True,exist_ok=True)
    class CheckedHandler(Handler):
        def send(self,status,body,content_type='application/json; charset=utf-8'):
            if self.path.startswith('/?') and content_type.startswith('text/html'):
                body=body.replace(b'</body>',SCRIPT.encode('utf-8')+b'</body>')
            super().send(status,body,content_type)
    fixture=ExperienceFixture(out)
    server=ThreadingHTTPServer(('127.0.0.1',0),CheckedHandler);server.fixture=fixture
    threading.Thread(target=server.serve_forever,daemon=True).start();checks=[]
    try:
        for pid,p in fixture.projects.items():
            for width,height in [(1280,720),(760,1000)]:
                name=p['mode']+'-'+str(width)
                result=subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--no-first-run','--disable-background-networking',f'--user-data-dir={out/("profile-"+name)}',f'--window-size={width},{height}','--virtual-time-budget=35000',f'--screenshot={out/(name+".png")}','--dump-dom',f'http://127.0.0.1:{server.server_port}/?check=1#/p/{pid}'],capture_output=True,timeout=50)
                dom=result.stdout.decode('utf-8','replace');(out/(name+'.html')).write_text(dom,encoding='utf-8')
                match=re.search(r'data-check="([^"]+)"',dom);data=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='No completion marker')
                checks.append(dict(case=name,**data));print(json.dumps(checks[-1],ensure_ascii=False),flush=True)
    finally:
        server.shutdown();server.server_close();fixture.close()
        (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)

if __name__=='__main__':main()
