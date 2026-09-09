"""Reproduce real two-second project polling against temporary API/store."""
import html,json,re,subprocess,sys,threading
from pathlib import Path
from wsgiref.simple_server import make_server
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.creation_ui_fixture import MovieTests,Quiet
PAGE='''<!doctype html><meta charset="utf-8"><link rel="stylesheet" href="/static/studio/style.css"><main id="root"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div><script type="module">
import {mountWorkspace as script} from '/static/studio/modes/authoring/workspace.js';
import {mountWorkspace as movie} from '/static/studio/modes/movie/workspace.js';
import {workspaceViewState} from '/static/studio/ui/workspace-view-state.js';
const root=document.querySelector('#root'),q=new URLSearchParams(location.search),pid=q.get('pid'),get=()=>fetch('/api/v5/projects/'+pid).then(r=>r.json()),pause=ms=>new Promise(r=>setTimeout(r,ms));let w;
const assert=(value,message)=>{if(!value)throw Error(message)};
try{
const p=await get();w=(p.kind==='authoring'?script:movie)(root,p);
const summary=p.kind==='authoring'?'补充视觉参考':'当前剧本正文';
const detail=()=>[...root.querySelectorAll('details')].find(d=>d.querySelector('summary')?.textContent===summary);
let d=detail();assert(d,'missing disclosure');d.querySelector('summary').click();await pause(20);assert(d.open,'could not open');
await pause(4500);assert(detail().open,'poll collapsed disclosure');assert(detail()===d,'unchanged snapshot rebuilt DOM');
const next=await get();next.revision+=1;next.name+='（状态更新）';w.session.receive(next);assert(detail().open,'changed snapshot collapsed disclosure');assert(root.textContent.includes(next.name),'changed snapshot not rendered');
detail().querySelector('summary').click();await pause(20);const changed=structuredClone(next);changed.revision++;changed.name+='2';w.session.receive(changed);assert(!detail().open,'user closed disclosure reopened');
if(p.kind==='movie'){const label='已保存的正式 Prompt',find=()=>[...root.querySelectorAll('details')].find(d=>d.querySelector('summary')?.textContent.startsWith(label));find().querySelector('summary').click();await pause(20);w.session.receive({...changed,revision:changed.revision+1});assert(find().open,'opened prompt disclosure collapsed');}
if(p.kind==='authoring'){detail().open=true;root.querySelector('[data-next]').click();await pause(30);assert(!detail().open,'view state leaked to another step');root.querySelector('[data-back]').click();await pause(30);assert(detail().open,'return to step lost expansion');}
const input=root.querySelector('textarea,input:not([type=file])');if(input){input.focus();input.value='保留当前输入';input.dispatchEvent(new Event('input',{bubbles:true}));w.session.receive({...changed,revision:changed.revision+1});assert(root.contains(input)&&input.value==='保留当前输入','focused draft lost');}
w.dispose();
const probe=document.createElement('section');document.body.append(probe);const view=workspaceViewState(probe),markup=order=>order.map(id=>`<div data-view-key="${id}"><details><summary>管理素材</summary><p>${id}</p></details></div>`).join('')+'<div class="desk-canvas" style="height:50px;max-height:50px;overflow:auto"><div style="min-height:800px">scroll</div></div><video src="data:video/mp4;base64,"></video>';
let restore=view.beforeRender('first');probe.innerHTML=markup(['a','b']);restore();probe.querySelector('[data-view-key=a] details').open=true;probe.querySelector('.desk-canvas').scrollTop=120;const player=probe.querySelector('video');
restore=view.beforeRender('first');probe.innerHTML=markup(['b','a']);restore();assert(probe.querySelector('[data-view-key=a] details').open&&!probe.querySelector('[data-view-key=b] details').open,'reordered references exchanged disclosure state');assert(probe.querySelector('.desk-canvas').scrollTop===120,'scroll reset');assert(probe.querySelector('video')===player,'media recreated');view.dispose();probe.remove();
document.body.dataset.check=JSON.stringify({passed:true,mode:p.kind});
}catch(e){w?.dispose();document.body.dataset.check=JSON.stringify({passed:false,error:e.stack});}
</script>'''
def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True);case=MovieTests();case.setUp();case.setup_movie()
    def app(env,start):
        if env['PATH_INFO']=='/refresh-fixture':start('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [PAGE.encode()]
        return case.app(env,start)
    server=make_server('127.0.0.1',0,app,handler_class=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start();checks=[]
    try:
        for mode,pid in [('authoring',case.p['id']),('movie',case.movie['id'])]:
            result=subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--no-first-run','--disable-background-networking',f'--user-data-dir={out/("profile-"+mode)}','--virtual-time-budget=16000','--dump-dom',f'http://127.0.0.1:{server.server_port}/refresh-fixture?pid={pid}'],capture_output=True,timeout=40)
            match=re.search(r'data-check="([^"]+)"',result.stdout.decode('utf-8','replace'));data=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='No completion marker');checks.append({'mode':mode,**data});print(json.dumps(checks[-1],ensure_ascii=False),flush=True)
    finally:
        server.shutdown();server.server_close();case.doCleanups();(out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if not all(c['passed'] for c in checks):raise SystemExit(1)
if __name__=='__main__':main()
