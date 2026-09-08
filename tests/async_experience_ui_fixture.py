"""Five real controllers with delayed browser transport; no AI generation or production data."""
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests import result_experience_ui_fixture as base

class NoBootstrap(base.Handler):
    def send(self,status,body,content_type='application/json; charset=utf-8'):
        if content_type.startswith('text/html'):
            body=re.sub(rb'<script type="module" src="/static/studio/app.js[^>]+></script>',b'',body)
        super().send(status,body,content_type)
base.Handler=NoBootstrap

base.SCRIPT=r'''<script type="module">
import * as ui from '/static/studio/ui/primitives.js';
import {pickLibraryAsset} from '/static/studio/features/asset-picker/index.js';
const sleep=ms=>new Promise(r=>setTimeout(r,ms)),assert=(v,m)=>{if(!v)throw Error(m)};
const wait=async fn=>{for(let i=0;i<400;i++){if(await fn())return;await sleep(30)}throw Error('UI wait: '+fn)};
const click=async s=>{await wait(()=>document.querySelector(s)&&!document.querySelector(s).disabled);document.querySelector(s).click();await sleep(40)};
const q=new URLSearchParams(location.search),assembly=q.has('assembly'),pid=assembly?q.get('pid'):location.hash.split('/p/')[1];
const originalFetch=window.fetch.bind(window),root=document.querySelector('#app')||document.querySelector('#root');
let hold=false,rejectRead=false,held=null,saveCount=0,holdCatalog=false,catalogHeld=null;
window.fetch=async(url,opts={})=>{
 if(String(url)==='/api/v5/projects/'+pid&&(!opts.method||opts.method==='GET')){
   if(rejectRead){rejectRead=false;throw new TypeError('isolated dropped connection');}
   if(hold){hold=false;const response=await originalFetch(url,opts);return await new Promise(resolve=>held=()=>resolve(response));}
 }
 if(String(url)==='/api/v5/library/catalog'&&holdCatalog){holdCatalog=false;const response=await originalFetch(url,opts);return await new Promise(resolve=>catalogHeld=()=>resolve(response));}
 if(opts.method==='POST'&&(String(url).endsWith('/change-plan')||String(url).endsWith('/save')))saveCount++;
 return originalFetch(url,opts);
};
const get=()=>originalFetch('/api/v5/projects/'+pid).then(r=>r.json());
let workspace;
try{
 const initial=await get(),image=initial.kind==='image',mode=assembly?'video_assembly':initial.mode;
 const mount=async p=>{
   if(assembly){const {mountWorkspace}=await import('/static/studio/modes/video-assembly/workspace.js');return mountWorkspace(root,p,await originalFetch('/api/v5/assembly/catalog').then(r=>r.json()));}
   if(image){const {mountWorkspace}=await import('/static/studio/app/image-workspace-controller.js');return mountWorkspace(root,p,await originalFetch('/api/v5/image-projects/catalog').then(r=>r.json()));}
   const {getMode}=await import('/static/studio/app/mode-registry.js');const definition=getMode(mode),view=await definition.load(),{mountWorkspace}=await import('/static/studio/app/workspace-controller.js');return mountWorkspace(root,p,await originalFetch('/api/v5/catalog').then(r=>r.json()),definition,view);
 };
 workspace=await mount(initial);
 if(assembly){await click('[data-workspace-step="1"]');await click('[data-extension]');}
 if(mode==='swap'){await click('[data-workspace-step="edit"]');const choice=root.querySelector('[data-swap-mode]');choice.value='custom';choice.dispatchEvent(new Event('change',{bubbles:true}));await click('#save');}
 const selector=image?'#image-prompt':assembly?'[data-prompt]':mode==='swap'?'textarea[data-field="swap_custom_prompt"]':'textarea[data-field="prompt"]';
 await wait(()=>root.querySelector(selector));
 // A real poll starts first; typing after dispatch must survive receipt.
 document.activeElement?.blur();hold=true;held=null;await wait(()=>held);
 const field=root.querySelector(selector);field.focus();field.value='异步保留 '+mode;field.dispatchEvent(new Event('input',{bubbles:true}));held();held=null;await sleep(100);
 assert(root.querySelector(selector)===field&&field.value==='异步保留 '+mode,'poll replaced rendered editor');
 const saveSelector=image?'#image-save':assembly?'.savebar [data-save]':'#save';
 saveCount=0;const save=root.querySelector(saveSelector);save.click();save.click();await wait(()=>!workspace.session.dirty&&!workspace.session.working&&!workspace.session.actionPending);
 assert(saveCount===1,'double click submitted '+saveCount+' plans');
 const saved=await get(),text=image?saved.tasks[0].prompt:assembly?saved.assembly.clips[0].extensions[0].prompt:mode==='swap'?saved.segments[0].swap_custom_prompt:saved.segments[0].prompt;
 assert(text==='异步保留 '+mode,'saved draft differs from visible input');
 // Waiting for a catalog must not open an obsolete selector over a newer dialog.
 holdCatalog=true;catalogHeld=null;const picker=pickLibraryAsset();await wait(()=>catalogHeld);
 const newer=ui.modal('<h2 id="new-dialog-marker">新的弹窗</h2>');catalogHeld();assert(await picker===null,'obsolete picker resolved selection');
 assert(document.querySelector('#new-dialog-marker')&&newer.open,'late picker replaced new dialog');ui.cancelModal();
 // A failed read keeps project data; the next successful read clears only connection feedback.
 document.activeElement?.blur();rejectRead=true;await wait(()=>root.querySelector('[data-async-feedback]')?.textContent.includes('连接中断'));
 assert(root.querySelector(selector).value==='异步保留 '+mode,'connection error lost input');
 await wait(()=>!root.querySelector('[data-async-feedback]')||root.querySelector('[data-async-feedback]').hidden);
 // Reload via a new workspace preserves persisted inputs; delayed old read cannot touch it.
 document.activeElement?.blur();hold=true;held=null;await wait(()=>held);workspace.dispose();root.innerHTML='<p id="detached-marker">已经离开项目</p>';held();await sleep(100);
 assert(root.querySelector('#detached-marker'),'disposed poll rendered into next page');
 workspace=await mount(await get());
 if(assembly){await click('[data-workspace-step="1"]');await click('[data-extension]');}
 if(mode==='swap')await click('[data-workspace-step="edit"]');
 await wait(()=>root.querySelector(selector));assert(root.querySelector(selector).value==='异步保留 '+mode,'reopen lost saved draft');
 if(!image&&!assembly){
   const {saveProjectMedia}=await import('/static/studio/features/asset-picker/result-import.js');
   await saveProjectMedia(workspace.ctx,{kind:'candidate',resultId:'candidate-a'});
   await click('#save-library-result button.primary');await wait(()=>document.querySelector('#save-library-status a'));await click('#save-library-close');
   workspace.dispose();workspace=await mount(await get());await click('[data-workspace-step="review"]');await click('[data-property-tab="runs"]');
   await wait(()=>root.querySelector('.result-collect a[href="#/assets/fixture-collected"]'));
   assert((await get()).segments[0].selected==='candidate-b','receipt recovery selected another candidate');
 }
 if(mode==='swap'){
   const {mountTaskCenter}=await import('/static/studio/features/task-center/index.js');
   const underlying=window.fetch;let queueHold=false,queueHeld=null,stopHeld=null,actions=0;
   let tasks=[{id:'owned',project:pid,kind:'video',name:'隔离任务',title:'生成中',state:'running',active:true,actions:['stop'],url:'#/p/'+pid}];
   const response=data=>new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}});
   window.fetch=async(url,opts={})=>{
     if(url==='/api/v5/tasks'){
       const value=response({version:1,tasks:structuredClone(tasks),active_count:tasks.length,attention_count:0});
       if(queueHold){queueHold=false;return await new Promise(resolve=>queueHeld=()=>resolve(value));}return value;
     }
     if(url==='/api/v5/tasks/action'){actions++;assert(JSON.parse(opts.body).id==='owned','wrong task');return await new Promise(resolve=>stopHeld=()=>resolve(response({message:'停止已请求，等待确认'})));}
     return underlying(url,opts);
   };
   const disposeQueue=mountTaskCenter();await wait(()=>document.querySelector('#global-tasks').textContent.includes('1'));
   queueHold=true;await click('#global-tasks');await wait(()=>queueHeld);await click('[data-task-action="stop"]');queueHeld();await sleep(60);
   const yes=document.querySelector('[data-yes]');yes.click();yes.click();await wait(()=>stopHeld);assert(actions===1,'duplicate stop');
   document.querySelector('#task-center [data-close]').click();assert(document.querySelector('#task-center').open,'closed while stop submitting');
   tasks[0].stop_requested=true;stopHeld();await wait(()=>document.querySelector('.task-card').textContent.includes('停止已请求'));
   assert(!document.querySelector('.task-card').textContent.includes('已取消'),'request falsely displayed stopped');
   tasks=[];await click('#task-center [data-refresh]');await wait(()=>document.querySelector('.task-empty'));
   disposeQueue();window.fetch=underlying;
 }
 const counts=assembly?null:await originalFetch('/__fixture/state').then(r=>r.json());
 assert(!counts||counts.generation_requests===0&&!counts.engine_attempts?.length,'generation called');
 assert(document.documentElement.scrollWidth<=innerWidth+1,'horizontal overflow');
 document.body.dataset.check=JSON.stringify({passed:true,mode,width:innerWidth,checks:['poll during typing','double save','obsolete modal','connection failure/recovery','disposed read','saved reopen',...(!image&&!assembly?['receipt after reopen']:[]),...(mode==='swap'?['global stop race and duplicate protection']:[])]});
}catch(error){document.body.dataset.check=JSON.stringify({passed:false,error:error.message,stack:error.stack})}
</script>'''

if __name__=='__main__':base.main()
