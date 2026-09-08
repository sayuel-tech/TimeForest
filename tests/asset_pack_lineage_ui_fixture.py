"""Real temporary pack import/export API and shared source UI at wide/narrow sizes."""
import argparse
import json
import sys
import threading
from pathlib import Path
from werkzeug.serving import make_server, WSGIRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_asset_origins import OriginTests
from tests.workspace_navigation_ui_fixture import capture
from h3ui.asset_library.service import Library
from h3ui.asset_library.packs import Packs
from h3ui.asset_library.origins import AssetOrigins

SCRIPT=r'''<script type="module">
import {importPack,exportPack} from '/static/studio/pages/asset-library/transfer.js';
import {mountDetail} from '/static/studio/pages/asset-library/detail.js';
const pause=()=>new Promise(r=>setTimeout(r,30));
const wait=async f=>{for(let i=0;i<600;i++){if(f())return;await pause()}throw Error('UI timeout')};
const assert=(v,m)=>{if(!v)throw Error(m)};
const get=async u=>{const r=await fetch(u);if(!r.ok)throw Error(await r.text());return r.json()};
const controller=new AbortController(),root=document.querySelector('#root');
const timer=setTimeout(()=>document.body.dataset.check=JSON.stringify({passed:false,error:'watchdog'}),45000);
try{
 const blob=await (await fetch('/pack-fixture')).blob();
 await importPack(new File([blob],'test.zip'),controller.signal);
 await wait(()=>document.querySelector('#pack-import-confirm')&&!document.querySelector('#pack-import-confirm').disabled);
 assert((await get('/api/v5/library/assets')).total===0,'preview imported assets');
 document.querySelector('#pack-import-confirm').click();
 await wait(()=>document.querySelector('#pack-import-report').textContent.includes('已恢复 2 项'));
 document.querySelector('#pack-import-close').click();
 const items=(await get('/api/v5/library/assets')).items,child=items.find(x=>x.name==='派生作品'),parent=items.find(x=>x.name==='包内原素材');
 assert(child&&parent,'import result absent');
 await mountDetail(root,child.id,new URLSearchParams(),controller.signal);
 await wait(()=>root.querySelector('.asset-origin'));
 assert(!root.querySelector('.asset-origin a[href^="#/p/"]'),'external project linked locally');
 assert(root.querySelector('.asset-origin').textContent.includes('包内原素材'),'mapped source absent');
 const source=root.querySelector('.asset-origin a[href*="'+parent.id+'"]');assert(source,'fixed source link absent');
 assert(source.getAttribute('href').includes('version='),'source version not pinned');
 assert(root.querySelector('.source-production-parameters')&&!root.querySelector('.source-production-parameters').open,'parameters missing/not collapsed');
 root.querySelector('.source-production-parameters').open=true;
 assert(root.querySelector('.asset-origin').textContent.includes('saved-model.safetensors'),'saved parameter missing');
 exportPack(items,controller.signal);
 assert(document.querySelector('[name="lineage"]').checked,'source option default');
 const nativeFetch=window.fetch;let release,requested=false;
 window.fetch=async(url,...args)=>{if(String(url).endsWith('/pack-plan')){requested=true;await new Promise(r=>release=r)}return nativeFetch(url,...args)};
 document.querySelector('#pack-form').requestSubmit();await wait(()=>requested);
 document.querySelector('[name="lineage"]').click();release();await new Promise(r=>setTimeout(r,350));
 assert(document.querySelector('#pack-export').disabled,'stale preview enabled export');window.fetch=nativeFetch;
 document.querySelector('#pack-form').requestSubmit();await wait(()=>!document.querySelector('#pack-export').disabled);
 assert(document.querySelector('#pack-report').textContent.includes('6.3.31'),'format version guidance missing');
 window.fetch=async(url,...args)=>{const response=await nativeFetch(url,...args);if(String(url).endsWith('/pack-plan')){const body=await response.json();delete body.pack_lineage_version;return new Response(JSON.stringify(body),{headers:{'Content-Type':'application/json'}})}return response};
 document.querySelector('#pack-form').requestSubmit();await wait(()=>document.querySelector('#toast').textContent.includes('重启导演台'));
 assert(document.querySelector('#pack-export').disabled,'old server allowed unsupported export');window.fetch=nativeFetch;
 assert(document.documentElement.scrollWidth<=innerWidth+1,'page overflow');
 document.querySelector('#pack-close').click();
 const lineage=root.querySelector('.asset-lineage');if(lineage?.tagName==='DETAILS')lineage.open=true;
 const style=document.createElement('style');style.textContent='*{scroll-behavior:auto!important}';document.head.append(style);
 root.querySelector('.asset-origin').scrollIntoView({block:'start'});await document.fonts.ready;await new Promise(r=>setTimeout(r,500));
 assert((await get('/api/v5/library/assets')).total===2,'export changed assets');
 clearTimeout(timer);document.body.dataset.check=JSON.stringify({passed:true,width:innerWidth,checks:['preview does not import','real import','mapped fixed source','external project quarantined','saved parameters','stale export preview discarded','opt out repreview','old server disabled','no overflow']});
}catch(e){clearTimeout(timer);document.body.dataset.check=JSON.stringify({passed:false,error:e.message,stack:e.stack})}
</script>'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence-dir',required=True);args=parser.parse_args()
    out=Path(args.evidence_dir);out.mkdir(parents=True,exist_ok=True);checks=[]
    OriginTests.setUpClass()
    try:
        for width in [1280,760]:
            case=OriginTests();case.setUp()
            sender=Library(case.root/'sender');packs=Packs(sender)
            from PIL import Image
            image=case.root/'pack.png';Image.new('RGB',(32,32),'green').save(image)
            parent=sender.ingest(image,'包内原素材',provenance=dict(type='local'));m=parent['snapshot']['media'][0]
            origin=dict(type='generated_image',project=case.pid,records=dict(seed=42,snapshot=dict(submode='single',inputs=dict(A=dict(provenance=dict(asset=parent['id'],version=parent['snapshot']['id'],media=m['id'],hash=m['hash']))),settings=dict(steps=19,cfg=2),models=dict(unet='saved-model.safetensors'))))
            child=sender.ingest(image,'派生作品',provenance=origin)
            plan=packs.preview(dict(assets=[dict(asset=a['id']) for a in [child,parent]],workflows=True),AssetOrigins(sender,case.s))
            packs.export(plan,lambda *a:None);raw=(sender.root/'exports'/(plan['token']+'.zip')).read_bytes()
            page='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/studio/style.css"><main id="root"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div>'+SCRIPT
            def app(environ,start_response):
                if environ.get('PATH_INFO') in ('/pack-check','/pack-fixture'):
                    binary=environ['PATH_INFO']=='/pack-fixture';start_response('200 OK',[('Content-Type','application/zip' if binary else 'text/html; charset=utf-8')]);return [raw if binary else page.encode()]
                return case.app(environ,start_response)
            class Quiet(WSGIRequestHandler):
                def log(self,*args,**kwargs):pass
            server=make_server('127.0.0.1',0,app,threaded=True,request_handler=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start()
            try:checks.append(capture(out,'pack-'+str(width),f'http://127.0.0.1:{server.server_port}/pack-check',width))
            finally:server.shutdown();server.server_close();case.doCleanups()
    finally:OriginTests.tearDownClass()
    (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)

if __name__=='__main__':main()
