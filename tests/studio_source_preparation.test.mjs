import test from "node:test";
import assert from "node:assert/strict";
import { ProjectSession } from "../static/studio/core/project-session.js";
import { ProjectCommands } from "../static/studio/core/project-commands.js";
import { createFeature } from "../static/studio/features/source-preparation/index.js";

const project = () => ({
  id: "fixture",
  revision: 1,
  mode: "swap",
  settings: {},
  segments: [],
  source_asset: "old",
  source_ready: false,
});
test("preparation waits for saved parameters and sends current revision and same source", async () => {
  const calls = [];
  const s = new ProjectSession(project(), async (path, method, body) => {
    calls.push([path, body]);
    if (path.endsWith("/change-plan"))
      return { requires_confirmation: false, token: "save" };
    return { ...project(), revision: 2 };
  });
  s.project.source_options = { segment_seconds: 10 };
  s.project.swap_prompt = { mode: "custom", custom: "my text" };
  s.markDirty();
  await new ProjectCommands(s, async () => true).prepareSource("old", "edit");
  assert.equal(calls[0][1].source_options.segment_seconds, 10);
  assert.equal(calls[0][1].swap_prompt.custom, "my text");
  assert.deepEqual(calls[2], [
    "/projects/fixture/prepare",
    { asset_id: "old", revision: 2, continue_to: "edit" },
  ]);
  s.dispose();
});
test("cancelled save never prepares and failed prepare remains visible", async () => {
  const paths = [];
  const s = new ProjectSession(project(), async (path) => {
    paths.push(path);
    return { requires_confirmation: true };
  });
  s.markDirty();
  const c = new ProjectCommands(s, async () => false);
  assert.equal(await c.prepareSource("old"), false);
  assert.equal(paths.length, 1);
  s.dirty = false;
  s.request = async () => {
    throw Error("源文件缺失");
  };
  await assert.rejects(c.prepareSource("old"));
  assert.equal(s.project.source_progress.active, false);
  assert.equal(s.project.source_progress.error, "源文件缺失");
  s.dispose();
});
test("generation guard redirects to preparation instead of submitting stale slices", async () => {
  let submitted = false;
  const s = new ProjectSession(project(), async () => {
    submitted = true;
  });
  const c = new ProjectCommands(s, async () => true);
  c.beforeGenerate = async () => false;
  await c.run("/generate", { all: true });
  assert.equal(submitted, false);
  s.dispose();
});
test("source progress updates without a full project revision change and advances only on completion", () => {
  const s = new ProjectSession(project());
  let renders = 0;
  const ctx = {
    project: s.project,
    catalog: { swap_preparation_version: 1 },
    tab: "source",
    renderProject: () => renders++,
    toast: () => {},
    root: { querySelector: () => null },
  };
  const feature = createFeature(ctx);
  s.receive({
    ...project(),
    source_progress: {
      id: "job",
      active: true,
      phase: "转换生成输入",
      percent: 42,
    },
  });
  assert.equal(s.project.source_progress.percent, 42);
  assert.equal(feature.observeSource("progress"), false);
  ctx.project.source_ready = true;
  ctx.project.source_progress = {
    id: "job",
    active: false,
    phase: "源视频准备完成",
    continue_to: "edit",
  };
  assert.equal(feature.observeSource("server"), true);
  assert.equal(ctx.tab, "edit");
  assert.equal(renders, 1);
  assert.equal(feature.observeSource("progress"), false);
  s.dispose();
});
