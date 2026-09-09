import { readFileSync, realpathSync, statSync } from 'node:fs';
import { dirname, isAbsolute, relative, resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

// Structural admission only: declarations and existing files cannot prove UX quality.
const baselineIds = ['swap', 'image_story', 'text_story', 'image_assets', 'video_assembly'];
export const scenarios = ['navigation', 'import', 'parameters', 'save', 'generation', 'results', 'recovery', 'async', 'visual', 'assetLifecycle', 'prompts'];
const sharedIds = ['chrome', 'settings', 'models', 'workbench', 'actions', 'references', 'timing', 'errors', 'candidates', 'results', 'playback', 'async', 'transfers', 'taskStates', 'assetSelection', 'assetOrigins', 'assetUsage', 'assetCollection', 'promptEditing', 'promptCollection', 'promptRecords', 'modal', 'refresh', 'viewState', 'statusRegions', 'libraryNavigation', 'designScale'];
const nonempty = value => typeof value === 'string' && value.trim().length > 0;

export function validateContract(contract, registeredIds, fileExists) {
  const errors = [];
  const requireValue = (ok, message) => { if (!ok) errors.push(message); };
  const file = (value, label) => requireValue(nonempty(value) && fileExists(value), `${label}: 文件不存在或路径不在仓库内`);
  requireValue(contract?.version === 1, '契约版本必须为 1');
  const shared = contract?.shared ?? {};
  for (const id of sharedIds) file(shared[id], `公共入口 ${id}`);
  const baseline = contract?.baseline ?? {};
  const modes = contract?.modes ?? {};
  for (const id of Object.keys(baseline)) {
    requireValue(baselineIds.includes(id), `${id}: 新模式不能使用历史豁免`);
    requireValue(!Object.hasOwn(modes, id), `${id}: 不能同时是历史缺口和已登记模式`);
    requireValue(nonempty(baseline[id]?.gap), `${id}: 必须保留具体待办`);
    file(baseline[id]?.review, `${id} 历史审查`);
  }
  for (const id of registeredIds) requireValue(Object.hasOwn(baseline, id) || Object.hasOwn(modes, id), `${id}: 未登记体验接入`);
  for (const id of [...Object.keys(baseline), ...Object.keys(modes)]) requireValue(registeredIds.includes(id), `${id}: 登记与实际模式不一致`);
  for (const [id, mode] of Object.entries(modes)) {
    file(mode?.review, `${id} 接入评审`);
    for (const key of sharedIds) {
      const use = mode?.shared?.[key];
      requireValue(['reuse', 'not-applicable'].includes(use?.kind), `${id}/${key}: 必须声明复用或业务不适用`);
      requireValue(nonempty(use?.reason), `${id}/${key}: 缺少适配说明`);
      if (use?.kind === 'reuse') file(use.adapter, `${id}/${key} 适配入口`);
    }
    for (const key of scenarios) {
      const check = mode?.scenarios?.[key];
      if(check?.status==='pending'){
        requireValue(false,`${id}/${key}: 待完成，不能通过体验准入：${check.reason||'未说明缺口'}`);
        continue;
      }
      requireValue(['checked', 'not-applicable'].includes(check?.status), `${id}/${key}: 缺少场景验收记录`);
      requireValue(nonempty(check?.reason), `${id}/${key}: 缺少实际结果或不适用依据`);
      if (check?.status === 'checked') {
        requireValue(Array.isArray(check.evidence) && check.evidence.length > 0, `${id}/${key}: 缺少证据文件`);
        for (const path of Array.isArray(check.evidence) ? check.evidence : []) file(path, `${id}/${key} 证据`);
      }
    }
  }
  return { errors, baseline: Object.keys(baseline) };
}

export function repositoryFileExists(root, path) {
  if (!nonempty(path) || isAbsolute(path)) return false;
  const resolved = resolve(root, path), local = relative(root, resolved);
  if (local === '..' || local.startsWith(`..${sep}`) || isAbsolute(local)) return false;
  try {
    const realLocal = relative(realpathSync(root), realpathSync(resolved));
    if (realLocal === '..' || realLocal.startsWith(`..${sep}`) || isAbsolute(realLocal)) return false;
    return statSync(resolved).isFile();
  } catch { return false; }
}

async function main() {
  const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
  // Only the registry is evaluated; lazy workspaces and application services stay unloaded.
  const registry = await import(pathToFileURL(resolve(root, 'static/studio/app/mode-registry.js')));
  registry.setImageAssetsEnabled(true);
  registry.setAssemblyEnabled(1);
  registry.setCreationEnabled(1);
  const contract = JSON.parse(readFileSync(resolve(root, 'docs/frontend/experience-contract.json'), 'utf8'));
  const result = validateContract(contract, registry.listModes().map(mode => mode.id), path => repositoryFileExists(root, path));
  if (result.errors.length) {
    console.error(result.errors.join('\n'));
    process.exitCode = 1;
    return;
  }
  console.log('体验接入结构检查通过；不代表交互或视觉验收通过。');
  console.log(`仍有 ${result.baseline.length} 个历史模式待按方案完善：${result.baseline.join(', ') || '无'}。`);
  console.log('普通新功能/页面不由注册表发现，须按接入规则逐项评审。');
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
