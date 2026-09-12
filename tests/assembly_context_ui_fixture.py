"""Q5b real temporary API/track source, synthetic candidates and fake export only."""
import argparse, html, json, re, subprocess, threading, shutil
from unittest.mock import patch
from pathlib import Path
import sys
from wsgiref.simple_server import make_server, WSGIRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_video_assembly_track import TrackTests
from h3ui.video_assembly import media
from tests.uiux_browser_capture import capture

PAGE=r'''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="/static/studio/style.css"><main id="root"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div>
<script type="module">
import {mountWorkspace} from '/static/studio/modes/video-assembly/workspace.js';
const root=document.querySelector('#root'),pid=new URLSearchParams(location.search).get('pid');
const pause=()=>new Promise(r=>setTimeout(r,40)),get=()=>fetch('/api/v5/projects/'+pid).then(r=>r.json());
const assert=(v,m)=>{if(!v)throw Error(m)};
async function wait(fn){for(let i=0;i<400;i++){if(await fn())return;await pause()}throw Error('Timed out')}
const click=async s=>{const el=root.querySelector(s)||document.querySelector(s);assert(el&&!el.disabled,'Unavailable '+s);el.click();await pause()};
let workspace;
try{
 document.body.classList.add('tf-experience');
 const initial=await get(),catalog=await fetch('/api/v5/assembly/catalog').then(r=>r.json());workspace=mountWorkspace(root,initial,catalog);
 const settled=()=>!workspace.session.working;
 const eid=initial.assembly.clips[0].extensions[0].id,key='extension:'+eid;
 assert(root.querySelectorAll('[data-track]').length===1,'unselected candidate on track');
 await click('[data-step="1"]');await click('[data-extension]');await click('[data-select]');await wait(settled);
 assert(root.querySelectorAll('[data-track]').length===2,'selected candidate absent from track');
 assert(root.querySelector('[data-candidate-identity]').textContent==='正在查看：候选 1 · 已选用：候选 1','candidate identity');
 const sourceLabel=root.querySelector('[data-continuation-source]').textContent;
 assert(sourceLabel.includes('使用终点'),'first continuation source');
 assert(root.querySelector('[data-track="'+key+'"]').textContent.includes('已选续接'),'selected slot label');
 assert(root.querySelector('[data-select]').disabled,'selected result still offers duplicate selection');
 root.querySelector('[data-select]').click();await wait(settled);assert(root.querySelectorAll('[data-track]').length===2,'reselect duplicates track');
 await click('[data-move="-1"]');await wait(settled);
 assert((await get()).assembly.track_order[0]===key,'arrow did not persist independent order');
 await click('[data-reload]');await wait(settled);
 assert(root.querySelector('[data-track]').dataset.track===key,'reload lost order');
 assert(root.querySelector('[data-continuation-source]').textContent===sourceLabel,'reorder changed generation source label');
 await click('[data-continue]');await wait(settled);
 assert(root.querySelector('.assembly-content h2').textContent.includes('续写 2'),'new continuation identity');
 assert(root.querySelector('[data-continuation-source]').textContent.includes('续写 1（已选结果）'),'continued source identity');
 const actualSource=await fetch('/fixture-source').then(r=>r.json());assert(actualSource.origin.candidate==='result','new continuation uses wrong parent');
 assert(root.querySelectorAll('[data-track]').length===2,'unselected continuation entered export track');
 await click('[data-remove-extension]');await click('#yes');await wait(settled);
 await click('[data-extension="'+eid+'"]');
 await click('[data-step="0"]');
 assert(root.querySelector('.assembly-player').src.includes('result.mp4'),'selected track previews wrong source');
 await click('[data-step="1"]');await click('[data-next]');
 assert(root.querySelector('.assembly-content ol li').textContent.includes('续接'),'export review differs from track');
 assert(root.querySelector('[data-export-summary]').textContent.includes('2个轨道片段'),'export count');
 await click('[data-export]');await wait(settled);
 await wait(async()=>(await get()).assembly.runs.some(r=>r.kind==='export'&&r.state==='success'));
 const saved=await get(),exported=saved.assembly.runs.find(r=>r.kind==='export');
 assert(exported.snapshot.parts[0].candidate==='result','real export ignores track order');
 assert(exported.snapshot.parts.length===2,'export duplicates selected result');
 await click('[data-reload]');await wait(settled);await click('[data-step="0"]');
 await wait(()=>root.querySelector('.assembly-player').readyState>=1);
 await click('[data-step="1"]');
 assert(root.querySelector('[data-candidate-identity]').textContent.includes('已选用：候选 1'),'final identity');
 assert(!root.querySelector('[data-error]').textContent.trim(),'unexpected UI error');
 assert(document.documentElement.scrollWidth<=innerWidth+1,'horizontal overflow');
 document.body.dataset.check=JSON.stringify({passed:true,slots:2,first:key,duration:exported.report.duration,width:innerWidth});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.message,stack:e.stack})}
// Keep media visible for the screenshot; the isolated browser exits immediately.
</script>'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence-dir',required=True);args=parser.parse_args()
    out=Path(args.evidence_dir);out.mkdir(parents=True,exist_ok=True)
    TrackTests.setUpClass();checks=[]
    try:
        for width in [1366,430]:
            case=TrackTests();case.setUp();eid=case.extension()['id'];case.candidate(eid)
            def app(environ,start_response):
                if environ['PATH_INFO']=='/track-check':
                    start_response('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [PAGE.encode()]
                if environ['PATH_INFO']=='/fixture-source':
                    case.refresh();source=case.s.source(case.p,case.p['assembly']['clips'][0]['extensions'][-1]['id'])
                    start_response('200 OK',[('Content-Type','application/json')]);return [json.dumps(source).encode()]
                return case.app(environ,start_response)
            class Quiet(WSGIRequestHandler):
                def log_message(self,*args):pass
            server=make_server('127.0.0.1',0,app,handler_class=Quiet)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                def fake_assemble(parts,directory,output,*args):
                    file=directory/'fake-export.mp4';shutil.copy2(case.sound,file)
                    return str(file),media.inspect(file)
                with patch.object(media,'assemble',side_effect=fake_assemble):
                    dom=capture(f'http://127.0.0.1:{server.server_port}/track-check?pid={case.pid}',out/f'{width}.png',width,768 if width==1366 else 900)
                (out/f'{width}.html').write_text(dom,encoding='utf-8')
                match=re.search(r'data-check="([^"]+)"',dom)
                check=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='missing completion marker')
                checks.append(check);print(json.dumps(check,ensure_ascii=False),flush=True)
            finally:server.shutdown();server.server_close();case.doCleanups()
    finally:TrackTests.tearDownClass()
    (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    assert all(c['passed'] for c in checks)

if __name__=='__main__':main()
