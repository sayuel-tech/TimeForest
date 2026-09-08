import {imageProductionGroups} from '../../ui/production-settings.js';
import { esc, toast } from '../../ui/primitives.js';
import { assertImageCatalog } from '../../core/image-catalog.js';
import { errorFeedback, bindErrorFeedback } from '../../ui/error-feedback.js';
import { openProductionSettings, productionSettingsActions, productionGroups, productionSettingsMarkup, bindSettingsNavigation, parameterField, seedFields } from '../../ui/production-settings.js';

const groups = imageProductionGroups;
const inputError = message => Object.assign(new Error(message), {kind:'input'});

/** Only the curated contract for the current tool is eligible for editing. */
export function imageParameters(task, catalog) {
  return (catalog.parameters?.[task.submode] || []).filter(field =>
    ['settings','models'].includes(field.scope) && Object.hasOwn(groups, field.group));
}

export function parseImageSeed(mode, value) {
  if (mode === 'random') return null;
  const text = String(value ?? '');
  if (mode !== 'fixed' || !/^\d+$/.test(text) || !Number.isSafeInteger(Number(text)) || Number(text) < 0)
    throw inputError('固定种子：请输入 0～9007199254740991 的十进制整数，固定值 0 有效');
  return Number(text);
}

export function readImageParameter(field, value) {
  if (field.type === 'number') {
    const number = Number(value);
    if (String(value ?? '').trim() === '' || !Number.isFinite(number))
      throw inputError(`${field.label}：请输入有效数值`);
    if ((field.min !== undefined && number < field.min) || (field.max !== undefined && number > field.max))
      throw inputError(`${field.label}：数值须在 ${field.min ?? '不限'}～${field.max ?? '不限'} 范围内`);
    if (field.step === 1 && !Number.isInteger(number))
      throw inputError(`${field.label}：请输入整数`);
    return number;
  }
  const text = String(value ?? '');
  if (!text.trim()) throw inputError(`${field.label}：请填写有效值`);
  if (field.type === 'model' && (/^(?:[a-z]:|[\\/])/i.test(text) || text.split(/[\\/]/).includes('..') || /[\x00-\x1f]/.test(text)))
    throw inputError(`${field.label}：请输入模型目录内的相对文件名`);
  return text;
}

/** This temporary transaction has no access to the canvas, save or generation. */
export function createImageSettingsDraft({ task, catalog, request, onApply = () => {}, onCatalog = () => {}, signal }) {
  assertImageCatalog(catalog,task.submode);
  const candidate = structuredClone({settings: task.settings || {}, models: task.models || {}});
  let currentCatalog = catalog, active = true;
  let seedMode = candidate.settings.seed == null ? 'random' : 'fixed';
  let seedValue = candidate.settings.seed == null ? '' : String(candidate.settings.seed);
  const isActive = () => active && !signal?.aborted;
  const fields = () => imageParameters(task, currentCatalog);
  const get = field => candidate[field.scope][field.key] ?? (field.scope === 'settings' ? currentCatalog.defaults?.[field.key] : currentCatalog.models?.[field.key]);
  return {
    get active() { return isActive(); },
    get catalog() { return currentCatalog; },
    get seedMode() { return seedMode; },
    get seedValue() { return seedValue; },
    fields, get,
    set(field, value) {
      if (!isActive() || !fields().some(f => f.scope === field.scope && f.key === field.key)) return;
      candidate[field.scope][field.key] = value;
    },
    setSeedMode(mode) { if (isActive()) seedMode = mode; },
    setSeedValue(value) { if (isActive()) seedValue = value; },
    resetDefaults() {
      if (!isActive()) return false;
      // Validate availability first so an incomplete catalog cannot reset half a task.
      const defaults=fields().map(field=>{
        const source=field.scope==='models'?currentCatalog.models:currentCatalog.defaults;
        if (!source || !Object.hasOwn(source,field.key) || source[field.key]===undefined)
          throw inputError(`${field.label}：后台未提供默认值，未恢复任何参数`);
        return {field,value:structuredClone(source[field.key])};
      });
      for (const {field,value} of defaults) {
        candidate[field.scope][field.key]=value;
        if (field.type==='seed') {seedMode=value==null?'random':'fixed';seedValue=value==null?'':String(value);}
      }
      return true;
    },
    cancel() { active = false; },
    async refresh(syncNodes = false) {
      const next = await request(syncNodes ? '/image-projects/catalog/sync' : '/image-projects/catalog', syncNodes ? 'POST' : 'GET', syncNodes ? {} : undefined, signal);
      if (!isActive()) return false;
      assertImageCatalog(next,task.submode);
      currentCatalog = next;
      onCatalog(next);
      return true;
    },
    async apply(saveNow = false) {
      if (!isActive()) return null;
      const result = structuredClone(candidate);
      const errors = [];
      for (const field of fields()) {
        try {
          result[field.scope][field.key] = field.type === 'seed'
            ? parseImageSeed(seedMode, seedValue) : readImageParameter(field, get(field));
        } catch (error) { errors.push(error.message); }
      }
      if (errors.length) throw inputError(errors.join('\n'));
      await onApply(result, saveNow);
      active = false;
      return result;
    },
  };
}

