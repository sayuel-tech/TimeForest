import test from 'node:test';
import assert from 'node:assert/strict';
import {createImageSettingsDraft} from '../static/studio/features/image-settings/index.js';

const fields=[
  {scope:'models',key:'unet',type:'model',group:'core',label:'底模文件'},
  {scope:'settings',key:'steps',type:'number',group:'sampling',label:'采样步数',min:1,max:50,step:1},
  {scope:'settings',key:'seed',type:'seed',group:'sampling',label:'种子'},
];
const task=()=>({id:'fixture',submode:'dual',settings:{steps:13,seed:0},models:{unet:'saved/sub/model.safetensors'}});
const oldCatalog=()=>({tools:{single:'单图',dual:'双图',region:'局部',outpaint:'扩图'},defaults:{steps:10},choices:{unet:[]},checked:1788718290});
const currentCatalog=()=>({...oldCatalog(),parameter_contract_version:1,parameters:Object.fromEntries(['single','dual','region','outpaint'].map(tool=>[tool,fields]))});

test('text creation needs its explicit capability and fields; legacy four tools remain usable',()=>{
  const textTask={...task(),submode:'text'};
  assert.throws(()=>createImageSettingsDraft({task:textTask,catalog:currentCatalog()}));
  const catalog=currentCatalog();catalog.tools.text='文生图';catalog.text_to_image_version=1;
  assert.throws(()=>createImageSettingsDraft({task:textTask,catalog}));
  catalog.parameters.text=fields;
  assert.equal(createImageSettingsDraft({task:textTask,catalog}).fields().length,3);
  delete catalog.text_to_image_version;
  assert.throws(()=>createImageSettingsDraft({task:textTask,catalog}));
  assert.equal(createImageSettingsDraft({task:task(),catalog:currentCatalog()}).fields().length,3);
});

test('old running backend catalog is rejected before opening an empty parameter editor',()=>{
  const original=task(),before=structuredClone(original);
  assert.throws(()=>createImageSettingsDraft({task:original,catalog:oldCatalog()}),error=>error.code==='IMAGE_PARAMETER_CONTRACT_MISMATCH' && /重新启动网站/.test(error.message));
  assert.deepEqual(original,before);
});

test('refresh from an incompatible backend retains the last valid fields and edited task draft',async()=>{
  const draft=createImageSettingsDraft({task:task(),catalog:currentCatalog(),request:async()=>oldCatalog()});
  draft.set(fields[1],'17');
  await assert.rejects(draft.refresh(),error=>error.code==='IMAGE_PARAMETER_CONTRACT_MISMATCH');
  assert.equal(draft.get(fields[1]),'17');assert.equal(draft.catalog.parameter_contract_version,1);
  assert.equal(draft.active,true);assert.equal(draft.fields().length,3);
});

test('incomplete tool contracts are rejected while current real-shaped declarations are usable',()=>{
  const missing=currentCatalog();missing.parameters.outpaint=[];
  assert.throws(()=>createImageSettingsDraft({task:task(),catalog:missing}),error=>error.code==='IMAGE_PARAMETER_CONTRACT_MISMATCH');
  for (const invalid of [[null], fields.slice(0, 1)]) {
    const partial=currentCatalog();partial.parameters.single=invalid;
    assert.throws(()=>createImageSettingsDraft({task:task(),catalog:partial}),error=>error.code==='IMAGE_PARAMETER_CONTRACT_MISMATCH');
  }
  assert.equal(createImageSettingsDraft({task:task(),catalog:currentCatalog()}).fields().length,3);
});
