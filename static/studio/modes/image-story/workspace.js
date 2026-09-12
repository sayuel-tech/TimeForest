import {workbench} from '../../ui/workbench.js';
import {shotHeading,shotPrompt,shotProperties} from '../../features/prompts/authoring.js';
import { esc, fmt } from "../../ui/primitives.js";
import {
  projectSummary,
  savebar,
  shotNavigation,
  bindEditor,
  resultPlayer,
} from "../../features/prompts/editor-parts.js";

export const navigation = [
  ["edit", "角色与片段"],
  ["review", "制作与审核"],
  ["export", "成片"],
];
export const className = "mode-image-story";
const referenceNote = (s) => s.asset_mode === 'none'
  ? '本段不添加参考素材；声画衔接由片段关系决定。'
  : '本段暂无图片参考，可在素材区添加角色、场景或色系图。';
const referenceFigure = (a) => `<figure><img src="${esc(a.url)}" loading="lazy" alt="${esc(a.name)}"><figcaption>${esc(a.name)}</figcaption></figure>`;
export function renderEdit(ctx) {
  const p=ctx.project,s=p.segments[ctx.shot];
  const images=s?ctx.localAssets(s).filter(a=>a.kind==='image'):[];
  const visual=s?`<details class="reading-disclosure image-story-references" data-view-key="references-${esc(s.id)}"><summary>P${String(s.index+1).padStart(2,'0')} · ${esc(ctx.assetModeLabel(s))} · ${images.length}张图片参考</summary><div class="reference-contact-sheet">${images.map(referenceFigure).join('')||`<p class="helper">${referenceNote(s)}</p>`}</div></details>`:'';
  ctx.view.innerHTML=projectSummary(ctx)+workbench({kind:'image-desk',rail:shotNavigation(ctx),canvas:s?shotHeading(ctx,s)+visual+shotPrompt(ctx,s):'<p>先设置视频时长。</p>',inspector:s?shotProperties(ctx,s):''})+savebar(ctx);
  bindEditor(ctx);
}
export function reviewComparison(ctx, s) {
  const references = ctx.localAssets(s).filter((a) => a.kind === "image");
  const previous = ctx.project.segments[s.index - 1];
  return `<div class="image-review"><div class="screen">${resultPlayer(s)}</div><aside class="reference-rail"><span class="eyebrow">CHARACTER & SCENE</span><h3>P${String(s.index+1).padStart(2,'0')} 本段参考</h3><p class="helper">${esc(ctx.assetModeLabel(s))} · ${references.length}张图片</p>${references.map(referenceFigure).join('') || `<p>${referenceNote(s)}</p>`}${previous?.delivery_url ? `<details><summary>查看上一段 · 检查衔接</summary><video controls preload="none" src="${esc(previous.delivery_url)}"></video></details>` : ""}</aside></div>`;
}
