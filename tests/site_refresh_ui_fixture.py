"""Real temporary APIs and actual seven adapters; controlled read-only progress snapshots."""
import json,sys,threading,subprocess,re,html
from pathlib import Path
from werkzeug.serving import make_server,WSGIRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_prompt_library import PromptLibraryTests
from tests.creation_ui_fixture import MovieTests
from tests.workspace_navigation_ui_fixture import capture
from h3ui.studio_recipes import defaults

SCRIPT=r'''<script type="module">
import {api} from '/static/studio/core/api-client.js';
import {getMode} from '/static/studio/app/mode-registry.js';
import {updateStatusRegion} from '/static/studio/ui/status-region.js';
const root=document.querySelector('#root'),pid=new URLSearchParams(location.search).get('pid');
const pause=ms=>new Promise(r=>setTimeout(r,ms)),assert=(v,m)=>{if(!v)throw Error(m)};let w;
try{
 let snapshot=await api('/projects/'+pid);const kind=snapshot.kind,mode=snapshot.mode;
 if(kind==='image')snapshot.runs=[{id:'fixture-run',task:snapshot.tasks[0].id,state:'running',note:'进度 1',seed:0,started:100,progress:{step:1,step_total:20,phase:'进度 1'}}];
 else if(kind==='assembly')snapshot.assembly.runs=[{id:'fixture-run',extension:'ext',kind:'extension',state:'running',note:'进度 1',seed:0,started:100}];
 else if(['authoring','movie'].includes(kind))snapshot.creation_jobs=[{job_id:'fixture-run',kind:kind==='movie'?'media_export':'llm',context:{target:{target_ids:[]}},state:'running',phase:'进度 1',created:100,updated:101}];
 else snapshot.runtime={active:true,step:1,step_total:20,phase:'进度 1',started:100};
 const originalFetch=window.fetch;window.fetch=(url,options)=>String(url)==='/api/v5/projects/'+pid&&(!options?.method||options.method==='GET')?Promise.resolve(new Response(JSON.stringify(snapshot),{headers:{'Content-Type':'application/json'}})):originalFetch(url,options);
 if(kind==='image'){const m=await import('/static/studio/app/image-workspace-controller.js');w=m.mountWorkspace(root,structuredClone(snapshot),await api('/image-projects/catalog'));}
 else if(kind==='assembly'){const m=await import('/static/studio/modes/video-assembly/workspace.js');w=m.mountWorkspace(root,structuredClone(snapshot),await api('/assembly/catalog'));root.querySelector('[data-next]').click();root.querySelector('[data-extension]')?.click();}
 else if(['authoring','movie'].includes(kind)){const m=await import('/static/studio/modes/'+kind+'/workspace.js');w=m.mountWorkspace(root,structuredClone(snapshot));}
 else {const m=await import('/static/studio/app/workspace-controller.js'),definition=getMode(mode);w=m.mountWorkspace(root,structuredClone(snapshot),await api('/catalog'),definition,await definition.load());}
 const anchor=root.querySelector('[data-workspace-header]'),input=root.querySelector('textarea'),disclosure=root.querySelector('details');
 if(disclosure)disclosure.open=true;
 await pause(2300);assert(root.contains(anchor),'identical poll rebuilt '+mode);if(disclosure)assert(disclosure.open,'identical poll closed disclosure');
 snapshot=structuredClone(snapshot);snapshot.revision++;
 if(kind==='image'){snapshot.runs[0].progress.step=2;snapshot.runs[0].progress.phase='进度 2';}
 else if(kind==='assembly')snapshot.assembly.runs[0].note='进度 2';
 else if(['authoring','movie'].includes(kind)){snapshot.creation_jobs[0].phase='进度 2';snapshot.creation_jobs[0].updated=102;}
 else {snapshot.runtime.phase='进度 2';snapshot.runtime.step=2;}
 await pause(2300);assert(root.contains(anchor),'progress rebuilt workspace '+mode);if(input)assert(root.contains(input),'progress replaced editor '+mode);if(disclosure)assert(disclosure.open,'progress closed disclosure');
 if(['image','assembly','authoring','movie'].includes(kind))assert(root.textContent.includes('进度 2'),'status patch not visible '+mode);
 snapshot={...snapshot,revision:snapshot.revision+1,name:'更新后的项目标题'};
 await pause(2300);assert(root.textContent.includes(snapshot.name),'content update not received '+mode);
 if(disclosure){const name=disclosure.querySelector('summary').textContent;const fresh=[...root.querySelectorAll('details')].find(d=>d.querySelector('summary')?.textContent===name);assert(fresh?.open,'content render lost expansion '+mode);}
 const field=root.querySelector('textarea');if(field){field.focus();field.value='当前未保存文字';field.dispatchEvent(new Event('input',{bubbles:true}));snapshot={...snapshot,revision:snapshot.revision+1,name:'不应打断编辑'};await pause(2300);assert(root.contains(field)&&field.value==='当前未保存文字','draft lost '+mode);}
 w.dispose();
 const box=document.createElement('div');document.body.append(box);const markup=(order,n)=>order.map(id=>`<article data-view-key="${id}"><details><summary>反馈</summary><p>进度 ${n}</p></details><button data-id="${id}">停止 ${id}</button></article>`).join('');
 updateStatusRegion(box,markup(['a','b'],1));const old=box.querySelector('[data-view-key=a]'),button=old.querySelector('button');old.querySelector('details').open=true;button.focus();
 updateStatusRegion(box,markup(['b','a'],2));assert(box.querySelector('[data-view-key=a]')===old&&old.querySelector('details').open,'task reordering lost identity/disclosure');assert(document.activeElement===button,'task progress lost focus');box.remove();
 document.body.dataset.check=JSON.stringify({passed:true,mode,checks:['identical poll','status patch/editor identity','changed content/disclosure','focused draft','keyed task reorder']});
}catch(e){w?.dispose();document.body.dataset.check=JSON.stringify({passed:false,error:e.stack});}
</script>'''

