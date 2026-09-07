import {runTiming,runStatusRow} from '../../ui/run-timing.js';
/** View feature; receives a project-scoped public workspace context. */
export function createFeature(ctx) {
  function fileUrl(path) {
    const match = String(path)
      .replaceAll("\\", "/")
      .split("/" + ctx.project.id + "/");
    return (
      "/api/v5/projects/" +
      ctx.project.id +
      "/files/" +
      match.slice(1).join("/" + ctx.project.id + "/")
    );
  }
  function attemptDialog(a) {
    const runs = a.tasks
      ? a.tasks.flatMap((t, i) =>
          t.attempts.map((r) => ({ ...r, task: i + 1 })),
        )
      : [a];
    const d = ctx.modal(
      `<h2>实际运行文件</h2><p>这里是实际提交的执行图，不是当前参数的预检图。</p>${runs.map((r) => `<section class="panel"><h3>${r.task ? "内部任务 " + r.task : "本次运行"}</h3><small>seed ${ctx.esc(r.seed)} · ${ctx.esc(r.prompt_id || "尚未收到提交编号")}</small><div class="row">${["workflow.json", "manifest.json", "prompt.txt", ...(r.prompt_id ? ["request.json"] : []), ...(r.status === "complete" ? ["history.json", "qa.json"] : [])].map((f) => `<a href="${fileUrl(r.directory + "/" + f)}" target="_blank" rel="noreferrer">${f === "workflow.json" ? "查看 / 下载实际执行图" : f}</a>`).join("")}</div></section>`).join("") || "<p>尚未提交内部任务。</p>"}<button id="close-attempt">关闭</button>`,
    );
    ctx.$("#close-attempt").onclick = () => d.close();
  }
  function executionCard(segment) {
    const info = segment?.execution_info;
    if (!info) return "";
    return `<details class="execution-details"><summary>本次实际执行的工作流与参数${info.finished ? " · 用时 " + ctx.elapsed(info.started, info.finished) : ""}</summary>${info.runs
      .map((run, i) => {
        const s = run.summary;
        if (!s) return "";
        return `<div class="panel"><b>内部任务 ${i + 1} · ${s.split_core ? "原日程 " + s.steps + "＋" + s.refine_steps + " → 潜空间放大二采" : s.two_pass ? "完整一采 → 潜空间放大 → 独立精修" : "单次采样"}</b><p>底模：${ctx.esc(s.model)}</p><p>一采：${s.width}×${s.height} · ${s.steps}步 · ${ctx.esc(s.sampler)}${s.split_core ? " · 总日程" + s.total_steps + "步的前段" : s.denoise !== null && s.denoise !== undefined ? " · 降噪 " + s.denoise : ""}</p>${s.two_pass ? `<p>潜空间放大 ${s.scale}× → 二采 ${s.refine_steps}步${s.split_core ? " · 原日程剩余sigmas" : s.refine_denoise !== null && s.refine_denoise !== undefined ? " · 降噪 " + s.refine_denoise : ""} → ${s.output_width}×${s.output_height}</p>` : ""}<p>最终画面取${s.picture_source}；声音与续接检查点取${s.audio_source}。</p><small>实际种子 ${ctx.esc(run.seed)} · 任务编号 ${ctx.esc(run.prompt_id || "等待提交")}</small><p><a href="${fileUrl(s.workflow)}" target="_blank" rel="noreferrer">查看 / 下载本次实际执行图</a></p></div>`;
      })
      .join("")}</details>`;
  }
  function progressCard() {
    const r = ctx.project?.runtime;
    if (!r?.phase) return "";
    if (
      ctx.project.status === "assembling" ||
      r.operation === "export" ||
      /合成/.test(r.phase)
    )
      return "";
    const start = r.started || r.updated,
      end = r.active ? null : r.finished || r.updated;
    const sampling = Number(r.step_total) > 0,
      pct = sampling
        ? Math.min(100, (100 * Number(r.step || 0)) / Number(r.step_total))
        : 0;
    return `<section class="panel run-progress" aria-live="polite">${runStatusRow(`<div class="notice" role="status"><strong>${ctx.esc(r.phase)}</strong><small>${r.active ? "正在制作" : "运行状态"}${r.shot !== null && r.shot !== undefined ? " · 片段 " + (r.shot + 1) : ""}${r.task_total ? " · 内部任务 " + ((r.task || 0) + 1) + "/" + r.task_total : ""}</small></div>`,runTiming({start,end,live:r.active,uncertain:ctx.project.status==='interrupted'}))}${sampling ? `<div class="row between"><span>当前节点采样 ${r.step ?? 0} / ${r.step_total} 步</span><span>${pct.toFixed(0)}%</span></div><progress value="${r.step || 0}" max="${r.step_total}"></progress>` : '<p class="muted">' + (r.active ? "该阶段可能没有逐步进度，计时仍会继续。" : "本次运行已停止计时。") + "</p>"}${r.node ? `<small>节点 ${ctx.esc(r.node)} · ${ctx.esc(r.node_type || "")} · 已完成/复用 ${r.nodes_done || 0}/${r.nodes_total || "?"} 个节点（各节点耗时不同）</small>` : ""}${r.active && r.last_event ? `<p class="muted">距上次节点上报 <span data-clock="${r.last_event}">${ctx.elapsed(r.last_event)}</span></p>` : ""}${r.transport_error || r.connection_error ? `<p class="notice error">${ctx.esc(r.transport_error || r.connection_error)}</p>` : ""}${r.error ? `<p class="notice error">${ctx.esc(r.error)}</p>` : ""}</section>`;
  }
  function updateProgress() {
    if (ctx.$("#run-progress"))
      ctx.$("#run-progress").innerHTML =
        ctx.tab === "export" ? ctx.exportProgressCard() : progressCard();
    ctx.updateClocks();
  }
  return {
    fileUrl,
    attemptDialog,
    executionCard,
    progressCard,
    updateProgress,
  };
}
