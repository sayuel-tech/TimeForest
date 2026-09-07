import * as ui from "../../ui/primitives.js";
import { libraryApi, followTask } from "./library-client.js";

export async function saveProjectMedia(ctx, { kind, resultId } = {}) {
  try {
    const response = await libraryApi(
      `/projects/${ctx.project.id}/outputs`,
      "GET",
      undefined,
      ctx.session.controller.signal,
    );
    const items = response.items.filter(
      (x) =>
        (!kind || x.kind === kind) && (!resultId || x.result_id === resultId),
    );
    if (!items.length) return ui.toast("这项媒体尚未完整保存，暂时不能入库");
    const catalog = await libraryApi("/catalog");
    const d = ui.scopedModal(
      `<h2>加入独立资产库</h2><p>选择确切文件后入库，之后可在资产详情抽帧、选段或提取声音。不会自动采用最新候选。</p><form id="save-library-result">${ui.field(
        "要入库的文件",
        `<select name="output">${ui.opts(
          items.map((x) => [x.id, x.name]),
          items[0].id,
        )}</select>`,
      )}${ui.field("资产名称", `<input name="name" required maxlength="160" value="${ui.esc(items[0].name)}">`)}${ui.field("分类", `<select name="category">${ui.opts([["", "稍后整理"], ...catalog.categories.map((c) => [c.id, c.name])], kind === "candidate" || kind === "final" ? "video" : "")}</select>`)}<p class="helper">已有的运行提示词会复制到资产资料，原始运行记录单独保留；不会改动项目正文。</p><div id="save-library-status" role="status"></div><div class="dialog-actions"><button type="button" id="save-library-close">收起</button><button class="primary">确认入库</button></div></form>`,
    );
    d.querySelector("#save-library-close").onclick = () => d.close();
    d.querySelector("form").onsubmit = async (e) => {
      e.preventDefault();
      const form = e.target,
        button = form.querySelector(".primary");
      button.disabled = true;
      try {
        const task = await libraryApi("/project-results", "POST", {
          output: form.elements.output.value,
          name: form.elements.name.value,
          metadata: {
            categories: form.elements.category.value
              ? [form.elements.category.value]
              : [],
          },
        });
        const item = await followTask(
          task,
          (t) => {
            if (d.open)
              d.querySelector("#save-library-status").innerHTML =
                `<p>${ui.esc(t.note)}</p><progress max="1" value="${t.progress}"></progress>`;
          },
          ctx.session.controller.signal,
        );
        if (d.open)
          d.querySelector("#save-library-status").innerHTML =
            `<p>原结果已入库，删除项目也不会移除它。</p><a class="btn" href="#/assets/${item.id}">查看资产与派生工具</a>`;
      } catch (error) {
        if (d.open)
          d.querySelector("#save-library-status").textContent = error.message;
        button.disabled = false;
      }
    };
  } catch (error) {
    ui.toast(error.message);
  }
}
