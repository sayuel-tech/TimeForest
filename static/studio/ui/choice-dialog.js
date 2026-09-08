import {esc} from './primitives.js';
import {errorFeedback, bindErrorFeedback} from './error-feedback.js';

/** A modal decision must not replace the parameter draft underneath it. */
export function chooseAction({title, message, choices, signal}) {
  if (signal?.aborted) return Promise.resolve(null);
  const trigger = document.activeElement, dialog = document.createElement('dialog');
  dialog.className = 'choice-dialog';
  dialog.setAttribute('aria-label', title);
  dialog.innerHTML = `<button class="dialog-close" type="button" aria-label="关闭对话框">×</button><div class="dialog-heading"><h2>${esc(title)}</h2><p>${esc(message)}</p></div><div data-choice-error role="alert"></div><div class="dialog-actions">${choices.map((item,i)=>`<button type="button" data-choice="${i}" class="${item.primary?'primary':''}">${esc(item.label)}</button>`).join('')}</div>`;
  document.body.append(dialog);
  return new Promise(resolve => {
    let settled = false, busy = false;
    const finish = value => {
      if (settled) return;
      settled = true;signal?.removeEventListener('abort', abort);
      dialog.close();dialog.remove();
      if (trigger?.isConnected) trigger.focus({preventScroll:true});
      resolve(value);
    };
    const abort = () => finish(null);
    const cancel = event => {event?.preventDefault();if (!busy) finish(null);};
    dialog.oncancel = cancel;
    dialog.querySelector('.dialog-close').onclick = cancel;
    dialog.addEventListener('close', () => finish(null), {once:true});
    signal?.addEventListener('abort', abort, {once:true});
    dialog.querySelectorAll('[data-choice]').forEach(button => button.onclick = async () => {
      if (busy || settled) return;
      busy = true;
      dialog.querySelectorAll('button').forEach(el=>el.disabled=true);
      const item = choices[Number(button.dataset.choice)];
      try {
        if (!item.run || await item.run() !== false) finish(item.value);
      } catch (error) {
        if (!settled) {
          const box=dialog.querySelector('[data-choice-error]');
          box.innerHTML=errorFeedback(error);bindErrorFeedback(box);
        }
      } finally {
        busy=false;
        if (!settled) dialog.querySelectorAll('button').forEach(el=>el.disabled=false);
      }
    });
    dialog.showModal();
  });
}

export function confirmLeave({save, signal}) {
  return chooseAction({title:'离开当前项目？', message:'当前有未保存修改。保存后再离开，或留在此页继续编辑；放弃修改只丢弃未保存草稿，不会停止生成任务。',signal,
    choices:[{value:'stay',label:'留在此页'},{value:'discard',label:'放弃修改并离开'},{value:'save',label:'保存后离开',primary:true,run:save}]});
}
