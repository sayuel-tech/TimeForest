import test from 'node:test';
import assert from 'node:assert/strict';
import {api, ApiError} from '../static/studio/core/api-client.js';
import {ImageSession} from '../static/studio/core/image-session.js';
import {renderImageWorkspace,generationReason} from '../static/studio/features/image-results/workspace-view.js';
import {mountWorkspace} from '../static/studio/app/image-workspace-controller.js';

const workspaceFixture = mode => {
  const task={id:'task-a',name:'编辑任务 1',submode:mode,prompt:'保留正文',A:null,B:null,mask:null,settings:{left:10,right:20,top:0,bottom:0},models:{}};
  const project={id:'image-fixture',name:'隔离图片',tasks:[task],inputs:[],outputs:[],runs:[],busy:false};
  const fields=['left','right','top','bottom'].map(key=>({key,scope:'settings',group:'picture',type:'number',label:key+'扩展（px）',min:0,max:4096,step:1}));
  return {task,project,catalog:{tools:{single:'单图编辑',dual:'双图编辑',region:'局部重绘／移除',outpaint:'图像扩展'},parameters:{[mode]:fields}},page:'edit',view:{inspectorTab:'assets',saveTarget:'new'},presetNames:{single:[],dual:[],region:[],outpaint:[]}};
};

const fixture = () => ({id:'image-fixture',revision:1,current_task:'task-a',name:'隔离图片',
  tasks:[{id:'task-a',prompt:'未保存正文',settings:{steps:10,seed:null},models:{unet:'sub/current.safetensors'}},
    {id:'task-b',prompt:'另一个任务',settings:{steps:12,seed:7},models:{unet:'other.safetensors'}}],
  runs:[],outputs:[{id:'old-output'}],busy:false});

test('text generation has five tools but no source-upload or editing-canvas controls',()=>{
  const ctx=workspaceFixture('text');ctx.catalog.text_to_image_version=1;ctx.catalog.tools.text='文生图';
  const html=renderImageWorkspace(ctx);
  assert.equal((html.match(/data-tool=/g)||[]).length,5);assert.match(html,/画面描述/);assert.match(html,/描述与创作/);
  assert.doesNotMatch(html,/data-upload|data-library|<canvas|data-pen|data-property-tab="assets"/);
  assert.equal(generationReason(ctx.project,ctx.task),'');ctx.task.prompt='';assert.match(generationReason(ctx.project,ctx.task),/画面描述/);
  ctx.page='results';ctx.project.outputs=[{id:'text-output',task:ctx.task.id,run:'text-run',url:'/text.png'}];
  ctx.project.runs=[{id:'text-run',task:ctx.task.id,state:'success',snapshot:{submode:'text'}}];
  const result=renderImageWorkspace(ctx);assert.doesNotMatch(result,/image-compare-toggle/);assert.match(result,/image-reroll/);assert.match(result,/image-quick-ingest/);
});

test('task discard is explicit, protects busy and old backends, and zero tasks has an add/recovery state',()=>{
  const ctx=workspaceFixture('single');ctx.catalog.task_discard_version=1;
  let html=renderImageWorkspace(ctx);assert.match(html,/id="image-task-discard" class="quiet"  title/);assert.match(html,/废弃当前任务/);
  ctx.project.busy=true;html=renderImageWorkspace(ctx);assert.match(html,/id="image-task-discard" class="quiet" disabled/);
  ctx.project.busy=false;delete ctx.catalog.task_discard_version;html=renderImageWorkspace(ctx);assert.match(html,/请重启导演台后刷新页面以加载任务废弃功能/);
  ctx.task=undefined;ctx.project.tasks=[];html=renderImageWorkspace(ctx);
  assert.match(html,/0 个编辑任务/);assert.match(html,/id="image-new"/);assert.match(html,/查看已废弃任务/);assert.doesNotMatch(html,/image-generate|image-settings|image-task-name/);
});

