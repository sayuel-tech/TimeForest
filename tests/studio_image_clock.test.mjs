import test from 'node:test';
import assert from 'node:assert/strict';
import {imageRunStatus} from '../static/studio/features/image-results/workspace-view.js';
import * as ui from '../static/studio/ui/primitives.js';

const render=run=>imageRunStatus({runs:[{id:'run',task:'task',seed:0,...run}]},{id:'task'});
test('image queue has a live waiting clock using the persisted enqueue time',()=>{
  const html=render({state:'waiting',created:100});
  assert.match(html,/已等待/);assert.match(html,/data-clock="100"/);assert.doesNotMatch(html,/data-clock-end/);
});
test('image execution uses its own start and completed duration freezes at finish',()=>{
  const live=render({state:'running',created:100,started:120,progress:{started:125}});
  assert.match(live,/本次任务用时/);assert.match(live,/data-clock="120"/);assert.match(live,/排队用时/);
  const done=render({state:'success',created:100,started:120,finished:185});
  assert.match(done,/data-clock-end="185"/);assert.match(done,/1分 05秒/);
});
test('old progress timestamps remain readable and unknown or missing times are not invented',()=>{
  const old=render({state:'success',created:100,progress:{started:120,finished:180}});
  assert.match(old,/data-clock="120"/);assert.match(old,/data-clock-end="180"/);
  assert.doesNotMatch(render({state:'unknown',created:100,started:120}),/data-clock=/);
  assert.match(render({state:'unknown',created:100}),/用时待确认/);
  assert.doesNotMatch(render({state:'cancelled',created:100,started:120,finished:999,closed_without_result:true}),/data-clock=/);
  assert.doesNotMatch(render({state:'success',created:100}),/data-clock=/);
});
test('cancelled waiting freezes and legacy running time explicitly includes waiting',()=>{
  const stopped=render({state:'cancelled',created:100,finished:140});
  assert.match(stopped,/等待用时/);assert.match(stopped,/data-clock-end="140"/);
  assert.match(render({state:'running',created:100}),/含等待/);
});
test('shared clock ticker updates only text in its scope and disposes its interval',()=>{
  const oldSet=globalThis.setInterval,oldClear=globalThis.clearInterval;
  let tick,delay,cleared;
  globalThis.setInterval=(fn,ms)=>{tick=fn;delay=ms;return 7;};globalThis.clearInterval=id=>cleared=id;
  const el={dataset:{clock:'100',clockEnd:'165'},textContent:''};
  const scope={querySelectorAll:selector=>{assert.equal(selector,'[data-clock]');return [el];}};
  try{
    const stop=ui.watchClocks(scope);assert.equal(delay,1000);tick();assert.equal(el.textContent,'1分 05秒');stop();assert.equal(cleared,7);
  }finally{globalThis.setInterval=oldSet;globalThis.clearInterval=oldClear;}
});
