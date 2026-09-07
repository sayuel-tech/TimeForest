/** View feature; receives a project-scoped public workspace context. */
export function createFeature(ctx) {
  let deleted = false, loadId = 0, legacyLoadId = 0;
  async function changeArchive(p, legacy, button) {
    const restore = deleted;
    if (!restore && !(await ctx.confirm(
      `删除「${p.name}」？`,
      "项目将从档案和最近制作中移入已删除，可随时恢复。素材、生成结果与资产库内容均保留；此操作不释放磁盘空间。",
      "删除项目",
    ))) return;
    if (!ctx.isCurrent()) return;
    button.disabled = true;
    try {
      await ctx.api(`/${legacy ? "legacy" : "projects"}/${p.id}/trash`, "POST", { revision: p.revision, restore });
      if (!ctx.isCurrent()) return;
      ctx.toast(restore ? "项目已恢复" : "项目已移入已删除");
      await refresh();
    } catch (e) {
      if (ctx.isCurrent()) { ctx.toast(e.message); button.disabled = false; }
    }
  }
  async function archive() {
    deleted = false;
    ctx.$("#app").innerHTML =
      `<span class="eyebrow">PRODUCTION ARCHIVE</span><h1>项目档案</h1><div class="filter archive-filter"><input id="search" aria-label="搜索项目" placeholder="搜索项目名称"><select id="filter-mode" aria-label="按模式筛选">${ctx.opts([["", "全部模式"], ...Object.entries(ctx.MODES).map(([k, m]) => [k, m.name])], "")}</select><select id="archive-state" aria-label="档案范围"><option value="active">全部项目</option><option value="deleted">已删除</option></select></div><p id="archive-note" class="muted"></p><div id="archive-items"></div><section class="section"><div class="section-head"><h2>旧版记录</h2><span class="muted">保留原素材与制作结果</span></div><div id="legacy-items"></div><div id="legacy-pages" class="row"></div></section>`;
    ctx.$("#archive-state").onchange = () => {
      deleted = ctx.$("#archive-state").value === "deleted";
      refresh();
    };
    await refresh();
  }
  async function refresh() {
    const epoch = ++loadId;
    ctx.$("#search").oninput = null;
    ctx.$("#filter-mode").onchange = null;
    ctx.$("#archive-note").textContent = deleted ? "已删除项目仍保留本地文件，恢复后可继续制作。" : "废弃项目可删除，之后在已删除列表中恢复。";
    ctx.$("#archive-items").textContent = "读取中…";
    const oldRecords = legacyList(1);
    try {
      const d = await ctx.api("/projects?trash=" + (deleted ? "1" : "0"));
      if (!ctx.isCurrent() || epoch !== loadId) return;
      const draw = () => {
        const q = ctx.$("#search").value.toLowerCase(), mode = ctx.$("#filter-mode").value;
        const ps = d.projects.filter(p => p.name.toLowerCase().includes(q) && (!mode || p.mode === mode));
        ctx.$("#archive-items").innerHTML = ps.length ? `<div class="grid3">${ps.map(p => {
          const busy = p.busy || ["generating", "preparing", "assembling"].includes(p.status);
          const card = deleted ? ctx.projectCard(p).replace(/^<a [^>]*>/, '<article class="project-card">').replace(/<\/a>$/, '</article>') : ctx.projectCard(p);
          return `<div class="archive-project-entry">${card}<div class="archive-project-actions"><span class="muted">${busy ? "任务处理中" : deleted ? "可恢复" : ""}</span><button class="quiet" data-project-trash="${p.id}" aria-label="${deleted ? "恢复" : "删除"}项目：${ctx.esc(p.name)}" ${busy ? "disabled" : ""}>${deleted ? "恢复项目" : "删除项目"}</button></div></div>`;
        }).join("")}</div>` : `<div class="panel empty">${deleted ? "没有已删除的项目" : "没有匹配的项目"}</div>`;
        document.querySelectorAll("[data-project-trash]").forEach(b => b.onclick = () => changeArchive(ps.find(p => p.id === b.dataset.projectTrash), false, b));
      };
      ctx.$("#search").oninput = draw;
      ctx.$("#filter-mode").onchange = draw;
      draw();
    } catch(e) { if (ctx.isCurrent() && epoch === loadId) ctx.$("#archive-items").textContent = e.message; }
    await oldRecords;
  }
  async function legacyList(page) {
    const epoch = ++legacyLoadId;
    ctx.$("#legacy-items").textContent = "读取中…";
    ctx.$("#legacy-pages").innerHTML = "";
    try {
      let d = await ctx.api("/legacy?page=" + page + "&trash=" + (deleted ? "1" : "0"));
      if (!ctx.isCurrent() || epoch !== legacyLoadId) return;
      if (page > d.pages) return legacyList(d.pages);
      ctx.$("#legacy-items").innerHTML =
        `<div class="grid3">${d.projects.map((p) => `<article class="project-card">${p.reference_url ? `<img class="project-cover" src="${ctx.esc(p.reference_url)}" alt="${ctx.esc(p.name)}参考图">` : ""}<div class="card-body"><span class="eyebrow">LEGACY</span><h3>${ctx.esc(p.name)}</h3><small>${ctx.fmt(p.duration_seconds)}秒 · ${p.segment_count}段</small><div class="row">${deleted ? "" : `<button class="quiet" data-legacy="${p.id}">查看结果</button><button class="quiet" data-migrate="${p.id}">建立v5副本</button>`}<button class="quiet" data-legacy-trash="${p.id}" aria-label="${deleted ? "恢复" : "删除"}旧项目：${ctx.esc(p.name)}">${deleted ? "恢复项目" : "删除项目"}</button></div></div></article>`).join("")}</div>`;
      if (!d.projects.length) ctx.$("#legacy-items").innerHTML = '<p class="muted">暂无旧版记录</p>';
      document.querySelectorAll("[data-legacy-trash]").forEach(b => b.onclick = () => changeArchive(d.projects.find(p => p.id === b.dataset.legacyTrash), true, b));
      ctx.$("#legacy-pages").innerHTML =
        d.pages > 1
          ? `<button id="legacy-prev" ${page <= 1 ? "disabled" : ""}>上一页</button><span>${page}/${d.pages}</span><button id="legacy-next" ${page >= d.pages ? "disabled" : ""}>下一页</button>`
          : "";
      if (ctx.$("#legacy-prev")) {
        ctx.$("#legacy-prev").onclick = () => legacyList(page - 1);
        ctx.$("#legacy-next").onclick = () => legacyList(page + 1);
      }
      document
        .querySelectorAll("[data-legacy]")
        .forEach((b) => (b.onclick = () => showLegacy(b.dataset.legacy)));
      document.querySelectorAll("[data-migrate]").forEach(
        (b) =>
          (b.onclick = async () => {
            if (
              !(await ctx.confirm(
                "建立新版制作副本",
                "复用原素材，原结果不覆盖；新版片段需要重新检查正文和参数。",
                "建立副本",
              ))
            )
              return;
            try {
              b.disabled = true;
              const p = await ctx.api(
                "/legacy/" + b.dataset.migrate + "/migrate",
                "POST",
                {},
              );
              ctx.tab = "edit";
              ctx.go("/p/" + p.id);
            } catch (e) {
              ctx.toast(e.message);
              b.disabled = false;
            }
          }),
      );
    } catch (e) {
      if (ctx.isCurrent() && epoch === legacyLoadId && ctx.$("#legacy-items"))
        ctx.$("#legacy-items").textContent = e.message;
    }
  }
  async function showLegacy(id) {
    let p;
    try {
      p = await ctx.readLegacyProject(id);
    } catch (e) {
      if (ctx.isCurrent()) ctx.toast(e.message);
      return;
    }
    if (!ctx.isCurrent()) return;
    const videos = [
      p.final_url,
      ...p.segments.map((s) => s.delivery_with_audio_url || s.delivery_url),
    ].filter(Boolean);
    const d = ctx.modal(
      `<h2>${ctx.esc(p.name)}</h2><p>旧项目只读查看</p>${videos.map((url) => `<video controls preload="metadata" src="${ctx.esc(url)}"></video>`).join("") || "<p>没有已交付视频。</p>"}<button id="close-legacy">关闭</button>`,
    );
    ctx.$("#close-legacy").onclick = () => d.close();
  }
  return { archive, legacyList, showLegacy };
}
