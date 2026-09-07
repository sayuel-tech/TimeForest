import {mountRecycleBin} from './recycle-bin.js';
import { openLauncher } from "./engine-settings.js";
import * as ui from "../../ui/primitives.js";
import {
  libraryApi,
  followTask,
} from "../../features/asset-picker/library-client.js";
import {
  thumbnail,
  primaryMedia,
  mediaSummary,
  mediaPlayer,
} from "../../features/asset-picker/media-view.js";
import { showUploads } from "./uploads.js";
import { exportPack, importPack, collectFolder } from "./transfer.js";

export async function mountLibrary(root, hash, signal) {
  root.classList.add("library-page");
  const match = hash.match(/^#\/assets(?:\/([a-f0-9]+))?(?:\?(.*))?$/);
  const params = new URLSearchParams(match?.[2] || "");
  if (match?.[1]) {
    const { mountDetail } = await import("./detail.js");
    return mountDetail(root, match[1], params, signal);
  }
  const catalog = await libraryApi("/catalog", "GET", undefined, signal);
  if (signal.aborted) return;
  const savedScroll = Number(
    sessionStorage.getItem("tf-library-scroll:" + hash) || 0,
  );
  sessionStorage.setItem("tf-library-list", hash);
  function url(changes) {
    const next = new URLSearchParams(params);
    next.delete("page");
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    return "#/assets?" + next;
  }
  const selected = new Set();
  root.innerHTML = `<section class="library-header"><div><span class="eyebrow">THE MATERIAL COLLECTION</span><h1>资产库</h1><p>本地保存角色、场景、视频与声音，随时用于新的创作。</p></div><div class="library-toolbar"><a class="btn" href="${ui.esc(url({ view: "tasks" }))}">处理任务</a><label class="btn primary">导入素材<input id="library-upload" type="file" multiple hidden accept="image/*,video/*,audio/*,.json"></label><details id="library-transfer"><summary>更多导入方式</summary><div class="library-toolbar"><button id="library-folder">收集输出文件夹</button><label class="btn">导入素材包<input type="file" accept=".zip" id="library-pack-upload" hidden></label></div></details></div></section><div class="library-layout"><aside class="library-sidebar"><a href="#/assets" class="${!params.size ? "active" : ""}">全部资产</a><a href="${ui.esc(url({ favorite: "1", view: "", trash: "" }))}">我的收藏</a><a href="${ui.esc(url({ sort: "used", view: "", trash: "" }))}">最近使用</a><a href="${ui.esc(url({ unorganized: "1", view: "", trash: "" }))}">待整理</a><span class="eyebrow">CATEGORIES</span>${catalog.categories.map((c) => `<a class="${params.get("category") === c.id ? "active" : ""}" href="${ui.esc(url({ category: c.id, view: "", trash: "" }))}">${ui.esc(c.name)}</a>`).join("")}<span class="eyebrow">ORGANIZE</span><a href="${ui.esc(url({ view: "organize" }))}">分类与合集</a><a href="#/assets?view=trash" class="${params.get("view")==="trash"||params.get("trash")==="1"?"active":""}">回收站</a><a href="${ui.esc(url({ view: "storage" }))}">本地存储与备份</a></aside><section id="library-content"></section></div>`;
  root.querySelectorAll('label:has(input[type="file"])').forEach((label) => {
    label.tabIndex = 0;
    label.setAttribute("role", "button");
    label.onkeydown = (e) => {
      if (["Enter", " "].includes(e.key)) {
        e.preventDefault();
        label.querySelector("input").click();
      }
    };
  });
  const content = root.querySelector("#library-content");
  root.querySelector("#library-folder").onclick = () => collectFolder(signal);
  root.querySelector("#library-pack-upload").onchange = (e) => {
    if (e.target.files[0]) void importPack(e.target.files[0], signal);
  };
  root.querySelector("#library-upload").onchange = (e) =>
    showUploads(
      [...e.target.files],
      { categories: params.get("category") ? [params.get("category")] : [] },
      () => {
        if (!signal.aborted && !document.querySelector("#dialog").open)
          void render();
      },
    );
  function active() {
    return !signal.aborted;
  }
  async function render() {
    if (!active()) return;
    try {
      const view = params.get("view");
      if (view === "tasks") return renderTasks();
      if (view === "storage") return renderStorage();
      if (view === "organize") return renderOrganize();
      if (view === "trash" || params.get("trash") === "1") return mountRecycleBin(content, params, signal);
      const data = await libraryApi(
        "/assets?" + params,
        "GET",
        undefined,
        signal,
      );
      if (!active()) return;
      content.innerHTML = `<form class="library-search"><input name="q" aria-label="搜索资产名称" placeholder="搜索资产名称" value="${ui.esc(params.get("q") || "")}"><select name="kind" aria-label="媒体类型">${ui.opts(
        [
          ["", "所有媒体"],
          ["image", "图片"],
          ["video", "视频"],
          ["audio", "声音"],
          ["workflow", "工作流资料"],
        ],
        params.get("kind"),
      )}</select><button>搜索</button><a href="#/assets">清除筛选</a><details><summary>更多筛选</summary><div class="library-toolbar">${ui.field("合集", `<select name="collection">${ui.opts([["", "全部"], ...catalog.collections.map((c) => [c.id, c.name])], params.get("collection"))}</select>`)}${ui.field("标签", `<input name="tag" value="${ui.esc(params.get("tag") || "")}">`)}${ui.field(
        "来源",
        `<select name="source">${ui.opts(
          [
            ["", "全部"],
            ["local", "本地参考"],
            ["project", "项目素材"],
            ["generated", "本站生成视频"],
            ["generated_image", "图片资产创作"],
            ["comfy_output", "ComfyUI输出"],
            ["derived", "派生素材"],
          ],
          params.get("source"),
        )}</select>`,
      )}${ui.field(
        "图片编辑工具",
        `<select name="image_tool">${ui.opts([["","全部"],["single","单图编辑"],["dual","双图编辑"],["region","局部重绘／移除"],["outpaint","图像扩展"],["text","文生图"]],params.get("image_tool"))}</select>`,
      )}${ui.field(
        "画幅",
        `<select name="aspect">${ui.opts(
          [
            ["", "全部"],
            ["portrait", "竖幅"],
            ["landscape", "横幅"],
            ["square", "方形"],
          ],
          params.get("aspect"),
        )}</select>`,
      )}${ui.field(
        "音轨",
        `<select name="audio">${ui.opts(
          [
            ["", "全部"],
            ["1", "有声音"],
            ["0", "无声音"],
          ],
          params.get("audio"),
        )}</select>`,
      )}${[
        ["min_duration", "最短时长（秒）"],
        ["max_duration", "最长时长（秒）"],
        ["min_width", "最小宽度"],
        ["min_fps", "最低帧率"],
      ]
        .map(([k, label]) =>
          ui.field(
            label,
            `<input type="number" min="0" step="any" name="${k}" value="${ui.esc(params.get(k) || "")}">`,
          ),
        )
        .join(
          "",
        )}${ui.field("生成模型记录", `<input name="model" value="${ui.esc(params.get("model") || "")}">`)}${ui.field("LoRA记录", `<input name="lora" value="${ui.esc(params.get("lora") || "")}">`)}</div></details></form><div class="library-toolbar"><span>${data.total} 项资产</span><select id="library-sort" aria-label="排序">${ui.opts(
        [
          ["", "最近更新"],
          ["used", "最近使用"],
          ["name", "名称"],
          ["oldest", "最早入库"],
        ],
        params.get("sort"),
      )}</select><button id="library-layout">${params.get("layout") === "list" ? "卡片视图" : "列表视图"}</button></div><div id="library-batch" hidden></div><div class="library-grid ${params.get("layout") === "list" ? "list" : ""}">${data.items.map((item) => `<article class="library-card"><label><input type="checkbox" data-select="${item.id}" aria-label="选择${ui.esc(item.name)}"></label><a href="#/assets/${item.id}"><figure>${thumbnail(item)}</figure><div class="library-card-copy"><h3>${item.favorite ? "☆ " : ""}${ui.esc(item.name)}</h3><small>${ui.esc(mediaSummary(primaryMedia(item)))}</small><small>${item.snapshot.categories.map((id) => ui.esc(catalog.categories.find((c) => c.id === id)?.name || id)).join(" · ") || "未分类"} ${item.state === "selected" ? "· 已选用" : ""}</small></div></a></article>`).join("") || '<div class="panel empty"><h2>从第一份素材开始。</h2><p>导入一张角色图、一段参考视频或一份声音，在这里慢慢建立自己的创作素材库。</p></div>'}</div><div class="library-pagination"><a class="btn" ${data.page === 1 ? 'aria-disabled="true"' : `href="${ui.esc(url({ page: data.page - 1 }))}"`}>上一页</a><span>${data.page} / ${Math.max(1, Math.ceil(data.total / data.limit))}</span><a class="btn" ${data.page * data.limit >= data.total ? 'aria-disabled="true"' : `href="${ui.esc(url({ page: data.page + 1 }))}"`}>下一页</a></div>`;
      content.querySelector("form").onsubmit = (event) => {
        event.preventDefault();
        location.hash = url(Object.fromEntries(new FormData(event.target)));
      };
      content.querySelector("#library-sort").onchange = (e) =>
        (location.hash = url({ sort: e.target.value }));
      content.querySelector("#library-layout").onclick = () =>
        (location.hash = url({
          layout: params.get("layout") === "list" ? "" : "list",
        }));
      content.querySelectorAll("[data-select]").forEach(
        (input) =>
          (input.onchange = () => {
            input.checked
              ? selected.add(input.dataset.select)
              : selected.delete(input.dataset.select);
            batchBar(data.items);
          }),
      );
      content
        .querySelectorAll(".library-card>a")
        .forEach(
          (a) =>
            (a.onclick = () =>
              sessionStorage.setItem(
                "tf-library-scroll:" + hash,
                window.scrollY,
              )),
        );
    } catch (error) {
      if (active())
        content.innerHTML = `<div class="notice">${ui.esc(error.message)}</div>`;
    }
  }
  function batchBar(items) {
    const bar = content.querySelector("#library-batch");
    bar.hidden = !selected.size;
    bar.className = "library-batch";
    bar.innerHTML = `<span>已选 ${selected.size} 项</span><button data-batch="compare">并排比较</button><button data-batch="favorite">收藏</button><button data-batch="category">加入分类</button><button data-batch="tag">添加标签</button><button data-batch="collection">加入合集</button><button data-batch="${params.get("trash") ? "restore" : "trash"}">${params.get("trash") ? "恢复" : "移入回收站"}</button><button id="export-selected-pack">导出选中素材包</button>`;
    bar.querySelectorAll("[data-batch]").forEach(
      (b) =>
        (b.onclick = async () => {
          const action = b.dataset.batch,
            chosen = items.filter((x) => selected.has(x.id));
          if (action === "compare") {
            if (chosen.length !== 2) return ui.toast("请选择两项候选进行比较");
            const d = ui.scopedModal(
              `<h2>候选比较</h2><p>手动判断选用结果。两个候选的时长可能不同，各自播放；不会自动评价或合成。</p><div class="library-compare">${chosen.map((x) => `<div><h3>${ui.esc(x.name)}</h3>${mediaPlayer(primaryMedia(x))}<p>${ui.esc(mediaSummary(primaryMedia(x)))}</p><button data-choose="${x.id}">标为选用</button></div>`).join("")}</div>`,
            );
            d.querySelectorAll("[data-choose]").forEach(
              (button) =>
                (button.onclick = async () => {
                  try {
                    const item = chosen.find(
                      (x) => x.id === button.dataset.choose,
                    );
                    await libraryApi("/assets/" + item.id, "PATCH", {
                      revision: item.revision,
                      changes: { state: "selected" },
                    });
                    button.disabled = true;
                    button.textContent = "已选用";
                  } catch (error) {
                    ui.toast(error.message);
                  }
                }),
            );
            return;
          }
          let value;
          if (["category", "tag", "collection"].includes(action)) {
            value = await simpleInput(
              action === "tag"
                ? "添加标签"
                : action === "category"
                  ? "加入分类"
                  : "加入合集",
              action === "tag"
                ? null
                : (action === "category"
                    ? catalog.categories
                    : catalog.collections
                  ).map((c) => [c.id, c.name]),
            );
            if (!value || !active()) return;
          }
          b.disabled = true;
          const errors = [];
          if (action === "collection") {
            try {
              const c = await libraryApi("/collections/" + value);
              await libraryApi("/collections", "POST", {
                ...c,
                items: [...new Set([...c.items, ...selected])],
              });
            } catch (error) {
              errors.push(error.message);
            }
          } else
            for (const item of chosen) {
              try {
                if (["trash", "restore"].includes(action))
                  await libraryApi(`/assets/${item.id}/trash`, "POST", {
                    revision: item.revision,
                    restore: action === "restore",
                  });
                else
                  await libraryApi("/assets/" + item.id, "PATCH", {
                    revision: item.revision,
                    changes:
                      action === "favorite"
                        ? { favorite: true }
                        : action === "category"
                          ? {
                              categories: [
                                ...new Set([
                                  ...item.snapshot.categories,
                                  value,
                                ]),
                              ],
                            }
                          : {
                              tags: [
                                ...new Set([...item.snapshot.tags, value]),
                              ],
                            },
                  });
              } catch (error) {
                errors.push(item.name + "：" + error.message);
              }
            }
          selected.clear();
          await render();
          ui.toast(errors.length ? errors.join("；") : "整理已保存");
        }),
    );
    bar.querySelector("#export-selected-pack").onclick = () =>
      exportPack(items.filter((x) => selected.has(x.id)), signal);
  }
  async function renderTasks() {
    const data = await libraryApi("/tasks", "GET", undefined, signal);
    if (!active()) return;
    content.innerHTML = `<h2>本地处理任务</h2><p class="helper">上传后的检验、预览、派生和备份在本机处理，不需要生成引擎。</p>${data.items.map((task) => `<div class="library-task-row"><div><strong>${ui.esc({ ingest: "资产入库", backup: "资产备份", derive: "媒体派生", scan: "目录收集", pack: "导出素材包" }[task.action] || task.action)}</strong><p>${ui.esc(task.note)}</p></div>${["failed", "interrupted"].includes(task.state) ? `<button data-retry="${task.id}">重试</button>` : task.result?.id ? `<a class="btn" href="#/assets/${task.result.id}">查看资产</a>` : ""}<progress max="1" value="${task.progress}" aria-label="任务进度"></progress>${task.result?.path ? `<small>${ui.esc(task.result.path)}</small>` : ""}</div>`).join("") || '<div class="empty">暂时没有处理任务。</div>'}`;
    content.querySelectorAll("[data-retry]").forEach(
      (b) =>
        (b.onclick = async () => {
          try {
            await libraryApi(`/tasks/${b.dataset.retry}/retry`, "POST", {});
            await renderTasks();
          } catch (error) {
            ui.toast(error.message);
          }
        }),
    );
    if (data.items.some((t) => ["queued", "running"].includes(t.state)))
      timer = setTimeout(() => void renderTasks().catch(() => {}), 900);
  }
  function renderStorage() {
    const storage = catalog.storage;
    content.innerHTML = `<div class="panel"><span class="eyebrow">LOCAL STORAGE</span><h2>本地素材，独立留存。</h2><p>资产目录：<code>${ui.esc(storage.directory)}</code></p><p>${storage.objects} 份去重原件 · ${ui.bytes(storage.stored_bytes)} · 磁盘可用 ${ui.bytes(storage.free_bytes)}</p><p class="helper">项目删除不会删除已入库素材；已有项目使用固定版本副本。备份包含数据库、原件和校验清单。</p><button class="primary" id="library-backup">创建完整备份</button><p id="library-backup-note" role="status"></p><details><summary>目录迁移、恢复与空间管理</summary><p class="helper">为保证目录切换时没有并发写入，迁移与恢复在停止网站后执行。维护工具先预览，再复制、校验和切换配置；失败保留原库。默认不永久删除历史版本或原件。仅已完成且超过7天的派生临时文件可以清理。</p><a class="btn" href="/api/v5/library/maintenance-guide">下载维护说明</a></details><details><summary>生成引擎启动设置</summary><p class="helper">可选设置，不影响离线管理素材。只有在你配置并开启后，生成请求才允许启动本机引擎。</p><button id="engine-launch-settings">设置按需启动</button></details></div>`;
    content.querySelector("#engine-launch-settings").onclick = () => openLauncher(signal);
    content.querySelector("#library-backup").onclick = async (e) => {
      e.target.disabled = true;
      try {
        const task = await libraryApi("/backup", "POST", {
          key: crypto.randomUUID(),
        });
        const result = await followTask(
          task,
          (t) => {
            if (active())
              content.querySelector("#library-backup-note").textContent =
                t.note;
          },
          signal,
        );
        if (active())
          content.querySelector("#library-backup-note").textContent =
            "已备份：" + result.path;
      } catch (error) {
        if (active()) ui.toast(error.message);
      } finally {
        if (active()) e.target.disabled = false;
      }
    };
  }
  function renderOrganize() {
    content.innerHTML = `<h2>分类与合集</h2><p class="helper">分类描述用途，合集组织一次创作。视频入口同时聚合所有含视频的资产。</p><div class="library-toolbar"><button id="new-category">新增分类</button><button id="new-collection">新增合集</button></div>${catalog.categories.map((c) => `<div class="library-task-row"><span>${ui.esc(c.name)}</span><div><button data-rename="${c.id}">改名</button>${c.system ? "" : `<button data-delete-category="${c.id}">删除／迁移</button>`}</div></div>`).join("")}<h3>合集</h3>${catalog.collections.map((c) => `<div class="library-task-row"><a href="${ui.esc(url({ view: "", collection: c.id }))}">${ui.esc(c.name)}</a><button data-rename-collection="${c.id}">改名</button></div>`).join("") || "<p>尚未创建合集。选择多个资产后可一起加入。</p>"}`;
    async function update(action) {
      try {
        await action();
        Object.assign(catalog, await libraryApi("/catalog"));
        if (active()) renderOrganize();
      } catch (error) {
        ui.toast(error.message);
      }
    }
    content.querySelector("#new-category").onclick = async () => {
      const name = await simpleInput("新分类名称");
      if (name) await update(() => libraryApi("/categories", "POST", { name }));
    };
    content.querySelector("#new-collection").onclick = async () => {
      const name = await simpleInput("新合集名称");
      if (name)
        await update(() => libraryApi("/collections", "POST", { name }));
    };
    content.querySelectorAll("[data-rename]").forEach(
      (b) =>
        (b.onclick = async () => {
          const name = await simpleInput("分类名称");
          if (name)
            await update(() =>
              libraryApi("/categories", "POST", { id: b.dataset.rename, name }),
            );
        }),
    );
    content.querySelectorAll("[data-delete-category]").forEach(
      (b) =>
        (b.onclick = async () => {
          const move_to = await simpleInput(
            "删除分类并迁移已有资产",
            catalog.categories
              .filter((c) => c.id !== b.dataset.deleteCategory)
              .map((c) => [c.id, c.name]),
          );
          if (move_to)
            await update(() =>
              libraryApi("/categories", "POST", {
                id: b.dataset.deleteCategory,
                delete: true,
                move_to,
              }),
            );
        }),
    );
    content.querySelectorAll("[data-rename-collection]").forEach(
      (b) =>
        (b.onclick = async () => {
          const name = await simpleInput("合集名称");
          const c = catalog.collections.find(
            (x) => x.id === b.dataset.renameCollection,
          );
          if (name)
            await update(() =>
              libraryApi("/collections", "POST", { ...c, name }),
            );
        }),
    );
  }
  let timer;
  await render();
  if (active() && savedScroll)
    window.scrollTo({ top: savedScroll, behavior: "instant" });
  signal.addEventListener("abort", () => clearTimeout(timer), { once: true });
}

export function simpleInput(title, choices) {
  return new Promise((resolve) => {
    const d = ui.scopedModal(
      `<h2>${ui.esc(title)}</h2><form id="library-value-form">${choices ? `<select name="value" required aria-label="${ui.esc(title)}">${ui.opts([["", "请选择"], ...choices], "")}</select>` : `<input name="value" required maxlength="160" aria-label="${ui.esc(title)}">`}<div class="dialog-actions"><button type="button" id="library-value-cancel">取消</button><button class="primary">确认</button></div></form>`,
    );
    const done = (value) => {
      d.close();
      resolve(value);
    };
    d.oncancel = (e) => {
      e.preventDefault();
      done(null);
    };
    d.querySelector("#library-value-cancel").onclick = () => done(null);
    d.querySelector("form").onsubmit = (e) => {
      e.preventDefault();
      done(e.target.elements.value.value.trim());
    };
  });
}
