/** View feature; receives a project-scoped public workspace context. */
export function createFeature(ctx) {
  async function upgradeStory() {
    if (
      !(await ctx.confirm(
        "预览升级片段编排",
        "按每15秒一个片段重新组织，原有内容按序保留，不自动合并提示词。超出的内容移入草稿；保存前仍可取消。",
        "预览升级",
      ))
    )
      return;
    ctx.project.storyboard_version = 1;
    ctx.setDirty();
    ctx.schedulePreview();
  }
  function showDrafts() {
    const all = [
      ...ctx.draftArchive,
      ...(ctx.project.removed_drafts || []),
      ...(ctx.project.previous_layouts || []).flat(),
    ];
    const d = ctx.modal(
      `<h2>保留的片段草稿</h2><p>可将内容恢复到当前片段；不会删除原生成文件。</p>${all.map((s, i) => `<details><summary>原P${s.index + 1} · ${ctx.fmt(s.deliver / 24)}秒</summary><pre>${ctx.esc(s.prompt)}</pre><label>恢复到<select id="restore-target-${i}">${ctx.project.segments.map((t, j) => `<option value="${j}">P${j + 1}</option>`).join("")}</select></label><button data-restore="${i}">恢复提示词与素材</button></details>`).join("") || "<p>没有移出的内容。</p>"}<button id="close-drafts">返回</button>`,
    );
    ctx.$("#close-drafts").onclick = () => d.close();
    document.querySelectorAll("[data-restore]").forEach(
      (b) =>
        (b.onclick = () => {
          const i = Number(b.dataset.restore),
            target =
              ctx.project.segments[Number(ctx.$("#restore-target-" + i).value)],
            src = all[i];
          ctx.draftArchive.push(structuredClone(target));
          for (const k of [
            "prompt",
            "prompt_mode",
            "voice",
  "speaker_order",
            "staging",
            "beats",
            "soundscape",
            "music",
            "ending",
            "assets",
            "inherit_ids",
            "asset_mode",
            "swap_prompt_mode",
            "swap_custom_prompt",
          ])
            target[k] = structuredClone(
              src[k] ??
                (k === "swap_prompt_mode"
                  ? "inherit"
                  : k === "asset_mode"
                    ? "auto"
                    : k === "assets" || k === "inherit_ids"
                      ? []
                      : ""),
            );
          ctx.setDirty();
          d.close();
          ctx.renderProject();
        }),
    );
  }
  return { upgradeStory, showDrafts };
}
