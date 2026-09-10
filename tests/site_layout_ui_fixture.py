"""Bounded visual inventory of actual workspace pages; temporary APIs, no generation."""
import json,sys,threading,subprocess,re,html
from pathlib import Path
from werkzeug.serving import make_server,WSGIRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_prompt_library import PromptLibraryTests
from tests.creation_ui_fixture import MovieTests
from h3ui.studio_recipes import defaults
from tests.readability_ui_fixture import BODY, PROMPTS

SCRIPT=r'''<script type="module">
import {api} from '/static/studio/core/api-client.js';
import {getMode} from '/static/studio/app/mode-registry.js';
const root=document.querySelector('#root'),q=new URLSearchParams(location.search),pid=q.get('pid'),step=Number(q.get('step')||0);
const pause=()=>new Promise(r=>setTimeout(r,100)),assert=(v,m)=>{if(!v)throw Error(m)};let w;
try{
 const p=await api('/projects/'+pid),kind=p.kind;
 if(kind==='image'){const m=await import('/static/studio/app/image-workspace-controller.js');w=m.mountWorkspace(root,p,await api('/image-projects/catalog'));}
 else if(kind==='assembly'){const m=await import('/static/studio/modes/video-assembly/workspace.js');w=m.mountWorkspace(root,p,await api('/assembly/catalog'));}
 else if(['authoring','movie'].includes(kind)){const m=await import('/static/studio/modes/'+kind+'/workspace.js');w=m.mountWorkspace(root,p);}
 else{const m=await import('/static/studio/app/workspace-controller.js'),d=getMode(p.mode);w=m.mountWorkspace(root,p,await api('/catalog'),d,await d.load());}
 const steps=[...root.querySelectorAll('[data-workspace-step]')];assert(steps.length>step,'missing step');steps[step].click();await pause();await pause();
 assert(root.querySelector('[data-workspace-step][aria-current=step]')?.dataset.workspaceStep===steps[step].dataset.workspaceStep,'step not reached');
 if(q.get('reading')){
  if(kind==='assembly'){root.querySelector('[data-extension]')?.click();await pause();}
  const editor=root.querySelector('.desk-canvas textarea:not([readonly])');
  if(editor){
   editor.value=editor.value.length>600?editor.value:window.fixtureReadingText;editor.dispatchEvent(new Event('input',{bubbles:true}));
   const style=getComputedStyle(editor);assert(parseFloat(style.fontSize)>=16,'small main text');assert(editor.clientHeight>=100,'cramped editor');
   const toggle=root.querySelector('[data-toggle-inspector]');if(toggle){const value=editor.value;toggle.click();assert(root.contains(editor)&&editor.value===value,'focus layout rebuilt draft');if(innerWidth>850)assert(editor.getBoundingClientRect().width>600,'focused editor too narrow');toggle.click();}
   editor.scrollTop=editor.scrollHeight;assert(editor.scrollTop+editor.clientHeight>=editor.scrollHeight-2,'cannot reach ending');editor.scrollTop=0;
  }else assert(root.querySelector('.creation-prose')?.textContent.length>600,'long source prompt missing');
 }
 if(q.get('settings')){root.querySelector('.project-actions button').click();for(let i=0;i<40&&!document.querySelector('dialog[open] .dialog-heading');i++)await pause();assert(document.querySelector('dialog[open] .dialog-heading'),'settings not opened');}
 await document.fonts.ready;await pause();await pause();
 const dialog=document.querySelector('dialog[open]'),surface=dialog||root;
 assert(document.documentElement.scrollWidth<=innerWidth+1,'horizontal page overflow');
 if(dialog){assert(dialog.scrollWidth<=dialog.clientWidth+1,'dialog overflow');const h=dialog.querySelector('h2');assert(!h||parseFloat(getComputedStyle(h).fontSize)<=24,'oversized dialog heading');}
 const boxes=[...surface.querySelectorAll('.director-desk,.desk-canvas,.desk-inspector,.savebar,.settings-workbench,.dialog-actions')].filter(el=>el.getClientRects().length);
 for(const el of boxes){const r=el.getBoundingClientRect();assert(r.left>=-1&&r.right<=innerWidth+1,'clipped region '+el.className);}
 const header=document.querySelector('.site-header');if(header){assert(!document.querySelector('.studio-nav'),'sidebar remains');assert(root.getBoundingClientRect().top>=header.getBoundingClientRect().bottom-1,'header overlays workspace');const bar=root.querySelector('.savebar');if(bar)assert(bar.getBoundingClientRect().bottom<=innerHeight+2,'top navigation clips bottom actions');}
 const heading=root.querySelector('[data-workspace-header] h1');assert((document.body.classList.contains('tf-experience')?parseFloat(getComputedStyle(heading).fontSize)===parseFloat(getComputedStyle(root).getPropertyValue('--title-page')):parseFloat(getComputedStyle(heading).fontSize)<=32),'page title scale');
 window.scrollTo({top:0,behavior:'instant'});if(dialog)dialog.scrollTop=0;await pause();
 document.body.dataset.check=JSON.stringify({passed:true,mode:p.mode,step,width:innerWidth,settings:!!q.get('settings'),reading:!!q.get('reading'),regions:boxes.length});
}catch(e){w?.dispose();document.body.dataset.check=JSON.stringify({passed:false,error:e.stack});}
</script>'''

