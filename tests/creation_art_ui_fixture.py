"""Temporary real pages: artwork load, responsive placement and missing-art fallback.

No model, media processing, credentials or production data are used.
"""
import html,json,re,subprocess,sys,threading
from pathlib import Path
from wsgiref.simple_server import make_server
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.creation_ui_fixture import MovieTests,Quiet

PAGE='''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/studio/style.css"><main id="root"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div>
<script type="module">
import {renderHome} from '/static/studio/pages/home.js';
import {setCreationEnabled} from '/static/studio/app/mode-registry.js';
import {mountWorkspace as script} from '/static/studio/modes/authoring/workspace.js';
import {mountWorkspace as movie} from '/static/studio/modes/movie/workspace.js';
const q=new URLSearchParams(location.search),root=document.querySelector('#root'),scene=q.get('scene'),pause=()=>new Promise(r=>setTimeout(r,60));let workspace;
const assert=(v,m)=>{if(!v)throw Error(m)};
try{
  if(scene==='home'){
    setCreationEnabled(1);renderHome(root,[],()=>{});
    root.querySelector('.hero').remove();root.querySelector('.recent').remove();
    root.querySelectorAll('[data-create]').forEach(card=>{if(!['image_story','authoring','movie'].includes(card.dataset.create))card.remove();});
  }else{
    const p=await fetch('/api/v5/projects/'+q.get('pid')).then(r=>r.json());
    workspace=(scene==='story'?script:movie)(root,p);
    if(scene==='story')root.querySelector('[data-next]').click();
    if(scene==='edit')root.querySelector('[data-edit-next]').click();
    await pause();
  }
  const images=[...root.querySelectorAll('[data-decorative-art]')];assert(images.length===(scene==='home'?3:1),'missing rendered artwork');
  for(const image of images){image.loading='eager';await image.decode();assert(image.naturalWidth>0,'asset decode failed');assert(image.alt==='','decorative alt');const r=image.getBoundingClientRect();assert(r.width>0&&r.left>=0&&r.right<=innerWidth,'horizontal clipping');}
  const image=images.at(-1),src=image.src,before=root.textContent;image.src='/static/assets/not-present-art-check.webp';
  for(let i=0;i<30&&!image.hidden;i++)await pause();assert(image.hidden,'missing artwork did not hide broken icon');assert(root.textContent===before,'missing art removed meaning/actions');
  image.hidden=false;image.src=src;await image.decode();await pause();
  workspace?.dispose();window.scrollTo(0,0);await pause();document.body.dataset.check=JSON.stringify({passed:true,scene,images:images.length,missing_art_fallback:true});
}catch(e){workspace?.dispose();document.body.dataset.check=JSON.stringify({passed:false,scene,error:e.stack});}
</script>'''

def main():
    out=Path(__import__('tempfile').mkdtemp(prefix='timeforest-art-checks-'));out.mkdir(exist_ok=True)
    case=MovieTests();case.setUp();case.setup_movie()
    story=case.service.create('authoring',dict(title='空白剧本 · 美术检查',request_key='art-script'))
    def app(environ,start):
        if environ['PATH_INFO']=='/art-fixture':start('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [PAGE.encode()]
        return case.app(environ,start)
    server=make_server('127.0.0.1',0,app,handler_class=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start();checks=[]
    try:
        for width in [1440,760]:
            for scene in ['home','story','takes','edit']:
                name=f'{scene}-{width}';pid=story['id'] if scene=='story' else case.movie['id']
                result=subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--no-first-run','--disable-background-networking',f'--user-data-dir={out/("profile-"+name)}',f'--window-size={width},1000','--virtual-time-budget=12000',f'--screenshot={out/(name+".png")}','--dump-dom',f'http://127.0.0.1:{server.server_port}/art-fixture?scene={scene}&pid={pid}'],capture_output=True,timeout=40)
                dom=result.stdout.decode('utf-8','replace');match=re.search(r'data-check="([^"]+)"',dom)
                data=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='No browser completion marker')
                checks.append(dict(width=width,**data));print(json.dumps(checks[-1],ensure_ascii=False),flush=True)
    finally:
        server.shutdown();server.server_close();case.doCleanups();(out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)

if __name__=='__main__':main()
