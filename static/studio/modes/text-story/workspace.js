import {workbench} from '../../ui/workbench.js';
import {shotHeading,shotPrompt,shotProperties} from '../../features/prompts/authoring.js';
import { esc, field, opts } from "../../ui/primitives.js";
import {
  projectSummary,
  savebar,
  shotNavigation,
  bindEditor,
  resultPlayer,
} from "../../features/prompts/editor-parts.js";

export const navigation = [
  ["edit", "剧本与镜头"],
  ["review", "画面与剧本审核"],
  ["export", "成片"],
];
export const className = "mode-text-story";
export function renderEdit(ctx) {
  // Start with writing space; subsequent toggles remain owned by the workbench.
  if(ctx.inspectorHidden===undefined)ctx.inspectorHidden=true;
  const s=ctx.project.segments[ctx.shot];
  ctx.view.innerHTML=projectSummary(ctx)+workbench({kind:'text-desk',rail:shotNavigation(ctx,'镜头目录'),canvas:s?shotHeading(ctx,s)+shotPrompt(ctx,s):'<p>先设置视频时长。</p>',inspector:s?shotProperties(ctx,s):''})+savebar(ctx);
  bindEditor(ctx);
}
export function reviewComparison(ctx, s) {
  return `<div class="script-review"><div class="screen">${resultPlayer(s)}</div><aside class="script-review-copy"><span class="eyebrow">THE SCRIPT</span><h3>P${String(s.index+1).padStart(2,'0')} 当前片段正文</h3><p class="helper">当前编排原文；实际提交正文可在运行记录中查看。</p><div class="script-prose" tabindex="0" aria-label="P${s.index+1}当前片段正文">${esc(s.prompt || "尚未填写提示词")}</div>${s.voice ? `<p><b>声线</b> ${esc(s.voice)}</p>` : ""}${s.ending ? `<p><b>结束状态</b> ${esc(s.ending)}</p>` : ""}</aside></div>`;
}
