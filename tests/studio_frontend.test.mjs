import test from 'node:test';
import assert from 'node:assert/strict';
import {ProjectSession} from '../static/studio/core/project-session.js';
import {ProjectCommands} from '../static/studio/core/project-commands.js';
import {visibleParameters,geometryPreview} from '../static/studio/core/capability-client.js';
import {registerMode,getMode,listModes} from '../static/studio/app/mode-registry.js';
const fixture=()=>({id:'project-a',revision:1,mode:'text_story',settings:{render_cap:15},segments:[{id:'s1',index:0,prompt:'原文',assets:[],inherit_ids:[],attempts:[]}],asset_library:[],duration:15,storyboard_version:1,timing_mode:'natural'});
test('save coalesces requests and cancellation never applies or generates',async()=>{
  const calls=[];const request=async(path)=>{calls.push(path);return {requires_confirmation:true,summary:['变更'],segments:[],token:'x'};};
  const s=new ProjectSession(fixture(),request);s.markDirty();
  const a=s.save(async()=>false),b=s.save(async()=>false);assert.equal(a,b);assert.equal(await a,false);assert.equal(calls.length,1);assert.equal(s.dirty,true);s.dispose();
});
test('generate waits for save and uses confirmed current project',async()=>{
  const calls=[];const request=async(path)=>{calls.push(path);if(path.endsWith('/change-plan'))return {requires_confirmation:false,token:'t'};return {...fixture(),revision:2};};
  const s=new ProjectSession(fixture(),request);s.markDirty();const c=new ProjectCommands(s,async()=>true);
  await c.run('/generate',{index:0});assert.deepEqual(calls,['/projects/project-a/change-plan','/projects/project-a/apply','/projects/project-a/generate','/projects/project-a']);assert.equal(s.dirty,false);s.dispose();
});
test('failed save blocks execution and preserves text',async()=>{
  const calls=[];const s=new ProjectSession(fixture(),async(path)=>{calls.push(path);throw new Error('版本冲突');});s.project.segments[0].prompt='保留新正文';s.markDirty();
  await assert.rejects(new ProjectCommands(s,async()=>true).run('/generate',{}));assert.equal(calls.length,1);assert.equal(s.project.segments[0].prompt,'保留新正文');assert.equal(s.dirty,true);assert.equal(s.working,false);s.dispose();
});
test('disposed session ignores late server response',async()=>{
  let release;const s=new ProjectSession(fixture(),()=>new Promise(resolve=>release=resolve));let events=0;s.subscribe(()=>events++);const pending=s.reload();s.dispose();release({...fixture(),id:'wrong',revision:2});await pending;assert.equal(s.project.id,'project-a');assert.equal(events,0);
});
test('preview preserves text entered while planning and ignores stale results',async()=>{
  const releases=[];const s=new ProjectSession(fixture(),()=>new Promise(resolve=>releases.push(resolve)));
  const first=s.preview();const second=s.preview();s.project.segments[0].prompt='输入中的文字';
  releases[1]({segments:[{...fixture().segments[0],deliver:345}],duration:14.375});await second;
  releases[0]({segments:[],duration:0});await first;assert.equal(s.project.segments.length,1);assert.equal(s.project.segments[0].prompt,'输入中的文字');s.dispose();
});
test('capability conditions and geometry reflect real declared configuration',()=>{
  assert.deepEqual(visibleParameters({parameters:[{key:'width',when:{size_mode:'custom'}},{key:'steps'}]},{size_mode:'area'}).map(f=>f.key),['steps']);
  assert.deepEqual(geometryPreview({size_mode:'area',megapixels:.3,aspect:'9:16',scale:1.5},{two_pass:true}),{w:416,h:736,ow:640,oh:1088});
});
test('new mode registers independent workspace without editing existing modes',async()=>{
  const count=listModes().length;let disposed=false;
  registerMode({id:'acceptance-demo',name:'隔离演示',load:async()=>({renderEdit:()=>'<article>独立布局</article>',dispose:()=>{disposed=true;}})});
  const mode=await getMode('acceptance-demo').load();assert.equal(listModes().length,count+1);assert.match(mode.renderEdit(),/独立布局/);mode.dispose();assert.ok(disposed);assert.equal(getMode('unknown'),undefined);assert.throws(()=>registerMode({id:'acceptance-demo',load:()=>{}}));
});

test('watch disposal clears timers and ignores an in-flight response', async()=>{
  const {watchProject}=await import('../static/studio/core/progress-channel.js');
  const original={setTimeout:globalThis.setTimeout,clearTimeout:globalThis.clearTimeout,setInterval:globalThis.setInterval,clearInterval:globalThis.clearInterval};
  const timers=new Map();let serial=0,release,events=0;
  globalThis.setTimeout=globalThis.setInterval=(fn)=>{const id=++serial;timers.set(id,fn);return id;};
  globalThis.clearTimeout=globalThis.clearInterval=(id)=>timers.delete(id);
  try {
    const s=new ProjectSession(fixture(),()=>new Promise(resolve=>release=resolve));s.subscribe(()=>events++);
    const stop=watchProject(s,()=>{});assert.equal(timers.size,2);
    const pending=timers.get(2)();stop();s.dispose();assert.equal(timers.size,0);
    release({...fixture(),revision:99});await pending;assert.equal(events,0);assert.equal(timers.size,0);
  } finally {Object.assign(globalThis,original);}
});
