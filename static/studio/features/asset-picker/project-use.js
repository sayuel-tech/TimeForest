import {referencePurposes} from '../../ui/reference-metadata.js';
import * as ui from "../../ui/primitives.js";
import { pickLibraryAsset } from "./index.js";
import { libraryApi, followTask } from "./library-client.js";
import { mediaSummary } from "./media-view.js";

const purposes = [...referencePurposes('image'),...referencePurposes('audio'),
  ['accessory','饰品（需适配）'],['control','控制参考（需适配）'],['texture','材质（需适配）']];

/** Preview without saving; confirm the current draft and references as one change. */
export async function useLibrary(
  ctx,
  segmentId,
  target = "references",
  updateAsset = null,
) {
  try {
    await ctx.commands.perform(async () => {
      const item = updateAsset
        ? await libraryApi("/assets/" + updateAsset.library_reference.asset)
        : await pickLibraryAsset({
            signal:ctx.session.controller.signal,
            kind: target === "source" ? "video" : "",
            title:
              target === "source" ? "选择参考表演视频" : "选择角色与参考素材",
          });
      if (!item || ctx.session.disposed) return;
      if(ctx.session.previewPending)throw new Error('片段预览尚未完成，请稍候再添加素材；当前草稿保留。');
      const capabilities=await libraryApi('/catalog','GET',undefined,ctx.session.controller.signal);
      if(ctx.session.dirty&&capabilities.asset_import_draft_version!==1)throw new Error('后台尚未加载素材与草稿一起确认的功能，请先保存编辑并在任务结束后重启导演台。');
      if(ctx.session.disposed)return;
      if (updateAsset && item.version === updateAsset.library_reference.version)
        return ui.toast("本段已经使用这个资产的当前版本");
      const owner = updateAsset?.owners?.[0] || crypto.randomUUID();
      const bundle = await libraryApi(
        `/assets/${item.id}/bindings?version=${item.version}&owner=${owner}`,
        "GET",
        undefined,
        ctx.session.controller.signal,
      );
      const segment = ctx.project.segments.find((s) => s.id === segmentId);
      const prior = segment ? ctx.localAssets(segment) : [];
      const used = new Set(prior.map((a) => Number(a.subject)).filter(Boolean));
      const suggested =
        item.kind === "audio"
          ? prior.find((a) => a.subject)?.subject || "1"
          : String(
              Array.from({ length: 99 }, (_, i) => i + 1).find(
                (n) => !used.has(n),
              ) || 1,
            );
      const selections = Object.fromEntries(
        bundle.entries.map((e) => [
          e.key,
          {
            selected: e.selected,
            media:
              target === "source"
                ? e.media.find((m) => m.meta.kind === "video")?.id ||
                  e.selected_media
                : e.selected_media,
            purpose: e.purpose,
          },
        ]),
      );
      const applied = await selectionDialog(ctx, bundle, prior, {
        asset: item.id,
        version: item.version,
        owner,
        segment: segmentId,
        target,
        revision: ctx.project.revision,
        ...(ctx.session.dirty?{draft:{...structuredClone(ctx.project),removed_drafts:structuredClone(ctx.session.draftArchive)}}:{}),
        subject: updateAsset?.subject || suggested,
        entries: selections,
        from_version: updateAsset?.library_reference.version,
        replace: updateAsset
          ? prior.filter((a) => a.owners?.includes(owner)).map((a) => a.id)
          : [],
      });
      if (applied && !ctx.session.disposed) {
        await ctx.session.reload();
        if (applied.source_asset) {
          ctx.tab = "source";
          ctx.renderProject();
          await ctx.commands.submitSource(applied.source_asset, "edit");
        }
      }
    });
  } catch (error) {
    if (!ctx.session.disposed) ui.toast(error.message);
  }
}

