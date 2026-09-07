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
const wait=async fn=>{for(let i=0;i<400;i++){if(fn())return;await pause()}throw Error('UI wait timed out')};
try{
 await wait(()=>document.querySelector('.project-actions button'));
 document.querySelector('.project-actions button').click();
 await wait(()=>document.querySelector('.production-settings .settings-grid input,.production-settings .settings-grid select'));
 const original=document.querySelector('.production-settings');
 const chooser=document.querySelector('[data-model-choice]');
 assert(chooser?.tagName==='SELECT','shared model selector missing');
 const modelRoot=chooser.closest('[data-model-field]'),manual=modelRoot.querySelector('[data-model-filename]');
 modelRoot.querySelector('details').open=true;
 const originalCount=chooser.options.length;
 for(const value of ['custom/','custom/fixture.safetensors']){manual.value=value;manual.dispatchEvent(new Event('input',{bubbles:true}));}
 manual.dispatchEvent(new Event('change',{bubbles:true}));
 assert(chooser.value==='custom/fixture.safetensors','manual model not bound');
 assert(chooser.options.length<=originalCount+1,'typing polluted model choices');
 const directory=document.querySelector('.production-settings-directory');
 assert(document.querySelector('.settings-workbench').getBoundingClientRect().top-directory.getBoundingClientRect().bottom>=16,'directory spacing missing');

 const field=original.querySelector('input[type=number]');
 if(field){const old=field.value;field.value=String(Number(old)+1);field.dispatchEvent(new Event('input',{bubbles:true}));field.dispatchEvent(new Event('change',{bubbles:true}));}
 document.querySelector('#cancel-settings').click();await wait(()=>!document.querySelector('#dialog').open);
 await wait(()=>!document.querySelector('.project-actions button').disabled);document.querySelector('.project-actions button').click();await wait(()=>document.querySelector('#dialog').open&&document.querySelector('.production-settings')!==original&&document.querySelector('.production-settings .settings-grid'));
 const root=document.querySelector('.production-settings'),dialog=document.querySelector('#dialog');
 assert(root!==original,'dialog instance reused');
 await document.fonts.ready;
 const heading=getComputedStyle(root.querySelector('h2')),grid=getComputedStyle(root.querySelector('.settings-grid'));
 assert(heading.fontSize==='27px','shared heading style missing');
 assert(grid.display==='grid','shared field grid missing');
 assert(dialog.getBoundingClientRect().width>Math.min(1000,innerWidth*.8),'dialog too narrow');
 assert(dialog.scrollWidth<=dialog.clientWidth+1,'dialog content overflow');
 const actions=root.querySelector('.dialog-actions');actions.scrollIntoView({block:'nearest'});await pause();
 assert(actions.getBoundingClientRect().bottom<=innerHeight,'actions inaccessible');
 root.querySelector('h2').scrollIntoView({block:'nearest'});
 document.body.dataset.check=JSON.stringify({passed:true,heading:heading.fontSize,width:dialog.getBoundingClientRect().width,columns:grid.gridTemplateColumns});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.message,stack:e.stack})}
</script>'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence-dir',required=True);args=parser.parse_args()
    out=Path(args.evidence_dir);out.mkdir(parents=True,exist_ok=True)
    class CheckedHandler(Handler):
        def send(self,status,body,content_type='application/json; charset=utf-8'):
            if self.path.startswith('/?') and content_type.startswith('text/html'):
                body=body.replace(b'</body>',SCRIPT.encode('utf-8')+b'</body>')
            super().send(status,body,content_type)
    fixture=RealImageFixture(out)
    server=ThreadingHTTPServer(('127.0.0.1',0),CheckedHandler);server.fixture=fixture
    threading.Thread(target=server.serve_forever,daemon=True).start();checks=[]
    try:
        for pid,p in fixture.projects.items():
            for width,height in [(1280,720),(1920,1080),(760,1000)]:
                name=p['mode']+'-'+str(width)
                result=subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--no-first-run','--disable-background-networking',f'--user-data-dir={out/("profile-"+name)}',f'--window-size={width},{height}','--virtual-time-budget=20000',f'--screenshot={out/(name+".png")}','--dump-dom',f'http://127.0.0.1:{server.server_port}/?check=1#/p/{pid}'],capture_output=True,timeout=50)
                dom=result.stdout.decode('utf-8','replace');(out/(name+'.html')).write_text(dom,encoding='utf-8')
                match=re.search(r'data-check="([^"]+)"',dom);data=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='No completion marker')
                checks.append(dict(case=name,**data));print(json.dumps(checks[-1],ensure_ascii=False),flush=True)
    finally:
        server.shutdown();server.server_close();fixture.close()
        (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)

if __name__=='__main__':main()
