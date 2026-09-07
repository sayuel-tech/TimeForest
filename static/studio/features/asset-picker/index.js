import { libraryApi } from "./library-client.js";
import { thumbnail, primaryMedia, mediaSummary } from "./media-view.js";
import { modal, esc, opts, toast } from "../../ui/primitives.js";

/** A library browser only. The calling mode must separately preview and apply input changes. */
export async function pickLibraryAsset({
  kind = "",
  title = "从资产库选择",
  exclude = [],
  multiple = false,
} = {}) {
  const catalog = await libraryApi("/catalog");
  return new Promise((resolve) => {
    const controller = new AbortController();
    const selected = new Map();
    let page = 1,
      serial = 0,
      finished = false;
    const dialog = modal(
      `<div class="library-picker"><span class="eyebrow">ASSET LIBRARY</span><h2>${esc(title)}</h2><form class="library-search"><input name="q" placeholder="搜索资产名称" aria-label="搜索资产名称"><select name="category" aria-label="分类">${opts([["", "所有分类"], ...catalog.categories.map((c) => [c.id, c.name])], "")}</select><button>查找</button></form><div class="library-picker-results" aria-live="polite"></div><div class="library-pagination"><button data-page="-1">上一页</button><span></span><button data-page="1">下一页</button></div><p class="helper">这里仅选择资产；引用用途、绑定内容和工作流变化会在下一步核对。资料PROMPT不会进入制作。</p>${multiple?'<button type="button" class="primary picker-apply" disabled>导入所选视频（0）</button>':''}<button type="button" class="picker-cancel">取消</button></div>`,
    );
    const view = dialog.querySelector(".library-picker");
    const done = (value) => {
      if (finished) return;
      finished = true;
      controller.abort();
      dialog.close();
      resolve(value);
    };
    dialog.oncancel = (event) => {
      event.preventDefault();
      done(null);
    };
    view.querySelector(".picker-cancel").onclick = () => done(null);
    if(multiple)view.querySelector(".picker-apply").onclick=()=>done([...selected.values()]);
    async function load() {
      const current = ++serial;
      const search = new URLSearchParams(
        new FormData(view.querySelector("form")),
      );
      search.set("page", page);
      search.set("limit", 12);
      if (kind) search.set("contains_kind", kind);
      try {
        const data = await libraryApi(
          "/assets?" + search,
          "GET",
          undefined,
          controller.signal,
        );
        if (current !== serial || finished) return;
        view.querySelector(".library-picker-results").innerHTML =
          data.items
            .map(
              (item) =>
                `<button class="library-pick-card" ${multiple?`aria-pressed="${selected.has(item.id)}"`:""} data-pick="${item.id}" ${exclude.includes(item.id) ? "disabled" : ""}>${thumbnail(item)}<strong>${esc(item.name)}</strong><small>${esc(mediaSummary(primaryMedia(item)))}</small></button>`,
            )
            .join("") ||
          '<p class="empty">没有符合条件的资产，可先在资产库上传。</p>';
        view.querySelector(".library-pagination span").textContent =
          `${page} / ${Math.max(1, Math.ceil(data.total / 12))}`;
        view.querySelector('[data-page="-1"]').disabled = page === 1;
        view.querySelector('[data-page="1"]').disabled =
          page * 12 >= data.total;
        view.querySelectorAll("[data-pick]").forEach(
          (button) =>
            (button.onclick = async () => {
              button.disabled = true;
              try {
                const item = await libraryApi(
                  "/assets/" + button.dataset.pick,
                  "GET",
                  undefined,
                  controller.signal,
                );
                if(multiple){
                  if(selected.has(item.id))selected.delete(item.id);else selected.set(item.id,item);
                  button.setAttribute("aria-pressed",String(selected.has(item.id)));button.disabled=false;
                  const apply=view.querySelector(".picker-apply");apply.disabled=!selected.size;apply.textContent=`导入所选视频（${selected.size}）`;
                }else done(item);
              } catch (error) {
                if (!finished) {
                  toast(error.message);
                  button.disabled = false;
                }
              }
            }),
        );
      } catch (error) {
        if (error.name !== "AbortError") toast(error.message);
      }
    }
    view.querySelector("form").onsubmit = (event) => {
      event.preventDefault();
      page = 1;
      void load();
    };
    view.querySelectorAll("[data-page]").forEach(
      (b) =>
        (b.onclick = () => {
          page += Number(b.dataset.page);
          void load();
        }),
    );
    void load();
  });
}
