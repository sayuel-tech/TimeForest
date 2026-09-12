"""Q6b temporary archive/recycle APIs and exact stop against a fake engine."""
import html,json,re,sys,threading
from pathlib import Path
from werkzeug.serving import make_server,WSGIRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_task_center import TaskCenterTests
from tests.uiux_browser_capture import capture
from tests.uiux_r1_shell import application_shell

SCRIPT=r'''<script type="module">
import {createFeature} from '/static/studio/pages/archive.js';
import {projectCard} from '/static/studio/pages/home.js';
import {listModes} from '/static/studio/app/mode-registry.js';
import {mountRecycleBin} from '/static/studio/pages/asset-library/recycle-bin.js';
import {mountTaskCenter} from '/static/studio/features/task-center/index.js';
import {api} from '/static/studio/core/api-client.js';
import * as ui from '/static/studio/ui/primitives.js';
const $=s=>document.querySelector(s),root=$('#app'),controller=new AbortController();
const assert=(v,m)=>{if(!v)throw Error(m)},pause=()=>new Promise(r=>setTimeout(r,40));
async function wait(fn){for(let i=0;i<350;i++){if(await fn())return;await pause()}throw Error('Timed out')}
const change=(s,v)=>{$(s).value=v;$(s).dispatchEvent(new Event('change'))};
let dispose;
try{
 const archive=createFeature({...ui,$,api,projectCard,isCurrent:()=>true,MODES:Object.fromEntries(listModes().map(m=>[m.id,m]))});
 await archive.archive();
 assert($('#archive-items a[href="#/p/'+RUNNING+'"]'),'continue target');
 change('#archive-state','deleted');await wait(()=>$('#archive-items article'));
 assert($('#archive-items .project-resume').textContent==='恢复后可继续制作','deleted resume misleading');
 assert(!$('#archive-items a.project-card'),'deleted project navigable');
 await mountRecycleBin(root,new URLSearchParams('recycle=generations'),controller.signal);
 assert($('[data-recycle-restore]').disabled,'removed parent guard');
 await mountRecycleBin(root,new URLSearchParams('recycle=projects'),controller.signal);
 $('[data-recycle-restore]').click();await wait(()=>$('#yes'));$('#no').click();
 assert((await api('/recycle-bin?category=projects')).total===1,'cancel restored project');
 $('[data-recycle-restore]').click();await wait(()=>$('#yes'));$('#yes').click();
 await wait(async()=>(await api('/recycle-bin?category=projects')).total===0);
 const generations=await api('/recycle-bin?category=generations');assert(generations.total===1&&!generations.items[0].parent_deleted,'parent restore cascaded');
 await mountRecycleBin(root,new URLSearchParams('recycle=generations'),controller.signal);
 assert($('[data-recycle-restore]').getAttribute('aria-label').includes('恢复作品'),'restore identity');
 $('[data-recycle-restore]').click();await wait(()=>$('#yes'));$('#yes').click();
 await wait(async()=>(await api('/recycle-bin?category=generations')).total===0);
 await archive.archive();assert($('#archive-items a[href="#/p/'+DELETED+'"]'),'restored continue target');
 dispose=mountTaskCenter();$('#global-tasks').click();await wait(()=>$('[data-task-action="stop"]'));
 const stop=$('[data-task-action="stop"]');stop.click();assert($('[data-task-confirm] h3').textContent==='运行作品','stop confirmation project');
 assert($('[data-task-confirm]').textContent.includes('dddddddd'),'stop confirmation record');
 $('[data-no]').click();assert((await fetch('/fixture-state').then(r=>r.json())).posts.length===0,'cancel sent stop');
 $('[data-task-action="stop"]').click();$('[data-yes]').click();
 await wait(async()=>(await fetch('/fixture-state').then(r=>r.json())).posts.length===1);
 await wait(()=>$('[data-task-confirm]').hidden);
 const state=await fetch('/fixture-state').then(r=>r.json());assert(state.posts[0][0]==='/api/jobs/fixture-job/cancel','wrong stopped job');
 assert(state.posts[0][0]!=='/interrupt','global stop');
 assert(state.run.stop_requested&&state.run.state==='running','stop request claimed completion');
 assert($('#task-center').textContent.includes('停止已请求'),'stop request status');
 if(location.search.includes('confirm=1'))$('[data-task-action="stop"]').click();
 await document.fonts.ready;assert(document.documentElement.scrollWidth<=innerWidth+1,'page overflow');
 assert($('#task-center').scrollWidth<=$('#task-center').clientWidth+1,'task overflow');
 document.body.dataset.check=JSON.stringify({passed:true,width:innerWidth,checks:['archive target/deleted label','cancel restore','parent preserves removed candidate','restore candidate','exact stop/cancel/request status']});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.stack})}
</script>'''

def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True);checks=[]
    for width in [1366,430]:
        f=TaskCenterTests();f.setUp()
        f.s.store.mutate('projects',f.pid,lambda p:p.update(name='运行作品'))
        f.run_record('d'*32,'running','fixture-job')
        f.get.side_effect=lambda endpoint,**kwargs: {'queue_running':[[0,'fixture-job',{}, {'client_id':'time-forest-'+'d'*32}]]} if endpoint=='/queue' else {}
        p=f.s.create('恢复作品');rid='a'*32
        f.s.store.put('runs',dict(id=rid,project=p['id'],task=p['tasks'][0]['id'],state='success',created=1,seed=0,removed_at=123))
        response=f.c.post('/api/v5/projects/'+p['id']+'/trash',json={'revision':p['revision']});assert response.status_code==200,response.json
        page=application_shell('<script>const RUNNING='+json.dumps(f.pid)+',DELETED='+json.dumps(p['id'])+';</script>'+SCRIPT,root_id='app')
        def app(env,start):
            if env['PATH_INFO']=='/q6b':start('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [page.encode()]
            if env['PATH_INFO']=='/fixture-state':
                start('200 OK',[('Content-Type','application/json')]);return [json.dumps(dict(posts=[list(c.args) for c in f.post.call_args_list],run=f.s.store.get('runs','d'*32))).encode()]
            return f.app(env,start)
        class Quiet(WSGIRequestHandler):
            def log(self,*args,**kwargs):pass
        server=make_server('127.0.0.1',0,app,threaded=True,request_handler=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            dom=capture(f'http://127.0.0.1:{server.server_port}/q6b'+('?confirm=1' if '--confirm' in sys.argv else ''),out/f'{width}.png',width,768 if width==1366 else 900)
            (out/f'{width}.html').write_text(dom,encoding='utf-8');match=re.search(r'data-check="([^"]+)"',dom)
            result=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='missing marker');checks.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
        finally:server.shutdown();server.server_close();f.doCleanups()
    (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8');assert all(c['passed'] for c in checks)

if __name__=='__main__':main()
