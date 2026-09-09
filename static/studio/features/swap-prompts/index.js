import {createPromptPreview} from "./preview.js";
export function createFeature(ctx) {
  const finalPreview=createPromptPreview(ctx);
  const latest=ctx.catalog.swap_template_version||2;
  const policy = () =>
    ctx.project.swap_prompt || { mode: "template", custom: "", version: 1 };
  const choices = [
    ["template", "通用换人提示词"],
    ["custom", "自定义完整提示词"],
  ];
  function swapPromptProject() {
    if (!ctx.catalog.swap_prompt_modes) return "";
    const p = policy();
    return `<section class="panel section"><span class="eyebrow">SWAP DIRECTION</span><h3>项目默认换人提示词</h3><p class="helper">通用模板 v${p.version || 1} · ${p.version === 3 ? "具体外观与表演分开编写；遵循H3全参考格式" : p.version === 2 ? "一个目标人物，图片与源表演职责分开" : "保留本项目原模板"}</p>${(p.version || 1) < latest ? `<button type="button" class="quiet" data-upgrade-swap-template>升级通用模板至 v${latest}（自定义正文保持不变）</button>` : ""}${ctx.field("提示词方式", `<select id="swap-project-mode">${ctx.opts(choices, p.mode)}</select>`, "各片段默认继承这里的选择，也可以单独覆盖。切换方式保留原来的文字。")}${p.mode === "custom" ? ctx.field("项目自定义完整正文", `<textarea id="swap-project-custom" rows="9" placeholder="明确使用 <Picture 1> 替换 <Video 1> 中的角色……">${ctx.esc(p.custom)}</textarea>`, "正文直接提交，不再附加通用模板。请明确Picture 1是角色图、Video 1是当前源视频片段；声音要求须与输出声音设置一致。") : `<p class="muted">自动匹配当前${ctx.project.settings.recipe === "official_swap" ? "官方Ref2VA" : "跳舞"}配方模板：替换整体外观，保留源表演、镜头与场景。每段可补充导演说明。</p>`}<button class="quiet" data-copy-swap="project">从通用模板复制并编辑</button></section>`;
  }
  function swapPromptEditor(s) {
    const choice = s.swap_prompt_mode || "inherit",
      effective = choice === "inherit" ? policy().mode : choice;
    return `<section class="section"><h3>本段换人提示词</h3>${ctx.field("本段提示词方式", `<select data-swap-mode="${s.id}" aria-label="P${s.index + 1}换人提示词方式">${ctx.opts([["inherit", "继承项目默认"], ...choices], choice)}</select>`)}<p class="helper">&lt;Picture 1&gt;：目标角色图；&lt;Video 1&gt;：本段源表演。连续声画仍由工作流上下文连接提供。</p>${effective === "template" ? ctx.field("补充导演说明（选填）", `<textarea data-field="prompt" data-segment="${s.id}" aria-label="P${s.index + 1}补充导演说明">${ctx.esc(s.prompt)}</textarea>`, "本段说明追加到通用模板中。例如强调服装来源、保留的道具或遮挡关系。") : choice === "custom" ? ctx.field("本段自定义完整正文", `<textarea data-field="swap_custom_prompt" data-segment="${s.id}" rows="10" aria-label="P${s.index + 1}自定义换人正文">${ctx.esc(s.swap_custom_prompt || "")}</textarea>`, "直接提交这段正文；不会再混入通用模板或之前的补充说明。") : `<details><summary>查看继承的项目自定义正文</summary><pre class="prompt-text">${ctx.esc(policy().custom || "尚未填写，请在项目默认提示词中填写。")}</pre></details>`}${effective === "template" && (policy().version||1)>=3 ? `<details class="swap-observations"><summary>具体角色与原表演描述（可选，推荐补充）</summary><p class="helper">通用模板无法自动看懂新素材。用实际可见的细节描述角色、源人物和动作，可比反复强调“保留原视频”更明确；建议正文用英文。这里是制作说明，不会读取资产库资料PROMPT。</p>${ctx.field('目标外观', `<textarea data-field="staging" data-segment="${s.id}" aria-label="P${s.index+1}目标外观" placeholder="发型、服装颜色与款式、配饰……">${ctx.esc(s.staging||'')}</textarea>`)}${ctx.field('原人物与本段表演', `<textarea data-field="beats" data-segment="${s.id}" aria-label="P${s.index+1}原人物与本段表演" placeholder="替换画面中的谁；动作顺序、站位和镜头变化……">${ctx.esc(s.beats||'')}</textarea>`)}<p class="helper">源片段包含硬切时，在完整自定义正文中按实际切点写[Shot 2]及时间；通用模板不会猜测切镜时间。</p></details>` : ''}<div class="row"><button class="quiet" data-copy-swap="${s.id}">从通用模板复制并编辑本段</button><button type="button" class="quiet" data-swap-preview="${s.id}" aria-expanded="false" aria-controls="final-prompt-${s.id}">查看最终提示词</button></div>${finalPreview.markup(s)}</section>`;
  }
  function bindSwapPrompts() {
    const upgrade=ctx.root.querySelector('[data-upgrade-swap-template]');
    if(upgrade)upgrade.onclick=()=>{
      ctx.project.swap_prompt={...policy(),version:latest};ctx.setDirty();ctx.renderEdit();
    };
    const mode = ctx.root.querySelector("#swap-project-mode"),
      body = ctx.root.querySelector("#swap-project-custom");
    if (mode)
      mode.onchange = () => {
        ctx.project.swap_prompt = { ...policy(), mode: mode.value };
        ctx.setDirty();
        ctx.renderEdit();
      };
    if (body)
      body.oninput = () => {
        ctx.project.swap_prompt = { ...policy(), custom: body.value };
        ctx.setDirty();
      };
    ctx.root.querySelectorAll("[data-swap-mode]").forEach((el) => {
      el.onchange = () => {
        const s = ctx.project.segments.find(
          (s) => s.id === el.dataset.swapMode,
        );
        s.swap_prompt_mode = el.value;
        ctx.setDirty();
        ctx.renderEdit();
      };
    });
    finalPreview.bind();
    ctx.root.querySelectorAll("[data-copy-swap]").forEach((el) => {
      el.onclick = async () => {
        if (
          ctx.working ||
          ctx.actionPending ||
          ctx.project.status === "preparing"
        )
          return;
        const scope = el.dataset.copySwap,
          s =
            scope === "project"
              ? null
              : ctx.project.segments.find((s) => s.id === scope);
        const old = s ? s.swap_custom_prompt : policy().custom;
        if (
          old &&
          !(await ctx.confirm(
            "替换自定义草稿？",
            "将用当前配方的通用模板替换这个自定义正文。其他片段单独写的正文不会改变。",
            "替换草稿",
          ))
        )
          return;
        ctx.working = true;
        try {
          const stamp=JSON.stringify([ctx.project.settings,ctx.project.segments]);
          const data = await ctx.api(
            `/projects/${ctx.project.id}/swap-template`,
            "POST",
            {
              index: s?.index || 0,
              scope: s ? "segment" : "project",
              settings: ctx.project.settings,
              segments: ctx.project.segments,
            },
          );
          if (ctx.session.disposed) return;
          if(stamp!==JSON.stringify([ctx.project.settings,ctx.project.segments])){ctx.toast('编排已变化，请重新复制当前模板。');return;}
          if (s) {
            s.swap_custom_prompt = data.prompt;
            s.swap_prompt_mode = "custom";
          } else
            ctx.project.swap_prompt = { mode: "custom", custom: data.prompt, version: data.template_version };
          ctx.setDirty();
          ctx.renderEdit();
        } catch (e) {
          ctx.toast(e.message);
        } finally {
          ctx.working = false;
          ctx.syncDraftActions();
        }
      };
    });
  }
  return { swapPromptProject, swapPromptEditor, bindSwapPrompts };
}
