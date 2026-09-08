import test from 'node:test';
import assert from 'node:assert/strict';
import {sourceTarget} from '../static/studio/core/source-target.js';
const hash=(values,pid='p')=>'#/p/'+pid+'?'+new URLSearchParams(Object.entries(values).map(([k,v])=>['origin_'+k,v]));
const video=()=>({id:'p',mode:'image_story',segments:[{id:'s1',selected:'b',attempts:[{id:'a'},{id:'b'}]},{id:'s2',attempts:[{id:'c',removed_at:1}]}]});
test('三视频按确切片段候选定位，仅产生查看位置',()=>{
  for(const mode of ['swap','image_story','text_story']){
    const p={...video(),mode},before=structuredClone(p);
    assert.deepEqual(sourceTarget(p,hash({run:'a',segment:'s1'})),{asset:null,version:null,media:null,state:'found',message:'已定位来源记录；当前仅查看，项目选用与制作参数保持原样。',tab:'review',shot:0,run:'a'});
    assert.deepEqual(p,before);
    for(const values of [{run:'a',segment:'s2'},{run:'missing'},{run:'c'}])assert.equal(sourceTarget(p,hash(values)).state,'unavailable');
  }
});
test('成片必须匹配保存的导出标识，不把当前成片当成旧成片',()=>{
  const p={...video(),export:{created:123}};
  assert.equal(sourceTarget(p,hash({final:'123'})).tab,'export');
  assert.equal(sourceTarget(p,hash({final:'123.0'})).tab,'export');
  assert.equal(sourceTarget(p,hash({final:'122'})).state,'unavailable');
  assert.equal(sourceTarget(p,hash({final:'unknown'})).state,'unavailable');
});
test('图片定位到另一个任务的确切输出，不修改current_task或selected',()=>{
  const p={id:'p',kind:'image',current_task:'t2',tasks:[{id:'t1'},{id:'t2'}],runs:[{id:'r',task:'t1'}],outputs:[{id:'o',task:'t1',run:'r',selected:false},{id:'other',task:'t1',run:'r',selected:true}]},before=structuredClone(p);
  assert.equal(sourceTarget(p,hash({output:'o',run:'r',task:'t1'})).output,'o');
  assert.equal(sourceTarget(p,hash({run:'r'})).state,'unavailable');
  assert.equal(sourceTarget(p,hash({output:'o',task:'t2'})).state,'unavailable');
  assert.deepEqual(p,before);
  p.tasks[0].discarded_at=1;assert.equal(sourceTarget(p,hash({output:'o'})).recycle,'projects');
});
test('接续定位历史续写/导出候选，不改变选用、轨道顺序或依赖',()=>{
  const p={id:'p',kind:'assembly',assembly:{clips:[{id:'clip',extensions:[{id:'e',selected:'new'}]}],track_order:['clip:clip'],runs:[{id:'old',extension:'e',kind:'generate'},{id:'new',extension:'e',kind:'generate'},{id:'export',kind:'export'}]}},before=structuredClone(p);
  assert.equal(sourceTarget(p,hash({run:'old'})).extension,'e');
  assert.equal(sourceTarget(p,hash({run:'export'})).step,2);assert.deepEqual(p,before);
  p.assembly.clips[0].removed_at=1;assert.equal(sourceTarget(p,hash({run:'old'})).recycle,'projects');
  p.assembly.runs[2].removed_at=1;assert.equal(sourceTarget(p,hash({run:'export'})).state,'unavailable');
});
test('其他项目或普通URL无定位副作用，来源参数与导入参数分开',()=>{
  assert.equal(sourceTarget(video(),hash({run:'a'},'other')),null);
  assert.equal(sourceTarget(video(),'#/p/p?asset=a'),null);
  assert.equal(sourceTarget(video(),'#/p/p'),null);
});
