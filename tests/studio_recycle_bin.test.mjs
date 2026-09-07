import test from 'node:test';
import assert from 'node:assert/strict';
import {recycleView,recycleUrl,restoreRequest} from '../static/studio/pages/asset-library/recycle-bin.js';

test('discarded image tasks restore through their exact project and task with revision',()=>{
  const item={id:'edit-task',type:'image_task',project:'image-project',revision:4,title:'废弃编辑',task_name:'项目 A · 编辑任务',mode:'image_assets'};
  assert.deepEqual(restoreRequest(item),{path:'/image-projects/image-project/tasks/edit-task/discard',body:{revision:4,restore:true}});
  assert.match(recycleView({category:'projects',counts:{},items:[item],page:1,limit:24,total:1}),/项目 A · 编辑任务/);
  assert.throws(()=>restoreRequest({...item,blocked_reason:'请先恢复所属项目'}),/先恢复所属项目/);
});
test('three categories have canonical links without leaking asset filters',()=>{
  assert.equal(recycleUrl('projects'),'#/assets?view=trash&recycle=projects');
  const html=recycleView({category:'assets',counts:{assets:1,projects:2,generations:3},items:[],page:1,limit:24,total:0});
  for(const title of ['资产库移除的','项目移除的','生成移除的'])assert.ok(html.includes(title));
  assert.match(html,/暂无匹配/);assert.doesNotMatch(html,/永久删除|清空回收站/);
});
test('restoration preserves exact ownership and uses existing endpoints',()=>{
  const item={id:'r',project:'p',segment:'s',revision:4,type:'video_run'};
  assert.deepEqual(restoreRequest(item),{path:'/projects/p/records/visibility',body:{record:'r',segment:'s',revision:4,removed:false}});
  assert.equal(restoreRequest({id:'a',revision:5,type:'asset'}).path,'/library/assets/a/trash');
  assert.equal(restoreRequest({id:'l',type:'legacy_project'}).path,'/legacy/l/trash');
  assert.throws(()=>restoreRequest({...item,blocked_reason:'先恢复项目'}),/先恢复/);
});
test('deleted parents remain visible with a disabled restore and project-bin link',()=>{
  const item={id:'x',title:'<script>bad</script>',type:'image_run',project:'p',mode:'image_assets',parent_deleted:true,blocked_reason:'先恢复项目',seed:0,removed_at:100};
  const html=recycleView({category:'generations',counts:{},items:[item],page:1,limit:24,total:1});
  assert.doesNotMatch(html,/<script>/);assert.match(html,/种子 0/);assert.match(html,/前往项目回收站/);assert.match(html,/data-recycle-restore="0" disabled/);
});
