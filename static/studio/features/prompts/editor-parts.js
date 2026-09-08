import {bindVideoPrompts} from '../prompt-library/adapters.js';
import {draftStatus} from '../../ui/draft-status.js';
import {workspaceActions} from '../../ui/workspace-actions.js';
import {bindWorkbench} from '../../ui/workbench.js';
import {mediaPlayer} from '../../ui/media-player.js';
import {bindInputInventory} from '../../ui/input-inventory.js';
import { esc, fmt, field, opts, status } from "../../ui/primitives.js";

export function projectSummary(ctx) {
  const p = ctx.project;
  return `<details class="project-properties"><summary>项目设置 <span class="muted">${fmt(p.duration)}秒计划 · ${p.segments.length}个片段</span></summary><div class="split">${field("项目名称", `<input id="project-name" maxlength="120" value="${esc(p.name)}">`)}${field("计划总时长（秒）", `<input id="project-duration" type="number" min="1" max="3600" step=".01" value="${p.duration}">`, "每15秒一个提示词框，允许实际片长有轻微差别。")}</div>${
    p.storyboard_version
      ? field(
          "时长处理",
          `<select id="timing-mode">${opts(
            [
              ["natural", "自然长度（推荐）"],
              ["exact", "补足计划时长（增加内部渲染）"],
            ],
            p.timing_mode || "natural",
          )}</select>`,
          "预计有效长度单独显示；不拉伸画面和声音。",
        )
      : '<button id="upgrade-story">升级为15秒片段</button>'
  }<button id="drafts" class="quiet">找回移出的片段内容</button></details><p id="duration-preview" class="preview-note" role="status"></p>`;
}
export function savebar(ctx) {
  return workspaceActions({support:`${ctx.project.mode==='swap'?'<button id="back-source" class="quiet">返回上一步</button>':''}<span id="save-state" role="status">${draftStatus(ctx)}</span><button id="save" class="quiet">保存草稿</button>`,actions:`<button id="preflight" data-auto-save data-saved-label="检查工作流" data-dirty-label="保存并检查">检查工作流</button><button id="review-go" class="primary">进入制作 <span aria-hidden="true">→</span></button>`});
}
export function shotNavigation(ctx, title = "片段目录") {
  return `<div class="section-caption"><span class="eyebrow">SHOT INDEX</span><h3>${title}</h3></div><div class="shot-nav">${ctx.project.segments.map((s, i) => `<button data-focus-shot="${i}" class="${i === ctx.shot ? "active" : ""}"><span>P${String(i + 1).padStart(2, "0")}</span><span>${fmt((s.requested_frames ?? s.deliver) / 24)}秒</span>${status(s.status)}</button>`).join("")}</div>`;
}
export function sourceVideo(ctx) {
  return ctx.project.asset_library.find(
    (a) => a.id === (ctx.project.source_candidate || ctx.project.source_asset),
  );
}
export function sourcePlayer(ctx) {
  const a = sourceVideo(ctx);
  return a
    ? mediaPlayer(a.url,"源参考视频")
    : `<div class="source-empty"><span class="frame-icon" aria-hidden="true">＋</span><h3>先放入一段表演</h3><p>上传参考视频后，自动准备片段与换人提示词。</p></div>`;
}
export function bindEditor(ctx) {
  bindVideoPrompts(ctx);
  bindInputInventory(ctx);
  const root = ctx.root,
    p = ctx.project;
  bindWorkbench(ctx);
  root.querySelectorAll('[data-library-use]').forEach(b=>b.onclick=()=>ctx.useLibrary(b.dataset.libraryUse||null));
  root.querySelectorAll('[data-library-source]').forEach(b=>b.onclick=()=>ctx.useLibrary(null,'source'));
  root.querySelectorAll('[data-library-save]').forEach(b=>b.onclick=()=>ctx.saveProjectMedia({kind:'asset',resultId:b.dataset.librarySave}));
  root.querySelectorAll('[data-library-update]').forEach(b=>b.onclick=()=>ctx.updateLibraryAsset(b.dataset.segment,p.asset_library.find(a=>a.id===b.dataset.libraryUpdate)));
  root.querySelectorAll("[data-field]").forEach(
    (el) =>
      (el.oninput = () => {
        const s = p.segments.find((s) => s.id === el.dataset.segment);
        if (!s) return;
        s[el.dataset.field] = el.value;
        ctx.setDirty();
        if (el.dataset.field === "boundary" && p.storyboard_version)
          ctx.schedulePreview();
      }),
  );
  root.querySelectorAll("[data-asset-mode]").forEach((el) => {
    el.onchange = () => ctx.setAssetMode(el.dataset.assetMode, el.value);
  });
  const on = (id, event, fn) => {
    const el = root.querySelector("#" + id);
    if (el) el[event] = fn;
  };
  on("project-name", "oninput", (e) => {
    p.name = e.target.value;
    ctx.setDirty();
  });
  on("project-duration", "oninput", (e) => {
    p.duration = Number(e.target.value);
    ctx.setDirty();
    ctx.schedulePreview();
  });
  on("timing-mode", "onchange", (e) => {
    p.timing_mode = e.target.value;
    ctx.setDirty();
    ctx.schedulePreview();
  });
  on("source-file", "onchange", ctx.sourceUpload);
  on("upgrade-story", "onclick", ctx.upgradeStory);
  on("drafts", "onclick", ctx.showDrafts);
  on("save", "onclick", ctx.save);
  on("preflight", "onclick", ctx.preflight);
  on("source-preflight", "onclick", ctx.preflight);
  on("review-go", "onclick", () => ctx.switchTab("review"));
  root.querySelectorAll("[data-focus-shot]").forEach(
    (b) =>
      (b.onclick = () => {
        ctx.shot = Number(b.dataset.focusShot);
        ctx.renderEdit();
      }),
  );
  root
    .querySelectorAll("[data-upload]")
    .forEach((el) => (el.onchange = () => ctx.uploadAssets(el)));
  root
    .querySelectorAll("[data-remove]")
    .forEach(
      (b) =>
        (b.onclick = () =>
          ctx.removeAsset(b.dataset.segment, b.dataset.remove)),
    );
  root
    .querySelectorAll("[data-edit-asset]")
    .forEach(
      (b) =>
        (b.onclick = () =>
          ctx.editAsset(b.dataset.segment, b.dataset.editAsset)),
    );
  root
    .querySelectorAll("[data-inherit]")
    .forEach((b) => (b.onclick = () => ctx.inheritDialog(b.dataset.inherit)));
  root.querySelectorAll("[data-bind-asset]").forEach((button) => {
    button.onclick = () =>
      ctx.bindAsset(button.dataset.segment, button.dataset.bindAsset);
  });
  root.querySelectorAll("[data-asset-filter]").forEach(
    (b) =>
      (b.onclick = () => {
        const group = b.dataset.assetFilter;
        root
          .querySelectorAll("[data-library-kind]")
          .forEach(
            (a) =>
              (a.hidden = group !== "all" && a.dataset.libraryKind !== group),
          );
        root
          .querySelectorAll("[data-asset-filter]")
          .forEach((a) => a.setAttribute("aria-pressed", String(a === b)));
      }),
  );
}
export function resultPlayer(s) {
  return s.delivery_url
    ? mediaPlayer(s.delivery_url,s.status==='needs_review'?'本段待审核结果':'本段选用结果')
    : `<div class="empty result-empty"><img src="/static/assets/empty/empty-shot.svg" alt=""><h3>画面正在等待你的故事</h3><p>生成后的选用结果会显示在这里。</p></div>`;
}