function renderField(field, value, catalog, { quick = false, mode, seed, lastSeed } = {}) {
  if (field.type === 'seed') return seedFields({mode, value: seed, lastSeed});
  const attr = field.scope === 'models' ? 'data-model' : 'data-setting';
  let options = field.type === 'model' ? catalog.choices?.[field.key] || [] : field.options;
  return parameterField(field, value, {
    attributes: `${attr}="${esc(field.key)}"`,
    options,
    preserveCurrent: true,
  });
}

export function renderImageQuickSettings({ task, catalog }) {
  return imageParameters(task, catalog).filter(field => field.quick && field.type !== 'seed')
    .map(field => renderField(field, task[field.scope]?.[field.key] ?? catalog.defaults?.[field.key], catalog, {quick:true})).join('');
}

function directoryMarkup(catalog, tool) {
  catalog = {...catalog, missing: catalog.missing_by_tool?.[tool] ?? catalog.missing};
  const local = catalog.local_models || {}, nodes = catalog.node_catalog || {};
  const time = value => value ? new Date(value * 1000).toLocaleString() : '尚无记录';
  const remote = String(local.source || '').startsWith('remote');
  const sources = {filesystem:'本机文件目录',filesystem_partial:'本机扫描及保留缓存',filesystem_cache:'本机目录缓存',filesystem_unavailable:'本机目录暂不可用',remote_cache:'远程引擎节点缓存',remote_online:'远程引擎刚同步的声明',remote_unavailable:'远程引擎尚无缓存'};
  const description = remote
    ? '当前使用远程引擎。刷新模型列表只读取该引擎的已同步缓存，不扫描本机或远程文件。远程新增文件需在对应引擎目录放入，并通过下方节点同步更新在线声明。'
    : '刷新本地模型列表只扫描文件，无需启动 ComfyUI。保留完整文件名和当前选择；是否兼容由对应引擎实际执行反馈。';
  return `<details class="engine-directory"><summary>模型目录与节点能力</summary><p>${esc(description)}</p><p>文件来源：${esc(sources[local.source] || '尚无本地扫描记录')} · 上次扫描／缓存：${esc(time(local.updated))}</p>${local.note ? `<p>${esc(local.note)}</p>` : ''}${(local.errors || []).map(error => errorFeedback({kind:'website',message:'模型文件目录读取失败',raw:error})).join('')}<button id="image-refresh-models" type="button">${modelRefreshLabel(catalog)}</button><details><summary>节点能力（需要引擎在线）</summary><p>同步节点能力会读取当前引擎声明，不生成、不加载模型。${remote ? '当前模型列表来自此远程引擎的声明缓存。' : '本地文件刷新无需同步节点。'}</p><p>节点来源：${esc(nodes.engine_url || '尚无节点记录')} · 上次成功同步：${esc(time(nodes.updated || catalog.checked))}</p>${nodes.error ? errorFeedback({message:'节点能力同步失败',raw:nodes.error,kind:nodes.error_kind || 'website'}) : ''}${catalog.missing?.length ? `<p class="notice">待加载节点：${esc(catalog.missing.join('、'))}</p>` : ''}<button id="image-sync-nodes" type="button">同步节点能力</button></details></details>`;
}

function modelRefreshLabel(catalog) {
  return String(catalog.local_models?.source || '').startsWith('remote') ? '刷新模型列表（远程缓存）' : '刷新本地模型列表';
}

