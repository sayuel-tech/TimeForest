import test from 'node:test';
import assert from 'node:assert/strict';
import {ImageSession} from '../static/studio/core/image-session.js';
import {ApiError} from '../static/studio/core/api-client.js';
import {acceptsImage,imageDestinations} from '../static/studio/features/asset-picker/destinations.js';

test('image destinations distinguish segments and live continuation extensions',()=>{
  for(const mode of ['swap','image_story','text_story']){
    const p={mode,segments:[{id:'segment'}]};assert.ok(acceptsImage(p));assert.equal(imageDestinations(p)[0].id,'segment');
  }
  const p={mode:'video_assembly',assembly:{clips:[{id:'clip',name:'片段',extensions:[{id:'live'},{id:'removed',removed_at:1}]},{removed_at:1,extensions:[{id:'hidden'}]}]}};
  assert.ok(acceptsImage(p));assert.deepEqual(imageDestinations(p).map(t=>t.id),['live']);
  for(const mode of ['image','unsupported'])assert.equal(acceptsImage({mode}),false);
  assert.equal(acceptsImage({...p,deleted_at:1}),false);
});

for(const editAgain of [false,true])test(`image retries committed apply before another plan; newer draft=${editAgain}`,async()=>{
  const p={id:'image',revision:1,tasks:[{id:'one',prompt:'original'}],runs:[],outputs:[]};
  const s=new ImageSession(p);s.edit();let fail=true,token=0,committed;const calls=[];
  s.request=async(path,method,body)=>{
    calls.push([path,body]);
    if(path.endsWith('/change-plan')){committed={...structuredClone(p),...structuredClone(body),revision:body.revision+1};return {token:String(++token)};}
    if(fail){fail=false;throw new ApiError('library unavailable',503,'LIBRARY_USAGE_PENDING');}
    return structuredClone(committed);
  };
  await assert.rejects(s.save(),/library unavailable/);assert.ok(s.dirty);
  if(editAgain){s.project.tasks[0].prompt='newer';s.edit();}
  await s.save();assert.equal(s.dirty,false);
  assert.equal(calls[2][0],'/image-projects/image/apply');assert.equal(calls[2][1].token,'1');
  assert.equal(s.project.tasks[0].prompt,editAgain?'newer':'original');
  assert.equal(s.project.revision,editAgain?3:2);assert.equal(token,editAgain?2:1);s.dispose();
});

test('rejected image revision does not retain an unusable apply token',async()=>{
  const s=new ImageSession({id:'image',revision:1,tasks:[]});s.edit();
  s.request=async path=>{if(path.endsWith('/change-plan'))return {token:'stale'};throw new ApiError('conflict',409);};
  await assert.rejects(s.save(),/conflict/);assert.equal(s.retryApply,null);assert.ok(s.dirty);s.dispose();
});
