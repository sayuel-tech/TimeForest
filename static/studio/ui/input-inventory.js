import {esc} from './primitives.js';

export function inputTable(rows=[]) {
  return `<div class="table-scroll"><table class="input-table"><thead><tr><th>素材</th><th>职责</th><th>模型编号</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.name||r.asset_id||'未上传')}</td><td>${esc({character:'角色形象',face:'面部',costume:'服装',scene:'场景',palette:'色系',prop:'物品',voice:'音色与说话方式',source:'动作、镜头与场景'}[r.purpose]||r.purpose)}${r.subject?' · 角色'+esc(r.subject):''}</td><td><code>${esc(r.tag)}</code></td></tr>`).join('')||'<tr><td colspan="3">没有独立参考素材</td></tr>'}</tbody></table></div>`;
}

export function inputActions(ctx,s) {
  return `<button type="button" class="quiet" data-input-inventory="${s.id}">查看本段有效输入</button>`;
}

export function bindInputInventory(ctx) {
  ctx.root.querySelectorAll('[data-input-inventory]').forEach(button=>button.onclick=async()=>{
    button.disabled=true;
    try {
      const stamp=JSON.stringify({segments:ctx.project.segments,settings:ctx.project.settings});
      const selected=ctx.shot;
      const data=await ctx.api(`/projects/${ctx.project.id}/input-preview`,'POST',{
        segment:button.dataset.inputInventory,segments:ctx.project.segments,settings:ctx.project.settings});
      if(ctx.session.disposed || ctx.shot!==selected)return;
      if(stamp!==JSON.stringify({segments:ctx.project.segments,settings:ctx.project.settings})){ctx.toast('素材或设置已变化，请重新核对当前输入。');return;}
      const d=ctx.modal(`<h2>本段有效输入</h2><p>当前草稿 · 基于已保存版本 ${data.revision}</p>${inputTable(data.inputs)}<p>${esc(data.context)}</p><p class="helper">${esc(data.note)}</p>${data.warnings.map(w=>`<p class="notice">${esc(w)}</p>`).join('')}<p>人物身份 Subject、图片 Picture、发声身份 S 是不同的编号体系。</p><button type="button" data-close-inputs>返回编排</button>`);
      d.querySelector('[data-close-inputs]').onclick=()=>d.close();
    }catch(e){ctx.toast(e.message);}finally{if(button.isConnected)button.disabled=false;}
  });
}
