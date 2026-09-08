import { esc, toast } from "../../ui/primitives.js";
import { openProductionSettings, productionSettingsActions, productionGroups as groups, productionSettingsMarkup, bindSettingsNavigation, parameterField, parameterLoras, validateSettingsInputs } from "../../ui/production-settings.js";
import {
  visibleParameters,
  choicesFor,
  geometryPreview,
} from "../../core/capability-client.js";

/** Availability and ranges come from the backend; this module owns presentation. */
export function createFeature(ctx) {
  function openSettings() {
    const original = structuredClone(ctx.project.settings);
    let candidate = structuredClone(original);
    let selectedGroup="core";
    const surface = openProductionSettings({signal:ctx.session.controller?.signal});
    const {dialog, content} = surface;
    const recipe = () =>
      ctx.catalog.recipes.find((r) => r.id === candidate.recipe);
    function input(f) {
      const k = f.key,
        c = choicesFor(f, candidate, ctx.project, ctx.catalog);
      return parameterField(f, candidate[k], {attributes: `data-param="${k}"`, options: c});
    }
    function syncSummary() {
      const r = recipe(),
        g = geometryPreview(candidate, r),
        split = r.capabilities.sampler_structure === "split_schedule";
      const active = candidate.loras.filter(
        (l) => !l.bypass && Number(l.strength) !== 0,
      );
      const accelerated =
        r.official &&
        candidate.acceleration &&
        Number(candidate.accel_strength) !== 0;
      const effectiveSteps = accelerated
        ? r.id === "official_text"
          ? 8
          : 4
        : candidate.steps;
      if (split)
        candidate.refine_steps =
          Number(candidate.steps) - Number(candidate.split_step);
      content.querySelector("#geometry-preview").textContent =
        `一采 ${g.w}×${g.h}${r.two_pass ? ` → 二采 ${g.ow}×${g.oh}` : ""} · 导出 ${candidate.export_fps}fps · ${candidate.audio_policy === "source" ? "源视频原声" : "H3生成声音"}`;
      content.querySelector("#sampling-preview").textContent = split
        ? `总${candidate.steps}步＝一采${candidate.split_step}步＋二采${candidate.refine_steps}步。共用${candidate.scheduler}日程，整条降噪1.0，最终画面与声音取二采。`
        : `${r.two_pass ? "完整一采与独立二采" : "单次采样"}；原生24fps。${accelerated ? `加速LoRA已启用，实际一采${effectiveSteps}步；关闭加速后使用基础步数。` : `实际一采${effectiveSteps}步。`}`;
      const steps = content.querySelector('[data-param="steps"]');
      if (steps) {
        steps.disabled = Boolean(accelerated);
        steps.title = accelerated
          ? "由当前工作流的加速设置固定；关闭加速后可修改基础步数"
          : "基础采样步数";
      }
      const lora = content.querySelector("#lora-state");
      if (lora)
        lora.textContent = `实际启用 ${active.length} 个LoRA · Bypass或强度0均不加载。`;
      const model = content.querySelector('[data-param="model"]');
      if (model) model.title = candidate.model;
    }
    function draw() {
      const r = recipe();
      if (!r?.parameters || !r.capabilities) {
        content.innerHTML =
          '<h2>需要更新服务端</h2><p>当前后台未提供参数能力契约，请完成服务更新后再调整。</p><button id="close-settings">关闭</button>';
        content.querySelector("#close-settings").onclick = () => dialog.close();
        return;
      }
      const fields = visibleParameters(r, candidate);
      const sections = Object.entries(groups).map(([group, title]) => {
        const fs = fields.filter((f) => f.group === group),
          loras = group === "lora" && r.capabilities.lora_slots;
        if (!fs.length && !loras) return null;
        const html = `<div class="settings-grid">${fs.map(input).join("")}</div>${loras ? `<p id="lora-state" class="helper"></p>${parameterLoras(candidate.loras,ctx.catalog.loras,{step:.05})}` : ""}`;
        return {key:group, title, html};
      }).filter(Boolean);
      content.innerHTML = productionSettingsMarkup({
        scope: `当前项目草稿 · ${r.name}`,
        directory: `<details class="engine-directory"><summary>本地模型目录</summary><p>刷新页面或点击下方按钮会重新扫描本地模型目录，无需启动ComfyUI。你的文件选择会原样提交；不兼容时显示ComfyUI返回的错误。${ctx.catalog.local_models?.updated ? ` 上次扫描：${new Date(ctx.catalog.local_models.updated * 1000).toLocaleString()}` : ""}</p>${(ctx.catalog.local_models?.errors || []).map(e => `<p class="notice error">${esc(e)}</p>`).join("")}<button id="connect-engine" type="button">刷新本地模型列表</button></details>`,
        summary: `<div class="settings-summary"><strong id="geometry-preview"></strong><p id="sampling-preview"></p><details><summary>工作流说明与适用范围</summary><p>${esc(r.description)}</p><p>${esc(r.capabilities.verification)}</p></details></div>`,
        sections,
        actions: productionSettingsActions([{role:"reset",id:"reset-settings",label:"恢复默认"},{role:"cancel",id:"cancel-settings",label:"取消"},{role:"apply",id:"apply-settings",label:"应用"},{role:"save",id:"save-settings",label:"保存",primary:true}]),
        footer: '应用到当前项目草稿；保存会持久化当前项目的全部草稿。涉及已有结果的变化仍需确认。恢复默认仅改变本弹窗，取消可放弃。',
      });
      bindSettingsNavigation(content, selectedGroup, key => { selectedGroup = key; });
      const connect = content.querySelector("#connect-engine");
      if (connect)
        connect.onclick = () => surface.run(async () => {
          const next = await ctx.api("/catalog");
          if (!surface.alive() || ctx.session.disposed) return false;
          Object.assign(ctx.catalog, next);draw();
        });
      content.querySelectorAll("[data-param]").forEach(
        (el) =>
          (el.onchange = () => {
            const key = el.dataset.param;
            if (key === "recipe") {
              const next = ctx.catalog.recipes.find((r) => r.id === el.value);
              candidate = structuredClone(next.defaults);
              draw();
              return;
            }
            candidate[key] =
              el.type === "checkbox"
                ? el.checked
                : el.type === "number"
                  ? Number(el.value)
                  : el.value;
            if (["size_mode", "low_vram", "acceleration"].includes(key)) draw();
            else syncSummary();
          }),
      );
      content.querySelectorAll("[data-lora]").forEach(
        (el) =>
          (el.onchange = () => {
            candidate.loras[Number(el.dataset.lora)][el.dataset.key] =
              el.type === "checkbox"
                ? el.checked
                : el.type === "number"
                  ? Number(el.value)
                  : el.value;
            syncSummary();
          }),
      );
      content.querySelector("#cancel-settings").onclick = surface.cancel;
      content.querySelector("#reset-settings").onclick = () => {
        candidate = structuredClone(r.defaults);
        draw();
      };
      const validate = () => {
        validateSettingsInputs(content);
        if (r.capabilities.sampler_structure === "split_schedule" && !(Number(candidate.split_step)>=1 && Number(candidate.split_step)<Number(candidate.steps)))
          throw Object.assign(new Error("一采切点必须小于总步数，两采均至少保留1步"),{kind:'input'});
      };
      const commit = saveNow => surface.run(async () => {
        ctx.project.settings = structuredClone(candidate);
        ctx.setDirty();
        if (ctx.project.storyboard_version && candidate.render_cap !== original.render_cap) ctx.schedulePreview();
        if (saveNow) {
          const saved = await ctx.persistDraft();
          if (!saved) return false;
          toast("草稿已保存");
        } else toast("已应用到草稿，尚未保存");
        ctx.renderProject();
        return true;
      }, {closeOnSuccess:true, validate});
      content.querySelector("#apply-settings").onclick = () => commit(false);
      content.querySelector("#save-settings").onclick = () => commit(true);
      syncSummary();
    }
    draw();
  }
  return { openSettings };
}
