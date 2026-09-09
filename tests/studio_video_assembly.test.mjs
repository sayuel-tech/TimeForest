import test from 'node:test';
import assert from 'node:assert/strict';
import {activeClips,moveClip,savePayload} from '../static/studio/modes/video-assembly/workspace.js';
import {resetParameters,switchRecipe,visibleParameters} from '../static/studio/modes/video-assembly/settings.js';
import {restoreRequest} from '../static/studio/pages/asset-library/recycle-bin.js';
import {taskCard,confirmation} from '../static/studio/features/task-center/index.js';
import {trackItems,moveTrack} from '../static/studio/modes/video-assembly/track.js';

test('selected continuation is one independent delivery slot, including legacy projects',()=>{
  const p={revision:2,assembly_track_version:1,assembly:{draft_revision:1,output:{},clips:[{id:'a',name:'A',start:0,end:3,extensions:[{id:'e',selected:'r'}]},{id:'b',name:'B',start:0,end:4,extensions:[]}],runs:[{id:'r',extension:'e',state:'success',report:{duration:5},url:'/r.mp4'}]}};
  assert.deepEqual(trackItems(p).map(r=>r.key),['clip:a','extension:e','clip:b']);
  const moved=moveTrack(p,'extension:e',1);
  assert.deepEqual(savePayload(moved).track_order,['clip:a','clip:b','extension:e']);
  assert.deepEqual(moved.assembly.clips.map(c=>c.id),['a','b']);
  assert.equal(moved.assembly.clips[0].extensions[0].selected,'r');
  assert.deepEqual(trackItems(p).map(r=>r.key),['clip:a','extension:e','clip:b']);
  moved.assembly.track_order.push('extension:e','clip:foreign');
  assert.equal(trackItems(moved).length,3);
  p.assembly.runs[0].removed_at=1;
  assert.deepEqual(trackItems(moved).map(r=>r.key),['clip:a','clip:b']);
});

test('sequence sorting preserves removed records and input identity',()=>{
  const clips=['a','b','c'].map(id=>({id,file:id,extensions:[]}));clips.push({id:'trash',removed_at:1,extensions:[]});
  const p={revision:2,name:'n',assembly:{clips,output:{fps:24}}};
  const q=moveClip(p,'a',2);assert.deepEqual(activeClips(q).map(c=>c.id),['b','c','a']);
  assert.equal(q.assembly.clips[3].id,'trash');assert.equal(savePayload(q).clips.length,3);assert.equal(p.assembly.clips[0].id,'a');
});
test('parameter cancel/reset and recipe changes operate on a copy',()=>{
  const e={recipe:'dance_split',prompt:'保留正文',seed_mode:'fixed',seed:'0',sound:'mute',configurations:{dance_split:{steps:16},official_image:{steps:24}}};
  const catalog={defaults:{dance_split:{steps:12}}};const reset=resetParameters(e,catalog);
  assert.equal(e.configurations.dance_split.steps,16);assert.equal(reset.configurations.dance_split.steps,12);assert.equal(reset.prompt,e.prompt);
  assert.equal(switchRecipe(switchRecipe(e,'official_image'),'dance_split').configurations.dance_split.steps,16);
  assert.equal(e.seed,'0');assert.equal(reset.seed_mode,'random');
});
test('parameters follow recipe descriptor and conditional field visibility',()=>{
  const catalog={recipes:[{id:'official_image',parameters:[{key:'steps'},{key:'width',when:{size_mode:'custom'}}]}]};
  const e={recipe:'official_image',configurations:{official_image:{size_mode:'area'}}};
  assert.deepEqual(visibleParameters(catalog,e).map(x=>x.key),['steps']);
  e.configurations.official_image.size_mode='custom';assert.equal(visibleParameters(catalog,e).length,2);
});
test('three new removal types restore with exact project revision',()=>{
  for(const kind of ['clip','extension','run'])assert.deepEqual(restoreRequest({type:'assembly_'+kind,id:'x',project:'p',revision:3}),{path:'/assembly/p/visibility',body:{revision:3,id:'x',kind,removed:false}});
});
test('global active task has clear stop and recovery labels',()=>{
  const task={kind:'assembly',id:'abc',project:'p',name:'拼接',state:'unknown',actions:['recover','close'],active:true,url:'#/p/p'};
  const html=taskCard(task,0);assert.match(html,/查询恢复/);assert.doesNotMatch(html,/undefined/);
  assert.match(confirmation(task,'recover'),/不会重复/);
});
