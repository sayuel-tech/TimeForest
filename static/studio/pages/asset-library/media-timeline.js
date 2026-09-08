import * as ui from "../../ui/primitives.js";

/** Preview-only in/out marks and looping; this never changes the original media. */
export function bindTimeline(root,media) {
    const player = root.querySelector(".library-player");
    if (!player) return;
    const input = root.querySelector("#library-in"),
      output = root.querySelector("#library-out");
    let loop = false;
    const range = () => {
      const start = Number(input.value),
        end = Number(output.value);
      if (
        !Number.isFinite(start) ||
        !Number.isFinite(end) ||
        start < 0 ||
        end <= start ||
        end > media.meta.duration + 0.01
      )
        throw new Error("请选择有效的入点与出点");
      return { start, end };
    };
    root.querySelector("#mark-in").onclick = () =>
      (input.value = ui.fmt(player.currentTime));
    root.querySelector("#mark-out").onclick = () =>
      (output.value = ui.fmt(player.currentTime));
    root.querySelector("#loop-range").onclick = async (e) => {
      try {
        const r = range();
        loop = !loop;
        e.target.setAttribute("aria-pressed", String(loop));
        e.target.textContent = loop ? "停止循环" : "循环选段";
        if (loop) {
          player.currentTime = r.start;
          await player.play();
        }
      } catch (error) {
        ui.toast(error.message);
      }
    };
    player.ontimeupdate = () => {
      if (loop) {
        try {
          const r = range();
          if (player.currentTime >= r.end || player.currentTime < r.start)
            player.currentTime = r.start;
        } catch {
          loop = false;
        }
      }
    };
    player.onended = () => {
      if (loop) {
        player.currentTime = Number(input.value);
        void player.play().catch(() => {});
      }
    };
  }
