import {updateStatusRegion} from '../../ui/status-region.js';
import * as ui from "../../ui/primitives.js";
import {
  libraryApi,
  followTask,
} from "../../features/asset-picker/library-client.js";

export function mountMediaTools(root, asset, media, signal) {
  const slot = root.querySelector("#library-derive-tools");
  if (!slot) return;
  const kind = media.meta.kind;
  slot.innerHTML =
    kind === "image"
      ? `<details><summary>裁切、缩放与旋转</summary><p class="helper">每次处理创建新资产，原始字节和透明通道保持独立。</p><form id="derive-image"><div class="library-toolbar">${[
          ["x", "裁切X", 0],
          ["y", "裁切Y", 0],
          ["crop_width", "裁切宽度", media.meta.width],
          ["crop_height", "裁切高度", media.meta.height],
          ["width", "输出宽度", media.meta.width],
          ["height", "输出高度（留空等比）", ""],
        ]
          .map(([key, label, value]) =>
            ui.field(
              label,
              `<input name="${key}" type="number" min="0" value="${value}">`,
            ),
          )
          .join(
            "",
          )}${ui.field("顺时针旋转", `<select name="rotation">${ui.opts([0, 90, 180, 270], 0)}</select>`)}</div><button class="primary">另存处理后的图片</button></form></details>`
      : ["video", "audio"].includes(kind)
        ? `<div class="library-toolbar">${kind === "video" ? '<button data-derive="frame">抽取当前帧</button><button data-derive="first">抽取首帧</button><button data-derive="last">抽取尾帧</button><button data-derive="clip">所选视频区间另存</button>' : ""}${media.meta.has_audio ? '<button data-derive="audio">所选声音区间另存</button>' : ""}<button data-derive="convert">生成兼容播放副本</button></div><p class="helper">派生文件会作为新资产入库，保留原视频时间区间和来源；不改变原件或已有项目。</p>`
        : "";
  async function submit(operation, params) {
    const d = ui.scopedModal(
      '<h2>处理本地媒体</h2><div id="derive-task" role="status">正在登记处理任务…</div><div class="dialog-actions"><button id="derive-hide">收起</button></div>',
    );
    d.querySelector("#derive-hide").onclick = () => d.close();
    try {
      const task = await libraryApi(
        "/derive",
        "POST",
        {
          asset: asset.id,
          version: asset.snapshot.id,
          media: media.id,
          operation,
          params,
        },
        signal,
      );
      const result = await followTask(
        task,
        (t) => {
          if (d.open)
            updateStatusRegion(d.querySelector("#derive-task"),`<p>${ui.esc(t.note)}</p><progress max="1" value="${t.progress}"></progress>`);
        },
        signal,
      );
      if (d.open)
        d.querySelector("#derive-task").innerHTML =
          `<p>已另存为独立资产，原件保留。</p><a class="btn primary" href="#/assets/${result.id}">查看派生素材</a>`;
    } catch (error) {
      if (d.open) d.querySelector("#derive-task").textContent = error.message;
    }
  }
  slot.querySelector("#derive-image")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const params = Object.fromEntries(
      [...new FormData(e.target)].map(([k, v]) => [
        k,
        v === "" ? null : Number(v),
      ]),
    );
    void submit("image_transform", params);
  });
  slot.querySelectorAll("[data-derive]").forEach(
    (button) =>
      (button.onclick = () => {
        let operation = button.dataset.derive;
        const start = Number(root.querySelector("#library-in").value),
          end = Number(root.querySelector("#library-out").value);
        let params = { start, end };
        if (operation === "frame")
          params = { start: root.querySelector(".library-player").currentTime };
        if (operation === "first") {
          operation = "frame";
          params = { start: 0 };
        }
        if (operation === "last") {
          operation = "frame";
          params = { position: "last" };
        }
        if (operation === "convert")
          params = { start: 0, end: media.meta.duration };
        void submit(operation, params);
      }),
  );
}
