import * as ui from "../../ui/primitives.js";
import {
  libraryApi,
  followTask,
} from "../../features/asset-picker/library-client.js";

export function exportPack(assets, signal) {
  const d = ui.scopedModal(
    `<h2>导出便携素材包</h2><p>选中 ${assets.length} 项资产。先查看将包含的完整清单，再创建本地ZIP。</p><form id="pack-form"><div class="library-checks"><label><input type="checkbox" name="bindings">一并包含启用的绑定素材</label><label><input type="checkbox" name="documents" checked>包含资料PROMPT与设定</label><label><input type="checkbox" name="lineage" checked>保留来源关系（仅恢复包内素材）</label><label><input type="checkbox" name="workflows">包含已有来源工作流</label></div><button>预览素材包</button></form><div id="pack-report" role="status"></div><div class="dialog-actions"><button id="pack-close">收起</button><button id="pack-export" class="primary" disabled>创建素材包</button></div>`,
  );
  let plan = null;
  let previewRevision = 0;
  d.querySelector("#pack-close").onclick = () => d.close();
  d.querySelector("form").onchange = () => {
    previewRevision++;
    plan = null;
    d.querySelector("#pack-export").disabled = true;
  };
  d.querySelector("form").onsubmit = async (e) => {
    e.preventDefault();
    const form = e.target;
    const revision = ++previewRevision;
    plan = null;
    d.querySelector("#pack-export").disabled = true;
    try {
      const result = await libraryApi(
        "/pack-plan",
        "POST",
        {
          assets: assets.map((a) => ({ asset: a.id, version: a.version })),
          bindings: form.elements.bindings.checked,
          documents: form.elements.documents.checked,
          workflows: form.elements.workflows.checked,
          lineage: form.elements.lineage.checked,
        },
        signal,
      );
      if (!d.open || signal?.aborted || revision !== previewRevision) return;
      if (result.pack_lineage_version !== 1)
        throw new Error("当前后台未支持素材包来源关系，请保存编辑并结束任务后重启导演台，再重新预览。");
      plan = result;
      d.querySelector("#pack-report").innerHTML =
        `<p>${plan.assets.map((a) => ui.esc(a.name)).join("、")}</p><p>${plan.files} 份媒体 · ${ui.bytes(plan.bytes)} · 未带入 ${plan.excluded_bindings.length} 项绑定</p><p class="helper">${ui.esc(plan.note)}</p>`;
      d.querySelector("#pack-export").disabled = false;
    } catch (error) {
      if (d.open && !signal?.aborted && revision === previewRevision) ui.toast(error.message);
    }
  };
  d.querySelector("#pack-export").onclick = async (e) => {
    if (!plan) return;
    e.target.disabled = true;
    try {
      const task = await libraryApi(
        "/pack-export",
        "POST",
        { token: plan.token },
        signal,
      );
      const result = await followTask(
        task,
        (t) => {
          if (d.open) d.querySelector("#pack-report").textContent = t.note;
        },
        signal,
      );
      if (d.open)
        d.querySelector("#pack-report").innerHTML =
          `<a class="btn primary" href="${ui.esc(result.download)}" download>下载素材包 · ${ui.bytes(result.bytes)}</a>`;
    } catch (error) {
      if (d.open) {
        ui.toast(error.message);
        e.target.disabled = false;
      }
    }
  };
}

