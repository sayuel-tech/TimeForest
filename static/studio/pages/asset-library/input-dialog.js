import * as ui from "../../ui/primitives.js";

export function simpleInput(title, choices) {
  return new Promise((resolve) => {
    const d = ui.scopedModal(
      `<h2>${ui.esc(title)}</h2><form id="library-value-form">${choices ? `<select name="value" required aria-label="${ui.esc(title)}">${ui.opts([["", "请选择"], ...choices], "")}</select>` : `<input name="value" required maxlength="160" aria-label="${ui.esc(title)}">`}<div class="dialog-actions"><button type="button" id="library-value-cancel">取消</button><button class="primary">确认</button></div></form>`,
    );
    const done = (value) => {
      d.close();
      resolve(value);
    };
    d.oncancel = (e) => {
      e.preventDefault();
      done(null);
    };
    d.querySelector("#library-value-cancel").onclick = () => done(null);
    d.querySelector("form").onsubmit = (e) => {
      e.preventDefault();
      done(e.target.elements.value.value.trim());
    };
  });
}
