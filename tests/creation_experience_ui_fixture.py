"""One bounded authoring journey against real temporary APIs and a fake LLM."""
import json,sys,threading,subprocess,re,html,argparse,io
from PIL import Image
from pathlib import Path
from werkzeug.serving import make_server,WSGIRequestHandler
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_creation import CreationTests

PAGE='''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/studio/style.css"><main id="root"></main><dialog id="dialog"><div id="dialog-content"></div></dialog><div id="toast"></div><script>window.addEventListener("error",e=>document.body.dataset.check=JSON.stringify({passed:false,error:e.message}));window.addEventListener("unhandledrejection",e=>document.body.dataset.check=JSON.stringify({passed:false,error:String(e.reason)}));</script><script type="module">
import {mountWorkspace} from '/static/studio/modes/authoring/workspace.js';
const root=document.querySelector('#root'),pid=new URLSearchParams(location.search).get('pid'),get=()=>fetch('/api/v5/projects/'+pid).then(r=>r.json());
const pause=()=>new Promise(r=>setTimeout(r,40)),assert=(v,m)=>{if(!v)throw Error(m)};let w;
async function wait(check){for(let i=0;i<200;i++){if(await check())return;await pause();}throw Error('timed out '+root.innerText.slice(-400));}
async function click(selector){const e=document.querySelector(selector);assert(e,'missing '+selector);assert(!e.disabled,'disabled '+selector);e.click();await pause();}
function input(selector,value){const e=document.querySelector(selector);assert(e,'missing '+selector);e.value=value;e.dispatchEvent(new Event('input',{bubbles:true}));}
async function settled(){await wait(()=>!w.session.actionPending&&!w.session.working);assert(!w.ctx.error,w.ctx.error?.message);}
async function generate(task){await click('[data-ai-task="'+task+'"]');await settled();await wait(async()=>{const p=await get();if(p.creation_jobs.at(-1)?.state==='failed')throw Error(p.creation_jobs.at(-1).error);if(p.creation_jobs.at(-1)?.state==='succeeded'){w.session.receive(p);return true;}});await pause();assert(root.querySelector('[data-apply-candidate]'),'no applicable output');}
try{
 w=mountWorkspace(root,await get());input('[data-text="intent"]','张三与王五在修车铺相遇。');await click('[data-save]');await settled();await click('[data-nav-step="1"]');
 assert(!root.textContent.includes('段落标题')&&!root.querySelector('[data-add-block]'),'paragraph editor remains');
 input('[data-ai-instruction]','写出完整故事，保留冲突和结尾。');await click('[data-save]');await settled();w.dispose();w=mountWorkspace(root,await get());
 assert(root.querySelector('[data-ai-instruction]').value.includes('保留冲突'),'communication not restored');
 await generate('screenplay_draft');const first=(await get()).candidates.at(-1);const select=root.querySelector('[data-writing-basis]');select.value=first.candidate_id;select.dispatchEvent(new Event('change'));input('[data-ai-instruction]','基于上次输出，把结尾改温暖。');await generate('screenplay_draft');
 await click('[data-apply-candidate]');await settled();assert((await get()).content.confirmations.some(c=>c.layer==='screenplay'),'not confirmed');
 const recorded=JSON.stringify((await get()).candidates.at(-1).payload);input('[data-candidate-text]','张三与王五在修车铺相遇。确认后仍可修改完整剧本。');await click('[data-save-output]');await settled();assert((await get()).content.layers.find(l=>l.layer==='screenplay').content.blocks[0].text.includes('确认后仍可修改'),'confirmed output cannot be edited');assert(JSON.stringify((await get()).candidates.at(-1).payload)===recorded,'editing overwrote historic LLM output');
 await click('[data-nav-step="2"]');assert(!root.querySelector('.desk-inspector'),'asset page still has right inspector');assert(!root.querySelector('[data-candidate-text]'),'screenplay candidate leaked');
 await generate('asset_analysis');await click('[data-apply-candidate]');await settled();assert(root.querySelectorAll('[data-need-card]').length===3,'needs not turned into cards');
 for(const e of root.querySelectorAll('[data-need-source]')){e.value='text_only';e.dispatchEvent(new Event('change'));}
 await click('[data-save]');await settled();await click('[data-bind-existing]');await settled();assert((await get()).content.layers.find(l=>l.layer==='asset_bindings').content.bindings.some(b=>b.state==='bound'&&b.reference_id),'existing reference was not bound to named card');
 await click('[data-save]');await settled();await click('[data-asset-task="asset_screenplay"]');await generate('asset_screenplay');await click('[data-apply-candidate]');await settled();
 await click('[data-select=""]');await generate('storyboard');await click('[data-apply-candidate]');await settled();const shot=(await get()).content.layers.find(l=>l.layer==='storyboard').content.shots[0];
 await click('[data-select="'+shot.ref+'"]');assert(w.ctx.step===3,'shot route');input('[data-ai-instruction]','只改当前分镜');await generate('local_rewrite');input('[data-candidate-text]','两人在修车铺相遇，欲言又止。');await click('[data-apply-candidate]');await settled();assert((await get()).content.confirmations.some(c=>c.layer==='storyboard'&&c.target_id===shot.ref),'shot confirmation not scoped');await click('[data-shot-task="split"]');await generate('segment_plan');await click('[data-apply-candidate]');await settled();
 const segment=(await get()).content.layers.find(l=>l.layer==='segment').content.segments[0];if(!root.querySelector('[data-select="'+segment.ref+'"]'))await click('[data-expand="'+shot.ref+'"]');await click('[data-select="'+segment.ref+'"]');assert(w.ctx.step===4,'segment route');
 const policy=root.querySelector('[data-asset-policy]');policy.value='project';policy.dispatchEvent(new Event('change'));await click('[data-save]');await settled();assert((await get()).content.layers.find(l=>l.layer==='asset_bindings').content.policies[segment.ref]==='project','source not persisted');
 await click('[data-clip-task="rewrite"]');input('[data-ai-instruction]','细化当前片段');await generate('local_rewrite');await click('[data-apply-candidate]');await settled();await click('[data-clip-task="prompt"]');await generate('h3_prompt');await click('[data-apply-candidate]');await settled();
 await click('[data-nav-step="2"]');assert(root.querySelector('[data-select="'+segment.ref+'"]'),'cross-page directory lost segment');await click('[data-select="'+segment.ref+'"]');assert(w.ctx.step===4,'directory filtered instead of navigated');
 assert(root.querySelector('.creation-assist').getBoundingClientRect().top<root.querySelector('.writing-output').getBoundingClientRect().top,'output above communication');
 assert(document.documentElement.scrollWidth<=innerWidth+2,'horizontal clipping');
 const finalPage=new URLSearchParams(location.search).get('page');if(finalPage){await click('[data-nav-step="'+finalPage+'"]');}root.querySelector('.desk-canvas').scrollTop=0;w.dispose();document.body.dataset.check=JSON.stringify({passed:true,steps:5,scope:'real save/confirm/asset needs/tree/source/fake LLM'});
}catch(e){w?.dispose();document.body.dataset.check=JSON.stringify({passed:false,error:e.stack});}
</script>'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);parser.add_argument('--width',type=int,default=1440);parser.add_argument('--page',default='');args=parser.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    case=CreationTests();case.setUp();case.configure_fake();calls=[]
    picture=io.BytesIO();Image.new('RGB',(32,32),(80,120,90)).save(picture,format='PNG');picture.seek(0)
    item=case.c.post('/api/v5/library/uploads',data={'file':(picture,'fixture.png'),'key':'fixture-image'},content_type='multipart/form-data').get_json()
    case.post('/authoring/projects/'+case.p['id']+'/references',dict(revision=case.p['revision'],asset=item['id'],version=item['snapshot']['id'],media=item['snapshot']['media'][0]['id'],purpose='character',subject='1'))
    case.p=case.service.snapshot(case.p['id'])
    class Fake:
        def send(self,config,secret,payload=None,resource=None):
            context=json.loads(payload['messages'][1]['content']);task=context['task_type'];calls.append(context)
            sample=json.loads(Path('tests/fixtures/creation/llm/'+task+('.full' if task=='h3_prompt' else '')+'.ok.json').read_text(encoding='utf-8-sig'))
            for array in ['blocks','shots','needs']:
                for row in sample['payload'].get(array,[]):row['source_refs']=[] if 'source_refs' in row else row.get('source_refs',[])
            if task in ('screenplay_draft','asset_screenplay'):
                for row in sample['payload']['blocks']:row.pop('source_refs',None)
            if task=='asset_analysis':sample['payload']['needs']=[dict(ref='new_'+str(i),kind='character',name=name,description='剧本中的人物',source_refs=[],media_need='recommended',suggested_asset_refs=[]) for i,name in enumerate(['张三','王五','李四'])]
            if task=='segment_plan':
                for row in sample['payload']['segments']:row['shot_ref']=context['target']['target_ids'][0]
            return dict(choices=[dict(message=dict(content=json.dumps(sample,ensure_ascii=False)),finish_reason='stop')])
    case.service.writing.providers.transport=Fake()
    class Quiet(WSGIRequestHandler):
        def log(self,*args,**kwargs):pass
    def app(env,start):
        if env['PATH_INFO']=='/experience':start('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [PAGE.encode()]
        return case.app(env,start)
    server=make_server('127.0.0.1',0,app,threaded=True,request_handler=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        result=subprocess.run(['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--no-first-run','--disable-background-networking',f'--user-data-dir={out/"profile"}',f'--window-size={args.width},1100','--virtual-time-budget=20000',f'--screenshot={out/"page.png"}','--dump-dom',f'http://127.0.0.1:{server.server_port}/experience?pid={case.p["id"]}&page={args.page}'],capture_output=True,timeout=50)
        dom=result.stdout.decode('utf-8','replace');(out/'page.html').write_text(dom,encoding='utf-8');match=re.search(r'data-check="([^"]+)"',dom);check=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='No completion marker')
        check['requests']=len(calls);check['continued_from_output']=any(any(m['reference_key'].startswith('basis:') for m in c['materials']) for c in calls)
        (out/'checks.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(check,ensure_ascii=False))
        if not check['passed'] or not check['continued_from_output']:raise SystemExit(1)
    finally:server.shutdown();server.server_close();case.doCleanups()

if __name__=='__main__':main()