export async function importPack(file, signal) {
  const d = ui.scopedModal(
    '<h2>导入便携素材包</h2><p id="pack-import-report" role="status">正在上传并检查清单…</p><div class="dialog-actions"><button id="pack-import-close">收起</button><button id="pack-import-confirm" class="primary" disabled>确认恢复资产</button></div>',
  );
  d.querySelector("#pack-import-close").onclick = () => d.close();
  try {
    const form = new FormData();
    form.append("file", file);
    const preview = await libraryApi("/pack-upload", "POST", form, signal);
    if (!d.open) return;
    d.querySelector("#pack-import-report").textContent =
      preview.assets.map((a) => a.name).join("、") +
      " · " +
      ui.bytes(preview.bytes) +
      "。" +
      preview.note;
    const button = d.querySelector("#pack-import-confirm");
    button.disabled = false;
    button.onclick = async () => {
      button.disabled = true;
      try {
        const task = await libraryApi(
          "/pack-import",
          "POST",
          { token: preview.token },
          signal,
        );
        const result = await followTask(
          task,
          (t) => {
            if (d.open)
              d.querySelector("#pack-import-report").textContent = t.note;
          },
          signal,
        );
        if (d.open)
          d.querySelector("#pack-import-report").innerHTML =
            `已恢复 ${result.count} 项资产。<a href="#/assets">查看资产库</a>`;
      } catch (error) {
        if (d.open) {
          d.querySelector("#pack-import-report").textContent = error.message;
          button.disabled = false;
        }
      }
    };
  } catch (error) {
    if (d.open)
      d.querySelector("#pack-import-report").textContent = error.message;
  }
}

export function collectFolder(signal) {
  const d = ui.scopedModal(
    `<h2>收集本地输出目录</h2><p>适合从ComfyUI输出文件夹挑选素材。只检查你指定的文件夹，不开启后台监听。</p><form id="collect-form">${ui.field("文件夹绝对路径", '<input name="directory" required placeholder="例如 D:\\ComfyUI\\output\\my-film">')}<label><input name="recursive" type="checkbox">包含子文件夹</label><button class="primary">检查待整理文件</button></form><div id="collect-status" role="status"></div><div id="collect-files"></div><div class="dialog-actions"><button id="collect-close">收起</button><button id="collect-import" disabled>导入勾选文件</button></div>`,
  );
  let scan = null;
  d.querySelector("#collect-close").onclick = () => d.close();
  d.querySelector("form").onsubmit = async (e) => {
    e.preventDefault();
    const form = e.target;
    form.querySelector("button").disabled = true;
    try {
      const task = await libraryApi(
        "/scan",
        "POST",
        {
          directory: form.elements.directory.value,
          recursive: form.elements.recursive.checked,
        },
        signal,
      );
      scan = await followTask(
        task,
        (t) => {
          if (d.open) d.querySelector("#collect-status").textContent = t.note;
        },
        signal,
      );
      if (!d.open) return;
      d.querySelector("#collect-status").textContent =
        `找到 ${scan.items.length} 项，合计 ${ui.bytes(scan.bytes)}。跳过 ${scan.skipped.length} 项（可能仍写入或超过范围）。`;
      d.querySelector("#collect-files").innerHTML =
        scan.items
          .map(
            (x) =>
              `<label class="library-binding"><input type="checkbox" value="${x.id}" ${x.duplicate ? "" : "checked"}>${ui.esc(x.name)} · ${ui.bytes(x.bytes)}${x.duplicate ? " · 库中已有同文件" : ""}</label>`,
          )
          .join("") +
        scan.skipped
          .map((x) => `<small>${ui.esc(x.name)}：${ui.esc(x.reason)}</small>`)
          .join("<br>");
      d.querySelector("#collect-import").disabled = !scan.items.length;
    } catch (error) {
      if (d.open) ui.toast(error.message);
    } finally {
      form.querySelector("button").disabled = false;
    }
  };
  d.querySelector("#collect-import").onclick = async (e) => {
    const selected = [
      ...d.querySelectorAll("#collect-files input:checked"),
    ].map((x) => x.value);
    e.target.disabled = true;
    let completed = 0;
    const errors = [];
    for (const id of selected) {
      try {
        const task = await libraryApi(
          "/scan-import",
          "POST",
          { file: id },
          signal,
        );
        await followTask(task, () => {}, signal);
        completed++;
        d.querySelector(`#collect-files input[value="${id}"]`).checked = false;
      } catch (error) {
        errors.push(error.message);
      }
      if (d.open)
        d.querySelector("#collect-status").textContent =
          `已入库 ${completed}/${selected.length} 项。${errors.join("；")}`;
      if (signal.aborted) break;
    }
    if (d.open) e.target.disabled = false;
  };
}
