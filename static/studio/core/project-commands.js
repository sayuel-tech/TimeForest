import {uncertainMutation,requireKnownStatus} from './async-state.js';
import { finishesReview } from "./export-lifecycle.js";

/** Shared command gate: save → confirm impact → submit. Views never queue directly. */
export class ProjectCommands {
  constructor(session, decide) {
    this.session = session;
    this.decide = decide;
  }
  async perform(action) {
    const s = this.session;
    if (s.actionPending || s.disposed) return;
    s.actionPending = true;
    s.emit("busy");
    try {
      return await action();
    } finally {
      s.actionPending = false;
      s.emit("busy");
    }
  }
  async ensureSaved() {
    return !this.session.dirty || (await this.session.save(this.decide));
  }
  async preflight() {
    return this.perform(async () => {
      if (!(await this.ensureSaved())) return null;
      const s = this.session;
      s.working = true;
      s.emit("busy");
      try {
        return await s.request(`/projects/${s.project.id}/preflight`);
      } finally {
        s.working = false;
        s.emit("busy");
      }
    });
  }
  async prepareSource(assetId, continueTo = null) {
    return this.perform(async () => {
      if (!(await this.ensureSaved())) return false;
      return this.submitSource(assetId, continueTo);
    });
  }
  async submitSource(assetId, continueTo = null) {
    const s = this.session;
    if (s.disposed) return false;
    requireKnownStatus(s);
    if (!assetId) throw new Error("请先上传源视频");
    s.project.source_progress = {
      started: Date.now() / 1000,
      updated: Date.now() / 1000,
      active: true,
      phase: "正在提交准备任务",
    };
    s.emit("source-started");
    try {
      await s.request(`/projects/${s.project.id}/prepare`, "POST", {
        asset_id: assetId,
        revision: s.project.revision,
        continue_to: continueTo,
      });
      await s.reload();
      return true;
    } catch (error) {
      if(uncertainMutation(s,error)){s.project.source_progress.phase="准备提交结果待确认";s.emit("progress");throw error;}
      Object.assign(s.project.source_progress, {
        active: false,
        finished: Date.now() / 1000,
        error: error.message,
        phase: "提交准备任务未完成",
      });
      s.emit("progress");
      throw error;
    }
  }
  async run(path, body = {}) {
    return this.perform(async () => {
      const s = this.session;
      requireKnownStatus(s);
      if (s.dirty) {
        if (
          path === "/generate" ||
          path === "/export" ||
          path.endsWith("/reroll")
        ) {
          if (!(await this.ensureSaved())) return;
        } else throw new Error("请先保存或放弃修改，再执行审核操作");
      }
      if (s.disposed) return;
      if (
        (path === "/generate" || path.endsWith("/reroll")) &&
        this.beforeGenerate &&
        !(await this.beforeGenerate())
      )
        return;
      if (body.index !== undefined && body.index >= s.project.segments.length)
        throw new Error("片段已变化，请重新选择");
      const approval = path.match(/^\/segments\/(\d+)\/approve$/);
      const finalApproval =
        approval &&
        finishesReview(s.project, Number(approval[1]), body.attempt);
      const startExport = () => {
        s.project.runtime = {
          started: Date.now() / 1000,
          updated: Date.now() / 1000,
          active: true,
          operation: "export",
          phase: "正在提交合成任务",
          shot: null,
        };
        s.emit("export-started");
      };
      s.working = true;
      s.emit("busy");
      try {
        if (path === "/generate" || /\/(reroll|resume)$/.test(path)) {
          s.project.runtime = {
            started: Date.now() / 1000,
            updated: Date.now() / 1000,
            active: true,
            phase: "正在提交制作任务",
            shot: body.index ?? null,
          };
          s.emit("progress");
        }
        if (path === "/export") startExport();
        await s.request(`/projects/${s.project.id}${path}`, "POST", body);
        if (finalApproval && !s.disposed) startExport();
        await s.reload();
      } catch (error) {
        const uncertain=uncertainMutation(s,error);
        if (uncertain&&s.project.runtime){s.project.runtime.phase="提交结果待确认";s.emit("progress");}
        if (!uncertain &&
          ["正在提交制作任务", "正在提交合成任务"].includes(
            s.project.runtime?.phase,
          )
        ) {
          Object.assign(s.project.runtime, {
            active: false,
            finished: Date.now() / 1000,
            phase: "提交未完成",
            error: error.message,
          });
          s.emit("progress");
        }
        throw error;
      } finally {
        s.working = false;
        s.emit("busy");
      }
    });
  }
}
