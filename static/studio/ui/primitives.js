export const $ = (selector) => document.querySelector(selector);
export const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
export const fmt = (n) =>
  Number(n)
    .toFixed(3)
    .replace(/\.?0+$/, "");
export const bytes = (n) =>
  n > 1e9
    ? (n / 1e9).toFixed(2) + " GB"
    : n > 1e6
      ? (n / 1e6).toFixed(1) + " MB"
      : (n / 1024).toFixed(1) + " KB";
export const LABELS = {
  draft: "待编排",
  ready: "可生成",
  preparing: "准备素材",
  queued: "排队中",
  generating: "生成中",
  needs_review: "待审核",
  accepted: "已接受",
  done: "自动完成",
  assembling: "合成中",
  complete: "已完成",
  failed: "失败",
  interrupted: "已中断",
  stale: "已过期",
};
export const status = (s) =>
  `<span class="badge ${["failed", "interrupted"].includes(s) ? "bad" : s === "needs_review" ? "warn" : ""}">${esc(LABELS[s] || s)}</span>`;
export const opts = (values, chosen) =>
  values
    .map((x) => {
      const [v, l] = Array.isArray(x) ? x : [x, x];
      return `<option value="${esc(v)}" ${String(v) === String(chosen) ? "selected" : ""}>${esc(l)}</option>`;
    })
    .join("");
export const field = (label, html, help = "") =>
  `<label class="field"><span>${label}</span>${html}${help ? `<small>${help}</small>` : ""}</label>`;
let modalEpoch=0;
export const modalTicket=()=>{const epoch=modalEpoch;return ()=>epoch===modalEpoch;};
let toastTimer;
export function toast(message) {
  clearTimeout(toastTimer);
  $("#toast").textContent = message;
  $("#toast").className = "show";
  toastTimer = setTimeout(() => {
    $("#toast").className = "";
  }, 5000);
}
export function modal(content) {
  modalEpoch++;
  const d = $("#dialog");
  if (d.open) cancelModal();
  const trigger = document.activeElement;
  d.onclose = () => {
    if (d.open) return;
    const target = trigger?.id ? document.getElementById(trigger.id) : trigger;
    if (target?.isConnected) target.focus({ preventScroll: true });
  };
  d.oncancel = null;
  d.onkeydown = (event) => {
    if (event.key !== "Tab") return;
    const stops = [
      ...d.querySelectorAll(
        'button,input:not([type="hidden"]),textarea,select,a[href],summary,[tabindex="0"]',
      ),
    ].filter((el) => !el.disabled && el.getClientRects().length);
    const first = stops[0],
      last = stops.at(-1);
    if (!first) {
      event.preventDefault();
      return;
    }
    const active = document.activeElement;
    if (event.shiftKey && (active === first || active === d)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && (active === last || active === d)) {
      event.preventDefault();
      first.focus();
    }
  };
  $("#dialog-content").innerHTML =
    `<button class="dialog-close" aria-label="关闭对话框" type="button">×</button>${content}`;
  $(".dialog-close").onclick = cancelModal;
  if (!d.open) d.showModal();
  return d;
}
/** Resolve the active dialog's cancellation contract, including route disposal. */
export function cancelModal() {
  modalEpoch++;
  const d = $("#dialog");
  if (!d?.open) return;
  const event = new Event("cancel", { cancelable: true });
  if (d.dispatchEvent(event)) d.close();
}
/** Keep delayed local-task updates attached to their own dialog content. */
export function scopedModal(content) {
  const dialog = modal(`<div data-scoped-modal>${content}</div>`);
  const scope = dialog.querySelector("[data-scoped-modal]");
  return new Proxy(dialog, {
    get(target, key) {
      if (key === "open") return target.open && scope.isConnected;
      if (key === "querySelector" || key === "querySelectorAll")
        return scope[key].bind(scope);
      if (key === "close")
        return () => {
          if (scope.isConnected) target.close();
        };
      const value = Reflect.get(target, key, target);
      return typeof value === "function" ? value.bind(target) : value;
    },
    set(target, key, value) {
      if (scope.isConnected) Reflect.set(target, key, value, target);
      return true;
    },
  });
}
export function confirm(title, message, yes = "确认应用") {
  return new Promise((resolve) => {
    const d = modal(
      `<div class="dialog-heading"><span class="eyebrow">CHANGE REVIEW</span><h2>${esc(title)}</h2></div><div class="notice">${esc(message)}</div><div class="dialog-actions"><button id="no">取消</button><button id="yes" class="primary">${esc(yes)}</button></div>`,
    );
    const done = (value) => {
      d.oncancel = null;
      d.close();
      resolve(value);
    };
    $("#no").onclick = () => done(false);
    $("#yes").onclick = () => done(true);
    d.oncancel = (e) => {
      e.preventDefault();
      done(false);
    };
  });
}
export function download(value, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
export const elapsed = (start, end) => {
  const n = Math.max(0, Math.floor((end || Date.now() / 1000) - Number(start)));
  return `${Math.floor(n / 3600) ? Math.floor(n / 3600) + "小时 " : ""}${Math.floor((n % 3600) / 60)}分 ${String(n % 60).padStart(2, "0")}秒`;
};
export function updateClocks(scope = document) {
  scope
    .querySelectorAll("[data-clock]")
    .forEach(
      (e) =>
        (e.textContent = elapsed(
          e.dataset.clock,
          e.dataset.clockEnd ? Number(e.dataset.clockEnd) : null,
        )),
    );
}
export function watchClocks(scope) {
  const tick = () => updateClocks(scope);
  tick();
  const timer = setInterval(tick, 1000);
  return () => clearInterval(timer);
}

/** A queued close event from an older dialog must not close a newly opened scope. */
export function onScopedClose(dialog, callback) {
  const closed = () => { if (!dialog.open) { dialog.removeEventListener('close', closed); callback(); } };
  dialog.addEventListener('close', closed);
  return () => dialog.removeEventListener('close', closed);
}
