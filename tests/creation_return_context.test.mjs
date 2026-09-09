import test from 'node:test';
import assert from 'node:assert/strict';
import {readReturnContext,returnHref,withReturnContext} from '../static/studio/features/shot-segment-tree/return-context.js';
const context={origin_movie_id:'b70f4304-95a9-4d89-a193-7a82d43fe721',origin_page:'editing',origin_item_id:'a'.repeat(32),origin_segment_id:'b'.repeat(32),viewed_take_id:'c'.repeat(32),script_project_id:'ef98f56a-f217-421f-b4b2-d443cfc88c79',script_target_id:'d'.repeat(32),source_bundle_id:'e'.repeat(32),view:{zoom:1.5,scroll_x:120}};
test('source return accepts original project UUID and fixed target identities',()=>{
  const href=withReturnContext('#/p/'+context.script_project_id+'?step=3',context);
  const restored=readReturnContext(new URLSearchParams(href.split('?')[1]));
  assert.deepEqual(restored,context);
  const query=new URLSearchParams(returnHref(restored).split('?')[1]);
  assert.equal(query.get('step'),'1');assert.equal(query.get('item'),context.origin_item_id);assert.equal(query.get('zoom'),'1.5');assert.equal(query.get('scroll_x'),'120');
});
test('source return rejects foreign URLs and malformed view state',()=>{
  for(const change of [{origin_movie_id:'https://example.com'},{script_target_id:'../../data'},{view:{zoom:0}},{origin_page:'elsewhere'}]){
    assert.equal(readReturnContext(new URLSearchParams({return_context:JSON.stringify({...context,...change})})),null);
  }
});
