"""Real application routing, image blueprint and canvas; no engine calls permitted."""
import html
import json
import re
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.image_parameter_ui_fixture import Handler, RealImageFixture

SCRIPT = r'''<script type="module">
const pause=()=>new Promise(r=>setTimeout(r,50)),assert=(v,m)=>{if(!v)throw Error(m)};
const wait=async f=>{for(let i=0;i<250;i++){if(await f())return;await pause()}throw Error('Timed out '+f)};
const root=document.querySelector('#app'),pid=location.hash.split('/')[2];
const get=()=>fetch('/api/v5/projects/'+pid).then(r=>r.json());
async function click(selector){const e=root.querySelector(selector)||document.querySelector(selector);assert(e,'Missing '+selector);e.click();await pause()}
async function select(task){
 await click('[data-toggle-directory]');await click('[data-task="'+task.id+'"]');
 await wait(()=>root.querySelector('[data-tool="'+task.submode+'"][aria-pressed=true]'));
}
try{
 await wait(()=>root.querySelector('[data-toggle-directory]'));
 const project=await get(),region=project.tasks.find(t=>t.submode==='region'),outpaint=project.tasks.find(t=>t.submode==='outpaint');
 await select(region);await wait(()=>root.querySelector('canvas')?.width>300);
 if(root.querySelector('.director-desk').classList.contains('directory-open'))await click('[data-close-directory]');
 if(root.querySelector('.director-desk').classList.contains('inspector-open'))await click('[data-close-inspector]');
 await click('[data-pen=brush]');const canvas=root.querySelector('canvas');canvas.scrollIntoView({block:'center'});await pause();
 const before=canvas.toDataURL();document.body.dataset.pointerStroke='requested';
 await wait(()=>document.body.dataset.pointerStroke==='done');
 assert(canvas.toDataURL()!==before,'Pointer stroke did not reach the real canvas');
 const edited=canvas.toDataURL();await click('[data-mask=undo]');assert(canvas.toDataURL()===before,'Mask undo changed geometry');await click('[data-mask=redo]');assert(canvas.toDataURL()===edited,'Mask redo lost stroke');
 const oldMask=region.mask;await click('#image-save');await wait(async()=>{const p=await get();return p.tasks.find(t=>t.id===region.id).mask!==oldMask});
 const saved=(await get()).tasks.find(t=>t.id===region.id);assert(saved.A===region.A&&saved.mask,'Saving mask changed source');
 await select(outpaint);await wait(()=>root.querySelector('[data-setting=left]'));
 if(root.querySelector('.director-desk').classList.contains('directory-open'))await click('[data-close-directory]');
 const input=root.querySelector('[data-setting=left]');input.value='96';input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));
 await click('#image-save');await wait(async()=>{const p=await get();return p.tasks.find(t=>t.id===outpaint.id).settings.left===96});
 assert((await get()).tasks.find(t=>t.id===region.id).mask===saved.mask,'Outpaint task overwrote the other task mask');
 assert(document.documentElement.scrollWidth<=innerWidth+1,'Canvas page horizontally clipped');
 root.querySelector('.desk-canvas').scrollTop=0;
 document.body.dataset.check=JSON.stringify({passed:true,width:innerWidth,checks:['real pointer mask','undo redo','mask persisted','outpaint 96px persisted','task isolation']});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.stack})}
</script>'''


def main():
    output = Path(sys.argv[1]); output.mkdir(parents=True, exist_ok=True)
    width = int(sys.argv[2])

    class Checked(Handler):
        def do_GET(self):
            if self.path.startswith('/api/v5/prompt-library/pending/'):
                return self.send(200, {'items': []})
            return super().do_GET()
        def send(self, status, body, content_type='application/json; charset=utf-8'):
            if self.path.startswith('/?') and content_type.startswith('text/html'):
                body = body.replace(b'</body>', SCRIPT.encode() + b'</body>')
            super().send(status, body, content_type)

    fixture = RealImageFixture(output)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Checked); server.fixture = fixture
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url=f'http://127.0.0.1:{server.server_port}/?uiux=canvas#/p/{fixture.pid}'
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('uiux_browser_capture.py')),
            url,str(output/'page.png'),str(width),str(960 if width==1440 else 900)],capture_output=True,timeout=60)
        dom=result.stdout.decode('utf-8','replace');(output/'page.html').write_text(dom,encoding='utf-8')
        match=re.search(r'data-check="([^"]+)"',dom)
        data=json.loads(html.unescape(match[1])) if match else dict(passed=False,error=result.stderr.decode('utf-8','replace')[-1200:])
        data['engine_attempts']=fixture.engine_attempts
        (output/'checks.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(data,ensure_ascii=False))
        if not data['passed'] or fixture.engine_attempts:raise SystemExit(1)
    finally:
        server.shutdown();server.server_close();fixture.close()


if __name__=='__main__':main()
