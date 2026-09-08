import test from 'node:test';
import assert from 'node:assert/strict';
import {referenceMetadata,referencePurposes} from '../static/studio/ui/reference-metadata.js';

test('图片/声音用途按实际媒体限制，场景等不携带角色编号',()=>{
  assert.deepEqual(referenceMetadata('image','costume','2'),{purpose:'costume',subject:'2'});
  assert.deepEqual(referenceMetadata('image','palette','1'),{purpose:'palette',subject:''});
  assert.deepEqual(referenceMetadata('audio','voice','99'),{purpose:'voice',subject:'99'});
  assert.throws(()=>referenceMetadata('audio','character','1'));
  assert.throws(()=>referenceMetadata('image','voice','1'));
  assert.equal(referencePurposes('image').length,6);
});
test('角色编号校验保持错误原值，不自动调参',()=>{
  for(const value of ['0','100','1.2','-1','abc','１',''])assert.throws(()=>referenceMetadata('image','character',value));
});
