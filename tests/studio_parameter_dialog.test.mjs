import test from 'node:test';
import assert from 'node:assert/strict';
import {
  createImageSettingsDraft, imageParameters, parseImageSeed,
  renderImageQuickSettings,
} from '../static/studio/features/image-settings/index.js';
import { productionGroups, productionSettingsMarkup, parameterField, bindSettingsNavigation } from '../static/studio/ui/production-settings.js';

const fields = [
  {scope:'models',key:'unet',type:'model',group:'core',label:'底模文件'},
  {scope:'settings',key:'megapixels',type:'number',group:'picture',label:'处理像素面积（MP）',min:.25,max:2,step:.05,quick:true},
  {scope:'settings',key:'steps',type:'number',group:'sampling',label:'采样步数',min:1,max:50,step:1},
  {scope:'settings',key:'seed',type:'seed',group:'sampling',label:'种子模式'},
];
const catalog = () => ({parameter_contract_version:1,parameters:{single:fields,region:fields,outpaint:fields,dual:[...fields,{scope:'settings',key:'ratio',type:'select',group:'picture',label:'输出比例',options:['1:1','2:3'],quick:true}]},tools:{single:'单图编辑',dual:'双图编辑'},choices:{unet:['default.safetensors']},defaults:{steps:10,megapixels:1,seed:null}});
const task = () => ({id:'current-task',submode:'single',prompt:'未保存正文',A:'asset-a',mask:'saved-mask',settings:{steps:10,seed:null,megapixels:1,ratio:'2:3',hidden_setting:8},models:{unet:'folder/custom.safetensors',clip:'keep.safetensors'}});

test('defaults reset only eligible fields in the temporary draft and cancel remains reversible',async()=>{
  const original=task(),before=structuredClone(original),c={...catalog(),models:{unet:'default.safetensors'}};
  original.settings.steps=29;original.settings.seed=0;before.settings={...original.settings};
  const cancelled=createImageSettingsDraft({task:original,catalog:c});
  assert.equal(cancelled.resetDefaults(),true);assert.equal(cancelled.seedMode,'random');
  cancelled.cancel();assert.equal(cancelled.resetDefaults(),false);assert.deepEqual(original,before);
  const draft=createImageSettingsDraft({task:original,catalog:c});draft.resetDefaults();
  const result=await draft.apply();
  assert.equal(result.settings.steps,10);assert.equal(result.settings.seed,null);
  assert.equal(result.models.unet,'default.safetensors');assert.equal(result.models.clip,'keep.safetensors');
  assert.equal(result.settings.hidden_setting,8);assert.equal(result.settings.ratio,'2:3');
  assert.deepEqual(original,before);
});

test('missing defaults reject atomically and refresh uses the current backend defaults',async()=>{
  const c={...catalog(),models:{unet:'default.safetensors'}};delete c.defaults.steps;
  const draft=createImageSettingsDraft({task:task(),catalog:c,request:async()=>({...catalog(),defaults:{steps:12,megapixels:1,seed:null},models:{unet:'configured.safetensors'}})});
  draft.set(fields[2],'29');draft.setSeedMode('fixed');draft.setSeedValue('0');
  assert.throws(()=>draft.resetDefaults(),/未恢复任何参数/);
  assert.equal(draft.get(fields[0]),task().models.unet);assert.equal(draft.get(fields[2]),'29');assert.equal(draft.seedValue,'0');
  await draft.refresh();draft.resetDefaults();const result=await draft.apply();
  assert.equal(result.settings.steps,12);assert.equal(result.models.unet,'configured.safetensors');
});

test('cancelling parameter edits leaves all outer task drafts intact', () => {
  const original=task(), before=structuredClone(original), c=catalog();
  let applied=0;
  const draft=createImageSettingsDraft({task:original,catalog:c,onApply:()=>applied++});
  draft.set(fields[2],'17');draft.set(fields[0],'other/folder/model.safetensors');
  draft.setSeedMode('fixed');draft.setSeedValue('0');draft.cancel();
  assert.deepEqual(original,before);assert.equal(applied,0);
  assert.equal(draft.active,false);
});

test('apply returns only current task parameters, preserves hidden values and fixed seed zero', async () => {
  const original=task(), before=structuredClone(original);let result;
  const draft=createImageSettingsDraft({task:original,catalog:catalog(),onApply:value=>{result=value;}});
  draft.set(fields[2],'17');draft.set(fields[0],'subdir/new.safetensors');
  draft.setSeedMode('fixed');draft.setSeedValue('0');await draft.apply();
  assert.deepEqual(original,before);assert.deepEqual(Object.keys(result).sort(),['models','settings']);
  assert.equal(result.settings.steps,17);assert.equal(result.settings.seed,0);
  assert.equal(result.settings.ratio,'2:3');assert.equal(result.settings.hidden_setting,8);
  assert.equal(result.models.unet,'subdir/new.safetensors');assert.equal(result.models.clip,'keep.safetensors');
  result.settings.steps=3;assert.equal(original.settings.steps,10);
});

test('seed input rejects fractions, exponent notation, unsafe and blank fixed values without applying', async () => {
  for(const value of ['', '1.5', '1e2', '-1','9007199254740992','NaN']){
    assert.throws(()=>parseImageSeed('fixed',value));
    let applied=0;
    const draft=createImageSettingsDraft({task:task(),catalog:catalog(),onApply:()=>applied++});
    draft.setSeedMode('fixed');draft.setSeedValue(value);
    await assert.rejects(draft.apply());assert.equal(applied,0);assert.equal(draft.active,true);assert.equal(draft.seedValue,value);
  }
  assert.equal(parseImageSeed('fixed','0'),0);
  assert.equal(parseImageSeed('fixed','9007199254740991'),Number.MAX_SAFE_INTEGER);
  assert.equal(parseImageSeed('random','invalid'),null);
});

