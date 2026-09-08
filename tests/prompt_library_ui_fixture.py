"""Real isolated library and five workspace UI paths; no generation requests."""
import argparse
import json
import sys
import threading
from pathlib import Path
from werkzeug.serving import make_server,WSGIRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_prompt_library import PromptLibraryTests
from tests.workspace_navigation_ui_fixture import capture
from h3ui.studio_recipes import defaults

SCRIPT=r'''<script type="module">
import {mountPromptLibrary} from '/static/studio/pages/prompt-library/index.js';
import {getMode} from '/static/studio/app/mode-registry.js';
import {api} from '/static/studio/core/api-client.js';
const pause=()=>new Promise(r=>setTimeout(r,30));
const assert=(v,m)=>{if(!v)throw Error(m)};
const wait=async(fn,label)=>{for(let i=0;i<350;i++){if(fn())return;await pause()}throw Error('wait: '+label)};
const root=document.querySelector('#app'),checks=[];let workspace;
const input=(el,text)=>{assert(el,'missing input');el.value=text;el.dispatchEvent(new Event('input',{bubbles:true}));};
try{
 const controller=new AbortController();await mountPromptLibrary(root,controller.signal);
 root.querySelector('[data-new-branch]').click();await wait(()=>document.querySelector('[name="family"]'),'branch modal');
 input(document.querySelector('[name="name"]'),'Wan');input(document.querySelector('[name="family"]'),'wan');document.querySelector('#dialog form').requestSubmit();await wait(()=>!document.querySelector('#dialog').open,'branch saved');await pause();
 root.querySelector('[data-new]').click();await wait(()=>document.querySelector('[name="text"]'),'new prompt');input(document.querySelector('[name="title"]'),'森林中的镜头');input(document.querySelector('[name="text"]'),'从树林中向前行走');document.querySelector('#dialog form').requestSubmit();await wait(()=>!document.querySelector('#dialog').open,'template saved');
 await wait(()=>root.querySelector('[data-entry]'),'entry');root.querySelector('[data-entry]').click();assert(root.querySelector('.prompt-text').textContent.includes('向前行走'),'saved body');
 root.querySelector('[data-edit]').click();await wait(()=>document.querySelector('[name="text"]'),'edit');input(document.querySelector('[name="text"]'),'未保存文字');document.querySelector('[data-cancel]').click();await wait(()=>document.querySelector('.choice-dialog'),'discard question');[...document.querySelectorAll('.choice-dialog button')].find(b=>b.textContent==='放弃修改').click();await wait(()=>!document.querySelector('#dialog').open,'cancelled');
 checks.push('library branch/create/read/edit-cancel');
 const branches=await api('/prompt-library/catalog'),wan=branches.branches.find(b=>b.family==='wan');root.querySelector(`[data-branch="${wan.id}"]`).click();root.querySelector('[data-manage-category]').click();await wait(()=>document.querySelector('#dialog [name="position"]'),'empty branch management');input(document.querySelector('#dialog [name="name"]'),'Wan 系列');document.querySelector('#dialog form').requestSubmit();await wait(()=>!document.querySelector('#dialog').open,'branch renamed');await pause();checks.push('empty model branch can be managed');
 const combo=await api('/prompt-library/entries','POST',{title:'完整声画组合',purpose:'video',branch:'video:general',content:{type:'fields',fields:{prompt:'完整的声画正文',voice:'保留声线',music:'弦乐'},prompt_mode:'full'}});
 controller.abort();
 for(const item of FIXTURE){
   const p=await api('/projects/'+item.id);sessionStorage.setItem('time-forest:position:'+p.id,JSON.stringify({tab:'edit',shot:0}));sessionStorage.setItem('image-page:'+p.id,'edit');
   if(p.kind==='image'){const {mountWorkspace}=await import('/static/studio/app/image-workspace-controller.js');workspace=mountWorkspace(root,p,await api('/image-projects/catalog'));}
   else if(p.kind==='assembly'){const {mountWorkspace}=await import('/static/studio/modes/video-assembly/workspace.js');workspace=mountWorkspace(root,p,await api('/assembly/catalog'));root.querySelector('[data-next]').click();root.querySelector('[data-extension]').click();}
   else{const {mountWorkspace}=await import('/static/studio/app/workspace-controller.js');const definition=getMode(p.mode);workspace=mountWorkspace(root,p,await api('/catalog'),definition,await definition.load());}
   await wait(()=>root.querySelector('.prompt-tools'),'tools '+p.mode);
   const text=()=>root.querySelector('textarea[data-field="prompt"],#image-prompt,textarea[data-prompt]');
   input(text(),'本轮 '+p.mode);const old=text().value;
   const tools=()=>(text().closest('label.field')||text()).nextElementSibling;
   tools().querySelector('[data-tool="expand"]').click();await wait(()=>document.querySelector('[data-expanded]'),'expand');input(document.querySelector('[data-expanded]'),'应取消');document.querySelector('#dialog [data-cancel]').click();await wait(()=>!document.querySelector('#dialog').open,'cancel');await pause();assert(text().value===old,'cancel changed '+p.mode);
   tools().querySelector('[data-tool="expand"]').click();await wait(()=>document.querySelector('[data-expanded]'),'expand2');input(document.querySelector('[data-expanded]'),'采用 '+p.mode);document.querySelector('#dialog [data-apply]').click();await wait(()=>!document.querySelector('#dialog').open,'applied');await pause();assert(text().value==='采用 '+p.mode,'apply changed wrong field '+p.mode);
   if(p.mode==='image_story'){
     tools().querySelector('[data-tool="pick"]').click();await wait(()=>document.querySelector('.prompt-picker [data-branch="video:general"]'),'picker');document.querySelector('.prompt-picker [data-branch="video:general"]').click();await wait(()=>[...document.querySelectorAll('.prompt-picker [data-entry]')].some(b=>b.textContent.includes('森林中的镜头')),'picker entry');[...document.querySelectorAll('.prompt-picker [data-entry]')].find(b=>b.textContent.includes('森林中的镜头')).click();document.querySelector('[data-use]').click();await wait(()=>document.querySelector('.choice-dialog'),'apply choice');[...document.querySelectorAll('.choice-dialog button')].find(b=>b.textContent==='替换正文').click();await wait(()=>text().value==='从树林中向前行走','library applied');assert(workspace.session.project.segments[0].prompt_sources.prompt.version===1,'source version');checks.push('library picker preview/replace/fixed version');
   }
   if(p.mode==='text_story'||p.kind==='image'){
     const before=text().value;tools().querySelector('[data-tool="pick"]').click();await wait(()=>document.querySelector('.prompt-picker [data-purpose="video"]'),'combo picker');document.querySelector('.prompt-picker [data-purpose="video"]').click();document.querySelector('.prompt-picker [data-branch="video:general"]').click();await wait(()=>document.querySelector(`.prompt-picker [data-entry="${combo.id}"]`),'combo entry');document.querySelector(`.prompt-picker [data-entry="${combo.id}"]`).click();document.querySelector('[data-use]').click();await wait(()=>document.querySelector('[data-patch="prompt"]'),'field confirmation');
     if(p.kind==='image'){assert(document.querySelector('#dialog').textContent.includes('不支持：'),'unsupported fields not explained');document.querySelector('#dialog [data-cancel]').click();await wait(()=>!document.querySelector('#dialog').open,'unsupported cancel');assert(text().value===before,'cancel changed image');checks.push('unsupported fields explained/cancel unchanged');}
     else{document.querySelector('[data-patch="music"]').checked=false;document.querySelector('#dialog [data-apply]').click();await wait(()=>text().value==='完整的声画正文','combo applied');assert(workspace.session.project.segments[0].prompt_mode==='full','body mode not changed');assert(workspace.session.project.segments[0].voice==='保留声线','voice missing');assert(workspace.session.project.segments[0].music!=='弦乐','unchecked music overwritten');checks.push('explicit field bundle/full mode/unchecked fields preserved');}
   }
   let done=false,error;workspace.saveBeforeLeave().then(()=>done=true).catch(e=>{error=e;done=true});
   for(let i=0;i<300&&!done;i++){const b=[...document.querySelectorAll('.choice-dialog button')].find(b=>b.textContent==='确认应用');if(b)b.click();await pause();}
   if(error)throw error;assert(done,'save timeout '+p.mode);assert(!workspace.session.dirty,'dirty after save '+p.mode);
   const rows=await api('/prompt-library/entries?purpose='+(p.kind==='image'?'image':'video'));assert(rows.items.some(r=>r.source.project===p.id),'save did not collect '+p.mode);
   if(p.mode==='text_story'){const count=rows.total;tools().querySelector('[data-tool="favorite"]').click();await wait(()=>!tools().querySelector('[data-tool="favorite"]').disabled,'favorite saved record');const after=await api('/prompt-library/entries?purpose=video');assert(after.total===count&&after.items.some(r=>r.source.project===p.id&&r.favorite),'favorite duplicated instead of marking');checks.push('favorite saved record without duplicate');}
   checks.push(p.mode+': common tools/cancel/apply/real save/auto collect');workspace.dispose();workspace=null;
 }
 const end=new AbortController();root.className='page';await mountPromptLibrary(root,end.signal);
 root.querySelector('[data-entry]').click();assert(document.documentElement.scrollWidth<=innerWidth+1,'page horizontal overflow');await document.fonts.ready;
 document.body.dataset.check=JSON.stringify({passed:true,width:innerWidth,checks});
}catch(e){workspace?.dispose();document.body.dataset.check=JSON.stringify({passed:false,error:e.message,stack:e.stack,checks})}
</script>'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--evidence-dir',required=True);args=parser.parse_args()
    out=Path(args.evidence_dir);out.mkdir(parents=True,exist_ok=True);checks=[]
    for width in (1280,760):
        case=PromptLibraryTests();case.setUp();items=[]
        for mode in ('swap','image_story','text_story'):
            p=case.st.create(mode,'UI '+mode,5)
            if not p['segments']:
                from h3ui.studio_story import storyboard
                p['segments']=[case.st.new_segment(x) for x in storyboard(5)];p=case.st.store.save(p,p['revision'])
            items.append(p)
        items.append(case.app.config['IMAGE_STUDIO'].create('图片UI','text'))
        ext=dict(id='ext',prompt='继续',seconds=5,recipe='dance_split',configurations={k:defaults(k) for k in ('dance_split','official_image')},seed_mode='random',seed='0',sound='native',references=[])
        def init(p):p['assembly']['clips']=[dict(id='clip',name='源视频',start=0,end=2,meta=dict(duration=2,width=160,height=96,fps=24),provenance=dict(type='local'),file=str(case.s.store.directory(case.pid)/'fake.mp4'),extensions=[ext])]
        case.s.store.mutate(case.pid,init);items.append(case.s.snapshot(case.pid))
        page='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/studio/style.css"><main id="app" class="page"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div><script>const FIXTURE='+json.dumps([dict(id=p['id']) for p in items])+';</script>'+SCRIPT
        def app(environ,start):
            if environ['PATH_INFO']=='/prompt-check':start('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [page.encode()]
            return case.app(environ,start)
        class Quiet(WSGIRequestHandler):
            def log(self,*a,**k):pass
        server=make_server('127.0.0.1',0,app,threaded=True,request_handler=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:checks.append(capture(out,'prompts-'+str(width),f'http://127.0.0.1:{server.server_port}/prompt-check',width))
        finally:server.shutdown();server.server_close();case.doCleanups()
    (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)
if __name__=='__main__':main()