def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True);checks=[]
    for creation in ((True,) if "--creation-only" in sys.argv else (False,True)):
        case=MovieTests() if creation else PromptLibraryTests();case.setUp();items=[]
        if creation:
            case.setup_movie();items=[case.p,case.movie]
        else:
            for mode in ('swap','image_story','text_story'):
                p=case.st.create(mode,'同步检查 '+mode,5)
                if not p['segments']:
                    from h3ui.studio_story import storyboard
                    p['segments']=[case.st.new_segment(x) for x in storyboard(5)];p=case.st.store.save(p,p['revision'])
                items.append(p)
            items.append(case.app.config['IMAGE_STUDIO'].create('图片同步','text'))
            ext=dict(id='ext',prompt='继续',seconds=5,recipe='dance_split',configurations={k:defaults(k) for k in ('dance_split','official_image')},seed_mode='random',seed='0',sound='native',references=[])
            def init(p):p['assembly']['clips']=[dict(id='clip',name='源视频',start=0,end=2,meta=dict(duration=2,width=160,height=96,fps=24),provenance=dict(type='local'),file=str(case.s.store.directory(case.pid)/'fake.mp4'),extensions=[ext])]
            case.s.store.mutate(case.pid,init);items.append(case.s.snapshot(case.pid))
        page='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/studio/style.css"><main id="root" class="page"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div>'+SCRIPT
        def app(env,start):
            if env['PATH_INFO']=='/refresh-check':start('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [page.encode()]
            return case.app(env,start)
        class Quiet(WSGIRequestHandler):
            def log(self,*a,**k):pass
        server=make_server('127.0.0.1',0,app,threaded=True,request_handler=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            for p in items:
                url=f'http://127.0.0.1:{server.server_port}/refresh-check?pid={p["id"]}'
                if creation:
                    result=subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--no-first-run','--disable-background-networking',f'--user-data-dir={out/("profile-"+p["mode"])}','--virtual-time-budget=18000','--dump-dom',url],capture_output=True,timeout=40)
                    match=re.search(r'data-check="([^"]+)"',result.stdout.decode('utf-8','replace'));data=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='No completion marker');data['case']=p['mode'];checks.append(data);print(json.dumps(data,ensure_ascii=False),flush=True)
                else:checks.append(capture(out,p['mode'],url,1280))
                (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
        finally:server.shutdown();server.server_close();case.doCleanups()
    (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)
if __name__=='__main__':main()
