import {assetVersionLink} from '../../ui/asset-origin.js';
import {workspaceActions} from '../../ui/workspace-actions.js';
import {draftStatus} from '../../ui/draft-status.js';
import {importOptions} from '../../ui/reference-assets.js';
import {workbench,propertyTabs} from '../../ui/workbench.js';
import {shotHeading,shotPrompt,shotProperties} from '../../features/prompts/authoring.js';
import {mediaPlayer} from "../../ui/media-player.js";
import { esc, fmt, field, status } from "../../ui/primitives.js";
import {
  sourcePlayer,
  sourceVideo,
  savebar,
  bindEditor,
  resultPlayer,
} from "../../features/prompts/editor-parts.js";

export const navigation = [
  ["source", "源视频与角色"],
  ["edit", "分段与替换"],
  ["review", "对照审核"],
  ["export", "成片"],
];
export const className = "mode-swap";
export function renderEdit(ctx) {
  const p = ctx.project,
    s = p.segments[ctx.shot],
    first = p.segments[0];
  const target = first
    ? ctx.localAssets(first).filter((a) => a.kind === "image")
    : [];
  const options = p.source_options || {
    segment_seconds: 124 / 24,
    detect_cuts: true,
    cut_threshold: 0.45,
  };
  const supported = ctx.catalog.swap_preparation_version >= 1;
  const preparing = p.status === "preparing";
  const hasSource = Boolean(sourceVideo(ctx));
  const state = preparing
    ? "正在准备源视频，请查看下方进度。"
    : p.source_ready
      ? `${fmt(p.duration)}秒 · 已准备 ${p.segments.length} 段`
      : hasSource
        ? "原视频已保留，当前输入尺寸或分段设置需要重新准备切片。"
        : "上传后自动处理视频、识别切镜并准备换人片段。";
  const retry =
    hasSource && supported
      ? `<button id="reprepare-source" data-auto-save data-saved-label="使用原视频重新准备" data-dirty-label="保存并重新准备">${ctx.dirty ? "保存并重新准备" : "使用原视频重新准备"}</button>`
      : "";
  const character=`<h3>目标角色</h3>${target.map(a=>`<figure class="source-character-card"><img class="source-character" src="${esc(a.url)}" alt="${esc(a.name)}"><figcaption>${esc(a.name||"角色参考图")}</figcaption>${assetVersionLink(a.library_reference)}</figure>`).join('')||'<p>一张角色参考图即可，不需要拆成多张。</p>'}${first?importOptions([`<label class="upload">${target.length?'更换角色图':'添加角色图'}<input type="file" accept="image/png,image/jpeg,image/webp" data-upload="image" data-segment="${first.id}"></label>`,ctx.catalog.asset_library_version?`<button type="button" data-library-use="${first.id}">从资产库选择</button>`:'']):'<p class="helper">先准备源视频，再添加角色参考图。</p>'}<p class="helper">整体外形与服装来自角色图；源视频提供动作、镜头和场景。</p>`;
  const slicing=`${field('单段目标渲染时长（秒）',`<input id="source-seconds" type="number" min="5.167" max="15" step="0.001" value="${Number(options.segment_seconds.toFixed(3))}">`,'默认约5.17秒，可调整至15秒。实际交付扣除重复上下文。')}${field('自动识别切镜',`<select id="source-cuts"><option value="true" ${options.detect_cuts?'selected':''}>开启：切镜处独立生成</option><option value="false" ${!options.detect_cuts?'selected':''}>关闭：按长度连续切片</option></select>`)}${field('切镜阈值',`<input id="source-threshold" type="number" min="0.05" max="0.95" step="0.05" value="${options.cut_threshold}">`,'越低越容易识别为新镜头。')}<p class="helper">单次渲染上限 ${fmt(p.settings.render_cap)}秒；按合法帧数和源镜头确定切片。</p>${retry}`;
  const sourceCanvas=`<div class="shot-heading"><h2>参考表演${hasSource?`<small class="source-file-name">${esc(sourceVideo(ctx).name||"源参考视频")}</small>`:""}</h2><span class="helper">${state}</span></div>${sourcePlayer(ctx)}${assetVersionLink(sourceVideo(ctx)?.library_reference)}<div class="source-actions">${importOptions([`<label class="upload">${hasSource?'替换源视频':'上传参考视频'}<input id="source-file" type="file" accept="video/*"></label>`,ctx.catalog.asset_library_version?'<button type="button" data-library-source>从资产库选择</button>':''])}</div>`;
  const sourceProperties=propertyTabs(ctx,[{id:'character',label:'角色',html:character},{id:'slicing',label:'分段',html:slicing},{id:'policy',label:'提示词',html:ctx.swapPromptProject()},{id:'project',label:'项目',html:field('项目名称',`<input id="project-name" maxlength="120" value="${esc(p.name)}">`)}]);
  const sourcePage=workbench({kind:'source-desk',canvas:sourceCanvas,inspector:sourceProperties})+workspaceActions({support:`<span id="save-state" role="status">${draftStatus(ctx)}</span><button id="save" class="quiet">保存草稿</button>`,actions:`<button id="open-segments" class="primary" ${preparing||!hasSource?'disabled':''} title="${preparing?'正在准备源视频':!hasSource?'请先添加参考视频':''}">${p.source_ready?'查看分段与替换 →':'准备并继续 →'}</button>`});
  const rail=`<h3>源视频分段</h3><div class="shot-nav">${p.segments.map((segment,i)=>`<button data-focus-shot="${i}" class="${i===ctx.shot?'active':''}"><strong>P${String(i+1).padStart(2,'0')}</strong><span>${fmt(segment.start/24)}–${fmt((segment.start+segment.deliver)/24)}s</span>${status(segment.status)}</button>`).join('')}</div><button id="drafts" class="quiet">找回分段草稿</button>`;
  const canvas=s?shotHeading(ctx,s)+`<div class="swap-directing"><section class="source-stage"><span class="eyebrow">本段原表演</span>${mediaPlayer(s.source_preview_url,'编排对应源视频片段',s.source_preview_note)}</section><section class="swap-script">${shotPrompt(ctx,s)}</section></div>`:'<p>请先准备源视频。</p>';
  const editPage=`${!p.source_ready?`<div class="notice">${state}${retry}</div>`:''}${workbench({kind:'swap-desk',rail,canvas,inspector:s?shotProperties(ctx,s):''})}<div id="duration-preview" role="status"></div>${savebar(ctx)}`;
  ctx.view.innerHTML =
    `<div id="source-progress">${ctx.sourceProgressCard()}</div>` +
    (ctx.tab === "source" ? sourcePage : editPage);
  bindEditor(ctx);
  ctx.bindSwapPrompts();
  const bind = (id, fn) => {
    const el = ctx.root.querySelector(id);
    if (el) el.onclick = fn;
  };
  bind("#open-segments", () => ctx.switchTab("edit"));
  bind("#back-source", () => ctx.switchTab("source"));
  bind("#reprepare-source", async () => {
    if (
      p.source_ready &&
      !(await ctx.confirm(
        "重新准备当前源视频？",
        "将创建新的切片版本。当前生成结果保留在历史版本中，新的片段需重新生成。",
        "重新准备",
      ))
    )
      return;
    ctx.reprepareSource();
  });
  for (const [id, key, parse] of [
    ["source-seconds", "segment_seconds", Number],
    ["source-cuts", "detect_cuts", (v) => v === "true"],
    ["source-threshold", "cut_threshold", Number],
  ]) {
    const el = ctx.root.querySelector("#" + id);
    if (el)
      el.onchange = () => {
        p.source_options = {
          ...options,
          ...p.source_options,
          [key]: parse(el.value),
        };
        ctx.setDirty();
      };
  }
}
export function reviewComparison(ctx, s) {
  return `<div class="swap-comparison"><section><span class="eyebrow">SOURCE · 原表演</span>${s.source_file ? mediaPlayer(s.source_preview_url, "对应源视频片段", s.source_preview_note) : sourcePlayer(ctx)}</section><section><span class="eyebrow">RESULT · 替换结果</span>${resultPlayer(s)}</section></div><p class="helper">请检查整体人物、服装、动作与场景；可分别播放源片段和结果进行对照。</p>`;
}