/** Resolve with parameters after Apply, or null after cancel/close/Esc/disposal. */
export async function openImageSettings({ task, catalog, request, onApply, onCatalog, signal, lastSeed }) {
  if (signal?.aborted) return null;
  const draft=createImageSettingsDraft({task,catalog,request,onApply,onCatalog,signal});
  const surface=openProductionSettings({signal,onCancel:()=>draft.cancel()});
  const {content}=surface;
  let selectedGroup='core', result=null;
  function draw() {
    if (!surface.alive()) return;
    const current=draft.catalog, fields=draft.fields();
    const render=field=>renderField(field,draft.get(field),current,{mode:draft.seedMode,seed:draft.seedValue,lastSeed});
    const sections=Object.entries(groups).map(([key,title])=>{
      const selected=fields.filter(field=>field.group===key);
      const usual=selected.filter(field=>!field.advanced), advanced=selected.filter(field=>field.advanced);
      let html=`<div class="settings-grid">${usual.map(render).join('')}</div>`;
      if(key==='core')html=`<p class="helper">当前工作流：Krea 图片创作 · ${esc(current.tools?.[task.submode]||task.submode)}。</p>${html}`;
      if(advanced.length)html+=`<details><summary>更多${esc(title)}参数</summary><div class="settings-grid">${advanced.map(render).join('')}</div></details>`;
      return selected.length?{key,title,html}:null;
    }).filter(Boolean);
    content.innerHTML=productionSettingsMarkup({
      scope:`当前图片任务草稿 · ${task.name||task.id} · ${current.tools?.[task.submode]||task.submode}`,
      directory:directoryMarkup(current,task.submode), sections,
      actions:productionSettingsActions([{role:'reset',id:'image-reset-defaults',label:'恢复默认'},{role:'cancel',id:'cancel-settings',label:'取消'},{role:'apply',id:'apply-settings',label:'应用'},{role:'save',id:'save-settings',label:'保存',primary:true}]),
      footer:'应用只更新当前任务的参数草稿；保存会持久化当前图片项目的全部草稿与画布标注。恢复默认仅改变本弹窗，取消可放弃。'
    });
    bindSettingsNavigation(content,selectedGroup,key=>selectedGroup=key);bindErrorFeedback(content);
    content.querySelector('#image-reset-defaults').onclick=()=>surface.run(()=>{
      draft.resetDefaults();draw();
      content.querySelector('#parameter-errors').innerHTML='<p class="notice" role="status">当前工具的模型和制作参数已恢复默认；应用后才写入草稿，取消可放弃。</p>';
    });
    for(const field of fields.filter(field=>field.type!=='seed')){
      const attr=field.scope==='models'?'data-model':'data-setting';
      const element=content.querySelector(`[${attr}="${field.key}"]`);
      element.oninput=()=>draft.set(field,element.value);element.onchange=element.oninput;
    }
    const mode=content.querySelector('[data-seed-mode]'),seed=content.querySelector('[data-seed]');
    if(mode&&seed){mode.onchange=()=>{draft.setSeedMode(mode.value);seed.disabled=mode.value==='random';};seed.oninput=()=>draft.setSeedValue(seed.value);seed.onchange=seed.oninput;}
    const refresh=sync=>surface.run(async()=>{
      if(await draft.refresh(sync)&&surface.alive()){
        draw();const current=draft.catalog;
        if(sync&&current.node_catalog?.error)surface.showError({message:'节点能力同步失败，保留当前参数和目录缓存',raw:current.node_catalog.error,kind:current.node_catalog.error_kind||'website'});
        else if(current.local_models?.errors?.length)surface.showError({message:'模型目录读取不完整，保留当前选择',raw:current.local_models.errors.join('\n'),kind:'website'});
      }
    });
    content.querySelector('#image-refresh-models').onclick=()=>refresh(false);
    content.querySelector('#image-sync-nodes').onclick=()=>refresh(true);
    content.querySelector('#cancel-settings').onclick=surface.cancel;
    const commit=saveNow=>surface.run(async()=>{
      result=await draft.apply(saveNow);
      toast(saveNow?'草稿已保存':'已应用到草稿，尚未保存');
      return result!==null;
    },{closeOnSuccess:true});
    content.querySelector('#apply-settings').onclick=()=>commit(false);
    content.querySelector('#save-settings').onclick=()=>commit(true);
  }
  draw();await surface.closed;draft.cancel();return result;
}
