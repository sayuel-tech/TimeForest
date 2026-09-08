"""Real temporary library API, actual detail/picker UI, no engine or generation."""
import argparse
import json
import sys
import threading
from pathlib import Path
from werkzeug.serving import make_server, WSGIRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_asset_origins import OriginTests
from tests.workspace_navigation_ui_fixture import capture

SCRIPT=r'''<script type="module">
import {mountDetail} from '/static/studio/pages/asset-library/detail.js';
import {pickLibraryAsset} from '/static/studio/features/asset-picker/index.js';
const pause=()=>new Promise(r=>setTimeout(r,30));
const wait=async f=>{for(let i=0;i<500;i++){if(f())return;await pause()}throw Error('UI timeout')};
const assert=(v,m)=>{if(!v)throw Error(m)};
const get=async u=>{const r=await fetch(u);if(!r.ok)throw Error(await r.text());return r.json()};
const click=async s=>{await wait(()=>document.querySelector(s)&&!document.querySelector(s).disabled);document.querySelector(s).click();await pause()};
const q=new URLSearchParams(location.search),aid=q.get('asset'),root=document.querySelector('#root'),controller=new AbortController();
try{
 const before=await get('/api/v5/library/assets/'+aid),first=before.snapshot.media[0],second=before.snapshot.media[1];
 const mount=()=>mountDetail(root,aid,new URLSearchParams({media:first.id}),controller.signal);
 await mount();await wait(()=>root.querySelector('.asset-origin'));
 assert(root.querySelector('.asset-origin').textContent.includes('制作项目'),'source project missing');
 const source=root.querySelector('.asset-origin a[href^="#/p/"]');assert(source,'source project link missing');
 const project=await get('/api/v5/projects/'+source.getAttribute('href').slice(4));assert(project.name==='制作项目','link targets wrong project');
 source.click();assert(location.hash===source.getAttribute('href'),'source link not navigable');
 assert(!root.querySelector('.source-production-parameters').open,'parameters not collapsed');
 root.querySelector('.source-production-parameters').open=true;assert(root.querySelector('.asset-origin').textContent.includes('custom.safetensors'),'saved model not shown');
 await click('[data-media="'+second.id+'"]');await wait(()=>root.querySelector('.asset-origin')?.textContent.includes('未记录来源项目'));
 assert(!root.querySelector('.source-production-parameters'),'alternate stole primary parameters');
 // A delayed origin response may not replace the currently selected media.
 const nativeFetch=window.fetch;let release,late;
 window.fetch=async (url,...args)=>{if(String(url).includes('/origin?')&&String(url).includes(first.id)){late=true;await new Promise(r=>release=r)}return nativeFetch(url,...args)};
 await click('[data-media="'+first.id+'"]');await wait(()=>late);
 await click('[data-media="'+second.id+'"]');await wait(()=>root.querySelector('.asset-origin')?.textContent.includes('未记录来源项目'));
 release();await pause();await pause();window.fetch=nativeFetch;
 assert(root.querySelector('.asset-origin').textContent.includes('未记录来源项目'),'late origin replaced current media');
 // Saving asset notes cannot alter immutable provenance.
 const name=root.querySelector('[name="name"]');name.value='已修改资料';name.dispatchEvent(new Event('input',{bubbles:true}));
 await click('button[form="library-editor-form"]');await wait(()=>root.querySelector('#library-save-state')?.textContent==='资料已保存');
 const saved=await get('/api/v5/library/assets/'+aid);assert(JSON.stringify(saved.snapshot.media[0].provenance)===JSON.stringify(first.provenance),'notes changed provenance');
 const promise=pickLibraryAsset({kind:'image',multiple:true,signal:controller.signal});
 await wait(()=>document.querySelector('[data-preview="'+aid+'"]'));
 const preview=document.querySelector('[data-preview="'+aid+'"]');preview.open=true;
 await wait(()=>preview.querySelector('.asset-origin'));
 assert(document.querySelector('.picker-apply').disabled,'preview selected asset');
 await click('[data-pick="'+aid+'"]');assert(!document.querySelector('.picker-apply').disabled,'selection missing');
 await click('.picker-cancel');assert(await promise===null,'cancel returned selected assets');
 // Selection stays pinned to the displayed version even if notes change meanwhile.
 const oldScope=document.querySelector('.library-picker');const choose=pickLibraryAsset({kind:'image',signal:controller.signal});await wait(()=>document.querySelector('#dialog').open&&document.querySelector('.library-picker')!==oldScope&&document.querySelector('[data-pick="'+aid+'"]'));
 await fetch('/api/v5/library/assets/'+aid,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:saved.revision,changes:{name:'后来的版本'}})});
 await click('[data-pick="'+aid+'"]');const chosen=await choose;assert(chosen.snapshot.id===saved.snapshot.id,'selection silently chose newer version');
 // Shared detail opens the exact selected media in an old version.
 await mountDetail(root,aid,new URLSearchParams({version:before.snapshot.id,media:first.id}),controller.signal);
 await wait(()=>root.querySelector('.source-production-parameters'));
 root.querySelector('.source-production-parameters').open=true;
 assert(root.querySelector('[name="name"]').disabled,'historical notes editable');
 assert(document.documentElement.scrollWidth<=innerWidth+1,'horizontal overflow');
 const style=document.createElement('style');style.textContent='*{scroll-behavior:auto!important}';document.head.append(style);root.querySelector('.asset-origin').scrollIntoView({block:'start'});await document.fonts.ready;await new Promise(r=>setTimeout(r,500));
 document.body.dataset.check=JSON.stringify({passed:true,width:innerWidth,checks:['project link and saved fields','exact alternate/version','late response','notes save keeps origin','preview does not choose','multiple cancel','fixed selection after update','historical read-only','no overflow']});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.message,stack:e.stack})}
</script>'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence-dir',required=True);args=parser.parse_args()
    out=Path(args.evidence_dir);out.mkdir(parents=True,exist_ok=True);checks=[]
    OriginTests.setUpClass()
    try:
        for width in [1280,760]:
            case=OriginTests();case.setUp()
            p=case.c.post('/api/v5/projects',json=dict(mode='image_assets',name='制作项目')).get_json()
            item=case.asset(dict(type='generated_image',project=p['id'],actual_prompt='树林中的人物',records=dict(seed=0,snapshot=dict(submode='text',settings=dict(steps=19,cfg=2),models=dict(unet='custom.safetensors')))))
            item=case.asset(dict(type='local'),item['id'],item['revision'])
            page='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/studio/style.css"><main id="root"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div>'+SCRIPT
            def app(environ,start_response):
                if environ.get('PATH_INFO')=='/origin-check':
                    start_response('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [page.encode()]
                return case.app(environ,start_response)
            class Quiet(WSGIRequestHandler):
                def log(self,*args,**kwargs):pass
            server=make_server('127.0.0.1',0,app,threaded=True,request_handler=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start()
            try:checks.append(capture(out,'origins-'+str(width),f'http://127.0.0.1:{server.server_port}/origin-check?asset={item["id"]}',width))
            finally:server.shutdown();server.server_close();case.doCleanups()
    finally:OriginTests.tearDownClass()
    (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)


if __name__=='__main__':main()
