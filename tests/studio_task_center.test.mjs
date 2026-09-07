import test from 'node:test';
import assert from 'node:assert/strict';
import {visibleTasks,taskCard,confirmation} from '../static/studio/features/task-center/index.js';

test('current queue excludes finished records even with an obsolete all filter',()=>{
  const rows=[{id:'a',active:true},{id:'b',active:false,attention:true},{id:'c',active:true,attention:true}];
  assert.deepEqual(visibleTasks(rows,'all').map(t=>t.id),['a','c']);
  assert.deepEqual(visibleTasks(rows,'attention').map(t=>t.id),['c']);
});
test('queue card escapes project and feedback, keeps zero seed and scoped actions',()=>{
  const html=taskCard({id:'abc',kind:'image',name:'<script>x</script>',title:'编辑',state:'running',active:true,actions:['stop'],url:'#/p/abc',seed:0,error_raw:'<script>bad</script>'},2);
  assert.ok(!html.includes('<script>'));assert.ok(html.includes('种子 0'));
  assert.ok(html.includes('data-task-index="2"'));assert.ok(html.includes('停止当前生成'));
});
test('close confirmation discloses automatic queue continuation and unknown result',()=>{
  const text=confirmation({name:'旧项目',kind:'image'},'close');
  assert.match(text,/其他排队任务随后可以继续/);assert.match(text,/不会重新提交/);assert.match(text,/未确认/);
});
