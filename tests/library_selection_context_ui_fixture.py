"""Q6a real temporary libraries: search, read, fixed selection and cancel; no engine."""
import html, json, re, sys, threading
from pathlib import Path
from werkzeug.serving import make_server, WSGIRequestHandler
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.test_prompt_library import PromptLibraryTests
from tests.uiux_browser_capture import capture
from tests.uiux_r1_shell import application_shell

SCRIPT=r'''<script type="module">
import {pickLibraryAsset} from '/static/studio/features/asset-picker/index.js';
import {pickPrompt} from '/static/studio/features/prompt-library/tools.js';
const $=s=>document.querySelector(s),pause=()=>new Promise(r=>setTimeout(r,40));
const assert=(v,m)=>{if(!v)throw Error(m)};
async function wait(fn){for(let i=0;i<350;i++){if(fn())return;await pause()}throw Error('Timed out')}
async function assets(multiple=false){const old=$('[data-pick]'),promise=pickLibraryAsset({kind:'image',multiple});await wait(()=>$('[data-pick]')&&$('[data-pick]')!==old&&$('#dialog').open);return {promise}}
async function prompts(){const old=$('[data-path]'),promise=pickPrompt({purpose:'video',model:''});await wait(()=>$('[data-path]')?.textContent&&$('[data-path]')!==old&&$('#dialog').open);return {promise}}
function search(selector,value,button){$(selector).value=value;$(button).click()}
try{
 const view=new URLSearchParams(location.search).get('view');
 if(view==='assets'){
  let handle=await assets();
  search('[name=q]','没有匹配的关键词','.library-search button');await wait(()=>$('.empty'));
  assert($('.empty').textContent.includes('调整关键词'),'filtered empty guidance');
  search('[name=q]','森林','.library-search button');await wait(()=>$('[data-pick]'));
  assert($('[data-picker-count]').textContent.includes('1 项'),'asset result count');
  const id=$('[data-pick]').dataset.pick;
  $('[data-preview] summary').click();await wait(()=>$('[data-preview-content] img'));
  assert($('[data-preview-content]').textContent.includes('固定版本'),'preview version meaning');
  assert(getComputedStyle($('.library-pick-card strong')).whiteSpace==='normal','asset name truncates');
  $('.picker-cancel').click();assert(await handle.promise===null,'cancel returned selection');
  handle=await assets();$('[data-pick]').click();const selected=await handle.promise;
  assert(selected.id===id&&selected.snapshot.id===selected.version,'fixed asset version');
  handle=await assets(true);$('[data-pick]').click();await wait(()=>$('[data-pick-action]').textContent==='已勾选');
  assert($('[data-pick]').getAttribute('aria-pressed')==='true','multi state');
  $('.picker-cancel').click();assert(await handle.promise===null,'multi cancel returned selection');
  handle=await assets();$('[data-preview] summary').click();await wait(()=>$('[data-preview-content] img'));
 }else{
  let handle=await prompts();
  $('[data-branch="video:general"]').click();await wait(()=>$('[data-entry]'));
  search('[data-search]','没有匹配的关键词','[data-search-go]');await wait(()=>$('[data-empty]'));
  assert($('[data-empty]').textContent.includes('筛选条件'),'prompt empty guidance');
  search('[data-search]','森林','[data-search-go]');await wait(()=>$('[data-entry]'));
  $('[data-entry]').click();assert($('.prompt-text').textContent.includes('END OF TEXT'),'full long text');
  $('[data-back-list]').click();assert($('[data-search]').value==='森林','back lost filter');
  $('[data-entry]').click();$('[data-cancel]').click();assert(await handle.promise===null,'prompt cancel applied');
  handle=await prompts();$('[data-branch="video:general"]').click();await wait(()=>$('[data-entry]'));$('[data-entry]').click();
  assert($('[data-use]').textContent==='选择版本 2','explicit version');
  $('[data-history]').click();await wait(()=>$('[data-old-version="1"]'));
  $('[data-old-version="1"]').click();const selected=await handle.promise;
  assert(selected.version===1&&selected.content.text==='初始文字','historical version mismatch');
  handle=await prompts();$('[data-branch="video:general"]').click();await wait(()=>$('[data-entry]'));$('[data-entry]').click();
 }
 await document.fonts.ready;
 assert(document.documentElement.scrollWidth<=innerWidth+1,'page overflow');
 const d=$('#dialog');assert(d.scrollWidth<=d.clientWidth+1,'dialog overflow');
 document.body.dataset.check=JSON.stringify({passed:true,view,width:innerWidth});
}catch(e){document.body.dataset.check=JSON.stringify({passed:false,error:e.stack})}
</script>'''

def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
    case=PromptLibraryTests();case.setUp();checks=[]
    case.app.config['ASSET_LIBRARY'].ingest(next(Path('static/assets/modes').glob('*.webp')),'森林深处的角色与场景参考素材完整名称用于辨认',metadata={'categories':['scene']})
    item=case.post('/prompt-library/entries',dict(title='森林长镜头',purpose='video',branch='video:general',content=dict(type='text',text='初始文字')))
    case.post('/prompt-library/entries/'+item['id'],dict(revision=item['revision'],content=dict(type='text',text=('沿着林间小路向前走。The camera follows slowly through the forest.\n'*28)+'END OF TEXT')))
    page=application_shell(SCRIPT)
    def app(env,start):
        if env['PATH_INFO']=='/q6a':start('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [page.encode()]
        return case.app(env,start)
    class Quiet(WSGIRequestHandler):
        def log(self,*args,**kwargs):pass
    server=make_server('127.0.0.1',0,app,threaded=True,request_handler=Quiet)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        for width in [1366,430]:
            for view in (['assets'] if '--assets-only' in sys.argv else ['assets','prompts']):
                name=f'{view}-{width}';dom=capture(f'http://127.0.0.1:{server.server_port}/q6a?view={view}',out/(name+'.png'),width,768 if width==1366 else 900)
                (out/(name+'.html')).write_text(dom,encoding='utf-8')
                match=re.search(r'data-check="([^"]+)"',dom);result=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='missing marker')
                checks.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
    finally:server.shutdown();server.server_close();case.doCleanups()
    (out/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    assert all(c['passed'] for c in checks)

if __name__=='__main__':main()
