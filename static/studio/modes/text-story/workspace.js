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
  const s=ctx.project.segments[ctx.shot];
  ctx.view.innerHTML=projectSummary(ctx)+workbench({kind:'text-desk',rail:shotNavigation(ctx,'镜头目录'),canvas:s?shotHeading(ctx,s)+shotPrompt(ctx,s):'<p>先设置视频时长。</p>',inspector:s?shotProperties(ctx,s):''})+savebar(ctx);
  bindEditor(ctx);
}
export function reviewComparison(ctx, s) {
  return `<div class="script-review"><div class="screen">${resultPlayer(s)}</div><aside class="script-review-copy"><span class="eyebrow">THE SCRIPT</span><h3>这一段的剧本</h3><div class="script-prose">${esc(s.prompt || "尚未填写提示词")}</div>${s.voice ? `<p><b>声线</b> ${esc(s.voice)}</p>` : ""}${s.ending ? `<p><b>结束状态</b> ${esc(s.ending)}</p>` : ""}</aside></div>`;
}
