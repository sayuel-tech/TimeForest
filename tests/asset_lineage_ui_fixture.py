"""Expand actual detail/picker lineage through temporary real API, no generation."""
import argparse
import json
import sys
import threading
from pathlib import Path
from werkzeug.serving import make_server, WSGIRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_runtime_lineage import RuntimeLineageTests as LineageTests
from tests.workspace_navigation_ui_fixture import capture

SCRIPT=r'''<script type="module">
import {mountDetail} from '/static/studio/pages/asset-library/detail.js';
import {pickLibraryAsset} from '/static/studio/features/asset-picker/index.js';
const pause=()=>new Promise(r=>setTimeout(r,30));
const wait=async f=>{for(let i=0;i<450;i++){if(f())return;await pause()}throw Error('UI timeout')};
const assert=(v,m)=>{if(!v)throw Error(m)};
const q=new URLSearchParams(location.search),aid=q.get('asset'),kind=q.get('kind'),base=q.get('base'),root=document.querySelector('#root');
const get=async u=>{const r=await fetch(u);if(!r.ok)throw Error(await r.text());return r.json()};
setTimeout(()=>{if(!document.body.dataset.check)document.body.dataset.check=JSON.stringify({passed:false,error:'watchdog'})},25000);
try{
 const before=await get('/api/v5/library/assets/'+aid),signal=new AbortController().signal;
 await mountDetail(root,aid,new URLSearchParams(),signal);
 await wait(()=>root.querySelector('.asset-lineage'));
 const chain=root.querySelector('.asset-lineage');assert(!chain.open,'lineage must start collapsed');
 chain.querySelector('summary').click();assert(chain.open,'cannot expand lineage');
 assert(chain.querySelectorAll('ol > li').length===2,'full two-edge chain missing');
 assert(chain.textContent.includes(kind==='image'?'制作底图 A':'视频承接自'),'wrong relation labels');
 const upstream=chain.querySelector('a[href^="#/p/"]');assert(upstream,'upstream project link missing');
 const url=upstream.getAttribute('href');assert(url.includes('origin_run='+(kind==='image'?'r1':kind==='assembly'?'P11':'p1')),'not exact source record');
 assert(url.includes('origin_asset='+aid),'return to starting media missing');
 upstream.click();assert(location.hash===url,'source link not navigable');
 const fixed=chain.querySelector('a[href^="#/assets/"]');assert(fixed?.getAttribute('href').includes('media='),'fixed parent media missing');
 let resolved=false;
 const picked=pickLibraryAsset({kind:'image',signal}).then(value=>{resolved=true;return value});
 await wait(()=>document.querySelector('.library-pick-entry details'));
 for(const entry of document.querySelectorAll('.library-pick-entry')){
   entry.querySelector('details').open=true;
 }
 await wait(()=>[...document.querySelectorAll('[data-preview="'+aid+'"] .asset-origin .asset-lineage')].length);
 const preview=document.querySelector('[data-preview="'+aid+'"] .asset-origin .asset-lineage');preview.querySelector('summary').click();
 assert(preview.open&&!resolved,'preview unexpectedly selected the asset');
 assert(document.documentElement.scrollWidth<=innerWidth+1,'picker overflow');
 document.querySelector('.picker-cancel').click();assert(await picked===null,'cancel returned selection');
 assert(JSON.stringify(await get('/api/v5/library/assets/'+aid))===JSON.stringify(before),'read-only browsing wrote asset');
 assert(document.documentElement.scrollWidth<=innerWidth+1,'detail overflow');
 await mountDetail(root,base,new URLSearchParams(),signal);
 await wait(()=>root.querySelector('[data-descendant-more]'));
 const nativeFetch=window.fetch;
 window.fetch=async (url,...args)=>String(url).includes('/descendants?')?new Response(JSON.stringify({error:'隔离读取失败'}),{status:503,headers:{'Content-Type':'application/json'}}):nativeFetch(url,...args);
 const downstream=root.querySelector('[data-descendant-more]').closest('details');
 downstream.querySelector('summary').click();
 await wait(()=>downstream.querySelector('[data-descendant-error]').textContent.includes('隔离读取失败'));
 window.fetch=nativeFetch;downstream.querySelector('[data-descendant-more]').click();
 await wait(()=>downstream.querySelector('[data-descendant-results] a'));
 assert(downstream.querySelector('a[href^="#/assets/'+aid+'?"]'),'reverse result missing');
 assert(downstream.textContent.includes('本次范围已读取完毕'),'completion ambiguous');
 assert(document.documentElement.scrollWidth<=innerWidth+1,'downstream overflow');
 const projectResults=root.querySelector('[data-descendant-scope="projects"]');
 assert(projectResults&&!projectResults.open,'project results must begin collapsed');
 projectResults.querySelector('summary').click();
 await wait(()=>projectResults.querySelector('[data-descendant-results] a'));
 const link=projectResults.querySelector('a[href^="#/p/"]');
 assert(link?.href.includes('origin_run='+(kind==='image'?'r1':kind==='assembly'?'P11':'p1')),'uncollected result link incorrect');
 assert(link.href.includes('origin_asset='+base),'return to starting asset absent');
 link.click();assert(location.hash===link.getAttribute('href'),'project result link not navigable');
 assert(projectResults.textContent.includes('本次范围已读取完毕'),'project result scan incomplete');
 assert(document.documentElement.scrollWidth<=innerWidth+1,'project results overflow');
 projectResults.scrollIntoView({block:'start'});await document.fonts.ready;await new Promise(r=>setTimeout(r,400));
 document.body.dataset.check=JSON.stringify({passed:true,kind,width:innerWidth,checks:['real origin API','detail and picker expand','exact upstream/return links','fixed parent link','preview does not choose','read-only','downstream error/retry and fixed link','uncollected project results and exact navigation','no overflow']});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.message,stack:e.stack})}
</script>'''


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence-dir',required=True);args=parser.parse_args()
    out=Path(args.evidence_dir);out.mkdir(parents=True,exist_ok=True);checks=[]
    LineageTests.setUpClass()
    try:
        for kind in ('swap','image_story','text_story','assembly','image'):
            for width in (1280,760):
                case=LineageTests();case.setUp()
                if kind=='assembly':
                    base,item=case.assembly_chain()
                    def finish(p):
                        for run in p['assembly']['runs']:run.update(state='success',kind='generate',created=1)
                    case.st.store.mutate(case.pid,finish)
                elif kind=='image':_,_,base,item,_=case.image_chain()
                else:
                    _,base,origin=case.video_chain(kind);item=case.asset(origin)
                page='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/studio/style.css"><main id="root"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div>'+SCRIPT
                def app(environ,start_response):
                    if environ.get('PATH_INFO')=='/lineage-check':
                        start_response('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [page.encode()]
                    return case.app(environ,start_response)
                class Quiet(WSGIRequestHandler):
                    def log(self,*args,**kwargs):pass
                server=make_server('127.0.0.1',0,app,threaded=True,request_handler=Quiet)
                threading.Thread(target=server.serve_forever,daemon=True).start()
                try:checks.append(capture(out,kind+'-'+str(width),f'http://127.0.0.1:{server.server_port}/lineage-check?asset={item["id"]}&kind={kind}&base={base["id"]}',width))
                finally:server.shutdown();server.server_close();case.doCleanups()
    finally:LineageTests.tearDownClass()
    (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)


if __name__=='__main__':main()
