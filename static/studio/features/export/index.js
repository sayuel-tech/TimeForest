import {addRecordButton} from '../prompt-library/records.js';
import {resultActions,collectionActions} from '../../ui/result-view.js';
import {resultAsset} from '../asset-picker/result-import.js';
import {runTiming,runStatusRow} from '../../ui/run-timing.js';
import {workbench,propertyTabs,bindWorkbench} from '../../ui/workbench.js';
import {mediaPlayer} from '../../ui/media-player.js';
/** View feature; receives a project-scoped public workspace context. */
export function createFeature(ctx) {
  function exportProgressCard() {
    const p = ctx.project,
      r = p.runtime || {};
    const isExport =
      p.status === "assembling" ||
      r.operation === "export" ||
      /合成/.test(r.phase || "");
    if (!isExport) return "";
    const complete = p.status === "complete" && Boolean(p.export);
    const failed =
      !complete &&
      (p.status === "failed" || (r.operation === "export" && Boolean(r.error)));
    const active =
      !failed && !complete && (p.status === "assembling" || r.active);
    const start = r.started || r.updated;
    const end = active ? null : r.finished || r.updated;
    return `<section class="panel run-progress" aria-live="polite">${runStatusRow(`<div class="notice ${failed?'error':''}" role="status"><strong>${failed ? "合成未完成" : complete ? "完整视频已合成" : ctx.esc(r.operation === "export" ? r.phase : "正在合成完整视频与声音")}</strong><small>成片合成</small></div>`,runTiming({start,end,live:active,label:'本次合成用时'}))}${active ? '<progress aria-label="正在合成完整视频与声音"></progress><p class="muted">正在拼接画面与声音，完成后将在这里显示成片。合成服务暂不提供百分比，进度条表示任务进行中。</p>' : complete ? '<progress aria-label="合成已完成" value="1" max="1"></progress>' : ""}${failed ? `<p class="notice error">${ctx.esc(p.error || r.error || "请检查任务状态后重试。")}</p>` : ""}${r.transport_error || r.connection_error ? `<p class="notice error">${ctx.esc(r.transport_error || r.connection_error)}</p>` : ""}</section>`;
  }
  async function renderExport() {
    const p = ctx.project;
    const timeline=p.segments.map(s=>`<p>P${s.index+1} · ${ctx.fmt(s.deliver/24)}秒 · ${ctx.LABELS[s.status]||s.status}</p>`).join('');
    const stats=`<dl class="export-facts"><dt>计划总长</dt><dd>${ctx.fmt(p.duration)}秒</dd><dt>预计有效总长</dt><dd>${ctx.fmt(p.segments.reduce((n,s)=>n+s.deliver,0)/24)}秒</dd><dt>已接受</dt><dd>${p.segments.filter(s=>['accepted','done'].includes(s.status)).length}/${p.segments.length}</dd><dt>导出帧率</dt><dd>${p.settings.export_fps}fps</dd><dt>声音</dt><dd>${p.settings.audio_policy==='source'?'原片声音':'H3原生声音'}</dd></dl><p class="helper">声画生成与续接为24fps。导出帧率转换保持正常速度。</p>`;
    const storage='<h3>本机文件与恢复</h3><button id="diagnostic">下载诊断信息</button><div id="storage">读取磁盘占用…</div><div class="stack"><button id="clean-failed">清理已确认失败文件</button><button id="clean-export">清理旧导出缓存</button><button id="save-defaults">另存为新项目默认参数</button></div>';
    const canvas=`<div class="shot-heading"><h2>完整作品</h2>${ctx.status(p.status)}</div>${p.export?mediaPlayer(p.export.url,'完整成片'):'<div class="empty result-empty"><img src="/static/assets/empty/empty-shot.svg" alt=""><h3>片段准备好后，在这里合成。</h3><p>最后一段审核完成后会自动来到这里。</p></div>'}${resultActions({collect:p.export?collectionActions({url:p.export.url,asset:resultAsset(ctx,'final',String(p.export.created)),button:ctx.catalog.asset_library_version?'<button type="button" id="publish-final">加入资产库</button>':''}):'',decide:!p.export?`<button id="export-now" class="primary" data-auto-save data-saved-label="合成完整视频" data-dirty-label="保存并合成" ${p.busy?'disabled':''}>${ctx.dirty?'保存并合成':'合成完整视频'}</button>`:''})}`;
    ctx.$('#view').innerHTML=`<div id="run-progress">${exportProgressCard()}</div>`+workbench({kind:'export-desk',canvas,inspector:propertyTabs(ctx,[{id:'delivery',label:'成片',html:stats},{id:'timeline',label:'片段',html:timeline},{id:'storage',label:'文件',html:storage}])});
    bindWorkbench(ctx);
    if(p.export){const anchor=ctx.root.querySelector('#publish-final')||ctx.root.querySelector('.result-actions a');addRecordButton(anchor,{path:'/records/'+p.id+'?final='+encodeURIComponent(p.export.created),signal:ctx.session.controller.signal});}
    if (ctx.$("#export-now"))
      ctx.$("#export-now").onclick = () => ctx.runAction("/export", {});
    ctx.$("#diagnostic").onclick = async () => {
      try {
        ctx.download(
          await ctx.api(`/projects/${p.id}/diagnostic`),
          "time-forest-diagnostic.json",
        );
      } catch (e) {
        ctx.toast(e.message);
      }
    };
    const publish=ctx.root.querySelector('#publish-final');
    if(publish)publish.onclick=()=>ctx.saveProjectMedia({kind:'final',resultId:String(p.export.created)});
    ctx.$("#save-defaults").onclick = async () => {
      if (
        await ctx.confirm(
          "保存默认参数",
          "只影响此模式以后建立的新项目，不改其他已有项目。",
        )
      ) {
        try {
          if (ctx.dirty && !(await ctx.save())) return;
          await ctx.api(`/projects/${p.id}/defaults`, "POST", {});
          ctx.toast("默认参数已保存");
        } catch (e) {
          ctx.toast(e.message);
        }
      }
    };
    for (const [id, kind] of [
      ["clean-failed", "failed"],
      ["clean-export", "exports"],
    ])
      ctx.$("#" + id).onclick = async () => {
        if (
          await ctx.confirm(
            "清理本机文件",
            "保留当前选用结果和AV上下文，只清理指定的失败文件或旧导出。",
          )
        ) {
          try {
            const d = await ctx.api(`/projects/${p.id}/cleanup`, "POST", {
              kind,
            });
            ctx.toast("释放 " + ctx.bytes(d.freed_bytes));
            renderExport();
          } catch (e) {
            ctx.toast(e.message);
          }
        }
      };
    const storageTarget=ctx.root.querySelector("#storage");
    try {
      const d = await ctx.api(`/projects/${p.id}/storage`);
      if (!ctx.session.disposed && storageTarget?.isConnected && ctx.root.querySelector("#storage")===storageTarget)
        ctx.$("#storage").innerHTML =
          `<p>${ctx.bytes(d.bytes)}</p><div class="row">${Object.entries(
            d.groups,
          )
            .map(
              ([k, v]) =>
                `<span class="badge">${ctx.esc(k)} ${ctx.bytes(v)}</span>`,
            )
            .join("")}</div>`;
    } catch (e) {
      if (!ctx.session.disposed && storageTarget?.isConnected && ctx.root.querySelector("#storage")===storageTarget)
        ctx.$("#storage").textContent = e.message;
    }
  }
  return { renderExport, exportProgressCard };
}
