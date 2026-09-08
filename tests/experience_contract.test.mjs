import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { validateContract, repositoryFileExists, scenarios } from '../tools/check_experience_contract.mjs';

const keys = ['chrome', 'settings', 'models', 'workbench', 'actions', 'references', 'timing', 'errors', 'candidates', 'results', 'playback', 'async', 'transfers', 'taskStates', 'assetSelection', 'assetOrigins', 'assetUsage', 'assetCollection', 'promptEditing', 'promptCollection', 'promptRecords', 'modal'];
const contract = () => ({version: 1, shared: Object.fromEntries(keys.map(key => [key, 'shared.js'])), baseline: {}, modes: {}});
const mode = () => ({
  review: 'review.md',
  shared: Object.fromEntries(keys.map(key => [key, {kind: 'reuse', adapter: 'adapter.js', reason: '提供业务作用域'}])),
  scenarios: Object.fromEntries(scenarios.map(key => [key, {status: 'checked', reason: '预期与实际一致，细节见证据', evidence: ['review.md']}]))
});

test('新增实际注册模式漏登记时失败', () => {
  assert.match(validateContract(contract(), ['new_mode'], () => true).errors.join('\n'), /未登记体验接入/);
});

test('新模式不能遗漏页头与步骤的共同入口', () => {
  const data=contract();data.modes.new_mode=mode();delete data.modes.new_mode.shared.chrome;
  assert.match(validateContract(data,['new_mode'],()=>true).errors.join('\n'), /new_mode\/chrome/);
});
test('新模式必须声明结果及播放适配，图片可说明播放不适用', () => {
  const data=contract();data.modes.new_mode=mode();
  delete data.modes.new_mode.shared.results;delete data.modes.new_mode.shared.playback;
  const errors=validateContract(data,['new_mode'],()=>true).errors.join('\n');
  assert.match(errors,/new_mode\/results/);assert.match(errors,/new_mode\/playback/);
  data.modes.new_mode.shared.results=mode().shared.results;
  data.modes.new_mode.shared.playback={kind:'not-applicable',reason:'纯图片结果，无视频播放'};
  assert.deepEqual(validateContract(data,['new_mode'],()=>true).errors,[]);
});
test('历史缺口明确报告，不能伪装新模式为历史模式', () => {
  const data = contract();
  data.baseline.swap = {gap: '错误反馈待统一', review: 'audit.md'};
  assert.deepEqual(validateContract(data, ['swap'], () => true), {errors: [], baseline: ['swap']});
  data.baseline.new_mode = data.baseline.swap;
  assert.match(validateContract(data, ['swap', 'new_mode'], () => true).errors.join('\n'), /新模式不能使用历史豁免/);
});
test('登记场景必须有依据，公共入口及适配文件必须存在', () => {
  const data = contract(); data.modes.new_mode = mode();
  assert.deepEqual(validateContract(data, ['new_mode'], () => true).errors, []);
  data.modes.new_mode.scenarios.save.evidence = [];
  delete data.modes.new_mode.scenarios.async;
  data.modes.new_mode.shared.models = {kind: 'not-applicable', reason: ''};
  const errors = validateContract(data, ['new_mode'], path => path !== 'shared.js').errors.join('\n');
  assert.match(errors, /缺少证据文件/);
  assert.match(errors, /缺少场景验收记录/);
  assert.match(errors, /缺少适配说明/);
  assert.match(errors, /公共入口 settings/);
});
test('已删除模式、重复基线和错误版本不能静默通过', () => {
  const data = contract(); data.version = 2; data.modes.swap = mode();
  data.baseline.swap = {gap: '旧缺口', review: 'audit.md'};
  const errors = validateContract(data, [], () => true).errors.join('\n');
  assert.match(errors, /版本/); assert.match(errors, /不能同时/); assert.match(errors, /实际模式不一致/);
});
test('文件检查拒绝缺文件、目录和仓库外路径', () => {
  const root = mkdtempSync(join(tmpdir(), 'timeforest-experience-'));
  try {
    writeFileSync(join(root, 'evidence.md'), 'isolated');
    assert.equal(repositoryFileExists(root, 'evidence.md'), true);
    for (const path of ['missing.md', '.', '../outside.md', join(root, 'evidence.md')]) assert.equal(repositoryFileExists(root, path), false);
  } finally {
    assert.equal(dirname(resolve(root)), resolve(tmpdir()));
    assert.ok(root.includes('timeforest-experience-'));
    rmSync(root, {recursive: true, force: true});
  }
});

test('新模式不能省略异步接收、传输和任务事实适配',()=>{
  const data=contract();data.modes.new_mode=mode();
  for(const key of ['async','transfers','taskStates']){
    delete data.modes.new_mode.shared[key];
    assert.ok(validateContract(data,['new_mode'],()=>true).errors.some(e=>e.includes('new_mode/'+key)));
    data.modes.new_mode.shared[key]=mode().shared[key];
  }
});

test('新增模式须声明资产选择、来源、登记、入库及资产生命周期验收',()=>{
  for(const key of ['assetSelection','assetOrigins','assetUsage','assetCollection']){
    const data=contract();data.modes.new_mode=mode();delete data.modes.new_mode.shared[key];
    assert.ok(validateContract(data,['new_mode'],()=>true).errors.some(e=>e.includes('new_mode/'+key)));
  }
  const data=contract();data.modes.new_mode=mode();delete data.modes.new_mode.scenarios.assetLifecycle;
  assert.ok(validateContract(data,['new_mode'],()=>true).errors.some(e=>e.includes('new_mode/assetLifecycle')));
});

test('新模式须声明提示词共同工具、保存收录、固定记录与必要场景',()=>{
  const data=contract();data.modes.new_mode=mode();
  for(const key of ['promptEditing','promptCollection','promptRecords']){
    delete data.modes.new_mode.shared[key];
    assert.ok(validateContract(data,['new_mode'],()=>true).errors.some(e=>e.includes('new_mode/'+key)));
    data.modes.new_mode.shared[key]=mode().shared[key];
  }
  delete data.modes.new_mode.scenarios.prompts;
  assert.ok(validateContract(data,['new_mode'],()=>true).errors.some(e=>e.includes('new_mode/prompts')));
});
