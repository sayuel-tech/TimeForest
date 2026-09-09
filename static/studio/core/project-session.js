import {snapshotChange} from './snapshot-update.js';
import {projectContent,mergeProjectRuntime,acceptProjectRevision} from '../contracts/project-refresh.js';
import {canReplaceDraft,readStamp,currentRead} from './async-state.js';
import { api } from "./api-client.js";
import { singleFlight } from './single-flight.js';
import {
  authoredFields,
  normalizeProject,
  signature,
} from "../contracts/project.js";

/** A session belongs to exactly one project. Disposing it never cancels GPU work. */
export class ProjectSession {
  constructor(project, request = api) {
    this.project = normalizeProject(project);
    this.request = request;
    this.dirty = false;
    this.version=0;
    this.working = false;
    this.actionPending = false;
    this.disposed = false;
    this.saveInFlight = null;
    this.previewPending = false;
    this.previewSerial = 0;
    this.previewTimer = null;
    this.draftArchive = [];
    this.draftCache = new Map();
    this.listeners = new Set();
    this.controller = new AbortController();
    this.lastStatus = signature(this.project);
  }
  subscribe(fn) {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }
  emit(type, detail) {
    if (!this.disposed) this.listeners.forEach((fn) => fn(type, detail));
  }
  markDirty() {
    this.version++;
    this.dirty = true;
    this.emit("dirty");
  }
  async reload() {
    const stamp=readStamp(this);
    const next = await this.request(
      `/projects/${this.project.id}`,
      "GET",
      undefined,
      this.controller.signal,
    );
    if (!currentRead(this,stamp,next)) return;
    this.awaitingStatus=false;this.connection?.(null);
    this.replace(next);
  }
  replace(next) {
    this.pendingRefresh=false;
    this.project = normalizeProject(next);
    this.dirty = false;
    this.draftArchive = [];
    this.draftCache.clear();
    this.previewPending = false;
    this.previewSerial++;
    clearTimeout(this.previewTimer);
    this.lastStatus = signature(this.project);
    this.emit("replace");
  }
  receive(next) {
    if (this.disposed || next.id !== this.project.id || Number(next.revision)<Number(this.project.revision)) return;
    next=normalizeProject(next);
    const change=this.pendingRefresh?'content':snapshotChange(this.project,next,projectContent);
    if(change==='none')return;
    if(canReplaceDraft(this,this.root)&&change==='content'){
      this.pendingRefresh=false;this.project=next;this.lastStatus=signature(next);this.emit('server');
    }else{
      this.pendingRefresh=change==='content';
      mergeProjectRuntime(this.project,next);
      if(change==='status'&&canReplaceDraft(this,this.root))acceptProjectRevision(this.project,next);
      this.emit('progress');
    }
  }

  schedulePreview() {
    clearTimeout(this.previewTimer);
    if (!this.project.storyboard_version) {
      this.emit("notice", "请先升级为15秒片段，再修改时长。");
      return;
    }
    this.previewPending = true;
    const serial = ++this.previewSerial;
    this.emit("notice", "正在更新片段预览…");
    this.previewTimer = setTimeout(
      () => this.preview(serial).catch((e) => this.emit("error", e)),
      450,
    );
  }
  async preview(serial = ++this.previewSerial) {
    const p = this.project;
    if (!Number.isFinite(p.duration) || p.duration < 1 || p.duration > 3600)
      throw new Error("请输入1～3600秒");
    p.segments.forEach((s) => this.draftCache.set(s.index, structuredClone(s)));
    const result = await this.request(
      `/projects/${p.id}/preview`,
      "POST",
      {
        duration: p.duration,
        segments: [...this.draftCache.values()].sort(
          (a, b) => a.index - b.index,
        ),
        settings: p.settings,
        timing_mode: p.timing_mode,
      },
      this.controller.signal,
    );
    if (this.disposed || serial !== this.previewSerial) return false;
    p.segments.forEach((s) => this.draftCache.set(s.index, structuredClone(s)));
    result.segments.forEach((segment) => {
      const live = this.draftCache.get(segment.index);
      if (live)
        authoredFields.forEach((k) => {
          segment[k] = live[k];
        });
    });
    p.segments = result.segments;
    this.draftArchive = [...this.draftCache.values()].filter(
      (s) => s.index >= result.segments.length,
    );
    this.previewPending = false;
    this.emit("preview");
    this.emit(
      "notice",
      `计划${p.duration}秒 · ${p.segments.length}个片段 · 预计有效${Number(result.duration).toFixed(3)}秒。尚未保存。`,
    );
    return true;
  }
  save(decide) {
    return singleFlight(this, 'saveInFlight', () => this.saveDraft(decide), () => this.emit('busy'));
  }
  async saveDraft(decide) {
    this.working = true;
    this.emit("busy");
    try {
      if (this.project.busy && this.project.draft_storage_version) {
        const saved = await this.request(
          `/projects/${this.project.id}/draft`,
          "POST",
          {
            revision: this.project.saved_draft?.revision || 0,
            body: this.project,
          },
        );
        this.project.saved_draft = saved;
        this.emit(
          "notice",
          "制作中的修改已保存为独立草稿，不会改变当前任务；完成后可以载入并应用。",
        );
        return false;
      }
      if (this.previewPending) {
        clearTimeout(this.previewTimer);
        await this.preview();
        if (this.previewPending) throw new Error("请先修正片段时长");
      }
      const p = this.project;
      const plan = await this.request(`/projects/${p.id}/change-plan`, "POST", {
        revision: p.revision,
        name: p.name,
        duration: p.duration,
        review: p.review,
        settings: p.settings,
        segments: p.segments,
        storyboard_version: p.storyboard_version,
        timing_mode: p.timing_mode,
        removed_drafts: this.draftArchive,
        prompt_sources: p.prompt_sources,
        ...(p.mode === "swap"
          ? { source_options: p.source_options, swap_prompt: p.swap_prompt }
          : {}),
      });
      if (this.disposed) return false;
      if (plan.requires_confirmation && !(await decide(plan))) return false;
      if (this.disposed) return false;
      const stamp=readStamp(this);
    const next = await this.request(`/projects/${p.id}/apply`, "POST", {
        token: plan.token,
      });
      if (this.disposed) return false;
      this.replace(next);
      return true;
    } finally {
      this.working = false;
      this.emit("busy");
    }
  }
  dispose() {
    this.disposed = true;
    clearTimeout(this.previewTimer);
    this.previewSerial++;
    this.controller.abort();
    this.listeners.clear();
  }
}
