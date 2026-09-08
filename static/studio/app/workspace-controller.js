import {promptCollectionNotice} from '../features/prompt-library/collection.js';
import {bindVideoPrompts} from '../features/prompt-library/adapters.js';
import {sourceTarget} from '../core/source-target.js';
import {showSourceNavigation} from '../ui/source-navigation.js';
import {canReplaceDraft} from '../core/async-state.js';
import {asyncFeedback} from '../ui/async-feedback.js';
import {loadResultReceipts} from '../features/asset-picker/result-import.js';
import {draftStatus} from '../ui/draft-status.js';
import {chooseAction} from '../ui/choice-dialog.js';
import {errorFeedback,bindErrorFeedback} from '../ui/error-feedback.js';
import {bindMediaPlayers} from "../ui/media-player.js";
import {fitWorkbench} from "../ui/workbench.js";
import {workspaceHeader,workspaceSteps,bindWorkspaceSteps} from "../ui/workspace-chrome.js";
import * as ui from "../ui/primitives.js";
import { api } from "../core/api-client.js";
import { ProjectSession } from "../core/project-session.js";
import { ProjectCommands } from "../core/project-commands.js";
import { exportNavigation } from "../core/export-lifecycle.js";
import { watchProject } from "../core/progress-channel.js";
import { createFeature as assets } from "../features/assets/index.js";
import { createFeature as settings } from "../features/workflow-settings/index.js";
import { createFeature as records } from "../features/production/records.js";
import { createFeature as review } from "../features/production/review.js";
import { createFeature as preflight } from "../features/production/preflight.js";
import { createFeature as exportsFeature } from "../features/export/index.js";
import { createFeature as prompts } from "../features/prompts/index.js";
import { createFeature as sourcePreparation } from "../features/source-preparation/index.js";
import { createFeature as swapPrompts } from "../features/swap-prompts/index.js";

