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
export function renderEdit(ctx) {
  const p=ctx.project,s=p.segments[ctx.shot];
  const images=s?ctx.localAssets(s).filter(a=>a.kind==='image'):[];
  const visual=`<div class="reference-contact-sheet">${images.map(a=>`<figure><img src="${esc(a.url)}" alt="${esc(a.name)}"><figcaption>${esc(a.name)}</figcaption></figure>`).join('')||(s?.asset_mode==='none'?'<p class="helper">本段不添加参考素材，继续上一段的画面与声音。</p>':'<p class="helper">在右侧素材区加入角色、场景或色系图。</p>')}</div>`;
  ctx.view.innerHTML=projectSummary(ctx)+workbench({kind:'image-desk',rail:shotNavigation(ctx),canvas:s?shotHeading(ctx,s)+visual+shotPrompt(ctx,s):'<p>先设置视频时长。</p>',inspector:s?shotProperties(ctx,s):''})+savebar(ctx);
  bindEditor(ctx);
}
export function reviewComparison(ctx, s) {
  const references = ctx.localAssets(s).filter((a) => a.kind === "image");
  const previous = ctx.project.segments[s.index - 1];
  return `<div class="image-review"><div class="screen">${resultPlayer(s)}</div><aside class="reference-rail"><span class="eyebrow">CHARACTER & SCENE</span><h3>本段参考</h3>${references.map((a) => `<img src="${esc(a.url)}" loading="lazy" alt="${esc(a.name)}">`).join("") || (s.asset_mode === "none" && s.head ? "<p>本段不使用参考素材，承接上一段已接受的画面与声音。</p>" : "<p>本段暂无图片参考</p>")}${previous?.delivery_url ? `<details><summary>查看上一段 · 检查衔接</summary><video controls preload="none" src="${esc(previous.delivery_url)}"></video></details>` : ""}</aside></div>`;
}
