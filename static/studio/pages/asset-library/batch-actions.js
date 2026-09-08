import * as ui from "../../ui/primitives.js";
import {libraryApi} from "../../features/asset-picker/library-client.js";
import {primaryMedia,mediaPlayer,mediaSummary} from "../../features/asset-picker/media-view.js";
import {exportPack} from "./transfer.js";
import {simpleInput} from "./input-dialog.js";

/** List selection operations keep revisions and reload through the owning page. */
export function bindBatchActions({content,selected,params,catalog,active,render,signal},items) {
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
