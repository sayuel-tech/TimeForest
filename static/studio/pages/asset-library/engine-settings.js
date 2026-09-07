import * as ui from "../../ui/primitives.js";
import { api } from "../../core/api-client.js";

export async function openLauncher(signal) {
  try {
    const state = await api("/engine/launcher", "GET", undefined, signal);
    if (signal?.aborted) return;
    const d = ui.scopedModal(
      `<h2>按需启动生成引擎</h2><p>日常资产管理与编排不启动ComfyUI。只有生成时引擎未连接，才会按你保存的路径启动。</p><form id="launcher-form">${ui.field("ComfyUI使用的Python程序", `<input name="python" value="${ui.esc(state.python || "")}" placeholder="Python可执行文件的完整路径">`)}${ui.field("ComfyUI启动脚本", `<input name="script" value="${ui.esc(state.script || "")}" placeholder="实际ComfyUI目录中的 main.py">`)}${ui.field("附加启动参数", `<textarea name="args">${ui.esc(JSON.stringify(state.args || []))}</textarea>`, '字符串数组，例如 ["--port", "8188"]。不填写终端命令，不会安装模型。')}<label><input type="checkbox" name="enabled" ${state.enabled ? "checked" : ""}>允许生成时启动上述程序</label><p class="helper">${ui.esc(state.note)}。保存只核验路径和文件，不会启动程序；引擎升级后需要重新核对脚本。</p><div class="dialog-actions"><button type="button" id="launcher-cancel">取消</button><button class="primary">核对并保存</button></div><p id="launcher-note" role="status"></p></form>`,
    );
    d.querySelector("#launcher-cancel").onclick = () => d.close();
    d.querySelector("form").onsubmit = async (e) => {
      e.preventDefault();
      const f = e.target,
        button = f.querySelector(".primary");
      button.disabled = true;
      try {
        const saved = await api(
          "/engine/launcher",
          "POST",
          {
            python: f.elements.python.value,
            script: f.elements.script.value,
            args: JSON.parse(f.elements.args.value),
            enabled: f.elements.enabled.checked,
          },
          signal,
        );
        d.querySelector("#launcher-note").textContent = saved.note;
        ui.toast("启动设置已保存，本次没有启动生成引擎");
      } catch (error) {
        d.querySelector("#launcher-note").textContent = error.message;
      } finally {
        button.disabled = false;
      }
    };
  } catch (error) {
    if (!signal?.aborted) ui.toast(error.message);
  }
}
