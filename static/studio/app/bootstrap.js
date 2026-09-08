import {closePromptEditor} from '../features/prompt-library/editor.js';
import { api, readLegacyProject } from "../core/api-client.js";
import { assertImageCatalog } from "../core/image-catalog.js";
import { mountTaskCenter } from "../features/task-center/index.js";
import * as ui from "../ui/primitives.js";
import { getMode, listModes, setImageAssetsEnabled, setAssemblyEnabled } from "./mode-registry.js";
import { renderHome, projectCard } from "../pages/home.js";
import { createFeature as archiveFeature } from "../pages/archive.js";
import {confirmLeave} from '../ui/choice-dialog.js';

const root = ui.$("#app");
let workspace = null,
  epoch = 0,
  routeController = null,
  catalog = null,
  leaving = false;
let activeHash=location.hash||"#/";
const go = (hash) => {
  location.hash = hash;
};
async function createProject(modeId) {
  const mode = getMode(modeId);
  const d = ui.scopedModal(
    `<div class="dialog-heading"><span class="eyebrow">${mode.code} · NEW PRODUCTION</span><h2>${mode.name}</h2><p>${mode.description}</p></div><form id="new-form">${ui.field("项目名称", '<input name="name" required maxlength="120" placeholder="给这个故事一个名字" autofocus>')}${mode.kind === "image" ? ui.field("编辑工具", '<select name="submode"><option value="single">单图编辑</option><option value="dual">双图编辑</option><option value="region">局部重绘／移除</option><option value="outpaint">图像扩展</option><option value="text">文生图</option></select>') : ""}${modeId !== "swap" && mode.kind !== "image" && mode.kind !== "assembly" ? ui.field("计划总时长（秒）", '<input name="duration" type="number" min="1" max="3600" step=".01" value="15" required>', "每15秒一个片段；30秒写两段提示词。") : ""}<p class="helper">创建后进入${mode.entry}，准备完成后再生成${mode.kind === "image" ? "图片" : "视频"}。</p><div class="dialog-actions"><button type="button" id="close-new">取消</button><button class="primary">开始创作 →</button></div></form>`,
  );
  let creating=false;
  d.oncancel=e=>{if(creating)e.preventDefault();};
  d.querySelector("#close-new").onclick=()=>{if(!creating)d.close();};
  ui.$("#new-form").onsubmit = async (e) => {
    e.preventDefault();
    if(creating||!d.open)return;creating=true;e.target.dataset.operationPending='true';
    const button = e.target.querySelector(".primary");
    button.disabled = true;
    try {
      if(mode.kind==='image'&&e.target.elements.submode?.value==='text'){
        const current=assertImageCatalog(await api('/image-projects/catalog'));
        if(current.text_to_image_version!==1)throw new Error('当前后台尚未加载文生图，请重启导演台后刷新页面。');
      }
      const p = await api("/projects", "POST", {
        mode: modeId,
        submode: e.target.elements.submode?.value,
        name: e.target.elements.name.value,
        duration: Number(e.target.elements.duration?.value || 30),
      });
      if(!d.open)return;
      d.close();
      go("/p/" + p.id);
    } catch (error) {
      if(d.open)ui.toast(error.message);
      button.disabled = false;
    } finally {
      creating=false;delete e.target.dataset.operationPending;
    }
  };
}
async function route() {
  if (leaving) {
    if(workspace)history.replaceState(null,'','#/p/'+workspace.session.project.id);
    return;
  }
  const current = ++epoch,
    hash = location.hash || "#/";
  if(document.querySelector('dialog[open] [data-prompt-form]')){
    history.replaceState(null,'',activeHash);
    leaving=true;
    let proceed;try{proceed=await closePromptEditor();}finally{leaving=false;}
    if(!proceed)return;
    history.replaceState(null,'',hash);
  }
  if (workspace?.session.working || workspace?.session.actionPending) {
    ui.toast("当前操作正在处理，请稍候再离开");
    history.replaceState(null, "", "#/p/" + workspace.session.project.id);
    return;
  }
  if (workspace && document.querySelector('dialog[open] .production-settings')) {
    ui.toast('请先应用、保存或取消制作参数，再离开当前项目。');
    history.replaceState(null, "", "#/p/" + workspace.session.project.id);
    return;
  }
  if (workspace?.session.dirty) {
    history.replaceState(null,'','#/p/'+workspace.session.project.id);
    leaving=true;
    let choice;
    try {choice=await confirmLeave({save:()=>workspace.saveBeforeLeave()});}
    finally {leaving=false;}
    if (choice !== 'save' && choice !== 'discard') return;
    history.replaceState(null,'',hash);
  }
  if (current !== epoch) return;
  activeHash=hash;
  workspace?.dispose();
  workspace = null;
  routeController?.abort();
  routeController = new AbortController();
  ui.cancelModal();
  root.className = "page";
  root.innerHTML = '<div class="loader" role="status">正在打开创作空间…</div>';
  window.scrollTo({ top: 0, left: 0, behavior: "instant" });
  const signal = routeController.signal;
  try {
    if (current !== epoch) return;
    const match = hash.match(/^#\/p\/([a-zA-Z0-9-]+)(?:[/?].*)?$/);
    if (match) {
      const p = await api("/projects/" + match[1], "GET", undefined, signal);
      if(p.kind==='assembly'){
        const directory=await api('/assembly/catalog','GET',undefined,signal);
        const {mountWorkspace}=await import('../modes/video-assembly/workspace.js');
        if(current!==epoch)return;
        workspace=mountWorkspace(root,p,directory);return;
      }
      if (p.kind === 'image') {
        const imageCatalog = await api('/image-projects/catalog', 'GET', undefined, signal);
        assertImageCatalog(imageCatalog,p.tasks?.some(t=>t.submode==='text')?'text':undefined);
        const {mountWorkspace} = await import('./image-workspace-controller.js');
        if (current !== epoch) return;
        workspace = mountWorkspace(root, p, imageCatalog);
        return;
      }
      const directory = catalog || await api("/catalog", "GET", undefined, signal);
      catalog = directory;
      if(Number(directory.input_contract_version||0)<2 || Number(p.input_contract_version||0)<2)
        throw new Error('前后端版本尚未匹配。请完成工作台更新后刷新页面；现有项目与生成文件保留。');
      const definition = getMode(p.mode);
      if (!definition)
        throw new Error(
          `当前版本尚未安装“${p.mode}”模式，项目和原结果仍保留。`,
        );
      const [mode, { mountWorkspace }] = await Promise.all([
        definition.load(),
        import("./workspace-controller.js"),
      ]);
      if (current !== epoch) return;
      workspace = mountWorkspace(root, p, catalog, definition, mode);
    } else if (/^#\/assets(?:[/?]|$)/.test(hash)) {
      const { mountLibrary } = await import("../pages/asset-library/index.js");
      if (current !== epoch) return;
      await mountLibrary(root, hash, signal);
    } else if (hash === "#/prompts") {
      const {mountPromptLibrary}=await import("../pages/prompt-library/index.js");
      if(current!==epoch)return;
      await mountPromptLibrary(root,signal);
    } else if (hash === "#/archive") {
      const context = {
        ...ui,
        api: (path, method, body) => api(path, method, body, signal),
        readLegacyProject: (id) => readLegacyProject(id, signal),
        isCurrent: () => !signal.aborted && current === epoch,
        go,
        projectCard,
        MODES: Object.fromEntries(listModes().map((m) => [m.id, m])),
        tab: "edit",
      };
      Object.assign(context, archiveFeature(context));
      await context.archive();
    } else {
      const data = await api("/projects", "GET", undefined, signal);
      if (current !== epoch) return;
      setImageAssetsEnabled(data.image_assets_enabled);
      setAssemblyEnabled(data.assembly_contract_version);
      renderHome(root, data.projects, createProject);
    }
  } catch (e) {
    if (current !== epoch || e.name === "AbortError") return;
    root.innerHTML = `<div class="panel empty"><h2>暂时无法打开</h2><p>${ui.esc(e.message)}</p><a class="btn" href="#/">回到首页</a></div>`;
  }
}
async function health() {
  try {
    const h = await api("/health");
    setImageAssetsEnabled(h.image_assets_enabled);
    setAssemblyEnabled(h.assembly_contract_version);
    const imageMismatch = h.image_assets_enabled && h.image_parameter_contract_version !== 1;
    ui.$("#health").textContent = imageMismatch ? "网站后台待重启" : h.local_server_version
      ? h.busy
        ? "制作任务进行中"
        : "本地工作台就绪"
      : h.comfy_connected
        ? "ComfyUI 已连接"
        : "ComfyUI 未连接";
    ui.$("#health").className =
      "badge " + (!imageMismatch && (h.local_server_version || h.comfy_connected) ? "" : "warn");
  } catch {
    ui.$("#health").textContent = "工作台连接中断";
  }
}
window.addEventListener("hashchange", route);
window.addEventListener("beforeunload", (e) => {
  if (workspace?.session.dirty || workspace?.session.working || workspace?.session.actionPending || document.querySelector('dialog[open] [data-parameter-dirty="true"],dialog[open] [data-operation-pending]')) {
    e.preventDefault();
    e.returnValue = "";
  }
});
document.addEventListener(
  "error",
  (e) => {
    if (e.target instanceof HTMLImageElement) {
      e.target.classList.add("image-unavailable");
      e.target.alt = e.target.alt || "图片暂时无法显示";
    }
  },
  true,
);
document.addEventListener("visibilitychange", () => {
  document.documentElement.classList.toggle("page-hidden", document.hidden);
});
document.addEventListener(
  "play",
  (e) =>
    document.querySelectorAll("audio,video").forEach((el) => {
      if (el !== e.target) el.pause();
    }),
  true,
);
mountTaskCenter();
await health();
await route();
setInterval(health, 10000);
