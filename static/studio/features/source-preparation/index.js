import {updateStatusRegion} from '../../ui/status-region.js';
import {runTiming,runStatusRow} from '../../ui/run-timing.js';
import { uploadAsset } from "../../core/upload-client.js";

export function createFeature(ctx) {
  let upload = null;
  let completedId = ctx.project.source_progress?.active
    ? null
    : ctx.project.source_progress?.id;
  const supported = () => ctx.catalog.swap_preparation_version >= 1;
  function sourceProgressCard() {
    const r = upload || ctx.project.source_progress;
    if (!r?.phase) return "";
    if (!upload && !ctx.project.source_ready && r.phase === "源视频准备完成")
      return "";
    const active = r.active,
      end = active ? null : r.finished || r.updated;
    if(!active && !r.error && r.phase==='源视频准备完成')return runStatusRow(`<div class="notice" role="status"><strong>源视频已准备</strong><small>${r.total || ctx.project.segments.length}段</small></div>`,runTiming({start:r.started,end,label:'准备用时'}));
    return `<section class="panel run-progress" aria-live="polite">${runStatusRow(`<div class="notice ${r.error?'error':''}" role="status"><strong>${ctx.esc(r.phase)}</strong><small>源视频准备${r.stage ? ` · 阶段 ${r.stage}/${r.stages}` : ""}</small></div>`,runTiming({start:r.started,end,live:active,label:'准备用时'}))}${!r.error ? `<progress aria-label="源视频准备进度" ${Number.isFinite(r.percent) ? `value="${r.percent}" max="100"` : ""}></progress>` : ""}<p class="muted">${r.loaded !== undefined ? `${ctx.bytes(r.loaded)}${r.total ? ` / ${ctx.bytes(r.total)}` : ""}` : r.completed !== undefined ? `已完成 ${r.completed}/${r.total} 段` : r.processed_seconds !== undefined ? `已处理 ${ctx.fmt(r.processed_seconds)} / ${ctx.fmt(r.total_seconds)} 秒` : active ? "正在处理，计时持续更新。" : "准备状态已更新。"}${r.percent !== undefined && r.percent !== null ? ` · 当前阶段 ${Math.round(r.percent)}%` : ""}</p>${active && r.updated ? `<small>距上次上报 <span data-clock="${r.updated}">${ctx.elapsed(r.updated)}</span></small>` : ""}${r.transport_error ? `<p class="notice">${ctx.esc(r.transport_error)}</p>` : ""}${r.error ? `<p class="notice error">${ctx.esc(r.error)}。原视频和旧切片保留，可重新准备。</p>` : ""}</section>`;
  }
  function updateSourceProgress() {
    const el = ctx.root.querySelector("#source-progress");
    if (el) updateStatusRegion(el,sourceProgressCard());
  }
  function observeSource(type) {
    if (ctx.project.mode !== "swap") return false;
    if (type === "source-started") {
      ctx.tab = "source";
      ctx.renderProject();
      return true;
    }
    const r = ctx.project.source_progress;
    if (
      r?.id &&
      ctx.project.source_ready &&
      !r.active &&
      r.phase === "源视频准备完成" &&
      r.id !== completedId
    ) {
      completedId = r.id;
      if (r.continue_to === "edit") {
        ctx.tab = "edit";
        ctx.renderProject();
        ctx.toast("源视频准备完成，已进入分段与替换");
        return true;
      }
    }
    return false;
  }
  async function reprepareSource(continueTo = null) {
    try {
      await ctx.commands.prepareSource(
        ctx.project.source_candidate || ctx.project.source_asset,
        continueTo,
      );
    } catch (e) {
      ctx.toast(e.message);
    }
  }
  async function ensureSourcePrepared() {
    if (ctx.project.mode !== "swap" || ctx.project.source_ready) return true;
    if (!supported()) throw new Error("请刷新页面以加载源视频准备功能");
    const aid = ctx.project.source_candidate || ctx.project.source_asset;
    if (!aid) {
      ctx.tab = "source";
      ctx.renderProject();
      ctx.toast("请先上传源视频");
      return false;
    }
    if (ctx.project.status === "preparing" || ctx.project.busy) {
      ctx.tab = "source";
      ctx.renderProject();
      ctx.toast("正在处理，请等待源视频准备完成");
      return false;
    }
    if (
      await ctx.confirm(
        "需要重新准备源视频切片",
        "将复用已上传的原视频，按当前输入画布和分段规则准备。旧文件保留；无法按原时间范围匹配的文字移入可恢复草稿。完成后进入分段页。",
        "重新准备并继续",
      )
    )
      await ctx.commands.submitSource(aid, "edit");
    return false;
  }
  async function sourceUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    if (!supported()) {
      ctx.toast("请刷新页面后再上传");
      return;
    }
    try {
      await ctx.commands.perform(async () => {
        if (!(await ctx.commands.ensureSaved())) return;
        if (
          ctx.project.source_asset &&
          !(await ctx.confirm(
            "替换源视频？",
            "新视频会建立新的分段版本。旧结果和文字保留，角色参考图保留；分段文字不会按序号强行套到新视频。",
            "上传并准备",
          ))
        )
          return;
        upload = {
          started: Date.now() / 1000,
          updated: Date.now() / 1000,
          active: true,
          phase: "上传源视频",
          loaded: 0,
          total: file.size,
          percent: 0,
        };
        ctx.tab = "source";
        ctx.renderProject();
        const asset = await uploadAsset(
          ctx.project.id,
          file,
          (info) => {
            if (ctx.session.disposed) return;
            Object.assign(upload, info, {
              updated: Date.now() / 1000,
              percent: info.total ? (info.loaded / info.total) * 100 : null,
            });
            updateSourceProgress();
          },
          ctx.session.controller.signal,
        );
        if (ctx.session.disposed) return;
        ctx.project.asset_library.push(asset);
        ctx.project.source_candidate = asset.id;
        upload = null;
        await ctx.commands.submitSource(asset.id);
      });
    } catch (error) {
      if (upload) {
        Object.assign(upload, {
          active: false,
          finished: Date.now() / 1000,
          error: error.message,
          phase: "上传未完成",
        });
        updateSourceProgress();
      }
      if (!ctx.session.disposed) ctx.toast(error.message);
    }
  }
  return {
    sourceUpload,
    sourceProgressCard,
    updateSourceProgress,
    observeSource,
    reprepareSource,
    ensureSourcePrepared,
  };
}
