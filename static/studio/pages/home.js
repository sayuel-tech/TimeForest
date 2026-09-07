import { esc, fmt, status } from "../ui/primitives.js";
import { getMode, listModes } from "../app/mode-registry.js";
export function projectCard(p) {
  const mode = getMode(p.mode);
  return `<a class="project-card" href="#/p/${p.id}">${p.cover ? `<img class="project-cover" loading="lazy" src="${esc(p.cover)}" alt="${esc(p.name)}项目参考图">` : `<div class="project-cover text-cover"><span class="eyebrow">${mode?.code || "PROJECT"}</span><span>${esc(p.name)}</span></div>`}<div class="card-body"><div class="row between"><span class="eyebrow">${mode?.code || esc(p.mode)}</span>${status(p.status)}</div><h3>${esc(p.name)}</h3><small>${p.kind === 'image' ? `${p.tasks}个任务 · ${p.outputs}张候选 · ${p.selected}张已选` : `${fmt(p.duration)}秒 · ${p.segments}段 · ${p.accepted}段已接受`}</small></div></a>`;
}
export function renderHome(root, projects, create) {
  const items = projects.filter((p) => !p.archived);
  root.className = "page home-page";
  root.innerHTML = `<section class="hero"><div class="hero-copy"><span class="eyebrow">TIME FOREST · H3 DIRECTOR</span><h1>让镜头沿着<br>时间生长。</h1><p>从一段表演、一张角色图，或文字中的世界出发。<br>让画面与声音，一起成为完整作品。</p><a class="btn primary" id="hero-start" href="#modes">选择创作方式 <span aria-hidden="true">↗</span></a></div><picture><source media="(max-width:600px)" srcset="/static/assets/hero/hero-director-desk-mobile.webp"><img width="1200" height="750" src="/static/assets/hero/hero-director-desk.webp" alt="导演在森林中拍摄，胶片沿树枝延伸"></picture></section><section id="modes"><div class="section-head"><div><span class="eyebrow">CREATIVE WORKSPACES</span><h2>你的故事，从哪里开始？</h2></div><p class="muted">不同的起点，各自专注的创作空间。</p></div><div class="creation-grid">${listModes()
    .map(
      (m) =>
        `<button class="mode-card" data-create="${m.id}"><div class="mode-art"><img width="600" height="400" loading="lazy" src="/static/assets/modes/${m.art}" alt=""></div><div class="card-body"><span class="eyebrow">${m.code}</span><h3>${m.name}</h3><p>${m.description}</p><span class="mode-enter">进入${m.entry}<span aria-hidden="true">↗</span></span></div></button>`,
    )
    .join(
      "",
    )}</div></section><section class="section recent"><div class="section-head"><div><span class="eyebrow">RECENT PRODUCTIONS</span><h2>最近制作</h2></div><a href="#/archive" class="text-link">全部项目 →</a></div>${items.length ? `<div class="grid3">${items.slice(0, 6).map(projectCard).join("")}</div>` : '<div class="panel empty"><img src="/static/assets/empty/empty-projects.svg" alt=""><h3>新的故事，从这里开始。</h3><p>上方选择一种方式，建立你的第一个项目。</p></div>'}</section>`;
  root.querySelector("#hero-start").onclick = (e) => {
    e.preventDefault();
    root.querySelector("#modes").scrollIntoView({
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    });
  };
  root
    .querySelectorAll("[data-create]")
    .forEach((b) => (b.onclick = () => create(b.dataset.create)));
}
