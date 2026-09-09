import test from 'node:test';
import assert from 'node:assert/strict';
import {snapshotChange} from '../static/studio/core/snapshot-update.js';
import {projectContent} from '../static/studio/contracts/project-refresh.js';
import {ProjectSession} from '../static/studio/core/project-session.js';
import {ImageSession} from '../static/studio/core/image-session.js';

test('seven modes distinguish progress from content, terminal actions and result changes',()=>{
  for(const mode of ['swap','image_story','text_story','image','assembly','authoring','movie']){
    const record={id:'r',state:'running',note:'first',phase:'first',updated:1,progress:{step:1}};
    const p={id:'p',mode,kind:mode,revision:1,name:'project',busy:true,segments:[],runtime:{step:1},...(mode==='image'?{runs:[record]}:mode==='assembly'?{assembly:{runs:[record]}}:['authoring','movie'].includes(mode)?{creation_jobs:[record]}:{})};
    const next=structuredClone(p);next.revision++;next.updated=2;next.runtime.step=2;
    const run=mode==='image'?next.runs[0]:mode==='assembly'?next.assembly.runs[0]:['authoring','movie'].includes(mode)?next.creation_jobs[0]:null;
    if(run){run.note='second';run.phase='second';run.progress.step=2;run.updated=2;}
    assert.equal(snapshotChange(p,p,projectContent),'none',mode);
    assert.equal(snapshotChange(p,next,projectContent),'status',mode);
    const renamed={...next,name:'remote edit'};assert.equal(snapshotChange(p,renamed,projectContent),'content',mode);
    const finished={...next,busy:false};assert.equal(snapshotChange(p,finished,projectContent),'content',mode);
    if(run){run.state='success';assert.equal(snapshotChange(p,next,projectContent),'content',mode);}
  }
});
test('three video modes keep editor identity while progress/revision changes',()=>{
  for(const mode of ['swap','image_story','text_story']){
    const s=new ProjectSession({id:'p',mode,revision:1,segments:[{id:'s',prompt:'text'}],runtime:{step:1}}),before=s.project,events=[];
    s.subscribe(type=>events.push(type));const next=structuredClone(before);next.runtime.step=2;next.revision++;
    s.receive(next);assert.equal(s.project,before);assert.deepEqual(events,['progress']);assert.equal(s.project.revision,2);
    s.receive(structuredClone(next));assert.deepEqual(events,['progress']);s.dispose();
  }
});
test('image progress keeps task identity; postponed result still redraws after playback/input ends',()=>{
  const s=new ImageSession({id:'p',kind:'image',revision:1,tasks:[{id:'t',prompt:'text'}],runs:[{id:'r',state:'running',progress:{step:1}}],outputs:[]}),before=s.project;
  let next=structuredClone(before);next.runs[0].progress.step=2;next.revision++;
  assert.equal(s.receive(next),false);assert.equal(s.project,before);
  s.dirty=true;next=structuredClone(next);next.runs[0].state='success';next.outputs=[{id:'o'}];next.revision++;
  assert.equal(s.receive(next),false);assert.equal(s.project,before);
  s.dirty=false;assert.equal(s.receive(next),true);assert.equal(s.project.outputs[0].id,'o');s.dispose();
});
test('a blocked video busy transition remains pending after runtime facts merge',()=>{
  const s=new ProjectSession({id:'p',mode:'text_story',revision:1,busy:false,segments:[]}),events=[];
  s.subscribe(type=>events.push(type));s.dirty=true;
  const next={...structuredClone(s.project),revision:2,busy:true};s.receive(next);
  assert.deepEqual(events,['progress']);s.dirty=false;s.receive(next);
  assert.deepEqual(events,['progress','server']);s.dispose();
});
