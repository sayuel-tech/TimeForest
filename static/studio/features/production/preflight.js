import {inputTable} from '../../ui/input-inventory.js';
/** View feature; receives a project-scoped public workspace context. */
export function createFeature(ctx) {
  async function preflight() {
    try {
      const d = await ctx.commands.preflight();
      if (!d || ctx.session.disposed) return;
      const modalEl = ctx.modal(
        `<span class="eyebrow">WORKFLOW PREFLIGHT</span><h2>${d.ready ? "结构预检通过" : "需要补充或修正"}</h2><div class="notice ${d.ready ? "" : "error"}">${ctx.esc(d.errors.join("\n") || d.note)}</div>${d.segments
          .flatMap((s) =>
            s.tasks
              ? s.tasks.map((t, i) => ({ ...t, index: s.index, task_index: i }))
              : s,
          )
          .map(
            (s) =>
              `<details><summary>P${s.index + 1}${s.task_index !== undefined ? " · 内部任务" + (s.task_index + 1) : ""} · 渲染${s.raw}帧 / 交付${s.deliver}帧 ${s.errors.length ? "· 有错误" : ""}</summary><p>已保存版本预检 · 本次真正提交以后，请在运行记录查看固定快照。</p>${inputTable(s.compiled?.input_inventory)}<pre>${ctx.esc(s.prompt)}</pre>${s.compiled ? `<p>实际模型：${ctx.esc(s.compiled.workflow["1"].inputs.unet_name)} · ${Object.keys(s.compiled.workflow).length}节点</p><details><summary>节点绑定、素材与补丁</summary><pre>${ctx.esc(JSON.stringify({ bindings: s.compiled.bindings, assets: s.compiled.asset_map, patches: s.compiled.patches }, null, 2))}</pre></details><button data-wf="${s.index}" data-task="${s.task_index ?? ""}">下载执行图</button>` : ""}</details>`,
          )
          .join(
            "",
          )}<button id="close-preflight" class="primary">返回工作台</button>`,
      );
      ctx.$("#close-preflight").onclick = () => modalEl.close();
      document
        .querySelectorAll("[data-wf]")
        .forEach(
          (b) =>
            (b.onclick = () =>
              ctx.download(
                (b.dataset.task !== ""
                  ? d.segments[Number(b.dataset.wf)].tasks[
                      Number(b.dataset.task)
                    ]
                  : d.segments[Number(b.dataset.wf)]
                ).compiled.workflow,
                `P${Number(b.dataset.wf) + 1}-workflow.json`,
              )),
        );
    } catch (e) {
      ctx.toast(e.message);
    } finally {
      ctx.syncDraftActions();
    }
  }
  return { preflight };
}
