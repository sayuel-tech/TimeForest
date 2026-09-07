import {esc} from '../../ui/primitives.js';

/** Read-only draft inspection; never enters the save/preflight command pipeline. */
export function createPromptPreview(ctx) {
  const previews=new Map();
  const stamp=()=>JSON.stringify([ctx.project.revision,ctx.project.settings,ctx.project.swap_prompt,ctx.project.segments]);
  function content(s,entry) {
    const current=entry.stamp===stamp();
    return `<div class="final-prompt-heading"><h4>P${s.index+1} · 最终提示词</h4><button type="button" class="quiet" data-close-final>收起</button></div><p class="helper" data-final-note>${current?'按当前编排生成；未保存的修改也包含在内。预览不会保存项目或启动生成。':'编排已变化，请点击上方按钮更新提示词。'}</p><textarea readonly data-final-body aria-label="P${s.index+1}最终提示词" ${current?'':'hidden'}>${esc(entry.prompt)}</textarea><button type="button" class="quiet" data-copy-final ${current?'':'disabled'}>复制提示词</button>`;
  }
  function markup(s) {
    const entry=previews.get(s.id);
    return `<section class="final-prompt-preview" id="final-prompt-${s.id}" data-final-preview="${s.id}" ${entry?.open?'':'hidden'}>${entry?.open?content(s,entry):''}</section>`;
  }
  function bindContent(box,s,entry) {
    box.querySelector('[data-close-final]').onclick=()=>{entry.open=false;box.hidden=true;const b=ctx.root.querySelector(`[data-swap-preview="${s.id}"]`);b?.setAttribute('aria-expanded','false');b?.focus();};
    box.querySelector('[data-copy-final]').onclick=async()=>{
      if(entry.stamp!==stamp()){invalidate();return;}
      try{await navigator.clipboard.writeText(entry.prompt);ctx.toast('提示词已复制');}catch{ctx.toast('复制未获允许，可以选中下方正文手动复制。');}
    };
  }
  function invalidate() {
    for(const [id,entry] of previews) {
      if(!entry.open||entry.stamp===stamp())continue;
      const box=ctx.root.querySelector(`[data-final-preview="${id}"]`);if(!box)continue;
      const note=box.querySelector('[data-final-note]');if(!note)continue;
      note.textContent='编排已变化，请点击上方按钮更新提示词。';
      box.querySelector('[data-final-body]').hidden=true;box.querySelector('[data-copy-final]').disabled=true;
    }
  }
  for(const event of ['input','change'])ctx.root.addEventListener(event,()=>queueMicrotask(invalidate),{signal:ctx.session.controller.signal});
  function bind() {
    ctx.root.querySelectorAll('[data-swap-preview]').forEach(button=>{
      const s=ctx.project.segments.find(s=>s.id===button.dataset.swapPreview);
      const box=ctx.root.querySelector(`[data-final-preview="${s.id}"]`),entry=previews.get(s.id);
      button.setAttribute('aria-expanded',String(Boolean(entry?.open)));
      if(entry?.open)bindContent(box,s,entry);
      button.onclick=async()=>{
        const before=stamp();button.disabled=true;box.hidden=false;box.innerHTML='<p role="status">正在整理本段提示词…</p>';button.setAttribute('aria-expanded','true');
        try {
          const result=await ctx.api(`/projects/${ctx.project.id}/prompt-preview`,'POST',{revision:ctx.project.revision,segment:s.id,settings:ctx.project.settings,segments:ctx.project.segments,swap_prompt:ctx.project.swap_prompt});
          if(ctx.session.disposed||!box.isConnected)return;
          if(before!==stamp()){box.innerHTML='<p role="status">编排已变化，请重新查看当前提示词。</p>';return;}
          const entry={open:true,stamp:before,prompt:result.prompt};previews.set(s.id,entry);
          box.innerHTML=content(s,entry);bindContent(box,s,entry);
          button.textContent='更新最终提示词';box.scrollIntoView({block:'nearest'});
        } catch(error) {if(box.isConnected)box.innerHTML=`<p role="alert">${esc(error.message)}</p><p class="helper">请修正后再次查看。你的正文没有被修改。</p>`;}
        finally {if(button.isConnected)button.disabled=false;}
      };
    });
  }
  return {markup,bind};
}
