import { useLibrary } from "../asset-picker/project-use.js";
import { saveProjectMedia } from "../asset-picker/result-import.js";
/** View feature; receives a project-scoped public workspace context. */
export function createFeature(ctx) {
  const supportsAssetModes = () =>
    ctx.catalog?.asset_reference_modes?.includes("none");
  function useCustom(s) {
    if (supportsAssetModes()) s.asset_mode = "custom";
  }
  function assetModeLabel(s) {
    if (s.asset_mode === "none") return "不使用参考素材";
    if (s.asset_mode === "custom" || s.assets.length) return "本段指定素材";
    return s.index ? "默认沿用 P1 素材" : "P1 素材";
  }
  function assetModeControl(s) {
    if (!supportsAssetModes() || !s.index || ctx.project.mode === "swap")
      return "";
    return ctx.field(
      "本段参考素材",
      `<select data-asset-mode="${s.id}" aria-label="P${s.index + 1}素材引用方式">${ctx.opts(
        [
          ["auto", "默认沿用 P1（本段有素材时优先本段）"],
          ["custom", "只使用本段指定素材"],
          ["none", "不使用参考素材"],
        ],
        s.asset_mode || "auto",
      )}</select>`,
      "素材与声画续接分开控制。不使用素材仍可承接上一段；新场景需提供图片。已选文件始终保留。",
    );
  }
  function setAssetMode(sid, value) {
    const s = ctx.project.segments.find((x) => x.id === sid);
    if (
      !s ||
      !supportsAssetModes() ||
      !["auto", "custom", "none"].includes(value)
    )
      return;
    s.asset_mode = value;
    ctx.setDirty();
    ctx.renderEdit();
  }
  function localAssets(s) {
    if (s.asset_mode === "none") return [];
    const ids = [
      ...new Set([
        ...(s.assets.length
          ? s.assets
          : s.index && s.asset_mode !== "custom"
            ? ctx.project.segments[0].assets
            : []),
        ...(s.inherit_ids || []),
      ]),
    ];
    return ids
      .map((id) => ctx.project.asset_library.find((a) => a.id === id))
      .filter(Boolean);
  }
  function assetCard(a, s) {
    return `<div class="asset ${s.assets.includes(a.id) ? "" : "inherited"}">${a.kind === "image" ? `<img src="${ctx.esc(a.url)}" alt="${ctx.esc(a.name)}">` : a.kind === "audio" ? `<audio controls preload="none" src="${ctx.esc(a.url)}"></audio>` : ""}<h4>${ctx.esc(a.name)}</h4><small>${ctx.esc({ character: "角色", face: "脸部", costume: "服装", scene: "场景", palette: "色系", prop: "道具", voice: "音色参考" }[a.purpose] || a.purpose)} ${a.subject ? "· 角色" + ctx.esc(a.subject) : ""}</small>${a.duration ? `<small>${ctx.fmt(a.duration)}秒</small>` : ""}${s.assets.includes(a.id) || s.inherit_ids.includes(a.id) ? `<details class="asset-menu"><summary>管理素材</summary><button class="quiet" data-edit-asset="${a.id}" data-segment="${s.id}">修改用途/角色</button><button class="quiet danger" data-remove="${a.id}" data-segment="${s.id}">移除本段引用</button>${ctx.catalog.asset_library_version ? `<button type="button" class="quiet" data-library-save="${a.id}">保存到资产库</button>${a.library_reference?.root_asset===a.library_reference?.asset && a.library_reference ? `<button type="button" class="quiet" data-library-update="${a.id}" data-segment="${s.id}">检查库中版本</button>` : ""}` : ""}</details>` : "<small>来自P01</small>"}</div>`;
  }
  async function uploadAssets(el) {
    const files = Array.from(el.files),
      kind = el.dataset.upload,
      s = ctx.project.segments.find((x) => x.id === el.dataset.segment);
    if (!files.length) return;
    if (ctx.project.mode === "swap" && kind === "image" && files.length !== 1) {
      ctx.toast("换人模式每段使用一张角色参考图，请一次选择一张。");
      el.value = "";
      return;
    }
    if (
      s.index &&
      (s.asset_mode || "auto") === "auto" &&
      !s.assets.length &&
      !(await ctx.confirm(
        "本段开始使用自己的素材",
        "添加后将停止自动继承P01全部素材。需要保留某个角色/声音时，可以再点击“从P01沿用指定素材”。",
        "继续添加",
      ))
    ) {
      el.value = "";
      return;
    }
    let purpose = kind === "audio" ? "voice" : "character",
      subject = "1";
    const result = await assetInfo(kind);
    if (!result || ctx.session.disposed) return;
    ({ purpose, subject } = result);
    ctx.working = true;
    try {
      for (const f of files) {
        ctx.toast("正在上传 " + f.name);
        const fd = new FormData();
        fd.append("file", f);
        fd.append("kind", kind);
        fd.append("purpose", purpose);
        fd.append("subject", subject);
        const a = await ctx.api(
          `/projects/${ctx.project.id}/assets`,
          "POST",
          fd,
        );
        ctx.project.asset_library.push(a);
        if (ctx.project.mode === "swap" && kind === "image") {
          // Replace the active character reference; retain files and audio references.
          const keep = (id) =>
            ctx.project.asset_library.find((a) => a.id === id)?.kind !==
            "image";
          s.assets = s.assets.filter(keep);
          s.inherit_ids = (s.inherit_ids || []).filter(keep);
        }
        s.assets.push(a.id);
        useCustom(s);
        ctx.setDirty();
      }
      ctx.setDirty();
      ctx.renderProject();
      ctx.toast("素材已加入本段；进入制作时自动保存");
    } catch (e) {
      ctx.toast(e.message);
    } finally {
      ctx.working = false;
      ctx.syncDraftActions();
      el.value = "";
    }
  }
  function assetInfo(kind, initial = {}) {
    return new Promise((resolve) => {
      const d = ctx.modal(
        `<h2>这份素材用来做什么？</h2>${ctx.field(
          "用途",
          `<select id="asset-purpose">${ctx.opts(
            kind === "audio"
              ? [["voice", "只参考音色与说话方式"]]
              : [
                  ["character", "角色 / 同一角色多视图"],
                  ["face", "脸部特写"],
                  ["costume", "服装"],
                  ["scene", "场景"],
                  ["palette", "色系 / 风格"],
                  ["prop", "道具"],
                ],
            initial.purpose || (kind === "audio" ? "voice" : "character"),
          )}</select>`,
        )}${ctx.field("角色ID", `<input id="asset-subject" inputmode="numeric" value="${ctx.esc(initial.subject ?? "1")}">`, "同一个角色使用相同数字；第二个角色填写2。场景、色系和道具不需要角色ID。")}<div class="dialog-actions"><button id="asset-cancel">取消</button><button id="asset-ok" class="primary">确认素材信息</button></div>`,
      );
      const done = (x) => {
        d.close();
        resolve(x);
      };
      ctx.$("#asset-cancel").onclick = () => done(null);
      const syncSubject = () => {
        const needed = ["character", "face", "costume", "voice"].includes(
          ctx.$("#asset-purpose").value,
        );
        ctx.$("#asset-subject").disabled = !needed;
      };
      ctx.$("#asset-purpose").onchange = syncSubject;
      syncSubject();
      ctx.$("#asset-ok").onclick = () =>
        done({
          purpose: ctx.$("#asset-purpose").value,
          subject: ctx.$("#asset-subject").disabled
            ? ""
            : ctx.$("#asset-subject").value,
        });
      d.oncancel = (e) => {
        e.preventDefault();
        done(null);
      };
    });
  }
  async function editAsset(sid, aid) {
    const s = ctx.project.segments.find((x) => x.id === sid),
      a = ctx.project.asset_library.find((x) => x.id === aid),
      meta = await assetInfo(a.kind, a);
    if (!meta || ctx.session.disposed) return;
    ctx.working = true;
    try {
      const next = await ctx.api(
        `/projects/${ctx.project.id}/assets/${aid}/version`,
        "POST",
        meta,
      );
      ctx.project.asset_library.push(next);
      s.assets = s.assets.map((x) => (x === aid ? next.id : x));
      s.inherit_ids = s.inherit_ids.map((x) => (x === aid ? next.id : x));
      ctx.setDirty();
      ctx.renderProject();
    } catch (e) {
      ctx.toast(e.message);
    } finally {
      ctx.working = false;
    }
  }
  async function bindAsset(sid, aid) {
    const s = ctx.project.segments.find((item) => item.id === sid);
    if (!s || s.assets.includes(aid)) return;
    if (
      s.index &&
      (s.asset_mode || "auto") === "auto" &&
      !s.assets.length &&
      !(await ctx.confirm(
        "为本段指定素材",
        "绑定后，本段将使用指定素材，停止自动沿用P01全部素材。需要其他素材时可继续绑定或从P01沿用。",
        "绑定到本段",
      ))
    )
      return;
    if (ctx.session.disposed) return;
    s.assets.push(aid);
    useCustom(s);
    ctx.setDirty();
    ctx.renderEdit();
  }
  async function removeAsset(sid, aid) {
    const s = ctx.project.segments.find((x) => x.id === sid);
    const asset = ctx.project.asset_library.find((a) => a.id === aid);
    if (
      asset?.library_reference?.purpose === "character" &&
      asset.owners?.length
    ) {
      const introduced = new Set(
        ctx.project.asset_library
          .filter((a) =>
            a.owners?.some((owner) => asset.owners.includes(owner)),
          )
          .map((a) => a.id),
      );
      if (
        !(await ctx.confirm(
          "移除这位角色及其本次绑定",
          "将移除该角色此次带入的形象、声线等引用。其他角色单独引用的共用素材保留；库内资产和已有文件不变。",
          "移除本段角色包",
        ))
      )
        return;
      s.assets = s.assets.filter((id) => !introduced.has(id));
      s.inherit_ids = s.inherit_ids.filter((id) => !introduced.has(id));
      s.asset_mode =
        s.assets.length || s.inherit_ids.length ? "custom" : "none";
      ctx.setDirty();
      ctx.renderProject();
      return;
    }
    if (
      !supportsAssetModes() &&
      s.index &&
      s.assets.length === 1 &&
      s.assets[0] === aid &&
      !(await ctx.confirm(
        "恢复P01素材继承",
        "移除最后一个本段上传引用后，空素材片段会继承P01。",
        "移除并恢复继承",
      ))
    )
      return;
    s.assets = s.assets.filter((x) => x !== aid);
    s.inherit_ids = s.inherit_ids.filter((x) => x !== aid);
    if (supportsAssetModes())
      s.asset_mode =
        s.index && !s.assets.length && !s.inherit_ids.length
          ? "none"
          : "custom";
    ctx.setDirty();
    ctx.renderProject();
  }
  function inheritDialog(sid) {
    const s = ctx.project.segments.find((x) => x.id === sid),
      a = ctx.project.segments[0].assets
        .map((id) => ctx.project.asset_library.find((a) => a.id === id))
        .filter(Boolean);
    const d = ctx.modal(
      `<h2>从P01沿用</h2><p>仅勾选需要加入本段的素材。</p>${a.map((x) => `<label class="check"><input type="checkbox" value="${x.id}" ${s.inherit_ids.includes(x.id) ? "checked" : ""}>${ctx.esc(x.name)}</label>`).join("") || "<p>P01还没有素材。</p>"}<button id="inherit-save" class="primary">应用选择</button>`,
    );
    ctx.$("#inherit-save").onclick = () => {
      s.inherit_ids = [
        ...ctx.$("#dialog-content").querySelectorAll("input:checked"),
      ].map((x) => x.value);
      if (supportsAssetModes())
        s.asset_mode =
          s.assets.length || s.inherit_ids.length ? "custom" : "none";
      ctx.setDirty();
      d.close();
      ctx.renderProject();
    };
  }
  return {
    saveProjectMedia: (options) => saveProjectMedia(ctx, options),
    useLibrary: (sid, target) => useLibrary(ctx, sid, target),
    updateLibraryAsset: (sid, asset) =>
      useLibrary(ctx, sid, "references", asset),
    assetModeLabel,
    assetModeControl,
    setAssetMode,
    localAssets,
    assetCard,
    uploadAssets,
    assetInfo,
    editAsset,
    removeAsset,
    inheritDialog,
    bindAsset,
  };
}