/** Public context for composable view features. Mutable state belongs to session. */
export function mountWorkspace(root, project, catalog, definition, mode) {
  const session = new ProjectSession(project);
  session.root=root;
  const asyncStatus=asyncFeedback(root,session.controller.signal);
  session.connection=asyncStatus.connection;
  const disposePlayers = bindMediaPlayers(root);
  const resizeDesk=()=>fitWorkbench(root);
  window.addEventListener('resize',resizeDesk,{signal:session.controller.signal});
  root.addEventListener('toggle',resizeDesk,{capture:true,signal:session.controller.signal});
  document.fonts?.ready.then(()=>{if(!session.disposed)resizeDesk();});
  const followExport = exportNavigation(project);
  let position;
  try {
    position = JSON.parse(
      sessionStorage.getItem(`time-forest:position:${project.id}`),
    );
  } catch {}
  const ctx = {
    ...ui,
    api: (path, method, body) =>
      api(path, method, body, session.controller.signal,asyncStatus.transfer),
    root,
    session,
    catalog,
    tab:
      project.mode === "swap" && project.status === "preparing"
        ? "source"
        : project.status === "assembling"
          ? "export"
          : mode.navigation.some(([key]) => key === position?.tab)
            ? position.tab
            : mode.navigation[0][0],
    shot: Number.isInteger(position?.shot) ? position.shot : 0,
    editPage: 0,
  };
  for (const key of [
    "project",
    "dirty",
    "working",
    "actionPending",
    "draftArchive",
    "draftCache",
    "previewTimer",
    "previewSerial",
    "previewPending",
    "lastStatus",
  ]) {
    Object.defineProperty(ctx, key, {
      get: () => session[key],
      set: (value) => {
        session[key] = value;
        if (key === "working" || key === "actionPending") session.emit("busy");
      },
    });
  }
  Object.defineProperty(ctx, "view", {
    get: () => root.querySelector("#view"),
  });
  ctx.setDirty = () => session.markDirty();
  ctx.transferProgress=asyncStatus.transfer;
  ctx.schedulePreview = () => session.schedulePreview();
  ctx.previewNote = (message) => {
    const e =
      root.querySelector("#duration-preview") ||
      root.querySelector("#review-draft-note");
    if (e) e.textContent = message;
  };
  const decide = async plan => await chooseAction({
    title:'应用这次变化',message:plan.summary.join('\n')+'\n'+plan.segments.map(s=>`P${s.index+1} · ${ui.fmt(s.deliver/24)}秒`).join('，'),
    signal:session.controller.signal,choices:[{label:'取消',value:false},{label:'确认应用',value:true,primary:true}]
  }) === true;
  ctx.persistDraft = async () => {
    const previousDraft = session.project.saved_draft?.revision || 0;
    const saved = await session.save(decide);
    // A running project's independent draft is durable but must not start generation.
    return saved || (session.project.saved_draft?.revision || 0) > previousDraft;
  };
  const showProjectError = error => {
    const box=root.querySelector('#project-errors');
    if(box){box.innerHTML=errorFeedback(error);bindErrorFeedback(box);}
  };
  ctx.commands = new ProjectCommands(session, decide);
  ctx.save = async () => {
    try {
      const saved = await session.save(decide);
      if (saved) ui.toast("已保存，制作将使用这些参数");
      return saved;
    } catch (e) {
      showProjectError(e);
      return false;
    }
  };
  ctx.loadProject = () => session.reload().catch((e) => ui.toast(e.message));
  ctx.runAction = async (path, body) => {
    try {
      await ctx.commands.run(path, body);
    } catch (e) {
      ui.toast(e.message);
      const errors = root.querySelector("#project-errors");
      if (errors)
        showProjectError(e);
    }
  };
  ctx.switchTab = async (next) => {
    if (session.actionPending || session.working || next === ctx.tab) return;
    try {
      await ctx.commands.perform(async () => {
        if (
          (["review", "export"].includes(next) ||
            (ctx.project.mode === "swap" && next === "edit")) &&
          !(await ctx.commands.ensureSaved())
        )
          return;
        if (
          ctx.project.mode === "swap" &&
          ["edit", "review"].includes(next) &&
          !(await ctx.ensureSourcePrepared())
        )
          return;
        ctx.tab = next;
        ctx.renderProject();
      });
    } catch (e) {
      ui.toast(e.message);
    }
  };
  ctx.syncDraftActions = () => {
    if (session.disposed) return;
    root.querySelectorAll("[data-auto-save]").forEach((b) => {
      b.disabled =
        session.actionPending || session.working || Boolean(ctx.project.busy);
      if (
        ctx.project.mode === "swap" &&
        !ctx.project.source_ready &&
        ["run-all", "run-one"].includes(b.id)
      )
        b.disabled = true;
      b.textContent =
        b.dataset[ctx.dirty ? "dirtyLabel" : "savedLabel"] || b.textContent;
    });
    root
      .querySelectorAll(
        "#approve,#accept-only,#reroll,#recover,#resume-story,[data-select-attempt]",
      )
      .forEach((button) => {
        button.disabled =
          session.actionPending || session.working || Boolean(ctx.project.busy) || (button.hasAttribute("data-select-attempt") && button.textContent==="已选用");
      });
    root
      .querySelectorAll(
        "[data-tab],#review-go,#settings,#save,#save-review,#discard-review,input,textarea,select,[data-upload],.upload,[data-copy-swap],[data-swap-preview]",
      )
      .forEach((b) => {
        if ("disabled" in b)
          b.disabled =
            session.working ||
            session.actionPending ||
            (ctx.project.mode === "swap" &&
              ctx.project.status === "preparing" &&
              !b.hasAttribute("data-tab"));
        if (b.classList.contains("upload"))
          b.classList.toggle(
            "disabled",
            session.working || session.actionPending,
          );
      });
    root.querySelectorAll('[data-field="seed"]').forEach(el=>{
      const segment=ctx.project.segments.find(s=>s.id===el.dataset.segment);
      el.disabled=session.working||session.actionPending||segment?.seed_mode==='random';
    });
    const state = root.querySelector("#save-state");
    const sourceNext = root.querySelector("#open-segments");
    if (sourceNext)
      sourceNext.disabled =
        session.working ||
        session.actionPending ||
        ctx.project.status === "preparing" ||
        !(ctx.project.source_candidate || ctx.project.source_asset);
    if (state)
      state.textContent = draftStatus({dirty:ctx.dirty,working:session.working||session.actionPending});
  };
  for (const factory of [
    assets,
    settings,
    records,
    review,
    preflight,
    exportsFeature,
    prompts,
    sourcePreparation,
    swapPrompts,
  ])
    Object.assign(ctx, factory(ctx));
  ctx.commands.beforeGenerate = ctx.ensureSourcePrepared;
  ctx.reviewComparison = (s) => mode.reviewComparison(ctx, s);
  ctx.renderEdit = () => {
    if (session.disposed) return;
    mode.renderEdit(ctx);
    bindVideoPrompts(ctx);
    ctx.syncDraftActions();
  };
  ctx.renderProject = () => {
    if (session.disposed) return;
    const p = ctx.project;
    ctx.shot = Math.min(ctx.shot, Math.max(0, p.segments.length - 1));
    const recipe = catalog.recipes.find((r) => r.id === p.settings.recipe);
    root.className = "page project-page " + mode.className;
    root.innerHTML = `${workspaceHeader({name:p.name,code:definition.code,modeName:definition.name,state:p.status,summary:`${ui.fmt(p.duration)}秒计划 · ${p.segments.length}个片段 · 预计${ui.fmt(p.segments.reduce((n,s)=>n+s.deliver,0)/24)}秒`,settings:{workflow:recipe?.name||p.settings.recipe}})}${workspaceSteps({items:mode.navigation,current:ctx.tab,label:definition.name+'工作步骤'})}<div id="project-errors">${p.error ? errorFeedback(p.error) : ""}</div><div id="view"></div>`;
    root
      .querySelectorAll("[data-tab]")
      .forEach((b) => (b.onclick = () => ctx.switchTab(b.dataset.tab)));
    bindWorkspaceSteps(root);
    bindErrorFeedback(root);
    root.querySelector("#settings").onclick = ctx.openSettings;
    if (p.draft_storage_version && (p.busy || p.saved_draft)) {
      const banner = document.createElement("section");
      banner.className = "notice workspace-draft-note";
      banner.innerHTML = `<p>${p.busy ? "当前任务使用已固定的运行快照；可以编辑并单独保存下一次使用的草稿。" : "有一份单独保存的编排草稿，可载入当前页面核对后应用。"}</p><div class="row"><button id="save-separate-draft">保存独立草稿</button>${p.saved_draft ? `<button id="restore-separate-draft" ${p.busy ? "disabled" : ""}>载入草稿到编排</button><button id="discard-separate-draft">移除这份草稿</button>` : ""}</div>`;
      root.querySelector("#view").before(banner);
      banner.querySelector("#save-separate-draft").onclick = () => ctx.commands.perform(async () => {
        try {
          const saved = await ctx.api(`/projects/${p.id}/draft`, "POST", {
            revision: p.saved_draft?.revision || 0,
            body: structuredClone(p),
          });
          if(session.disposed)return;
          p.saved_draft = saved;
          ctx.renderProject();
          ui.toast("已单独保存草稿，不改变当前运行");
        } catch (error) {
          if(!session.disposed)showProjectError(error);
        }
      });
      const restore = banner.querySelector("#restore-separate-draft");
      if (restore)
        restore.onclick = () => {
          const draft = p.saved_draft.body;
          for (const key of [
            "name",
            "duration",
            "review",
            "settings",
            "storyboard_version",
            "timing_mode",
            "source_options",
            "swap_prompt",
          ])
            if (key in draft) p[key] = structuredClone(draft[key]);
          for (const segment of p.segments) {
            const saved = draft.segments.find((s) => s.id === segment.id);
            if (saved) Object.assign(segment, structuredClone(saved));
          }
          ctx.setDirty();
          ctx.renderProject();
          ui.toast("已载入到页面草稿，进入制作时再确认应用");
        };
      const discard = banner.querySelector("#discard-separate-draft");
      if (discard)
        discard.onclick = async () => {
          if (
            !(await ui.confirm(
              "移除独立草稿？",
              "仅移除此份待应用草稿；当前项目和运行记录保留。",
            ))
          )
            return;
          try {
            await ctx.api(`/projects/${p.id}/draft/discard`, "POST", {
              revision: p.saved_draft.revision,
            });
            p.saved_draft = null;
            ctx.renderProject();
          } catch (error) {
            ui.toast(error.message);
          }
        };
    }
    if (mode.renderPage) mode.renderPage(ctx);
    else if (ctx.tab === "review") ctx.renderReview();
    else if (ctx.tab === "export") void ctx.renderExport();
    else ctx.renderEdit();
    bindVideoPrompts(ctx);
    ctx.syncDraftActions();
    asyncStatus.render();
    void loadResultReceipts(ctx);
    showSourceNavigation(root,ctx.sourceLocation);
    promptCollectionNotice(root,session);
  };
  function preserveRender() {
    const scrolls=['.desk-rail','.desk-canvas','.review-media',...Array.from(root.querySelectorAll('.property-panel'),el=>'#'+el.id)]
      .map(selector=>{const el=root.querySelector(selector);return [selector,el?.scrollTop||0,el?.scrollLeft||0];});
    const media = [...root.querySelectorAll("video[src],audio[src]")];
    const positions = new Map(media.map((el) => [el, el.getAttribute("src")]));
    const active = document.activeElement;
    const key = active?.id;
    const sid = active?.dataset.segment;
    const field = active?.dataset.field;
    const selection = active?.selectionStart;
    const selectionEnd = active?.selectionEnd;
    const x = window.scrollX,
      y = window.scrollY;
    const opened = [...root.querySelectorAll("details")]
      .map((el, i) => (el.open ? i : -1))
      .filter((i) => i >= 0);
    ctx.renderProject();
    const fresh = [...root.querySelectorAll("video[src],audio[src]")];
    for (const [old, src] of positions) {
      const index = fresh.findIndex(
        (el) => el.tagName === old.tagName && el.getAttribute("src") === src,
      );
      if (index >= 0) {
        fresh[index].replaceWith(old);
        fresh.splice(index, 1);
      }
    }
    const details = root.querySelectorAll("details");
    disposePlayers.refresh();
    for(const [selector,top,left] of scrolls){const el=root.querySelector(selector);if(el){el.scrollTop=top;el.scrollLeft=left;}}
    opened.forEach((i) => {
      if (details[i]) details[i].open = true;
    });
    const target = key
      ? document.getElementById(key)
      : sid && field
        ? root.querySelector(
            `[data-segment="${CSS.escape(sid)}"][data-field="${CSS.escape(field)}"]`,
          )
        : null;
    target?.focus({ preventScroll: true });
    if (target?.setSelectionRange && selection !== null)
      try {
        target.setSelectionRange(selection, selectionEnd);
      } catch {}
    window.scrollTo(x, y);
  }
  session.subscribe((type, detail) => {
    if (ctx.observeSource(type)) return;
    if (
      type === "export-started" ||
      (["replace", "server"].includes(type) && followExport(ctx.project))
    ) {
      ctx.tab = "export";
      ctx.renderProject();
      root.querySelector(".steps")?.scrollIntoView({ block: "start" });
    } else if (["replace", "server", "preview"].includes(type))
      preserveRender();
    else if (type === "progress") {
      ctx.updateProgress();
      ctx.updateSourceProgress();
      ctx.syncDraftActions();
    } else if (type === "notice") ctx.previewNote(detail);
    else if (type === "error") {
      ctx.previewNote(detail.message);
      ui.toast(detail.message);
    } else ctx.syncDraftActions();
  });
  ctx.sourceLocation=sourceTarget(project);
  if(ctx.sourceLocation?.state==='found'){ctx.tab=ctx.sourceLocation.tab;ctx.shot=ctx.sourceLocation.shot??ctx.shot;ctx.sourceRun=ctx.sourceLocation.run;ctx.inspectorTab='runs';}
  const modeCleanup = mode.mount?.(ctx);
  ctx.renderProject();
  const stop = watchProject(session, ui.updateClocks);
  return {
    session,
    saveBeforeLeave: () => ctx.persistDraft(),
    ctx,
    dispose() {
      try {
        sessionStorage.setItem(
          `time-forest:position:${project.id}`,
          JSON.stringify({ tab: ctx.tab, shot: ctx.shot }),
        );
      } catch {}
      stop();
      disposePlayers();
      modeCleanup?.();
      mode.dispose?.(ctx);
      session.dispose();
    },
  };
}
