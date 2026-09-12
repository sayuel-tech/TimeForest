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
 if(new URLSearchParams(location.search).has('q2')){
   const originalFetch=window.fetch,prior=await get(),count=prior.creation_jobs.length;
   input('[data-ai-instruction]','保留冲突，补充人物行动。失败时保留本次沟通。');
   const prose='清晨的修车铺里，张三收起扳手，王五把旧车推进门。雨声渐轻，两人终于说出昨天没有说完的话。';
   input('[data-candidate-text]',Array(12).fill(prose).join(String.fromCharCode(10)));
   const node=root.querySelector('[data-candidate-text]');node.focus();w.session.receive({...prior,revision:prior.revision+1,name:'迟到状态'});
   assert(root.querySelector('[data-candidate-text]')===node&&node.value.includes(prose),'late response replaced writing draft');
   window.fetch=(url,opts)=>String(url).endsWith('/save')&&opts?.method==='POST'?Promise.resolve(new Response(JSON.stringify({error:'隔离保存失败'}),{status:503,headers:{'Content-Type':'application/json'}})):originalFetch(url,opts);
   try{await click('[data-ai-task="screenplay_draft"]');await wait(()=>!w.session.actionPending&&!w.session.working);}finally{window.fetch=originalFetch;}
   assert(w.ctx.error,'save failure not shown');assert((await get()).creation_jobs.length===count,'save failure still submitted model job');
   assert(root.querySelector('[data-ai-instruction]').value.includes('失败时保留')&&root.querySelector('[data-candidate-text]').value.includes(prose),'save failure lost input');
   await click('[data-save-output]');await settled();
   assert(root.querySelector('.writing-version-label').textContent.includes('可继续编辑'),'current editing state hidden');
   assert(!root.querySelector('[data-output]').closest('summary'),'version action nested in disclosure');
   await click('[data-output="'+first.candidate_id+'"]');assert(!root.querySelector('[data-candidate-text]').value.includes(prose),'older output mixed with current prose');
   await click('[data-output="'+prior.candidates.at(-1).candidate_id+'"]');assert(root.querySelector('[data-candidate-text]').value.includes(prose),'current saved prose lost on version return');
 }
 await click('[data-nav-step="2"]');assert(!root.querySelector('.desk-inspector'),'asset page still has right inspector');assert(!root.querySelector('[data-candidate-text]'),'screenplay candidate leaked');
 await generate('asset_analysis');await click('[data-apply-candidate]');await settled();assert(root.querySelectorAll('[data-need-card]').length===(new URLSearchParams(location.search).has('q1')?8:3),'needs not turned into cards');if(new URLSearchParams(location.search).has('q1')){const rev=(await get()).revision;await click('.asset-need-slot');await wait(()=>document.querySelector('.picker-cancel'));assert(document.querySelector('.library-picker h2').textContent.includes('张三'),'binding target unclear');await click('.picker-cancel');await settled();assert((await get()).revision===rev,'cancel changed project');}const revision=(await get()).revision;await click('[data-need-filter=character]');w.render();assert(root.querySelector('[data-need-filter=character]').getAttribute('aria-pressed')==='true','category view lost after redraw');assert((await get()).revision===revision,'filter wrote project');await click('[data-need-filter=all]');
 for(const e of root.querySelectorAll('[data-need-source]')){e.value='text_only';e.dispatchEvent(new Event('change'));}
 await click('[data-save]');await settled();root.querySelector('[data-bind-existing]').closest('.asset-need-options').open=true;root.querySelector('[data-bind-existing]').closest('details').open=true;await click('[data-bind-existing]');await settled();assert((await get()).content.layers.find(l=>l.layer==='asset_bindings').content.bindings.some(b=>b.state==='bound'&&b.reference_id),'existing reference was not bound to named card');
 if(new URLSearchParams(location.search).has('q1')){
   const before=await get(),bindings=before.content.layers.find(l=>l.layer==='asset_bindings').content.bindings;
   const first=bindings.find(b=>b.state==='bound'),identity=first.need_ref;
   await click('.asset-need-actions [data-need-pick]');await wait(()=>document.querySelector('.library-pick-card'));
   await click('.picker-cancel');await settled();assert((await get()).revision===before.revision,'replacement cancel wrote project');
   await click('.asset-need-actions [data-need-pick]');await wait(()=>document.querySelector('.library-pick-card'));
   await click('.library-pick-card');await settled();
   const after=(await get()).content.layers.find(l=>l.layer==='asset_bindings').content.bindings.find(b=>b.need_ref===identity);
   assert(after.state==='bound'&&after.asset_ref===first.asset_ref&&after.asset_version===first.asset_version,'picker lost target or fixed asset');
   w.dispose();w=mountWorkspace(root,await get());await click('[data-nav-step="2"]');
   assert(root.querySelector('[data-need-card="'+identity+'"] .asset-need-media a'),'bound preview not restored');
 }
 await click('[data-save]');await settled();await click('[data-asset-task="asset_screenplay"]');await generate('asset_screenplay');await click('[data-apply-candidate]');await settled();
 await click('[data-select=""]');await generate('storyboard');await click('[data-apply-candidate]');await settled();const shot=(await get()).content.layers.find(l=>l.layer==='storyboard').content.shots[0];
 await click('[data-select="'+shot.ref+'"]');assert(w.ctx.step===3,'shot route');input('[data-ai-instruction]','只改当前分镜');await generate('local_rewrite');input('[data-candidate-text]','两人在修车铺相遇，欲言又止。');await click('[data-apply-candidate]');await settled();assert((await get()).content.confirmations.some(c=>c.layer==='storyboard'&&c.target_id===shot.ref),'shot confirmation not scoped');await click('[data-shot-task="split"]');await generate('segment_plan');await click('[data-apply-candidate]');await settled();
 const segment=(await get()).content.layers.find(l=>l.layer==='segment').content.segments[0];if(!root.querySelector('[data-select="'+segment.ref+'"]'))await click('[data-expand="'+shot.ref+'"]');await click('[data-select="'+segment.ref+'"]');assert(w.ctx.step===4,'segment route');
 const policy=root.querySelector('[data-asset-policy]');policy.value='project';policy.dispatchEvent(new Event('change'));await click('[data-save]');await settled();assert((await get()).content.layers.find(l=>l.layer==='asset_bindings').content.policies[segment.ref]==='project','source not persisted');
 await click('[data-clip-task="rewrite"]');input('[data-ai-instruction]','细化当前片段');await generate('local_rewrite');await click('[data-apply-candidate]');await settled();await click('[data-clip-task="prompt"]');await generate('h3_prompt');await click('[data-apply-candidate]');await settled();
 if(new URLSearchParams(location.search).has('q2b')){
   const change=(selector,value)=>{const el=root.querySelector(selector);assert(el,'missing '+selector);el.value=value;el.dispatchEvent(new Event('change'));};
   await click('[data-select="'+shot.ref+'"]');change('[data-need-source]','text_only');await click('[data-save]');await settled();
   await click('[data-select="'+segment.ref+'"]');change('[data-asset-policy]','parent');await click('[data-save]');await settled();
   assert(root.querySelector('.asset-scope-context').textContent.includes(shot.title),'asset scope has no shot name');
   assert(root.querySelector('.desk-canvas > h2').textContent.includes('片段 1'),'active clip unclear');
   assert(root.querySelector('.asset-need-origin').hash.includes(shot.ref),'inherited source does not point to shot');
   change('[data-asset-policy]','project');assert(root.querySelector('[data-need-card] .badge').textContent==='已绑定','project policy ignored');
   change('[data-need-source]','disabled');change('[data-asset-policy]','parent');assert(root.querySelector('[data-need-card] .badge').textContent==='不使用','policy erased local override');assert(root.querySelector('[data-binding-policy-note]').textContent.includes('1 项'),'local override not explained');
   change('[data-need-source]','inherit');await click('[data-save]');await settled();
   input('[data-ai-instruction]','只属于当前片段的沟通');await click('.asset-need-origin');await wait(()=>document.querySelector('.choice-dialog'));
   await click('[data-choice="0"]');assert(w.ctx.selected===segment.ref,'cancel source jump left clip');assert(root.querySelector('[data-ai-instruction]').value==='只属于当前片段的沟通','cancel lost clip draft');
   await click('.asset-need-origin');await wait(()=>document.querySelector('.choice-dialog'));await click('[data-choice="2"]');await wait(()=>!document.querySelector('.choice-dialog'));await settled();
   assert(w.ctx.step===3&&w.ctx.selected===shot.ref,'source jump did not locate shot');assert(root.querySelector('[data-ai-instruction]').value!=='只属于当前片段的沟通','clip dialogue leaked to shot');
   await click('[data-select="'+segment.ref+'"]');assert(root.querySelector('[data-ai-instruction]').value==='只属于当前片段的沟通','return lost saved clip dialogue');
   if(innerWidth<1180){await click('[data-toggle-inspector]');assert(root.querySelector('.asset-scope-context').getBoundingClientRect().height>0,'asset drawer not visible');await click('[data-close-inspector]');}
 }
 await click('[data-nav-step="2"]');assert(root.querySelector('[data-select="'+segment.ref+'"]'),'cross-page directory lost segment');await click('[data-select="'+segment.ref+'"]');assert(w.ctx.step===4,'directory filtered instead of navigated');
 assert(root.querySelector('.creation-assist').getBoundingClientRect().top<root.querySelector('.writing-output').getBoundingClientRect().top,'output above communication');
 assert(document.documentElement.scrollWidth<=innerWidth+2,'horizontal clipping');
 const optionsPanel=root.querySelector('.segment-options'),writingPanel=root.querySelector('.writing-output-zone');
 if(optionsPanel&&writingPanel)assert(optionsPanel.getBoundingClientRect().top>=writingPanel.getBoundingClientRect().bottom-2,'segment controls overlap writing output');
 if(new URLSearchParams(location.search).has('q2')){
   await click('[data-nav-step="1"]');
   const conversation=root.querySelector('.writing-dialogue-expanded'),instruction=conversation.querySelector('textarea');
   assert(instruction.getBoundingClientRect().width>=conversation.clientWidth*.9,'communication width restricted');
   assert(instruction.clientHeight>=76,'communication collapsed into one line');
   const summary=root.querySelector('.writing-version-label');assert(summary.textContent.includes('可继续编辑'),'editing state not visible');
   root.querySelector('.writing-output-zone').scrollTop=0;root.querySelector('[data-candidate-text]').scrollTop=0;
 }
 const finalPage=new URLSearchParams(location.search).get('page');if(finalPage&&w.ctx.step!==Number(finalPage)){await click('[data-nav-step="'+finalPage+'"]');}if(new URLSearchParams(location.search).has('q1')){for(const [index,state] of [[1,'pending'],[2,'pending'],[3,'disabled']]){const select=root.querySelectorAll('[data-need-source]')[index];select.value=state;select.dispatchEvent(new Event('change'));}const card=root.querySelector('[data-need-card]'),name=card.querySelector('h3');assert(parseFloat(getComputedStyle(name).fontSize)>=15,'asset name too small');assert(card.querySelector('.asset-need-media').getBoundingClientRect().height>=100,'asset preview too small');assert(document.documentElement.scrollWidth<=innerWidth+2,'asset board overflow');}root.querySelectorAll('.asset-need-options[open]').forEach(d=>d.querySelector('summary').click());root.querySelector('.desk-canvas').scrollTop=0;const bodyArea=root.querySelector('[data-candidate-text]');let readableLines=null;if(bodyArea&&finalPage==='2'){const b=bodyArea.getBoundingClientRect(),st=getComputedStyle(bodyArea);let bottom=Math.min(b.bottom,root.querySelector('.savebar').getBoundingClientRect().top);for(let parent=bodyArea.parentElement;parent&&parent!==root;parent=parent.parentElement)if(['auto','hidden','scroll'].includes(getComputedStyle(parent).overflowY))bottom=Math.min(bottom,parent.getBoundingClientRect().bottom);readableLines=Math.max(0,Math.floor((bottom-b.top-parseFloat(st.paddingTop))/parseFloat(st.lineHeight)));}let scrolledReadableLines=null;if(new URLSearchParams(location.search).has('q1')&&bodyArea){bodyArea.scrollIntoView({block:'start'});await pause();const r=bodyArea.getBoundingClientRect(),canvas=root.querySelector('.desk-canvas').getBoundingClientRect(),style=getComputedStyle(bodyArea);scrolledReadableLines=Math.floor((Math.min(r.bottom,canvas.bottom)-Math.max(r.top,canvas.top)-parseFloat(style.paddingTop))/parseFloat(style.lineHeight));assert(scrolledReadableLines>=4,'asset script cannot be read after scrolling');assert(bodyArea.clientWidth>=canvas.width*.8,'asset script unnecessarily narrow');root.querySelector('.desk-canvas').scrollTop=0;}if(new URLSearchParams(location.search).get('density')==='1')assert(readableLines>=6,'density: fewer than six visible body lines: '+readableLines);if(innerWidth===1440&&finalPage==='2'&&!new URLSearchParams(location.search).has('q1'))assert(root.querySelector('[data-candidate-text]').getBoundingClientRect().top<root.querySelector('.savebar').getBoundingClientRect().top,'asset script body absent from first viewport');w.dispose();document.body.dataset.check=JSON.stringify({passed:true,steps:5,scope:'real save/confirm/asset needs/tree/source/fake LLM',readableLines,scrolledReadableLines,geometry:[...root.querySelectorAll('.asset-needs-heading,.asset-needs-toolbar,.asset-need-card,.asset-need-title,.asset-need-description,.asset-need-actions,.asset-need-options')].slice(0,8).map(e=>({cls:e.className,h:e.getBoundingClientRect().height,margin:getComputedStyle(e).margin,padding:getComputedStyle(e).padding,gap:getComputedStyle(e).gap}))});
}catch(e){w?.dispose();document.body.dataset.check=JSON.stringify({passed:false,error:e.stack});}
</script>'''

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);parser.add_argument('--width',type=int,default=1440);parser.add_argument('--page',default='');parser.add_argument('--r1',action='store_true');parser.add_argument('--height',type=int);parser.add_argument('--density',action='store_true');parser.add_argument('--q1',action='store_true');parser.add_argument('--q2',action='store_true');parser.add_argument('--q2b',action='store_true');args=parser.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
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
            if task=='asset_screenplay':sample['payload']['blocks'][0]['text']='\n'.join(['清晨的修车铺里，张三收起扳手，王五把旧车推进门。窗外雨声渐轻，两人开始谈起昨天未说完的事。']*12)
            if task=='asset_analysis':sample['payload']['needs']=[dict(ref='new_'+str(i),kind='character',name=name,description='剧本中的人物',source_refs=[],media_need='recommended',suggested_asset_refs=[]) for i,name in enumerate(['张三','王五','李四'])]
            if task=='asset_analysis' and args.q1:
                sample['payload']['needs']=[dict(ref='new_'+str(i),kind=kind,name=name,description='当前剧本需要的'+name,source_refs=[],media_need='recommended',suggested_asset_refs=[],**({'subject_ref':'new_0'} if kind in ('costume','voice') else {})) for i,(kind,name) in enumerate([('character','张三'),('character','王五'),('scene','修车铺'),('scene','街道'),('costume','张三的工作服'),('voice','张三的声音'),('prop','旧自行车'),('style','暖色胶片')])]
            if task=='segment_plan':
                for row in sample['payload']['segments']:row['shot_ref']=context['target']['target_ids'][0]
            return dict(choices=[dict(message=dict(content=json.dumps(sample,ensure_ascii=False)),finish_reason='stop')])
    case.service.writing.providers.transport=Fake()
    class Quiet(WSGIRequestHandler):
        def log(self,*args,**kwargs):pass
    page=PAGE
    if args.r1:
        from tests.uiux_r1_shell import application_shell
        page=application_shell(page)
    def app(env,start):
        if env['PATH_INFO']=='/experience':start('200 OK',[('Content-Type','text/html; charset=utf-8')]);return [page.encode()]
        return case.app(env,start)
    server=make_server('127.0.0.1',0,app,threaded=True,request_handler=Quiet);threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        url=f'http://127.0.0.1:{server.server_port}/experience?pid={case.p["id"]}&page={args.page}&density={int(args.density)}'+('&q1=1' if args.q1 else '')+('&q2=1' if args.q2 else '')+('&q2b=1' if args.q2b else '')
        if args.r1:
            command=[sys.executable,str(Path(__file__).with_name('uiux_browser_capture.py')),url,str(out/'page.png'),str(args.width),str(args.height or (960 if args.width==1440 else 900))]
        else:
            command=['C:/Program Files/Google/Chrome/Application/chrome.exe','--headless=new','--disable-gpu','--no-first-run','--disable-background-networking',f'--user-data-dir={out/"profile"}',f'--window-size={args.width},1100','--virtual-time-budget=20000',f'--screenshot={out/"page.png"}','--dump-dom',url]
        result=subprocess.run(command,capture_output=True,timeout=60)
        dom=result.stdout.decode('utf-8','replace');(out/'page.html').write_text(dom,encoding='utf-8');match=re.search(r'data-check="([^"]+)"',dom);check=json.loads(html.unescape(match[1])) if match else dict(passed=False,error='No completion marker')
        check['requests']=len(calls);check['continued_from_output']=any(any(m['reference_key'].startswith('basis:') for m in c['materials']) for c in calls)
        (out/'checks.json').write_text(json.dumps(check,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(check,ensure_ascii=False))
        if not check['passed'] or not check['continued_from_output']:raise SystemExit(1)
    finally:server.shutdown();server.server_close();case.doCleanups()

if __name__=='__main__':main()
