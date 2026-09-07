import test from 'node:test';
import assert from 'node:assert/strict';
import {esc} from '../static/studio/ui/primitives.js';
import {recordControl,removedRecords,recordConfirmation} from '../static/studio/ui/candidate-records.js';
import {chosenOutput,imageRecordHistory,imageRunStatus} from '../static/studio/features/image-results/workspace-view.js';
import {videoCandidateHistory} from '../static/studio/features/production/review-parts.js';

test('image selection and status exclude removed records; restore stays available when all removed',()=>{
  const p={busy:false,outputs:[{id:'a',task:'t',run:'a',removed_at:2,url:'/a.png'},{id:'b',task:'t',run:'b'}],runs:[{id:'b',task:'t',state:'success'},{id:'a',task:'t',state:'success',removed_at:2,seed:0}]};
  assert.equal(chosenOutput(p,{id:'t'},'a').id,'b');
  assert.ok(!imageRunStatus(p,{id:'t'}).includes('种子 0'));
  p.outputs[1].removed_at=2;p.runs[0].removed_at=2;
  assert.equal(chosenOutput(p,{id:'t'},'a'),undefined);
  assert.match(imageRecordHistory(p,{id:'t'}),/已移除（2）/);
  assert.match(imageRecordHistory(p,{id:'t'}),/data-record-restore="a"/);
});
test('failed and cancelled image runs can be removed without an output',()=>{
  const html=imageRecordHistory({outputs:[],runs:[{id:'failed',task:'t',state:'failed',note:'bad',seed:0}]},{id:'t'});
  assert.match(html,/未产生候选的记录/);assert.match(html,/data-record-remove="failed"/);
});
test('video history hides removed playback and selection, exposes restore only',()=>{
  const ctx={esc,LABELS:{},project:{busy:false},catalog:{asset_library_version:1}};
  const s={selected:'kept',attempts:[{id:'old',status:'complete',removed_at:4,delivery_url:'/hidden.mp4'},{id:'kept',status:'complete',created:1},{id:'unused',status:'failed',created:2}]};
  const html=videoCandidateHistory(ctx,s);
  assert.ok(!html.includes('/hidden.mp4'));assert.ok(!html.includes('data-select-attempt="old"'));
  assert.match(html,/data-record-restore="old"/);assert.match(html,/data-record-remove="unused"/);
  assert.ok(!html.includes('data-record-remove="kept"'));
});
test('controls explain selected or uncertain protection and escape ids',()=>{
  assert.match(recordControl({id:'a',state:'unknown'},{image:true}),/暂不可移除/);
  assert.match(recordControl({id:'a',status:'complete'},{selected:true}),/换选后/);
  const html=removedRecords([{id:'"><script>bad',removed_at:1}]);assert.ok(!html.includes('<script>'));
  assert.match(recordConfirmation(false),/不释放磁盘空间/);assert.match(recordConfirmation(true),/不会自动选用/);
});
