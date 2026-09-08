"""Real image-result transfer dialogs and temporary library/project APIs; no engine."""
import argparse, html, json, re, subprocess, sys, threading
from pathlib import Path
from wsgiref.simple_server import make_server, WSGIRequestHandler
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_video_assembly import AssemblyTests

PAGE=r'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="/static/studio/style.css"><main><h1>图片用于视频接续 · 隔离检查</h1></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div>
<script type="module">
import {sendToVideo} from '/static/studio/features/image-results/transfer.js';
import {useImageInAssembly} from '/static/studio/features/asset-picker/assembly-use.js';
import {mountLibrary} from '/static/studio/pages/asset-library/index.js';
import {mountDetail} from '/static/studio/pages/asset-library/detail.js';
const q=new URLSearchParams(location.search),pid=q.get('pid'),aid=q.get('aid');
const pause=()=>new Promise(r=>setTimeout(r,40)),assert=(ok,msg)=>{if(!ok)throw Error(msg);};
const wait=async fn=>{for(let i=0;i<200;i++){if(fn())return;await pause();}throw Error('Timeout');};
const click=async sel=>{const el=document.querySelector(sel);assert(el,'Missing '+sel);el.click();await pause();};
const get=()=>fetch('/api/v5/projects/'+pid).then(r=>r.json());
const library=()=>fetch('/api/v5/library/assets/'+aid).then(r=>r.json());
const originalFetch=window.fetch;let mutations=0,generations=0;
window.fetch=(url,options)=>{if(options?.method==='POST'){mutations++;if(String(url).includes('/generate'))generations++;}return originalFetch(url,options);};
try{
 const asset=await library(),before=await get(),signal=new AbortController().signal;
 let pending=sendToVideo(asset,signal);await wait(()=>document.querySelector('#video-next'));
 await click('#video-cancel');await pending;assert(mutations===0,'project cancellation mutated');
 const open=async()=>{pending=sendToVideo(asset,signal);await wait(()=>document.querySelector('#dialog').open&&document.querySelector('#video-next'));document.querySelector('#image-video-project').value=pid;await click('#video-next');await wait(()=>document.querySelector('#dialog').open&&document.querySelector('[data-use-extension]'));};
 await open();assert(document.querySelector('[data-use-extension]').options.length===2,'wrong target extension count');
 await click('[data-use-cancel]');await pending;assert(mutations===0,'target cancellation mutated');
 await open();await click('.dialog-close');await pending;assert(mutations===0,'close mutated');
 await open();document.querySelector('#dialog').dispatchEvent(new Event('cancel',{cancelable:true}));document.querySelector('#dialog').close();await pending;
 await open();document.querySelector('[data-use-extension]').value=before.assembly.clips[0].extensions[1].id;
 document.querySelector('[data-use-purpose]').value='costume';document.querySelector('[data-use-subject]').value='2';
 await click('[data-use-apply]');await pending;
 const saved=await get(),extensions=saved.assembly.clips[0].extensions;
 assert((extensions[0].references||[]).length===0,'wrong extension modified');
 assert(extensions[1].references[0].purpose==='costume'&&extensions[1].references[0].subject==='2','selected purpose/subject lost');
 assert(extensions[1].prompt==='保留续接正文'&&JSON.stringify(extensions[1].configurations)===JSON.stringify(before.assembly.clips[0].extensions[1].configurations),'transfer changed prompt/settings');
 assert(saved.assembly.runs.length===before.assembly.runs.length&&generations===0,'transfer generated');
 const detail=await library();assert(detail.references.some(r=>r.project===pid&&r.version===asset.version),'library reference missing');assert(detail.used,'recently used missing');
 assert(mutations===1,'duplicate apply');
 // A stale project snapshot must keep the dialog and preserve the project.
 pending=useImageInAssembly(asset,before,signal);await pause();await click('[data-use-apply]');
 await wait(()=>document.querySelector('[data-use-error]')?.textContent);
 assert(document.querySelector('#dialog').open,'conflict closed dialog');assert((await get()).revision===saved.revision,'conflict modified project');
 await click('[data-use-cancel]');await pending;
 let empty=false;try{await useImageInAssembly(asset,{...saved,assembly:{clips:[]}},signal);}catch(e){empty=e.message.includes('添加续接');}assert(empty,'empty target not explained');
 let legacy=false;try{await useImageInAssembly(asset,{...saved,library_usage_version:undefined},signal);}catch(e){legacy=e.message.includes('重启');}assert(legacy,'legacy backend not explained');
 // Exercise the extracted list batch actions and detail timeline via their real pages.
 const root=document.querySelector('main'),listController=new AbortController();
 location.hash='#/assets?q='+encodeURIComponent('隔离服装');
 await mountLibrary(root,location.hash,listController.signal);
 await click('[data-select="'+aid+'"]');await click('[data-batch="favorite"]');
 await wait(()=>root.querySelector('#library-batch')?.hidden);assert((await library()).favorite,'batch favorite not saved');
 await click('[data-select="'+aid+'"]');await click('[data-batch="category"]');
 await wait(()=>document.querySelector('#library-value-cancel'));const revision=(await library()).revision;
 await click('#library-value-cancel');assert((await library()).revision===revision,'cancelled category saved');
 listController.abort();
 await mountDetail(root,q.get('vid'),new URLSearchParams(),signal);
 const player=root.querySelector('.library-player');player.play=async()=>{};
 player.currentTime=0.2;await click('#mark-in');player.currentTime=1;await click('#mark-out');
 assert(root.querySelector('#library-in').value==='0.2'&&root.querySelector('#library-out').value==='1','timeline marks failed');
 await click('#loop-range');assert(root.querySelector('#loop-range').getAttribute('aria-pressed')==='true','loop not enabled');
 player.currentTime=1.2;player.dispatchEvent(new Event('timeupdate'));assert(Math.abs(player.currentTime-0.2)<0.01,'loop did not seek to in mark');
 await click('#loop-range');assert(root.querySelector('#loop-range').getAttribute('aria-pressed')==='false','loop not disabled');
 root.innerHTML='<h1>图片用于视频接续 · 隔离检查</h1>';
 await open();await document.fonts.ready;
 const d=document.querySelector('#dialog');assert(d.scrollWidth<=d.clientWidth+1,'dialog overflows');
 assert(document.querySelector('[data-use-cancel]').getBoundingClientRect().bottom<innerHeight,'cancel unreachable');
 document.body.dataset.check=JSON.stringify({passed:true,width:innerWidth,mutations,generations,checks:['cancel','close','escape','reopen','target','purpose','subject','refs','used','preserve','conflict','empty','legacy','batch-favorite','batch-cancel','media-timeline','layout']});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.stack});}
