import test from 'node:test';
import assert from 'node:assert/strict';
import {ProjectSession} from '../static/studio/core/project-session.js';
import {ProjectCommands} from '../static/studio/core/project-commands.js';
import {ApiError} from '../static/studio/core/api-client.js';
import {ImageSession} from '../static/studio/core/image-session.js';
import {readStamp,currentRead,canReplaceDraft} from '../static/studio/core/async-state.js';
import {uploadForm} from '../static/studio/core/upload-client.js';
import {TASK_STATES} from '../static/studio/core/task-state.js';
import {imageRunStates} from '../static/studio/features/image-results/workspace-view.js';
const project=mode=>({id:'isolated',mode,revision:4,busy:false,segments:[{id:'s',prompt:'draft',attempts:[]}],tasks:[{id:'t',prompt:'draft'}],runs:[],outputs:[]});
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};

test('a read started before save cannot overwrite a replaced project or a newer revision',()=>{
  const session=new ProjectSession(project('swap')),stamp=readStamp(session);
  assert.equal(currentRead(session,stamp,{...project('swap'),revision:3}),false);
  session.replace({...project('swap'),revision:5});
  assert.equal(currentRead(session,stamp,{...project('swap'),revision:99}),false);
  session.dispose();assert.equal(currentRead(session,readStamp(session),session.project),false);
});
test('all draft adapters defer replacement for typing, modal or playing media',()=>{
  let modal=false,focused=false,playing=false;
  const root={ownerDocument:{querySelector:()=>modal,activeElement:{matches:()=>focused}},contains:()=>true,querySelectorAll:()=>[{paused:!playing}]};
  for(const mode of ['swap','image_story','text_story','image_assets','video_assembly']){
    const s={project:project(mode)};
    assert.equal(canReplaceDraft(s,root),true);
    modal=true;assert.equal(canReplaceDraft(s,root),false);modal=false;
    focused=true;assert.equal(canReplaceDraft(s,root),false);focused=false;
    playing=true;assert.equal(canReplaceDraft(s,root),false);playing=false;
    s.dirty=true;assert.equal(canReplaceDraft(s,root),false);
  }
});
test('image polling retains rendered task identity and authored text while reporting task completion',()=>{
  const s=new ImageSession(project('image_assets')),task=s.project.tasks[0];
  assert.equal(s.receive(structuredClone(s.project)),false);assert.equal(s.project.tasks[0],task);
  task.prompt='typed after request';s.edit();
  const next={...project('image_assets'),revision:5,runs:[{state:'success'}],outputs:[{id:'out'}]};
  assert.equal(s.receive(next),false);assert.equal(s.project.tasks[0],task);assert.equal(task.prompt,'typed after request');assert.equal(s.project.outputs[0].id,'out');
  s.dirty=false;assert.equal(s.receive(next),true);assert.equal(s.project.revision,5);s.dispose();
});
test('disposed image save does not submit an apply after delayed planning finishes',async()=>{
  const s=new ImageSession(project('image_assets')),pending=deferred(),calls=[];
  s.request=path=>{calls.push(path);return pending.promise;};s.edit();const saved=s.save();await Promise.resolve();s.dispose();pending.resolve({token:'old'});
  assert.equal(await saved,false);assert.equal(calls.length,1);assert.equal(s.dirty,true);
});
test('upload reports bytes then processing, preserves raw failure, and never retries',async()=>{
  const original=globalThis.XMLHttpRequest;let xhr,count=0;
  globalThis.XMLHttpRequest=class{constructor(){xhr=this;this.upload={};}open(){}send(){count++;}abort(){this.onabort();}};
  try{
    const stages=[],request=uploadForm('/isolated',new FormData(),s=>stages.push(s));
    xhr.upload.onprogress({loaded:50,total:100,lengthComputable:true});xhr.upload.onload();
    assert.equal(stages[1].loaded,50);assert.equal(stages[2].total,null);assert.match(stages[2].phase,/服务器/);
    xhr.status=500;xhr.responseText='server failed after transfer';xhr.onload();
    await assert.rejects(request,e=>e.raw==='server failed after transfer');assert.equal(stages.at(-1),null);assert.equal(count,1);
    const controller=new AbortController(),aborted=uploadForm('/isolated',new FormData(),()=>{},controller.signal);controller.abort();await assert.rejects(aborted,e=>e.name==='AbortError');assert.equal(count,2);
  }finally{globalThis.XMLHttpRequest=original;}
});
test('uncertain and queued states share meanings with the global task list',()=>{
  for(const state of ['waiting','queued','submitting','unknown','failed','cancelled'])assert.equal(imageRunStates[state],TASK_STATES[state]);
  assert.notEqual(TASK_STATES.unknown,TASK_STATES.success);
});
test('unknown submission is not declared failed or repeated before a fresh state read',async()=>{
  let submissions=0;
  const s=new ProjectSession(project('text_story'),async(path,method)=>{
    if(method==='POST'){submissions++;throw new ApiError('response lost',0,null,{kind:'network'});}
    return {...project('text_story'),busy:true,revision:5};
  });
  const commands=new ProjectCommands(s,async()=>true);
  await assert.rejects(commands.run('/generate'),/response lost/);
  assert.equal(s.awaitingStatus,true);assert.equal(s.project.runtime.phase,'提交结果待确认');assert.equal(s.project.runtime.finished,undefined);
  await assert.rejects(commands.run('/generate'),/尚未确认/);assert.equal(submissions,1);
  await s.reload();assert.equal(s.awaitingStatus,false);assert.equal(s.project.busy,true);s.dispose();
});
