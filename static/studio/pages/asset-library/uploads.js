import {updateStatusRegion} from '../../ui/status-region.js';
import * as ui from "../../ui/primitives.js";
import {
  uploadToLibrary,
  followTask,
} from "../../features/asset-picker/library-client.js";

export function showUploads(files, metadata, after, target = {}) {
  const controller = new AbortController();
  let active = false;
  const state = files.map((file) => ({
    file,
    status: "待上传",
    progress: 0,
    done: false,
  }));
  const total = files.reduce((n, file) => n + file.size, 0);
  const dialog = ui.scopedModal(
    `<h2>导入资产</h2><p>共 ${files.length} 项，原文件合计 ${ui.bytes(total)}。托管复制和暂存通常需要约两倍空间。</p><div class="library-upload-rows"></div><div class="dialog-actions"><button data-upload-close>收起</button><button class="primary" data-upload-start>开始导入</button></div><p class="helper">原件独立保存，生成PROMPT和设定作为资料。单项失败可以重试，已完成的项目不会重复导入。</p>`,
  );
  const rows = dialog.querySelector(".library-upload-rows");
  function draw() {
    if (!dialog.open) return;
    updateStatusRegion(rows,state
      .map(
        (row,index) =>
          `<div class="library-upload-row" data-view-key="upload:${index}"><strong>${ui.esc(row.file.name)}</strong><small>${ui.esc(row.status)}</small><progress max="1" value="${row.progress}" aria-label="${ui.esc(row.file.name)}导入进度"></progress></div>`,
      )
      .join(""));
  }
  function close() {
    controller.abort();
    dialog.close();
    void after?.();
  }
  dialog.oncancel = (event) => {
    event.preventDefault();
    close();
  };
  dialog.querySelector("[data-upload-close]").onclick = close;
  dialog.querySelector("[data-upload-start]").onclick = async (event) => {
    if (active) return;
    active = true;
    event.target.disabled = true;
    for (const row of state.filter((r) => !r.done)) {
      if (controller.signal.aborted) break;
      try {
        let task = row.task;
        if (!task)
          task = row.task = await uploadToLibrary(
            row.file,
            metadata,
            (value, note) => {
              row.progress = value * 0.6;
              row.status = note;
              draw();
            },
            controller.signal,
            target,
          );
        if (["failed", "interrupted"].includes(task.state)) {
          const { libraryApi } =
            await import("../../features/asset-picker/library-client.js");
          task = row.task = await libraryApi(
            `/tasks/${task.id}/retry`,
            "POST",
            {},
          );
        }
        await followTask(
          task,
          (current) => {
            row.task = current;
            row.progress = 0.6 + 0.4 * current.progress;
            row.status = current.note;
            draw();
          },
          controller.signal,
        );
        row.done = true;
        row.status = "已入库";
        row.progress = 1;
      } catch (error) {
        row.status =
          error.name === "AbortError"
            ? "上传已暂停，可再次选择同文件续传"
            : error.message;
      }
      draw();
    }
    active = false;
    if (dialog.open) {
      event.target.disabled = false;
      event.target.textContent = state.every((r) => r.done)
        ? "全部完成"
        : "重试未完成项";
      event.target.disabled = state.every((r) => r.done);
    }
    void after?.();
  };
  draw();
}
