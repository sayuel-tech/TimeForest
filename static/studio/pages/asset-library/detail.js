import {mountAssetOrigin} from '../../features/asset-picker/origin-view.js';
import {projectOriginLink} from '../../ui/asset-origin.js';
import {bindTimeline} from "./media-timeline.js";
import * as ui from "../../ui/primitives.js";
import { libraryApi } from "../../features/asset-picker/library-client.js";
import {
  primaryMedia,
  mediaPlayer,
  mediaSummary,
} from "../../features/asset-picker/media-view.js";
import { pickLibraryAsset } from "../../features/asset-picker/index.js";
import { showUploads } from "./uploads.js";
import { mountMediaTools } from "./media-tools.js";
import { exportPack } from "./transfer.js";

const purposes = [
  ["character", "角色形象"],
  ["voice", "角色声线"],
  ["scene", "场景"],
  ["prop", "物品"],
  ["costume", "服装"],
  ["accessory", "饰品"],
  ["palette", "色系"],
  ["control", "控制参考"],
  ["texture", "材质纹理"],
];

export async function mountDetail(root, aid, params, signal) {
  let [asset, catalog] = await Promise.all([
    libraryApi(
      "/assets/" +
        aid +
        (params.get("version")
          ? "?version=" + encodeURIComponent(params.get("version"))
          : ""),
      "GET",
      undefined,
      signal,
    ),
    libraryApi("/catalog", "GET", undefined, signal),
  ]);
  if (signal.aborted) return;
  const historical = Boolean(params.get("version"));
  const draftKey = "tf-library-draft:" + aid;
  let draft = structuredClone(asset.snapshot),
    dirty = false,
    currentMedia = asset.snapshot.media.some(m=>m.id===params.get('media'))?params.get('media'):primaryMedia(asset).id;
  const cached = localStorage.getItem(draftKey);
  let stale = false;
  if (cached && !historical) {
    try {
      const saved = JSON.parse(cached);
      draft = saved.data;
      dirty = true;
      stale = saved.revision !== asset.revision;
    } catch {
      /* invalid browser draft does not affect the library */
    }
  }
  function persist() {
    if (historical) return;
    dirty = true;
    localStorage.setItem(
      draftKey,
      JSON.stringify({ revision: asset.revision, data: draft }),
    );
    const label = root.querySelector("#library-save-state");
    if (label) label.textContent = "修改已留在本机草稿，尚未入库";
  }
  function gather() {
    const form = root.querySelector("#library-editor-form");
    if (!form || historical) return;
    for (const field of ["name", "record_prompt", "description"])
      draft[field] = form.elements[field].value;
    draft.tags = form.elements.tags.value
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean);
    draft.favorite = form.elements.favorite.checked;
    draft.state = form.elements.state.value;
    draft.categories = [
      ...form.querySelectorAll('[name="category"]:checked'),
    ].map((x) => x.value);
    draft.bindings = [...form.querySelectorAll("[data-binding]")].map(
      (row) => ({
        ...draft.bindings[Number(row.dataset.binding)],
        purpose: row.querySelector("select").value,
        default: row.querySelector("[type=checkbox]").checked,
      }),
    );
    persist();
  }
  async function reload() {
    if (signal.aborted) return;
    asset = await libraryApi("/assets/" + aid, "GET", undefined, signal);
    if (signal.aborted) return;
    if (!dirty) draft = structuredClone(asset.snapshot);
    draw();
  }
  function draw() {
    if (signal.aborted) return;
    const media =
      asset.snapshot.media.find((x) => x.id === currentMedia) ||
      primaryMedia(asset);
    const back = sessionStorage.getItem("tf-library-list") || "#/assets";
    root.innerHTML = `<div class="library-header"><div><a href="${ui.esc(back)}">← 返回资产库</a><h1>${ui.esc(draft.name)}</h1><p>${ui.esc(mediaSummary(media))}${historical ? " · 历史版本，只读" : ""}</p></div><div class="library-toolbar"><a class="btn" href="${ui.esc(media.url)}?download=1">导出原件</a>${media.meta.kind === 'image' ? '<button id="library-create-image">用这张图创作</button>' : ''}${!historical ? `<button id="library-trash">${asset.deleted ? "从回收站恢复" : "移入回收站"}</button>` : `<a class="btn" href="#/assets/${aid}">查看当前版本</a>`}</div></div><div class="library-detail"><div class="library-preview-panel">${mediaPlayer(media)}<div class="library-media-strip">${asset.snapshot.media.map((m, i) => `<button data-media="${m.id}" aria-pressed="${m.id === currentMedia}">${m.role === "primary" ? "主媒体" : "备选 " + i} · ${ui.esc(m.meta.kind)}</button>`).join("")}</div><p class="helper">${ui.esc(mediaSummary(media))}${media.meta.fps ? " · 原始帧率 " + ui.esc(media.meta.fps) : ""}${media.meta.time_base ? " · 时基 " + ui.esc(media.meta.time_base) : ""}${media.meta.alpha ? " · 原件保留透明通道" : ""}</p>${["video", "audio"].includes(media.meta.kind) ? `<div class="library-time-controls">${ui.field("入点（秒）", '<input id="library-in" type="number" min="0" value="0" step=".001">')}${ui.field("出点（秒）", `<input id="library-out" type="number" min="0" step=".001" value="${media.meta.duration}">`)}<button id="mark-in">当前位置作入点</button><button id="mark-out">当前位置作出点</button><button id="loop-range" aria-pressed="false">循环选段</button></div><p class="helper">这里只标记使用区间，不修改原件。原始长度 ${ui.fmt(media.meta.duration)} 秒。</p>` : ""}<div id="library-asset-origin"></div><div id="library-derive-tools"></div>${!historical ? `<label class="btn">添加备选媒体<input id="library-alternate" type="file" hidden accept="image/*,audio/*,video/*"></label>` : ""}</div><div><form id="library-editor-form" class="library-editor"><span class="eyebrow">ASSET NOTES</span><h2>留给下一次创作的资料</h2>${stale ? '<div class="notice">库中版本已经变化。保留了你之前的草稿；请核对后再保存，会建立新版本。</div>' : ""}${ui.field("自定义名称", `<input name="name" required maxlength="160" value="${ui.esc(draft.name)}">`)}<span>用途分类（可以多选）</span><div class="library-checks">${catalog.categories.map((c) => `<label><input type="checkbox" name="category" value="${c.id}" ${draft.categories.includes(c.id) ? "checked" : ""}>${ui.esc(c.name)}</label>`).join("")}</div>${ui.field("标签", `<input name="tags" value="${ui.esc((draft.tags || []).join(", "))}">`, "用逗号分隔，例如：舞者、灰色针织、侧面。")}<div class="library-toolbar"><label><input name="favorite" type="checkbox" ${draft.favorite ? "checked" : ""}> 收藏</label><select name="state" aria-label="选用状态">${ui.opts(
      [
        ["candidate", "备选"],
        ["selected", "已选用"],
      ],
      draft.state || "candidate",
    )}</select></div>${ui.field("生成这个资产时使用的 PROMPT", `<textarea name="record_prompt" maxlength="200000" placeholder="记录生成这份素材时使用的提示词…">${ui.esc(draft.record_prompt)}</textarea>`, "仅作资料记录，不会自动进入制作流程或工作流。")}<button type="button" data-copy="record_prompt">复制资料 PROMPT</button>${ui.field("设定说明", `<textarea name="description" maxlength="200000" placeholder="角色背景、服装设定、素材用途或使用备注…">${ui.esc(draft.description)}</textarea>`, "仅作资产说明；需要制作时请自行复制到片段正文。")}<button type="button" data-copy="description">复制设定</button><details open><summary>默认绑定素材 · ${(draft.bindings || []).length} 项</summary><p class="helper">选择角色时可一并引用其声线和其他素材。每次创作都可以取消或替换；当前工作流不支持的输入会提示处理。</p><div>${(draft.bindings || []).map((b, i) => `<div class="library-binding" data-binding="${i}"><a href="#/assets/${ui.esc(b.asset)}?version=${ui.esc(b.version)}">${ui.esc(b.label || b.asset)}</a><div class="library-toolbar"><select aria-label="绑定用途">${ui.opts(purposes, b.purpose)}</select><label><input type="checkbox" ${b.default !== false ? "checked" : ""}>默认带入</label><button type="button" data-remove-binding="${i}">解除绑定</button></div><small>固定版本 ${ui.esc(b.version.slice(0, 8))}</small></div>`).join("")}</div><button type="button" id="add-binding">＋ 绑定库内资产</button></details><details><summary>历史版本与来源</summary><p>${(media.provenance || asset.snapshot.provenance)?.metadata_status === "present" ? "已保存真实生成记录" : "未记录完整执行图；不代表没有来源信息"}；以下记录独立保存，编辑上方资料不会修改它。</p><div class="library-toolbar">${asset.versions.map((v) => `<a href="#/assets/${aid}?version=${v.id}">${ui.esc(new Date(v.created * 1000).toLocaleString())}</a>`).join("")}</div><pre>${ui.esc(JSON.stringify(media.provenance || asset.snapshot.provenance, null, 2))}</pre><div id="library-source-exports"></div></details><details><summary>所在合集</summary>${catalog.collections.map((c) => `<label class="library-binding"><span>${ui.esc(c.name)}</span><button type="button" data-collection="${c.id}">${asset.collections?.includes(c.id) ? "从合集移除" : "加入合集"}</button></label>`).join("") || "<p>可以在“分类与合集”页面新建合集。</p>"}</details></form>${!historical ? `<div class="library-save"><small id="library-save-state">${dirty ? "已恢复本机未保存草稿" : "资料已保存"}</small><button form="library-editor-form" class="primary">保存资料版本</button></div>` : ""}</div></div>`;
    void mountAssetOrigin(root.querySelector('#library-asset-origin'), {asset:aid,version:asset.snapshot.id,media:media.id,supported:asset.asset_origin_version===1}, signal);
    const form = root.querySelector("#library-editor-form");
    if (historical)
      form
        .querySelectorAll("input,textarea,select,button:not([data-copy])")
        .forEach((el) => (el.disabled = true));
    form.oninput = gather;
    form.onchange = gather;
    form.onsubmit = async (e) => {
      e.preventDefault();
      if (historical) return;
      gather();
      const buttons = root.querySelectorAll('[form="library-editor-form"]');
      buttons.forEach((b) => (b.disabled = true));
      try {
        const changes = Object.fromEntries(
          [
            "name",
            "record_prompt",
            "description",
            "categories",
            "tags",
            "favorite",
            "state",
            "bindings",
          ].map((k) => [k, draft[k] ?? (k === "bindings" ? [] : "")]),
        );
        await libraryApi(
          "/assets/" + aid,
          "PATCH",
          { revision: asset.revision, changes },
          signal,
        );
        localStorage.removeItem(draftKey);
        dirty = false;
        stale = false;
        await reload();
        ui.toast("资产资料已保存为新版本，已有项目引用保持原版本");
      } catch (error) {
        if (!signal.aborted) ui.toast(error.message);
      } finally {
        buttons.forEach((b) => (b.disabled = false));
      }
    };
    root.querySelectorAll("[data-media]").forEach(
      (b) =>
        (b.onclick = () => {
          currentMedia = b.dataset.media;
          draw();
        }),
    );
    root.querySelectorAll("[data-copy]").forEach(
      (b) =>
        (b.onclick = async () => {
          try {
            await navigator.clipboard.writeText(
              form.elements[b.dataset.copy].value,
            );
            ui.toast("已复制，需手动粘贴到制作正文");
          } catch {
            ui.toast("浏览器未允许复制，请选中文字复制");
          }
        }),
    );
    root.querySelectorAll("[data-remove-binding]").forEach(
      (b) =>
        (b.onclick = () => {
          gather();
          draft.bindings.splice(Number(b.dataset.removeBinding), 1);
          persist();
          draw();
        }),
    );
    root.querySelector("#add-binding").onclick = async () => {
      gather();
      const item = await pickLibraryAsset({
        signal,
        title: "为这项资产绑定素材",
        exclude: [aid],
      });
      if (!item || signal.aborted) return;
      draft.bindings ||= [];
      draft.bindings.push({
        asset: item.id,
        version: item.version,
        label: item.name,
        purpose:
          item.kind === "audio"
            ? "voice"
            : item.snapshot.categories.find((c) =>
                purposes.some((p) => p[0] === c),
              ) || "prop",
        default: true,
      });
      persist();
      draw();
    };
    root.querySelectorAll("[data-collection]").forEach(
      (b) =>
        (b.onclick = async () => {
          b.disabled = true;
          try {
            const c = await libraryApi("/collections/" + b.dataset.collection);
            const has = c.items.includes(aid);
            await libraryApi("/collections", "POST", {
              ...c,
              items: has ? c.items.filter((x) => x !== aid) : [...c.items, aid],
            });
            await reload();
          } catch (error) {
            ui.toast(error.message);
            b.disabled = false;
          }
        }),
    );
    if (!historical) {
      root.querySelector("#library-trash").onclick = async () => {
        try {
          await libraryApi(`/assets/${aid}/trash`, "POST", {
            revision: asset.revision,
            restore: Boolean(asset.deleted),
          });
          await reload();
        } catch (error) {
          ui.toast(error.message);
        }
      };
      root.querySelector("#library-alternate").onchange = (e) => {
        if (dirty) {
          e.target.value = "";
          return ui.toast("请先保存资料版本，再添加备选媒体");
        }
        showUploads([...e.target.files], {}, reload, {
          asset: aid,
          revision: asset.revision,
        });
      };
    }
    const records =
      (media.provenance || asset.snapshot.provenance)?.records || {};
    const exports = root.querySelector("#library-source-exports");
    for (const key of ["workflow", "prompt"])
      if (records[key] && typeof records[key] === "object") {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent =
          key === "workflow" ? "导出画布工作流" : "导出原API执行图";
        button.onclick = () =>
          ui.download(records[key], asset.name + "-" + key + ".json");
        exports.append(button);
      }
    if (!historical) {
      const controls = root.querySelector(".library-media-strip");
      async function changeMedia(changes) {
        if (dirty) return ui.toast("请先保存资料草稿，再修改主媒体或封面");
        try {
          await libraryApi(
            "/assets/" + aid,
            "PATCH",
            { revision: asset.revision, changes },
            signal,
          );
          await reload();
          ui.toast("已建立新版本，已有项目仍使用原版本");
        } catch (error) {
          ui.toast(error.message);
        }
      }
      if (media.role !== "primary") {
        const b = document.createElement("button");
        b.textContent = "将当前媒体设为主参考";
        b.onclick = () => changeMedia({ primary_media: media.id });
        controls.append(b);
      }
      const cover = document.createElement("button");
      cover.textContent = "选择封面图";
      cover.onclick = async () => {
        if (dirty) return ui.toast("请先保存资料草稿，再选择封面");
        const selected = await pickLibraryAsset({
        signal,
          title: "选择封面图片（不改变生成输入）",
          kind: "image",
        });
        if (selected && !signal.aborted) {
          const m = selected.snapshot.media.find(
            (m) => m.meta.kind === "image",
          );
          if (m) await changeMedia({ cover_hash: m.hash });
        }
      };
      controls.append(cover);
      const upload = root.querySelector("label:has(#library-alternate)");
      upload.tabIndex = 0;
      upload.setAttribute("role", "button");
      upload.onkeydown = (e) => {
        if (["Enter", " "].includes(e.key)) {
          e.preventDefault();
          upload.querySelector("input").click();
        }
      };
    }
    const references = document.createElement("details");
    references.innerHTML = `<summary>使用过这项资产的项目 · ${(asset.references || []).length}</summary><p class="helper">以下为历史引用登记；项目执行使用固定副本，库更新不会自动替换。已删除的项目可能仍保留历史登记。</p>${(asset.references || []).map((r) => `<p>${asset.reference_projects?.[r.project]?projectOriginLink(asset.reference_projects[r.project]):`项目 ${ui.esc(r.project)} · 当前状态未核对`} · 版本 ${ui.esc(r.version.slice(0, 8))}</p>`).join("")}`;
    root.querySelector(".library-editor").append(references);
    if (Object.keys(records).length) {
      const full = document.createElement("button");
      full.type = "button";
      full.textContent = "导出完整来源记录";
      full.onclick = () =>
        ui.download(records, asset.name + "-generation-records.json");
      exports.append(full);
    }
    bindTimeline(root,media);
    root.querySelector('#library-create-image')?.addEventListener('click', async () => {
      if (dirty && !(await ui.confirm('使用已保存的资产版本', '当前资料草稿不会进入图片创作。使用当前查看的固定图片版本继续？', '继续'))) return;
      try {
        const {api} = await import('../../core/api-client.js');
        const p = await api('/projects', 'POST', {mode:'image_assets', name:asset.snapshot.name+' · 图片创作'});
        if (!signal.aborted) location.hash='/p/'+p.id+'?'+new URLSearchParams({asset:asset.id,version:asset.version,media:media.id});
      } catch(e) { ui.toast(e.message); }
    });
    mountMediaTools(root, asset, media, signal);
    const packButton = document.createElement("button");
    packButton.textContent = "导出素材包";
    packButton.onclick = () =>
      exportPack([{ ...asset, version: asset.snapshot.id }], signal);
    root.querySelector(".library-header .library-toolbar").append(packButton);
  }
  draw();
  return { dirty: () => dirty };
}
