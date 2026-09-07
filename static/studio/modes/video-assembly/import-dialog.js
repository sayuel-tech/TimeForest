import {scopedModal} from '../../ui/primitives.js';
import {importOptions} from '../../ui/reference-assets.js';

/** Choose an input source without navigating or touching the project's draft. */
export function chooseVideoImport({signal} = {}) {
  if (signal?.aborted) return Promise.resolve(null);
  return new Promise(resolve => {
    const dialog = scopedModal(`<div class="dialog-heading"><span class="eyebrow">ADD VIDEO</span><h2>添加视频</h2><p>选择视频来源，追加到当前视频目录。</p></div>${importOptions(['<button type="button" data-local-video>导入本地视频</button>', '<button type="button" data-library-video>从资产库选择</button>'])}<input type="file" data-video-files accept="video/*,.mkv" multiple hidden><p class="helper">支持多选，添加后仍停留在当前步骤，可继续续接或调整顺序。</p><div class="dialog-actions"><button type="button" data-cancel-import>取消</button></div>`);
    let finished = false;
    const done = value => {
      if (finished) return;
      finished = true;
      signal?.removeEventListener('abort', cancel);
      dialog.removeEventListener('close', onClose);
      dialog.close();resolve(value);
    };
    const cancel = () => done(null);
    const onClose = () => { if (!dialog.open) cancel(); };
    dialog.oncancel = event => {event.preventDefault();cancel();};
    dialog.addEventListener('close', onClose);
    signal?.addEventListener('abort', cancel, {once:true});
    dialog.querySelector('[data-cancel-import]').onclick = cancel;
    dialog.querySelector('[data-library-video]').onclick = () => done({library:true});
    const input = dialog.querySelector('[data-video-files]');
    dialog.querySelector('[data-local-video]').onclick = () => input.click();
    input.onchange = () => {if (input.files.length) done({files:[...input.files]});};
  });
}