export function selectionDialog(ctx, bundle, prior, data) {
  return new Promise((resolve) => {
    let pending = false,
      plan = null,
      done = false;
    const entries =
      data.target === "source" ? bundle.entries.slice(0, 1) : bundle.entries;
    const d = ui.scopedModal(
      `<div class="library-use"><span class="eyebrow">REFERENCE SELECTION</span><h2>${data.from_version ? "更新到库中当前版本" : "确认本次引用"}</h2>${data.from_version ? `<p>旧版本 ${ui.esc(data.from_version.slice(0, 8))} → 新版本 ${ui.esc(data.version.slice(0, 8))}。下方列出新媒体和绑定；本段同一绑定包的旧引用已勾选替换，可逐项调整。其他角色不受影响。</p>` : ""}<p>绑定媒体会一起列出，可取消或选择备选。资料PROMPT和设定不进入制作。</p>${entries
        .map(
          (entry) =>
            `<div class="library-binding" data-entry="${entry.key}"><label><input type="checkbox" data-selected ${data.entries[entry.key].selected ? "checked" : ""}>${ui.esc(entry.name)}</label><small>固定版本 ${ui.esc(entry.version.slice(0, 8))}</small><select data-media aria-label="${ui.esc(entry.name)}使用媒体">${ui.opts(
              entry.media.map((m) => [
                m.id,
                (m.role === "primary" ? "主媒体" : "备选") +
                  " · " +
                  mediaSummary(m),
              ]),
              data.entries[entry.key].media,
            )}</select>${data.target === "source" ? "" : `<select data-purpose aria-label="${ui.esc(entry.name)}用途">${ui.opts(purposes, entry.purpose)}</select>`}</div>`,
        )
        .join("")}${
        data.target === "source"
          ? `<div class="split">${ui.field("从第几秒开始", '<input id="use-start" type="number" min="0" step=".001" value="0">')}${ui.field("到第几秒结束（留空使用完整视频）", '<input id="use-end" type="number" min="0" step=".001">')}</div>`
          : `${ui.field("本次角色编号", `<input id="use-subject" type="number" min="1" max="99" value="${data.subject}">`, "绑定声线与角色使用相同编号；独立选择声音时请对应已存在的角色。")}${prior.length ? `<details ${ctx.project.mode === "swap" ? "open" : ""}><summary>替换本段已有素材（主动勾选）</summary><p class="helper">保留未勾选的原素材。更换同角色声线或服装时，请勾选旧素材以避免重复。</p>${prior.map((a) => `<label class="library-binding"><input data-replace type="checkbox" value="${a.id}" ${data.replace.includes(a.id) ? "checked" : ""}>${ui.esc(a.name)} · ${ui.esc(a.purpose)} ${ui.esc(a.subject)}</label>`).join("")}</details>` : ""}${
              ctx.project.mode === "swap"
                ? ui.field(
                    "换人声音策略",
                    `<select id="use-audio-policy">${ui.opts(
                      [
                        ["source", "保留源视频原声"],
                        ["native", "模型生成声音（允许音色参考）"],
                      ],
                      ctx.project.settings.audio_policy,
                    )}</select>`,
                  )
                : ""
            }`
      }<div id="use-report" class="notice" role="status">先检查本次引用，确认后将当前草稿和素材一起保存。取消不会保存草稿或添加素材。</div><div class="dialog-actions"><button id="use-cancel">取消</button><button id="use-check">检查引用与工作流</button><button id="use-apply" class="primary" disabled>确认应用</button></div></div>`,
    );
    const view = d.querySelector(".library-use"),
      apply = view.querySelector("#use-apply"),
      check = view.querySelector("#use-check");
    const finish = (value) => {
      if (done) return;
      done = true;
      d.close();
      resolve(value);
    };
    d.oncancel = (e) => {
      e.preventDefault();
      if (pending) ui.toast("正在准备项目副本，请稍候；不会提交生成任务");
      else finish(null);
    };
    view.querySelector("#use-cancel").onclick = () => {
      if (!pending) finish(null);
    };
    const invalidate = () => {
      plan = null;
      apply.disabled = true;
      view.querySelector("#use-report").textContent =
        "选择已改变，请重新检查引用。";
    };
    view
      .querySelectorAll("input,select")
      .forEach((el) => (el.onchange = invalidate));
    function collect() {
      for (const row of view.querySelectorAll("[data-entry]")) {
        const e = data.entries[row.dataset.entry];
        e.selected = row.querySelector("[data-selected]").checked;
        e.media = row.querySelector("[data-media]").value;
        if (row.querySelector("[data-purpose]"))
          e.purpose = row.querySelector("[data-purpose]").value;
      }
      if (data.target === "source") {
        const end = view.querySelector("#use-end").value,
          start = Number(view.querySelector("#use-start").value);
        const row = entries[0],
          selected = row.media.find(
            (m) => m.id === data.entries[row.key].media,
          );
        data.range =
          start || end
            ? { start, end: end ? Number(end) : selected.meta.duration }
            : null;
      } else {
        data.subject = view.querySelector("#use-subject").value;
        data.replace = [...view.querySelectorAll("[data-replace]:checked")].map(
          (x) => x.value,
        );
        if (view.querySelector("#use-audio-policy"))
          data.audio_policy = view.querySelector("#use-audio-policy").value;
      }
    }
    check.onclick = async () => {
      if (pending) return;
      pending = true;
      check.disabled = true;
      view
        .querySelectorAll("input,select")
        .forEach((el) => (el.disabled = true));
      try {
        collect();
        plan = await libraryApi(
          `/projects/${ctx.project.id}/use-plan`,
          "POST",
          data,
          ctx.session.controller.signal,
        );
        if (ctx.session.disposed) return finish(null);
        view.querySelector("#use-report").innerHTML =
          `${plan.errors?.map((x) => `<p class="error">${ui.esc(x)}</p>`).join("") || ""}${plan.summary.map((x) => `<p>${ui.esc(x)}</p>`).join("")}<p>${plan.ready ? "可应用，素材与配方将在同一次确认中保存。" : "尚不能引用，请调整上方选择或先制作派生素材。"}</p>${plan.entries
            .filter((x) => x.selected)
            .map(
              (x) =>
                `<small>${ui.esc(x.name)} → ${ui.esc(x.purpose)}${x.subject ? " / 角色" + ui.esc(x.subject) : ""} · ${ui.esc(x.note)}</small><br>`,
            )
            .join("")}`;
        apply.disabled = !plan.ready;
      } catch (error) {
        view.querySelector("#use-report").textContent = error.message;
      } finally {
        pending = false;
        check.disabled = false;
        view
          .querySelectorAll("input,select")
          .forEach((el) => (el.disabled = false));
      }
    };
    apply.onclick = async () => {
      if (!plan?.ready || pending) return;
      pending = true;
      apply.disabled = true;
      check.disabled = true;
      view
        .querySelectorAll("input,select")
        .forEach((el) => (el.disabled = true));
      try {
        const task = await libraryApi(
          `/projects/${ctx.project.id}/use-apply`,
          "POST",
          { token: plan.token },
          ctx.session.controller.signal,
        );
        const result = await followTask(
          task,
          (t) => {
            view.querySelector("#use-report").innerHTML =
              `<p>${ui.esc(t.note)}</p><progress max="1" value="${t.progress}"></progress>`;
          },
          ctx.session.controller.signal,
        );
        finish(result);
      } catch (error) {
        if (!ctx.session.disposed)
          view.querySelector("#use-report").textContent = error.message;
      } finally {
        pending = false;
        check.disabled = false;
        view
          .querySelectorAll("input,select")
          .forEach((el) => (el.disabled = false));
      }
    };
  });
}
