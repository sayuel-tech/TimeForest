"""Two real temporary libraries: navigation, selection and import cancellation at two widths."""
import json,sys,threading
from pathlib import Path
from werkzeug.serving import make_server,WSGIRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_prompt_library import PromptLibraryTests
from tests.workspace_navigation_ui_fixture import capture

SCRIPT=r'''<script type="module">
import {mountLibrary} from '/static/studio/pages/asset-library/index.js';
import {mountPromptLibrary} from '/static/studio/pages/prompt-library/index.js';
import {pickPrompt} from '/static/studio/features/prompt-library/tools.js';
import {pickLibraryAsset} from '/static/studio/features/asset-picker/index.js';
import {renderHome,projectCard} from '/static/studio/pages/home.js';
import {createFeature as archive} from '/static/studio/pages/archive.js';
import {listModes,setCreationEnabled,setAssemblyEnabled,setImageAssetsEnabled} from '/static/studio/app/mode-registry.js';
import {mountTaskCenter} from '/static/studio/features/task-center/index.js';
import {api} from '/static/studio/core/api-client.js';
import * as ui from '/static/studio/ui/primitives.js';
const root=document.querySelector('#app'),view=new URLSearchParams(location.search).get('view'),controller=new AbortController();
const assert=(v,m)=>{if(!v)throw Error(m)},pause=()=>new Promise(r=>setTimeout(r,40)),wait=async(fn)=>{for(let i=0;i<150;i++){if(fn())return;await pause();}throw Error('timed out '+fn)};
try{
 if(view==='asset-picker'){
  void pickLibraryAsset({kind:'image',signal:controller.signal});await wait(()=>document.querySelector('.library-pick-card'));assert(parseFloat(getComputedStyle(document.querySelector('.library-picker h2')).fontSize)<=24,'asset picker heading scale');
 }else if(view==='home'){
  setCreationEnabled(1);setAssemblyEnabled(1);setImageAssetsEnabled(true);renderHome(root,[],()=>{});
 }else if(view==='archive'){
  root.id='app';await archive({...ui,api,MODES:Object.fromEntries(listModes().map(m=>[m.id,m])),projectCard,isCurrent:()=>true}).archive();
 }else if(view==='global-tasks'){
  const button=document.createElement('button');button.id='global-tasks';button.textContent='任务列表';root.append(button);mountTaskCenter();button.click();await wait(()=>document.querySelector('#task-center').open);
 }else if(['tasks','storage','organize','trash','detail'].includes(view)){
  if(view==='detail'){const data=await fetch('/api/v5/library/assets').then(r=>r.json());await mountLibrary(root,'#/assets/'+data.items[0].id,controller.signal);}
  else await mountLibrary(root,'#/assets?view='+view,controller.signal);
 }else if(view.startsWith('picker')){
  void pickPrompt({purpose:view==='picker-empty'?'script':'video',model:'',signal:controller.signal});
  await wait(()=>document.querySelector('.prompt-picker [data-path]')?.textContent);
  if(view==='picker-filled'){document.querySelector('[data-branch="video:h3"]').click();await wait(()=>document.querySelectorAll('[data-entry]').length===6);document.querySelector('[data-entry]').click();}
  const dialog=document.querySelector('#dialog');assert(parseFloat(getComputedStyle(dialog.querySelector('h2')).fontSize)<=24,'dialog heading too large');
  const search=dialog.querySelector('[data-search]'),button=dialog.querySelector('[data-search-go]');assert(Math.abs(search.getBoundingClientRect().height-button.getBoundingClientRect().height)<2,'search control heights differ');
  assert(Math.abs(search.getBoundingClientRect().top-button.getBoundingClientRect().top)<2,'search action wrapped away');
 }else if(view==='prompts'){
  await mountPromptLibrary(root,controller.signal);root.querySelector('[data-branch="video:h3"]').click();await wait(()=>root.querySelector('[data-path]').textContent==='视频 / H3');
  assert(root.querySelector('[data-purpose=video]').getAttribute('aria-expanded')==='true','purpose missing');assert(root.querySelector('[data-branch="video:h3"]').getAttribute('aria-current')==='page','branch missing');
  const global=root.querySelector('[data-global-search]');global.click();assert(!root.querySelector('.collection-navigation [aria-current]'),'global search retained local highlight');
  root.querySelector('[data-purpose=image]').click();root.querySelector('[data-branch="image:krea2"]').click();await wait(()=>root.querySelector('[data-path]').textContent==='图片 / Krea2');assert(!global.checked,'branch did not leave global search');
  root.querySelector('[data-purpose=video]').click();root.querySelector('[data-branch="video:h3"]').click();await wait(()=>root.querySelectorAll('[data-entry]').length===6);root.querySelector('[data-entry]').click();assert(root.querySelector('[data-entry][aria-pressed=true]'),'selected prompt not visible');
 }else{
  await mountLibrary(root,'#/assets?category=scene',controller.signal);assert(root.querySelector('.collection-navigation [aria-current]').textContent==='场景','asset category not selected');
  const figures=[...root.querySelectorAll('.library-card figure')];assert(figures.length===12,'missing assets');assert(figures.every(f=>f.getBoundingClientRect().height<=161),'thumbnails too tall');
  const columns=getComputedStyle(root.querySelector('.library-grid')).gridTemplateColumns.split(' ').length;if(innerWidth>1600)assert(columns>=5,'large screen density too low');
  const box=root.querySelector('[data-select]');box.click();const first=root.querySelector('.library-card');root.querySelector('#library-transfer').click();await wait(()=>document.querySelector('#dialog').open);
  assert(document.querySelector('[data-folder]')&&document.querySelector('[data-pack]'),'import alternatives missing');assert(!root.querySelector('#library-transfer details'),'inline expansion remains');
  document.querySelector('[data-close]').click();await pause();assert(box.checked&&root.contains(first),'cancel reset selection/list');
  if(view==='imports'){root.querySelector('#library-transfer').click();await wait(()=>document.querySelector('#dialog').open);}
 }
 await document.fonts.ready;await new Promise(r=>setTimeout(r,350));window.scrollTo(0,0);assert(document.documentElement.scrollWidth<=innerWidth+1,'page overflow');
 const dialog=document.querySelector('#dialog');if(dialog.open)assert(dialog.scrollWidth<=dialog.clientWidth+1,'import dialog overflow');
 document.body.dataset.check=JSON.stringify({passed:true,view,width:innerWidth});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,view,error:e.stack});}
</script>'''