test('step two exposes reroll, back and collection while step three keeps result-based editing',()=>{
  const ctx=workspaceFixture('single');ctx.page='results';ctx.task.A='source';
  ctx.catalog.quick_ingest_preserves_selection=true;
  ctx.project.outputs=[{id:'out',task:ctx.task.id,url:'/fixture.png',width:80,height:120}];
  let html=renderImageWorkspace(ctx);
  assert.match(html,/id="image-reroll"/);assert.match(html,/返回上一步/);assert.doesNotMatch(html,/继续编辑|调整后再生成/);
  assert.match(html,/下载图片<\/a><button id="image-quick-ingest" >加入资产库/);
  ctx.project.busy=true;html=renderImageWorkspace(ctx);assert.match(html,/id="image-reroll" disabled/);
  delete ctx.catalog.quick_ingest_preserves_selection;html=renderImageWorkspace(ctx);assert.match(html,/id="image-quick-ingest" disabled title="当前后台未加载/);
  ctx.project.outputs[0].library={asset:'saved'};html=renderImageWorkspace(ctx);
  assert.match(html,/已入库 · 查看资产/);assert.doesNotMatch(html,/id="image-quick-ingest"/);
  ctx.page='use';html=renderImageWorkspace(ctx);assert.match(html,/id="image-continue"/);assert.doesNotMatch(html,/id="image-reroll"|id="image-quick-ingest"/);
});

test('API preserves actual engine error details without retrying the mutation', async () => {
  const previous=globalThis.fetch; let calls=0;
  const raw={node_errors:{'27':{errors:[{details:'bad <model> selection'}]}}};
  globalThis.fetch=async()=>{calls++;return new Response(JSON.stringify({error:'输入被引擎拒绝',error_kind:'engine',error_raw:raw}),{status:400});};
  try {await assert.rejects(api('/image-projects/fixture/apply','POST',{token:'fixture'}),error=>{
    assert.ok(error instanceof ApiError);assert.equal(error.kind,'engine');assert.deepEqual(error.raw,raw);return true;
  }); assert.equal(calls,1);} finally {globalThis.fetch=previous;}
});

test('HTTP text and transport failures preserve their real text and source', async()=>{
  const previous=globalThis.fetch;
  try {
    globalThis.fetch=async()=>new Response('upstream temporarily unavailable <html>',{status:502});
    await assert.rejects(api('/image-projects/catalog'),error=>{assert.equal(error.raw,'upstream temporarily unavailable <html>');assert.equal(error.status,502);return true;});
    globalThis.fetch=async()=>{throw new TypeError('fixture connection refused');};
    await assert.rejects(api('/image-projects/catalog'),error=>{assert.equal(error.kind,'network');assert.match(error.raw,/fixture connection refused/);return true;});
    globalThis.fetch=async()=>{throw new DOMException('fixture aborted','AbortError');};
    await assert.rejects(api('/image-projects/catalog'),{name:'AbortError'});
  } finally {globalThis.fetch=previous;}
});

test('image save carries task-specific parameters including fixed zero and preserves other task/output', async()=>{
  const p=fixture(),session=new ImageSession(p),calls=[];
  session.project.tasks[0].settings={steps:13,seed:0};session.edit();
  let saved;
  session.request=async(path,method,body)=>{
    calls.push(path);
    if(path.endsWith('/change-plan')) {saved=structuredClone(body);return {token:'checked'};}
    return {...structuredClone(p),...saved,revision:2};
  };
  await session.save();
  assert.equal(saved.tasks[0].settings.seed,0);assert.equal(saved.tasks[0].settings.steps,13);
  assert.deepEqual(saved.tasks[1],fixture().tasks[1]);assert.equal(session.project.outputs[0].id,'old-output');
  assert.equal(session.project.tasks[0].prompt,'未保存正文');assert.equal(session.dirty,false);
  assert.deepEqual(calls,['/image-projects/image-fixture/change-plan','/image-projects/image-fixture/apply']);session.dispose();
});

test('failed image save keeps the complete outer draft and never applies or generates',async()=>{
  const session=new ImageSession(fixture()),calls=[];session.edit();const before=structuredClone(session.project);
  session.request=async(path)=>{calls.push(path);throw new ApiError('版本冲突',409,'conflict');};
  await assert.rejects(session.save(),/版本冲突/);
  assert.deepEqual(session.project,before);assert.equal(session.dirty,true);assert.equal(session.working,false);
  assert.deepEqual(calls,['/image-projects/image-fixture/change-plan']);session.dispose();
});

test('image workspace has one shared parameter action and project naming stays in project properties',()=>{
  for(const mode of ['single','dual','region','outpaint']){
    const ctx=workspaceFixture(mode),html=renderImageWorkspace(ctx);
    assert.equal((html.match(/制作参数/g)||[]).length,1);
    assert.doesNotMatch(html,/image-settings-inline|data-property-tab="settings"|id="image-rename"/);
    assert.ok(html.includes(`<div class="project-actions"><button id="image-settings">制作参数 <span aria-hidden="true">↗</span></button><small>${ctx.catalog.tools[mode]}</small></div>`));
    assert.match(html,/data-property-tab="project"/);assert.match(html,/id="image-project-name"/);
    assert.doesNotMatch(html,/data-setting="(?:megapixels|output_mp|ratio|steps|seed)"/);
  }
});

test('only outpaint keeps exact canvas expansion controls, next to its canvas tools',()=>{
  for(const mode of ['single','dual','region','outpaint']){
    const html=renderImageWorkspace(workspaceFixture(mode));
    const start=html.indexOf('class="image-canvas-tools"'),end=html.indexOf('class="image-viewport');
    const toolbar=html.slice(start,end);
    for(const key of ['left','right','top','bottom'])assert.equal(toolbar.includes(`data-setting="${key}"`),mode==='outpaint');
    assert.equal(toolbar.includes('id="image-target-ratio"'),mode==='outpaint');
    assert.equal(toolbar.includes('id="image-anchor"'),mode==='outpaint');
    assert.equal((html.match(/data-tool=/g)||[]).length,4);
    assert.match(html,/id="image-prompt"/);assert.match(html,/data-property-tab="assets"/);assert.match(html,/data-property-tab="inputs"/);
  }
});

test('outpaint anchor changes during a pending geometry refresh use only the current task source',async t=>{
  const ctx=workspaceFixture('outpaint'),first=ctx.task;
  first.A='source-a';first.settings={left:504,right:504,top:0,bottom:0};
  const second={...structuredClone(first),id:'task-b',A:'source-b',settings:{left:17,right:19,top:0,bottom:0}};
  const project={...ctx.project,current_task:first.id,tasks:[first,second],inputs:[
    {id:'source-a',name:'A',url:'/fixture-a.png',width:720,height:960},
    {id:'source-b',name:'B',url:'/fixture-b.png',width:960,height:960},
  ]};
  const element=()=>({value:'',dataset:{},listeners:{},style:{},classList:{toggle(){}},
    addEventListener(name,fn){this.listeners[name]=fn;},setAttribute(){},setCustomValidity(){},
    prepend(){},querySelector(){return null;},querySelectorAll(){return []},getContext(){return {}}});
  const ratio=element(),anchor=element(),host=element(),surface=element();
  surface.width=720;surface.height=960;host.querySelector=selector=>selector==='canvas'?surface:null;
  host.clientWidth=720;host.clientHeight=960;
  const pads=Object.fromEntries(['left','right','top','bottom'].map(key=>[key,{...element(),dataset:{setting:key}}]));
  const tasks=[{...element(),dataset:{task:first.id}},{...element(),dataset:{task:second.id}}];
  const root={...element(),ownerDocument:{activeElement:null,defaultView:{scrollX:0,scrollY:0,scrollTo(){}}},contains(){return false;},querySelector(selector){
    if(selector==='.image-viewport')return host;
    if(selector==='#image-target-ratio')return ratio;
    if(selector==='#image-anchor')return anchor;
    return pads[selector.match(/^\[data-setting="(\w+)"\]$/)?.[1]]||null;
  },querySelectorAll(selector){return selector==='[data-setting]'?Object.values(pads):selector==='[data-task]'?tasks:[]}};
  const pending=[];
  const replacements={
    window:{addEventListener(){},removeEventListener(){}},
    document:{createElement:element,addEventListener(){},removeEventListener(){}},
    location:{hash:'#/p/image-fixture'},
    sessionStorage:{getItem(){return null;},setItem(){}},
    requestAnimationFrame(){},
    Image:class{naturalWidth=0;},
    ResizeObserver:class{observe(){} disconnect(){}},
    fetch:async(path,options)=>{
      if(path.includes('/prompt-library/pending/'))return new Response(JSON.stringify({items:[]}));
      assert.ok(path.endsWith('/geometry'));
      return new Promise(resolve=>pending.push({resolve,body:JSON.parse(options.body)}));
    },
  };
  let workspace;t.after(()=>workspace?.dispose());
  for(const [key,value] of Object.entries(replacements)){
    const descriptor=Object.getOwnPropertyDescriptor(globalThis,key);
    Object.defineProperty(globalThis,key,{configurable:true,writable:true,value});
    t.after(()=>{if(descriptor)Object.defineProperty(globalThis,key,descriptor);else delete globalThis[key];});
  }
  workspace=mountWorkspace(root,project,ctx.catalog);
  const reply=async(index,work)=>{
    pending[index].resolve(new Response(JSON.stringify({work,canvas:work,output:work,offset:[0,0]})));
    await new Promise(resolve=>setImmediate(resolve));
  };
  await reply(0,[888,1184]);
  ratio.value='16:9';anchor.value='center';ratio.listeners.change();
  assert.deepEqual([first.settings.left,first.settings.right],[608,609]);
  // The first request is still pending when the user chooses another anchor.
  anchor.value='left';anchor.listeners.change();
  assert.deepEqual([first.settings.left,first.settings.right],[0,1217]);
  assert.equal(pending.length,3);
  await tasks[1].onclick();
  const secondBefore=structuredClone(second.settings);
  ratio.value='16:9';anchor.value='left';anchor.listeners.change();
  assert.deepEqual(second.settings,secondBefore,'a new task cannot reuse the preceding canvas dimensions');
  await reply(1,[888,1184]);await reply(2,[888,1184]);
  assert.deepEqual(second.settings,secondBefore,'late responses from the preceding task are ignored');
  await reply(3,[1024,1024]);anchor.listeners.change();
  assert.deepEqual([second.settings.left,second.settings.right],[0,796]);
  assert.equal(pending.at(-1).body.A,'source-b');
  assert.deepEqual([pending.at(-1).body.settings.left,pending.at(-1).body.settings.right],[0,796]);
  assert.deepEqual([first.settings.left,first.settings.right],[0,1217]);
});
