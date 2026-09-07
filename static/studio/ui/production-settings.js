import { esc, field, opts, scopedModal } from './primitives.js';
import { modelSelector, bindModelSelectors } from './model-selector.js';

/** Own the complete, instance-scoped dialog. Adapters own only drafts and commands. */
export function openProductionSettings({signal, onCancel = () => {}} = {}) {
  const dialog = scopedModal('<div class="production-settings" id="settings-content"></div>');
  const content = dialog.querySelector('.production-settings');
  bindModelSelectors(content);
  let settled = false, resolve;
  const closed = new Promise(done => resolve = done);
  const finish = () => {
    if (settled) return;
    settled = true;
    signal?.removeEventListener('abort', cancel);
    dialog.removeEventListener('close', onClose);
    resolve();
  };
  const close = () => { if (!settled) {dialog.close();finish();} };
  const cancel = event => {event?.preventDefault();onCancel();close();};
  const onClose = () => {if (!dialog.open) finish();};
  dialog.oncancel = cancel;
  dialog.addEventListener('close', onClose);
  signal?.addEventListener('abort', cancel, {once:true});
  if (signal?.aborted) cancel();
  return {dialog, content, closed, close, alive: () => !settled && dialog.open};
}

export const parameterGrid = html => `<div class="settings-grid">${html}</div>`;
export const parameterSlots = html => `<div class="lora-slots">${html}</div>`;

export function productionSettingsActions(items) {
  const order={reset:0,cancel:1,apply:2,save:3};
  return [...items].sort((a,b)=>order[a.role]-order[b.role]).map(item=>`<button type="button" ${item.id?`id="${esc(item.id)}"`:''} ${item.attributes||''} class="${item.primary?'primary':item.role==='reset'?'quiet':''}">${esc(item.label)}</button>`).join('');
}

// Keep the established video labels and order; a tool may qualify its own stages.
export const productionGroups = {
  core: '工作流与模型',
  picture: '画布与输出',
  sampling: '两采与时长',
  assets: '参考与声音',
  lora: 'LoRA',
  memory: '低显存',
  advanced: '高级模型组件',
};

/** The same top-right action and workflow caption in every workspace. */
export function productionSettingsAction({ id = 'settings', workflow = '' } = {}) {
  return `<div class="project-actions"><button id="${esc(id)}">制作参数 <span aria-hidden="true">↗</span></button><small>${esc(workflow)}</small></div>`;
}

/** Shared presentation only. The caller owns task/project drafts and persistence. */
export function productionSettingsMarkup({ scope, directory = '', summary = '', sections, extra = '', actions, footer = '' }) {
  directory = directory ? `<div class="production-settings-directory">${directory}</div>` : '';
  return `<div class="dialog-heading"><span class="eyebrow">PRODUCTION SETTINGS</span><h2>制作参数</h2><p>${esc(scope)}</p></div>${directory}${summary}<div id="parameter-errors" role="alert"></div><div class="settings-workbench"><nav class="settings-navigation" aria-label="制作参数分类">${sections.map(({key,title}) => `<button type="button" data-settings-section="${esc(key)}">${esc(title)}</button>`).join('')}</nav><div class="settings-fields">${sections.map(({key,title,html}) => `<section class="settings-group" data-settings-group="${esc(key)}"><h3>${esc(title)}</h3>${html}</section>`).join('')}</div></div>${extra}<div class="dialog-actions">${actions}</div>${footer ? `<p class="helper">${esc(footer)}</p>` : ''}`;
}

export function bindSettingsNavigation(content, selected = 'core', onSelect = () => {}) {
  const buttons = [...content.querySelectorAll('[data-settings-section]')];
  const show = (key) => {
    selected = buttons.some(button => button.dataset.settingsSection === key)
      ? key : buttons[0]?.dataset.settingsSection;
    buttons.forEach(button => button.setAttribute('aria-current', String(button.dataset.settingsSection === selected)));
    content.querySelectorAll('[data-settings-group]').forEach(section => { section.hidden = section.dataset.settingsGroup !== selected; });
    onSelect(selected);
  };
  buttons.forEach(button => { button.onclick = () => show(button.dataset.settingsSection); });
  show(selected);
}

/** attributes are owned by the caller, never copied from plugin fields. */
export function parameterField(definition, value, { attributes = '', options, preserveCurrent = false } = {}) {
  const f = definition;
  if (f.type === 'boolean')
    return `<label class="field"><span class="check"><input ${attributes} type="checkbox" ${value ? 'checked' : ''}>${esc(f.label)}</span><small>${esc(f.help)}</small></label>`;
  let control, help = f.help || '';
  if (['model', 'lora', 'vae', 'clip'].includes(f.type)) {
    return modelSelector(f, value, {attributes, options});
  } else if (options) {
    let choices = options;
    if (preserveCurrent && value !== undefined && !choices.some(option => String(Array.isArray(option) ? option[0] : option) === String(value)))
      choices = [[value, `${value}（当前值）`], ...choices];
    control = `<select ${attributes} title="${esc(value)}">${opts(choices, value)}</select>`;
  } else {
    control = `<input ${attributes} type="number" step="${esc(f.step ?? .01)}" ${f.min !== undefined ? `min="${esc(f.min)}"` : ''} ${f.max !== undefined ? `max="${esc(f.max)}"` : ''} value="${esc(value)}">`;
  }
  return field(esc(f.label), control, esc(help));
}

export function seedFields({ mode, value, lastSeed, modeAttributes = 'data-seed-mode', valueAttributes = 'data-seed' }) {
  return `${field('种子模式', `<select ${modeAttributes}>${opts([['random','每次随机'],['fixed','固定种子']], mode)}</select>`)}${field('固定种子', `<input ${valueAttributes} inputmode="numeric" value="${esc(value)}" ${mode === 'random' ? 'disabled' : ''}>`, `上次实际使用：${esc(lastSeed ?? '尚未生成')}。固定值 0 有效；请输入 0～9007199254740991 的整数。`)}`;
}
