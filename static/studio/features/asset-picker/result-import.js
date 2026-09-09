import {updateStatusRegion} from '../../ui/status-region.js';
import * as ui from "../../ui/primitives.js";
import { libraryApi, followTask } from "./library-client.js";
import {collectionActions} from '../../ui/result-view.js';
import {errorFeedback,bindErrorFeedback} from '../../ui/error-feedback.js';

// Confirmed receipts for this workspace instance, never a guessed library state.
const receipts=new WeakMap(),opening=new WeakSet(),receiptReads=new WeakMap();
export const resultAsset=(ctx,kind,id)=>receipts.get(ctx)?.get(kind+':'+id);

function paintReceipts(ctx){
  if(ctx.session.disposed)return;
  ctx.root.querySelectorAll('[data-publish-candidate],#publish-final').forEach(button=>{
    const kind=button.id==='publish-final'?'final':'candidate',id=kind==='final'?String(ctx.project.export?.created):button.dataset.publishCandidate;
    const asset=resultAsset(ctx,kind,id);
    if(asset){button.insertAdjacentHTML('afterend',collectionActions({asset}));button.remove();}
  });
}
export async function loadResultReceipts(ctx,{force=false}={}){
  if(ctx.session.disposed||!ctx.catalog.asset_library_version)return;
  const key=JSON.stringify([ctx.project.segments.flatMap(s=>s.attempts.filter(a=>a.delivery_url&&!a.removed_at).map(a=>[a.id,a.delivery_url])),ctx.project.export]);
  const old=receiptReads.get(ctx);
  if(old?.pending||(!force&&old?.key===key)){paintReceipts(ctx);return;}
  const state={key,pending:true};receiptReads.set(ctx,state);
  try{
    const response=await libraryApi('/projects/'+ctx.project.id+'/outputs','GET',undefined,ctx.session.controller.signal);
    if(ctx.session.disposed||receiptReads.get(ctx)!==state)return;
    if(response.result_receipts_version!==1)throw new Error("后台尚未加载入库记录读取，请在任务结束后重启导演台再刷新。");
    // Existing backend import records are the only durable authority.
    receipts.set(ctx,new Map(response.items.filter(x=>x.asset).map(x=>[x.kind+':'+x.result_id,x.asset])));
    paintReceipts(ctx);
    ctx.root.querySelector('[data-receipt-feedback]')?.remove();
  }catch(error){
    if(ctx.session.disposed||error.name==='AbortError')return;
    let box=ctx.root.querySelector('[data-receipt-feedback]');
    if(!box){box=document.createElement('div');box.dataset.receiptFeedback='';ctx.root.querySelector('#project-errors').after(box);}
    box.innerHTML=errorFeedback({kind:error.kind,message:'暂时无法读取入库记录，已有资产保留。',raw:error.raw??error.message})+'<button type="button" data-retry-receipts>重新读取入库记录</button>';
    bindErrorFeedback(box);box.querySelector('button[data-retry-receipts]').onclick=()=>loadResultReceipts(ctx,{force:true});
  }finally{state.pending=false;}
}

export async function saveProjectMedia(ctx, { kind, resultId } = {}) {
  if(opening.has(ctx)||ctx.session.disposed)return;
  const currentModal=ui.modalTicket();
  opening.add(ctx);
  try {
    const response = await libraryApi(
      `/projects/${ctx.project.id}/outputs`,
      "GET",
      undefined,
      ctx.session.controller.signal,
    );
    if(ctx.session.disposed||!currentModal())return;
    const items = response.items.filter(
      (x) =>
        (!kind || x.kind === kind) && (!resultId || x.result_id === resultId),
    );
    if (!items.length) return ui.toast("这项媒体尚未完整保存，暂时不能入库");
    if(ctx.session.disposed||!currentModal())return;
    const catalog = await libraryApi("/catalog","GET",undefined,ctx.session.controller.signal);
    if(ctx.session.disposed||!currentModal())return;
    const d = ui.scopedModal(
      `<h2>加入资产库</h2><p>选择确切文件后入库，之后可在资产详情抽帧、选段或提取声音。不会自动采用最新候选。</p><form id="save-library-result">${ui.field(
        "要入库的文件",
        `<select name="output">${ui.opts(
          items.map((x) => [x.id, x.name]),
          items[0].id,
        )}</select>`,
      )}${ui.field("资产名称", `<input name="name" required maxlength="160" value="${ui.esc(items[0].name)}">`)}${ui.field("分类", `<select name="category">${ui.opts([["", "稍后整理"], ...catalog.categories.map((c) => [c.id, c.name])], kind === "candidate" || kind === "final" ? "video" : "")}</select>`)}<p class="helper">已有的运行提示词会复制到资产资料，原始运行记录单独保留；不会改动项目正文。</p><div id="save-library-status" role="status"></div><div class="dialog-actions"><button type="button" id="save-library-close">取消</button><button class="primary">确认入库</button></div></form>`,
    );
    d.querySelector("#save-library-close").onclick = () => d.close();
    let working=false,changed=false;
    d.addEventListener('close',()=>{if(changed&&!ctx.session.disposed)ctx.renderProject();},{once:true});
    d.querySelector("form").onsubmit = async (e) => {
      e.preventDefault();
      if(working)return;
      working=true;
      const form = e.target,
        button = form.querySelector(".primary");
      const source=items.find(x=>x.id===form.elements.output.value);
      form.querySelectorAll("input,select").forEach(el=>el.disabled=true);
      d.querySelector("#save-library-close").textContent="收起";
      button.disabled = true;
      try {
        const task = await libraryApi("/project-results", "POST", {
          output: form.elements.output.value,
          name: form.elements.name.value,
          metadata: {
            categories: form.elements.category.value
              ? [form.elements.category.value]
              : [],
          },
        });
        const item = await followTask(
          task,
          (t) => {
            if (d.open)
              updateStatusRegion(d.querySelector("#save-library-status"),`<p>${ui.esc(t.note)}</p><progress max="1" value="${t.progress}"></progress>`);
          },
          ctx.session.controller.signal,
        );
        if(!receipts.has(ctx))receipts.set(ctx,new Map());
        receiptReads.delete(ctx);
        receipts.get(ctx).set(source.kind+':'+source.result_id,item.id);changed=true;
        if(!d.open&&!ctx.session.disposed)ctx.renderProject();
        if (d.open)
          d.querySelector("#save-library-status").innerHTML =
            `<p>原结果已入库，选用状态与项目步骤保持不变。</p>${collectionActions({asset:item.id})}`;
      } catch (error) {
        if (d.open)
          d.querySelector("#save-library-status").innerHTML = errorFeedback(error);
        if(d.open)bindErrorFeedback(d);
        working=false;
        form.querySelectorAll("input,select").forEach(el=>el.disabled=false);
        button.disabled = false;
      }
    };
  } catch (error) {
    if(!ctx.session.disposed&&currentModal()&&error.name!=="AbortError")ui.toast(error.message);
  } finally {
    opening.delete(ctx);
  }
}