def main():
 out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True);checks=[]
 for creation in (False,True):
  case=MovieTests() if creation else PromptLibraryTests();case.setUp();items=[]
  if creation:
   case.setup_movie()
   if '--readability' in sys.argv:
    case.save('intent',dict(story_text=PROMPTS[0][1]+BODY,target_duration_seconds=60,reference_ids=[],preferences='自然、克制，保持人物动机。'))
    case.save('screenplay',dict(blocks=[dict(ref='tmp:reading',heading='车站 · 没有寄出的信',text=(PROMPTS[0][1]+BODY)+'\n\n'+(PROMPTS[1][1]+BODY)+'\n\n'+PROMPTS[2][1])]))
    case.save('prompt',dict(prompt_mode='full',profile_id='movie.independent.dance_split',payload=dict(prompt_text=PROMPTS[0][1]+BODY,used_reference_keys=[])),[case.sid])
    case.movie=case.post('/movie/projects',dict(title='阅读检查 · 电影',source_project_id=case.p['id'],source_revision=case.p['revision'],segment_ids=[]))
   items=[(case.p,5),(case.movie,2)]
  else:
   for mode in ('swap','image_story','text_story'):
    p=case.st.create(mode,'林间旅程 · '+mode,5)
    if mode=='swap':p['source_ready']=True
    if not p['segments']:
     from h3ui.studio_story import storyboard
     p['segments']=[case.st.new_segment(x) for x in storyboard(5)];p=case.st.store.save(p,p['revision'])
    if mode=='swap':p['source_ready']=True;p=case.st.store.save(p,p['revision'])
    items.append((p,4 if mode=='swap' else 3))
   items.append((case.app.config['IMAGE_STUDIO'].create('图片创作 · 林间旅程','text'),3))
   ext=dict(id='ext',prompt='人物继续沿林间小径前行。',seconds=5,recipe='dance_split',configurations={k:defaults(k) for k in ('dance_split','official_image')},seed_mode='random',seed='0',sound='native',references=[])
   def init(p):p['assembly']['clips']=[dict(id='clip',name='林间原片',start=0,end=2,meta=dict(duration=2,width=160,height=96,fps=24),provenance=dict(type='local'),file=str(case.s.store.directory(case.pid)/'fake.mp4'),extensions=[ext])]
   case.s.store.mutate(case.pid,init);items.append((case.s.snapshot(case.pid),3))
  page='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/studio/style.css"><main id="root" class="page"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div><script>window.fixtureReadingText='+json.dumps(PROMPTS[0][1]+BODY)+';</script>'+SCRIPT
  if '--r1' in sys.argv:
   from tests.uiux_r1_shell import application_shell
   page=application_shell(page)
  def app(env,start):
   if env['PATH_INFO']=='/layout-audit':start('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [page.encode()]
   return case.app(env,start)
  class Quiet(WSGIRequestHandler):
   def log(self,*a,**k):pass
  server=make_server('127.0.0.1',0,app,threaded=True,request_handler=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   for p,count in items:
    requested=next((a.split('=',1)[1].split(',') for a in sys.argv if a.startswith('--modes=')),None)
    if requested and p['mode'] not in requested:continue
    scenes=[(1280,step,False) for step in range(count)]+[(1280,0,True),(760,0,False),(760,0,True)]
    if '--r1' in sys.argv:scenes=[(width,step,False) for width in next(([int(x) for x in a.split('=',1)[1].split(',')] for a in sys.argv if a.startswith('--widths=')),[1440,760,430]) for step in range(count)]
    if '--settings-only' in sys.argv:scenes=[s for s in scenes if s[2]]
    if '--readability' in sys.argv:scenes=[(width,1 if p['mode'] in ('swap','video_assembly','authoring') else 0,False) for width in (1280,760)]
    for width,step,settings in scenes:
     name=f'{p["mode"]}-{step}-{width}'+('-settings' if settings else '')
     selectedCases=next((a.split('=',1)[1].split(',') for a in sys.argv if a.startswith('--cases=')),None)
     if selectedCases and name not in selectedCases:continue
     url=f'http://127.0.0.1:{server.server_port}/layout-audit?pid={p["id"]}&step={step}'+('&settings=1' if settings else '')+('&reading=1' if '--readability' in sys.argv else '')
     if '--r1' in sys.argv:
      command=[sys.executable,str(Path(__file__).with_name('uiux_browser_capture.py')),url,str(out/(name+'.png')),str(width),str(next((int(a.split('=',1)[1]) for a in sys.argv if a.startswith('--height=')),960 if width==1440 else 900))]
     else:
      command=['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--no-first-run','--disable-background-networking',f'--user-data-dir={out/("profile-"+name)}',f'--window-size={width},1000','--virtual-time-budget=10000',f'--screenshot={out/(name+".png")}','--dump-dom',url]
     result=subprocess.run(command,capture_output=True,timeout=60)
     dom=result.stdout.decode('utf-8','replace');match=re.search(r'data-check="([^"]+)"',dom);data=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='No completion marker',exit_code=result.returncode,stderr=result.stderr.decode('utf-8','replace')[-1600:])
     data['case']=name;checks.append(data);print(json.dumps(data,ensure_ascii=False),flush=True);(out/(name+'.html')).write_text(dom,encoding='utf-8');(out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
  finally:server.shutdown();server.server_close();case.doCleanups()
 if not all(c['passed'] for c in checks):raise SystemExit(1)
if __name__=='__main__':main()