test('local model refresh and node synchronization preserve edited values and disclose failures', async () => {
  const original=task(),calls=[],published=[];
  const draft=createImageSettingsDraft({task:original,catalog:catalog(),request:async(path,method)=>{calls.push([path,method]);return {...catalog(),choices:{unet:['new.safetensors']}};},onCatalog:next=>published.push(next)});
  draft.set(fields[0],'not-listed/custom.safetensors');draft.set(fields[2],'19');draft.setSeedMode('fixed');draft.setSeedValue('0');
  await draft.refresh();await draft.refresh(true);
  assert.deepEqual(calls,[['/image-projects/catalog','GET'],['/image-projects/catalog/sync','POST']]);
  assert.equal(published.length,2);assert.equal(draft.get(fields[0]),'not-listed/custom.safetensors');assert.equal(draft.get(fields[2]),'19');assert.equal(draft.seedValue,'0');
  assert.equal(original.settings.steps,10);assert.equal(original.mask,'saved-mask');
  const error=new Error('node validation: exact original');error.raw='{"node":"42"}';
  const failed=createImageSettingsDraft({task:original,catalog:catalog(),request:async()=>{throw error;}});
  failed.set(fields[2],'21');await assert.rejects(failed.refresh(),e=>e===error);
  assert.equal(failed.get(fields[2]),'21');assert.equal(failed.active,true);
});

test('closing or disposing while a directory request is pending ignores its result', async () => {
  for(const abort of [false,true]){
    let release,changed=0;const controller=new AbortController();
    const draft=createImageSettingsDraft({task:task(),catalog:catalog(),request:()=>new Promise(resolve=>release=resolve),onCatalog:()=>changed++,signal:controller.signal});
    const pending=draft.refresh();if(abort)controller.abort();else draft.cancel();release(catalog());
    await pending;assert.equal(changed,0);assert.equal(draft.active,false);
  }
});

test('failed apply preserves the editable temporary draft and random mode does not discard its fixed input', async () => {
  const original=task(),before=structuredClone(original);
  const draft=createImageSettingsDraft({task:original,catalog:catalog(),onApply:()=>{throw new Error('当前任务已切换');}});
  draft.setSeedMode('fixed');draft.setSeedValue('0');draft.setSeedMode('random');
  assert.equal(draft.seedValue,'0');draft.setSeedMode('fixed');
  draft.set(fields[2],'23');
  await assert.rejects(draft.apply(),/当前任务已切换/);
  assert.equal(draft.active,true);assert.equal(draft.get(fields[2]),'23');assert.equal(draft.seedValue,'0');
  assert.deepEqual(original,before);
});

test('tool descriptors and shared field markup keep quick controls scoped and model names intact', () => {
  const c=catalog(),t=task();
  assert.equal(imageParameters(t,c).some(f=>f.key==='ratio'),false);
  assert.equal(imageParameters({...t,submode:'dual'},c).some(f=>f.key==='ratio'),true);
  const html=renderImageQuickSettings({task:t,catalog:c});
  assert.match(html,/data-setting="megapixels"/);assert.doesNotMatch(html,/data-setting="steps"|data-seed|data-model/);
  const model=parameterField(fields[0],'folder/a<b.safetensors',{attributes:'data-model="unet"',options:['default.safetensors'],listId:'test-models'});
  assert.match(model,/folder\/a&lt;b.safetensors/);assert.match(model,/当前目录未发现/);assert.match(model,/<input/);
  const shell=productionSettingsMarkup({scope:'当前图片任务草稿',sections:[{key:'core',title:'工作流与模型',html:'<p>字段</p>'}],actions:'<button>取消</button>'});
  assert.match(shell,/PRODUCTION SETTINGS/);assert.match(shell,/aria-label="制作参数分类"/);assert.match(shell,/data-settings-group="core"/);assert.match(shell,/parameter-errors/);
});

test('shared shell preserves video categories and its select/boolean/number controls', () => {
  assert.deepEqual(Object.entries(productionGroups),[['core','工作流与模型'],['picture','画布与输出'],['sampling','两采与时长'],['assets','参考与声音'],['lora','LoRA'],['memory','低显存'],['advanced','高级模型组件']]);
  const model=parameterField({key:'model',type:'model',label:'底模文件'},'saved/model.safetensors',{attributes:'data-param="model"',options:[['saved/model.safetensors','目录未列出，保留当前选择'],'new.safetensors']});
  assert.match(model,/<select data-param="model"/);assert.doesNotMatch(model,/<datalist/);assert.match(model,/data-model-filename/);
  assert.match(model,/<option value="saved\/model.safetensors" selected>/);
  const bool=parameterField({type:'boolean',label:'低显存'},true,{attributes:'data-param="low_vram"'});
  assert.match(bool,/type="checkbox" checked/);
  const numeric=parameterField({type:'number',label:'自定义宽度',min:128,max:2048,step:32},512,{attributes:'data-param="width"'});
  assert.match(numeric,/step="32" min="128" max="2048" value="512"/);
  const buttons=['core','sampling'].map(key=>({dataset:{settingsSection:key},setAttribute(name,value){this[name]=value;}}));
  const sections=['core','sampling'].map(key=>({dataset:{settingsGroup:key},hidden:false}));
  let selected;
  bindSettingsNavigation({querySelectorAll:selector=>selector==='[data-settings-section]'?buttons:sections},'sampling',key=>selected=key);
  assert.equal(selected,'sampling');assert.equal(sections[0].hidden,true);assert.equal(buttons[1]['aria-current'],'true');
  buttons[0].onclick();assert.equal(selected,'core');assert.equal(sections[1].hidden,true);
});
