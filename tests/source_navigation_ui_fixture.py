"""Shared origin query + five actual workspace adapters, isolated APIs/media only."""
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

class SourceFixture(base.ResultFixture):
    def seed_results(self):
        super().seed_results()
        tasks=self.image_service.store.all('tasks',self.pid)
        self.image_service.store.mutate('projects',self.pid,lambda p:p.update(current_task=tasks[1]['id']))
        self.projects[self.pid]=self.image_service.snapshot(self.pid)
base.ResultFixture=SourceFixture

base.SCRIPT=r'''<script type="module">
const sleep=ms=>new Promise(r=>setTimeout(r,ms)),assert=(v,m)=>{if(!v)throw Error(m)};
const wait=async fn=>{for(let i=0;i<400;i++){if(await fn())return;await sleep(30)}throw Error('UI wait: '+fn)};
const q=new URLSearchParams(location.search),assembly=q.has('assembly'),pid=assembly?q.get('pid'):location.hash.split('/p/')[1];
const root=document.querySelector('#app')||document.querySelector('#root'),nativeFetch=window.fetch;
let writes=0;
window.fetch=(url,options={})=>{if(options.method&&options.method!=='GET')writes++;return nativeFetch(url,options)};
const get=()=>nativeFetch('/api/v5/projects/'+pid).then(r=>r.json());
let workspace;
try{
 const initial=await get(),image=initial.kind==='image',mode=assembly?'video_assembly':initial.mode;
 const mount=async p=>{
  if(assembly){const {mountWorkspace}=await import('/static/studio/modes/video-assembly/workspace.js');return mountWorkspace(root,p,await nativeFetch('/api/v5/assembly/catalog').then(r=>r.json()))}
  if(image){const {mountWorkspace}=await import('/static/studio/app/image-workspace-controller.js');return mountWorkspace(root,p,await nativeFetch('/api/v5/image-projects/catalog').then(r=>r.json()))}
  const {getMode}=await import('/static/studio/app/mode-registry.js'),definition=getMode(mode),view=await definition.load(),{mountWorkspace}=await import('/static/studio/app/workspace-controller.js');
  return mountWorkspace(root,p,await nativeFetch('/api/v5/catalog').then(r=>r.json()),definition,view);
 };
 const target=image?initial.outputs[0]:null;
 const query=new URLSearchParams(image?{origin_task:target.task,origin_run:target.run,origin_output:target.id}:assembly?{origin_run:'result-a'}:{origin_segment:initial.segments[0].id,origin_run:'candidate-a'});
 history.replaceState(null,'','#/p/'+pid+'?'+query);
 workspace=await mount(initial);await wait(()=>root.querySelector('[data-source-navigation]'));
 assert(root.querySelector('[data-source-navigation]').textContent.includes('已定位来源记录'),'source target not found');
 const checkPosition=()=>{if(image){
  assert(root.querySelector('[data-output="'+target.id+'"]')?.getAttribute('aria-pressed')==='true','wrong image viewed');
  assert(workspace.session.project.current_task===initial.current_task,'view changed current task draft');
  assert(root.querySelector('[data-task="'+target.task+'"]')?.classList.contains('active'),'wrong task visible');
 }else if(assembly){
  assert(root.querySelector('[data-run-view="result-a"]')?.textContent.includes('正在查看'),'latest run substituted');
 }else{
  assert(workspace.ctx.tab==='review'&&workspace.ctx.shot===0,'wrong video view');
  assert(root.querySelector('[data-property-tab="runs"]').getAttribute('aria-selected')==='true','history tab not open');
  assert(root.querySelector('[data-source-run="candidate-a"]').open,'exact candidate not expanded');
 }};
 checkPosition();
 await sleep(2200);
 checkPosition();
 assert(!workspace.session.dirty,'origin navigation dirtied project');
 assert(writes===0,'origin navigation wrote data');
 assert(JSON.stringify(await get())===JSON.stringify(initial),'origin navigation changed stored state');
 // Missing targets must disclose failure and provide the real recycle route.
 workspace.dispose();history.replaceState(null,'','#/p/'+pid+'?origin_run=missing');
 workspace=await mount(await get());await wait(()=>root.querySelector('[data-source-navigation]'));
 assert(root.querySelector('[data-source-navigation]').textContent.includes('不存在'),'missing origin silently accepted');
 const recovery=root.querySelector('[data-source-navigation] a[href*="view=trash"]');
 assert(recovery&&recovery.getAttribute('href').includes('recycle='),'wrong recovery route');
 assert(!workspace.session.dirty,'missing origin dirtied project');
 workspace.dispose();history.replaceState(null,'','#/p/'+pid+'?'+query);workspace=await mount(await get());
 await wait(()=>root.querySelector('[data-source-navigation]'));await document.fonts.ready;
 assert(document.documentElement.scrollWidth<=innerWidth+1,'horizontal overflow');
 document.body.dataset.check=JSON.stringify({passed:true,mode,width:innerWidth,checks:['exact history target','no choose/save/generation','poll keeps read-only target','missing target feedback','correct recycle route','reopen','no overflow']});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.message,stack:e.stack})}
</script>'''

if __name__=='__main__':base.main()
