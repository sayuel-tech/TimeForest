import test from 'node:test';
import assert from 'node:assert/strict';
import {candidateButton,candidateState,resultActions,collectionActions} from '../static/studio/ui/result-view.js';
import {recordControl,removedRecords} from '../static/studio/ui/candidate-records.js';
import {selectionLabel,reviewActions} from '../static/studio/features/production/review-parts.js';
import {mediaPlayer} from '../static/studio/ui/media-player.js';
import {esc} from '../static/studio/ui/primitives.js';

test('viewing a candidate never implies selection or collection',()=>{
  const html=candidateButton({id:'second',number:2,viewing:true,attribute:'data-run-view'});
  assert.match(html,/正在查看/);assert.doesNotMatch(html,/已选用|已入库|data-select=/);
  assert.match(candidateState({selected:true,collected:true}),/已选用.*已入库/);
  assert.doesNotMatch(candidateState({selected:true}),/正在查看/);
});
test('collection preserves exact download and known receipt without adding a selection command',()=>{
  const html=collectionActions({url:'/exact.mp4?x=1&y=2',asset:'fixed',button:'<button data-ingest>加入资产库</button>'});
  assert.match(html,/exact.mp4\?x=1&amp;y=2/);assert.match(html,/#\/assets\/fixed/);
  assert.doesNotMatch(html,/data-ingest|data-select/);
  assert.match(resultActions({collect:html}),/result-collect/);
});
test('assembly restoration uses its original run endpoint adapter and protects uncertain/selected records',()=>{
  assert.match(recordControl({id:'x',state:'cancelled'},{assembly:true}),/data-remove-run="x"/);
  for(const state of ['unknown','running','preparing','submitting'])assert.doesNotMatch(recordControl({id:'x',state},{assembly:true}),/data-remove-run/);
  assert.doesNotMatch(recordControl({id:'x',state:'success'},{assembly:true,selected:true}),/data-remove-run/);
  assert.match(removedRecords([{id:'x',removed_at:1}],{assembly:true}),/data-restore-run="x"/);
});
test('video acceptance explicitly names auto-composition only when every other shot has passed review',()=>{
  const shot={id:'one'},ctx={project:{segments:[shot,{id:'two',status:'draft'}]}};
  assert.equal(selectionLabel(ctx,shot),'选用此结果');ctx.project.segments[1].status='accepted';
  assert.equal(selectionLabel(ctx,shot),'选用并合成');
  const markup=reviewActions({esc,project:{},catalog:{}},{status:'needs_review'},false);
  assert.match(markup,/选用并继续制作/);assert.match(markup,/选用此结果/);
});
test('shared result/player markup escapes filenames and retains the assembly player hook',()=>{
  const html=candidateButton({id:'"><img>',number:1,state:'<bad>',attribute:'data-output'});
  assert.doesNotMatch(html,/<img>|<bad>/);
  assert.throws(()=>candidateButton({attribute:'onclick'}));
  const player=mediaPlayer('/clip.mp4','<clip>','',{id:'assembly-player',className:'assembly-player'});
  assert.match(player,/data-media-retry/);assert.match(player,/id="assembly-player"/);assert.match(player,/object-fit|data-media-seek/);
  assert.doesNotMatch(player,/<clip>/);
});
