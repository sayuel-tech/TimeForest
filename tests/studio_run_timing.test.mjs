import test from 'node:test';
import assert from 'node:assert/strict';
import * as ui from '../static/studio/ui/primitives.js';
import {runTiming} from '../static/studio/ui/run-timing.js';
import {imageRunClock,imageRunStatus} from '../static/studio/features/image-results/workspace-view.js';
import {createFeature as records} from '../static/studio/features/production/records.js';
import {createFeature as exports} from '../static/studio/features/export/index.js';
import {createFeature as source} from '../static/studio/features/source-preparation/index.js';

const context=project=>({...ui,project,catalog:{},root:{}});
test('three video modes render the same clock and status layout as image mode',()=>{
  const clock=imageRunClock({state:'running',started:100});
  const image=imageRunStatus({runs:[{id:'r',task:'t',state:'running',started:100}]},{id:'t'});
  assert.match(image,/class="row between run-status-row"/);
  for(const mode of ['swap','image_story','text_story']){
    const project={mode,status:'generating',runtime:{phase:'正在采样',started:100,active:true,step:2,step_total:10}};
    const before=JSON.stringify(project),html=records(context(project)).progressCard();
    assert.ok(html.includes(clock));assert.match(html,/class="row between run-status-row"/);
    assert.match(html,/value="2" max="10"/);assert.equal(JSON.stringify(project),before);
  }
});
test('video completed clocks freeze, uncertain and missing timestamps do not invent durations',()=>{
  const p={status:'failed',runtime:{phase:'失败',started:100,finished:165,updated:200,active:false}};
  assert.match(records(context(p)).progressCard(),/data-clock-end="165"/);
  assert.match(records(context(p)).progressCard(),/1分 05秒/);
  p.status='interrupted';assert.match(records(context(p)).progressCard(),/用时待确认/);
  assert.doesNotMatch(records(context(p)).progressCard(),/data-clock="100"/);
  p.status='failed';p.runtime={phase:'失败',active:false};
  assert.match(records(context(p)).progressCard(),/用时未记录/);
  assert.doesNotMatch(records(context(p)).progressCard(),/NaN|data-clock=/);
});
test('source preparation and export use common timing, completed source keeps a fixed clock',()=>{
  const p={mode:'swap',source_ready:true,segments:[{}],source_progress:{phase:'源视频准备完成',started:100,finished:165,active:false},status:'assembling',runtime:{operation:'export',started:200,active:true}};
  const ready=source(context(p)).sourceProgressCard();
  assert.match(ready,/run-status-row/);assert.match(ready,/data-clock-end="165"/);assert.match(ready,/准备用时/);
  const assembling=exports(context(p)).exportProgressCard();
  assert.match(assembling,/run-status-row/);assert.match(assembling,/本次合成用时/);assert.match(assembling,/data-clock="200"/);assert.doesNotMatch(assembling,/data-clock-end/);
  p.status='complete';p.export={};p.runtime.finished=280;
  assert.match(exports(context(p)).exportProgressCard(),/data-clock-end="280"/);
});
test('shared renderer escapes labels and needs a real start and terminal end',()=>{
  assert.match(runTiming({start:100,end:165,label:'<img>'}),/&lt;img&gt;/);
  assert.doesNotMatch(runTiming({start:'bad',live:true}),/data-clock|NaN/);
  assert.doesNotMatch(runTiming({start:100}),/data-clock/);
  assert.match(runTiming({start:120,queuedAt:100,live:true}),/排队用时 0分 20秒/);
});
