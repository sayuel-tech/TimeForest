"""Read-only source disclosure in real workspace/API, using synthetic library videos."""
import argparse,html,json,re,subprocess,threading,sys
from pathlib import Path
from wsgiref.simple_server import make_server,WSGIRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests import test_video_source_parameters as source_tests

PAGE=r'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="/static/studio/style.css"><main id="root"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div>
<script type="module">
import {mountWorkspace} from '/static/studio/modes/video-assembly/workspace.js';
const root=document.querySelector('#root'),pid=new URLSearchParams(location.search).get('pid');
const pause=()=>new Promise(r=>setTimeout(r,60)),assert=(v,m)=>{if(!v)throw Error(m)};
let posts=0;const request=fetch.bind(window);window.fetch=(url,options)=>{if(options?.method==='POST')posts++;return request(url,options)};
const get=()=>fetch('/api/v5/projects/'+pid).then(r=>r.json());
const click=async s=>{const el=document.querySelector(s);assert(el,'Missing '+s);el.click();await pause()};
try{
const before=await get(),catalog=await fetch('/api/v5/assembly/catalog').then(r=>r.json()),workspace=mountWorkspace(root,before,catalog);
await click('[data-property-tab="source"]');
const details=root.querySelector('.source-production-parameters');assert(details&&!details.open,'source details not initially collapsed');
await click('.source-production-parameters summary');assert(details.open,'cannot expand parameters');
assert(details.textContent.includes('folder/model.safetensors')&&details.textContent.includes('总采样步数')&&details.textContent.includes('saved-lora.safetensors'),'saved settings missing');
assert(!details.querySelector('input,select,textarea'),'source records are editable');
assert(!workspace.session.dirty&&posts===0,'reading parameters mutated project');
await click('[data-track="clip:'+before.assembly.clips[1].id+'"]');
assert(!root.querySelector('.source-production-parameters'),'local video inherited unrelated settings');
await click('[data-track="clip:'+before.assembly.clips[0].id+'"]');await click('[data-property-tab="source"]');await click('.source-production-parameters summary');
assert(JSON.stringify((await get()).assembly)===JSON.stringify(before.assembly),'source disclosure changed saved configuration');
assert(root.querySelector('#property-source').scrollWidth<=root.querySelector('#property-source').clientWidth+1,'source fields overflow');
assert(document.documentElement.scrollWidth<=innerWidth+1,'page overflow');
document.body.dataset.check=JSON.stringify({passed:true,width:innerWidth,posts,collapsedByDefault:true,localEmpty:true});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.message,stack:e.stack})}
</script>'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence-dir',required=True);args=parser.parse_args()
    out=Path(args.evidence_dir);out.mkdir(parents=True,exist_ok=True);checks=[]
    cls=source_tests.SourceParameterTests;cls.setUpClass()
    try:
        for width in [1280,760]:
            case=cls();case.setUp()
            lib=case.s.lib
            case.import_asset(lib.ingest(case.sound,'带记录的视频',provenance=source_tests.origin()))
            case.import_asset(lib.ingest(case.silent,'无记录的视频'))
            def app(environ,start_response):
                if environ['PATH_INFO']=='/source-check':
                    start_response('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [PAGE.encode()]
                return case.app(environ,start_response)
            class Quiet(WSGIRequestHandler):
                def log_message(self,*args):pass
            server=make_server('127.0.0.1',0,app,handler_class=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                result=subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--no-first-run','--disable-background-networking',f'--user-data-dir={out/("profile-"+str(width))}',f'--window-size={width},1000','--virtual-time-budget=15000',f'--screenshot={out/(str(width)+".png")}','--dump-dom',f'http://127.0.0.1:{server.server_port}/source-check?pid={case.pid}'],capture_output=True,timeout=35)
                dom=result.stdout.decode('utf-8','replace');(out/f'{width}.html').write_text(dom,encoding='utf-8')
                match=re.search(r'data-check="([^"]+)"',dom);check=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='no completion marker')
                checks.append(check);print(json.dumps(check,ensure_ascii=False),flush=True)
            finally:server.shutdown();server.server_close();case.doCleanups()
    finally:cls.tearDownClass()
    (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    assert all(c['passed'] for c in checks)

if __name__=='__main__':main()
