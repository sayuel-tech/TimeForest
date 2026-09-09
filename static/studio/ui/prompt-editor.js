import {onScopedClose,esc,scopedModal} from './primitives.js';

/** Supporting text stays identifiable while the current task keeps the main area. */
export function readingDisclosure(title,text,{open=false}={}){
  const value=String(text||'');
  return `<details class="reading-disclosure" ${open?'open':''}><summary>${esc(title)}<span class="reading-excerpt">${esc(value.slice(0,110))}${value.length>110?'…':''}</span></summary><div class="creation-prose">${esc(value)}</div></details>`;
}

/** Read-only text never becomes a draft or an implicit replacement. */
export function openReading(text,label='查看全文'){
  const d=scopedModal(`<div class="dialog-heading"><h2>${esc(label)}</h2></div><div class="reading-document">${esc(text)}</div><div class="dialog-actions"><button data-close>关闭</button></div>`);
  d.querySelector('[data-close]').onclick=()=>d.close();
}

export function bindReadingPreviews(root){
  root.querySelectorAll('.property-panel .creation-prose,.property-panel .image-run-prompt').forEach(el=>{
    if(el.textContent.length<140||el.nextElementSibling?.hasAttribute('data-reading-preview'))return;
    const button=document.createElement('button');button.type='button';button.dataset.readingPreview='';button.textContent='展开阅读全文';el.after(button);
    button.onclick=()=>openReading(el.textContent,'来源正文');
  });
}

export async function expandPrompt(text,label,signal){
  const d=scopedModal(`<div class="dialog-heading"><h2>${esc(label)} · 展开编辑</h2><p>应用到当前草稿，保存后才持久化。</p></div><div class="reading-editor"><textarea data-expanded rows="16" aria-label="${esc(label)}">${esc(text)}</textarea></div><div class="dialog-actions"><button data-cancel>取消</button><button data-apply class="primary">应用到草稿</button></div>`);
  return new Promise(resolve=>{let settled=false;const done=v=>{if(settled)return;settled=true;signal?.removeEventListener('abort',abort);d.close();resolve(v);};const abort=()=>done(null);signal?.addEventListener('abort',abort,{once:true});d.oncancel=e=>{e.preventDefault();done(null);};d.querySelector('[data-cancel]').onclick=()=>done(null);d.querySelector('[data-apply]').onclick=()=>done(d.querySelector('textarea').value);onScopedClose(d,()=>done(null));});
}

/** Shared toolbar presentation. No library API or business state lives here. */
export function promptTools(el,bundle=false){
  const tools=document.createElement('div');tools.className='prompt-tools';tools.setAttribute('role','group');tools.setAttribute('aria-label','提示词工具');
  tools.innerHTML='<button type="button" data-tool="pick">从提示词库选择</button><button type="button" data-tool="favorite">收藏</button><button type="button" data-tool="copy">复制</button><button type="button" data-tool="expand">展开编辑</button>'+(bundle?'<button type="button" data-tool="bundle">收藏字段组合</button>':'')+'<span class="helper" data-source></span>';
  // Insert outside the field label: tool buttons must not focus/re-toggle its input.
  const label=el.closest('label.field');(label||el).insertAdjacentElement('afterend',tools);
  return tools;
}
