import {esc} from './primitives.js';

const labels = {input:'输入或参数检查',compile:'工作流编译',engine:'生成引擎反馈',
  network:'连接状态',conflict:'保存版本冲突',not_found:'内容不可用',website:'网站操作'};
const text = value => typeof value === 'string' ? value : JSON.stringify(value, null, 2);

/** Present only the error actually received; never infer a node or parameter. */
export function describeError(error, fallback='操作失败') {
  const kind=error?.kind || error?.error_kind || 'website';
  const raw=error?.raw ?? error?.error_raw ?? error?.message ?? error?.note ?? error;
  return {kind, label:labels[kind] || labels.website,
    summary:error?.message || error?.error || error?.note || (typeof error==='string'?error:fallback),
    raw:text(raw) || fallback};
}

export function errorFeedback(error, fallback='操作失败') {
  const info=describeError(error,fallback);
  return `<div class="error-feedback"><strong>${esc(info.label)}</strong><p>${esc(info.summary)}</p><details><summary>查看原始错误</summary><pre tabindex="0">${esc(info.raw)}</pre><button type="button" data-copy-error>复制原始错误</button><small data-copy-status role="status"></small></details></div>`;
}

export function bindErrorFeedback(container) {
  container?.querySelectorAll('[data-copy-error]').forEach(button=>{
    button.onclick=async()=>{
      const details=button.closest('details'),status=details.querySelector('[data-copy-status]');
      try {await navigator.clipboard.writeText(details.querySelector('pre').textContent);status.textContent='已复制';}
      catch {status.textContent='无法访问剪贴板，可选中上方原文手动复制。';}
    };
  });
}