</script>'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence-dir',required=True);args=parser.parse_args()
    out=Path(args.evidence_dir);out.mkdir(parents=True,exist_ok=True);checks=[]
    AssemblyTests.setUpClass();case=AssemblyTests();case.setUp()
    path=case.root/'transfer.png';Image.new('RGB',(80,120),(70,110,90)).save(path)
    asset=case.s.lib.ingest(path,'隔离服装',{'record_prompt':'不得进入续接正文'})
    video=case.s.lib.ingest(case.silent,'隔离选段视频')
    def application(environ,start_response):
        if environ.get('PATH_INFO')=='/transfer-check':
            start_response('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [PAGE.encode()]
        return case.app(environ,start_response)
    class Quiet(WSGIRequestHandler):
        def log_message(self,*args):pass
    server=make_server('127.0.0.1',0,application,handler_class=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        for width in [1280,760]:
            case.p=case.s.create('图片转入接续 · 隔离检查');case.pid=case.p['id'];case.refresh();case.upload()
            for i in range(2):case.post('extensions',clip=case.p['assembly']['clips'][0]['id'])
            p=case.s.get(case.pid);p['assembly']['clips'][0]['extensions'][1]['prompt']='保留续接正文';case.s.store.save(p,p['revision'])
            result=subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--no-first-run','--disable-background-networking',f'--user-data-dir={out/("profile-"+str(width))}',f'--window-size={width},1000','--virtual-time-budget=20000',f'--screenshot={out/(str(width)+".png")}','--dump-dom',f'http://127.0.0.1:{server.server_port}/transfer-check?pid={case.pid}&aid={asset["id"]}&vid={video["id"]}'],capture_output=True,timeout=45)
            dom=result.stdout.decode('utf-8','replace');(out/f'{width}.html').write_text(dom,encoding='utf-8')
            match=re.search(r'data-check="([^"]+)"',dom);data=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='No completion')
            checks.append(data);print(json.dumps(data,ensure_ascii=False),flush=True)
    finally:
        server.shutdown();server.server_close();case.doCleanups();AssemblyTests.tearDownClass()
        (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)

if __name__=='__main__':main()