def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True);case=PromptLibraryTests();case.setUp();checks=[]
    lib=case.app.config['ASSET_LIBRARY']
    images=list(Path('static/assets/modes').glob('*.webp'))
    for i in range(12):lib.ingest(images[i%len(images)],['林间小径','角色参考','远山与湖面','城市边缘'][i%4]+f' · {i+1}',metadata={'categories':['scene']})
    for purpose,branch in [('video','video:h3'),('image','image:krea2')]:
        for i in range(6):case.post('/prompt-library/entries',dict(title=f'森林镜头 · {i+1}',purpose=purpose,branch=branch,content=dict(type='text',text='人物沿着林间小路向前走，镜头从侧面缓缓跟随。保留傍晚的柔和光线与安静的树林。')))
    page='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/studio/style.css"><main id="app" class="page"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div>'+SCRIPT
    def app(env,start):
        if env['PATH_INFO']=='/layout-check':start('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [page.encode()]
        return case.app(env,start)
    class Quiet(WSGIRequestHandler):
        def log(self,*a,**k):pass
    server=make_server('127.0.0.1',0,app,threaded=True,request_handler=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        for width in [1920,760]:
            views=['home','archive','tasks','storage','organize','trash','detail','global-tasks'] if '--general' in sys.argv else ['assets','prompts','imports','picker-empty','picker-filled']
            chosen=next((a.split('=',1)[1] for a in sys.argv if a.startswith('--views=')),None)
            if chosen:views=chosen.split(',')
            for view in views:checks.append(capture(out,f'{view}-{width}',f'http://127.0.0.1:{server.server_port}/layout-check?view={view}',width))
    finally:server.shutdown();server.server_close();case.doCleanups()
    (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)
if __name__=='__main__':main()
