"""Second-step add-video UI with real temporary import/library/save APIs, no generation."""
import argparse, html, json, re, subprocess, sys, threading
from pathlib import Path
from wsgiref.simple_server import make_server, WSGIRequestHandler
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.test_video_assembly import AssemblyTests
from tests.video_assembly_ui_fixture import PAGE

CHECK=r'''
 await click('[data-step="1"]');await click('[data-add-extension]');await wait(settled);
 const originalExtension=workspace.session.project.assembly.clips[0].extensions[0].id;
 input('[data-prompt]','保留当前未保存的续接正文');
 const before=await get();
 const sameStep=()=>assert(root.querySelector('[data-step="1"]').getAttribute('aria-current')==='step','add video navigated away from step two');
 const open=async()=>{await click('[data-open-import]');sameStep();assert(document.querySelector('[data-local-video]')&&document.querySelector('[data-library-video]'),'missing source choices');};
 await open();await click('[data-cancel-import]');sameStep();
 assert((await get()).revision===before.revision&&root.querySelector('[data-prompt]').value.includes('未保存'),'cancel changed draft');
 await open();document.querySelector('#dialog').dispatchEvent(new Event('cancel',{cancelable:true}));await pause();
 assert(!document.querySelector('#dialog').open,'Esc cancellation failed');
 await open();await click('.dialog-close');assert(!document.querySelector('#dialog').open,'close failed');
 // A failed save must retain the old draft and prevent either import route.
 await open();
 const failInput=document.querySelector('[data-video-files]');
 const failTransfer=new DataTransfer();failTransfer.items.add(new File([await fetch('/fixture-video').then(r=>r.blob())],'不应导入.mp4',{type:'video/mp4'}));
 const originalFetch=window.fetch;let importAttempts=0;
 window.fetch=async(url,options)=>{const path=String(url);if(path.endsWith('/save'))return new Response(JSON.stringify({error:'隔离保存冲突'}),{status:409,headers:{'Content-Type':'application/json'}});if(path.endsWith('/import'))importAttempts++;return originalFetch(url,options);};
 failInput.files=failTransfer.files;failInput.dispatchEvent(new Event('change',{bubbles:true}));
 await wait(()=>settled()&&root.querySelector('[data-error]').textContent.includes('隔离保存冲突'));
 window.fetch=originalFetch;sameStep();assert(importAttempts===0,'import submitted after failed save');
 assert(root.querySelector('[data-prompt]').value==='保留当前未保存的续接正文'&&workspace.session.dirty,'failed save lost draft');
 await open();
 const files=document.querySelector('[data-video-files]');let clicked=0;files.click=()=>clicked++;
 await click('[data-local-video]');assert(clicked===1,'local button not bound to file chooser');
 files.dispatchEvent(new Event('cancel'));assert(document.querySelector('#dialog').open,'native file cancel dismissed source choices');
 const blob=await fetch('/fixture-video').then(r=>r.blob()),transfer=new DataTransfer();
 transfer.items.add(new File([blob],'本地片段一.mp4',{type:'video/mp4'}));transfer.items.add(new File([blob],'本地片段二.mp4',{type:'video/mp4'}));
 files.files=transfer.files;files.dispatchEvent(new Event('change',{bubbles:true}));
 await wait(()=>settled()&&root.querySelectorAll('[data-track]').length===3);sameStep();
 let saved=await get();assert(saved.assembly.clips[0].extensions[0].prompt==='保留当前未保存的续接正文','import lost existing draft');
 assert(saved.assembly.clips[0].extensions[0].id===originalExtension,'import replaced old extension');
 assert(root.querySelector('[data-track].active').dataset.track==='clip:'+saved.assembly.clips.at(-1).id,'last local clip not selected');
 await open();await click('[data-library-video]');await wait(()=>document.querySelector('.library-pick-card'));
 await click('.library-pick-card');await click('.picker-cancel');sameStep();assert((await get()).assembly.clips.length===3,'library cancel imported a video');
 await open();await click('[data-library-video]');await wait(()=>document.querySelector('.library-pick-card'));
 await click('.library-pick-card');await click('.picker-apply');await wait(()=>settled()&&root.querySelectorAll('[data-track]').length===4);sameStep();
 saved=await get();assert(saved.assembly.clips.at(-1).provenance.asset,'library fixed reference missing');
 await click('[data-reload]');await wait(settled);sameStep();assert(root.querySelectorAll('[data-track]').length===4,'reload lost added clips');
 await open();await document.fonts.ready;
 const dialog=document.querySelector('#dialog');assert(dialog.scrollWidth<=dialog.clientWidth+1,'dialog horizontal overflow');
 assert(dialog.querySelector('[data-cancel-import]').getBoundingClientRect().bottom<innerHeight,'cancel inaccessible');
'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence-dir',required=True);args=parser.parse_args()
    out=Path(args.evidence_dir);out.mkdir(parents=True,exist_ok=True)
    AssemblyTests.setUpClass();case=AssemblyTests();case.setUp();checks=[]
    case.s.lib.ingest(case.sound,'隔离资产视频')
    page=PAGE.replace(" if(q.has('references')){",CHECK+"\n if(q.has('references')){")
    def application(environ,start_response):
        path=environ.get('PATH_INFO')
        if path=='/import-check':
            start_response('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [page.encode()]
        if path=='/fixture-video':
            start_response('200 OK',[('Content-Type','video/mp4')]);return [case.silent.read_bytes()]
        return case.app(environ,start_response)
    class Quiet(WSGIRequestHandler):
        def log_message(self,*args):pass
    server=make_server('127.0.0.1',0,application,handler_class=Quiet)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        for width in [1280,760]:
            case.p=case.s.create('添加视频 · 隔离检查');case.pid=case.p['id'];case.refresh();case.upload()
            result=subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--no-first-run','--disable-background-networking',f'--user-data-dir={out/("profile-"+str(width))}',f'--window-size={width},1000','--virtual-time-budget=25000',f'--screenshot={out/(str(width)+".png")}','--dump-dom',f'http://127.0.0.1:{server.server_port}/import-check?pid={case.pid}'],capture_output=True,timeout=50)
            dom=result.stdout.decode('utf-8','replace');(out/f'{width}.html').write_text(dom,encoding='utf-8')
            match=re.search(r'data-check="([^"]+)"',dom);data=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='No completion')
            checks.append(data);print(json.dumps(data,ensure_ascii=False),flush=True)
    finally:
        server.shutdown();server.server_close();case.doCleanups();AssemblyTests.tearDownClass()
        (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)

if __name__=='__main__':main()
