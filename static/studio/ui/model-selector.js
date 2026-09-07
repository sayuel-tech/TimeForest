import {esc, field, opts} from './primitives.js';

/** Directory selection is unfiltered by the current filename; manual values remain editable. */
export function modelSelector(definition, value, {attributes = '', options = []} = {}) {
  value = String(value ?? '');
  const files = options.map(option => String(Array.isArray(option) ? option[0] : option));
  const missing = Boolean(value && !files.includes(value));
  const choices = files.includes(value) ? options : [[value, value ? `${value}（目录未发现，保留当前选择）` : '未选择文件'], ...options];
  return `<div data-model-field data-model-files="${esc(JSON.stringify(files))}">${field(esc(definition.label), `<select ${attributes} data-model-choice title="${esc(value)}">${opts(choices, value)}</select>`, esc(definition.help || ''))}<small data-model-presence="${esc(definition.key)}" ${missing ? '' : 'hidden'}>当前目录未发现此文件，保留当前选择；请核对模型来源。</small><details class="model-filename-editor"><summary>手动填写文件名</summary>${field('完整相对文件名', `<input data-model-filename value="${esc(value)}" spellcheck="false">`, '保留子目录和扩展名；应用或保存后生效。')}</details></div>`;
}

/** One delegated binding per dialog, surviving adapter redraws without duplicate listeners. */
export function bindModelSelectors(content) {
  const sync = event => {
    const fieldRoot = event.target.closest('[data-model-field]');
    if (!fieldRoot || !content.contains(fieldRoot)) return;
    const select = fieldRoot.querySelector('[data-model-choice]');
    const input = fieldRoot.querySelector('[data-model-filename]');
    if (event.target === input) {
      if (![...select.options].some(option => option.value === input.value)) {
        const option = select.querySelector('[data-manual-value]') || document.createElement('option');
        option.dataset.manualValue = '';
        option.value = input.value;option.textContent = input.value || '未选择文件';
        select.append(option);
      }
      select.value = input.value;
      select.dispatchEvent(new Event(event.type, {bubbles: true}));
    } else if (event.target === select) {
      input.value = select.value;select.title = select.value;
      fieldRoot.querySelector('[data-model-presence]').hidden = !select.value || JSON.parse(fieldRoot.dataset.modelFiles).includes(select.value);
    }
  };
  content.addEventListener('input', sync);
  content.addEventListener('change', sync);
}
