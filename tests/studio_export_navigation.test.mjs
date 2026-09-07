import test from "node:test";
import assert from "node:assert/strict";
import { ProjectSession } from "../static/studio/core/project-session.js";
import { ProjectCommands } from "../static/studio/core/project-commands.js";
import { exportNavigation } from "../static/studio/core/export-lifecycle.js";
import { createFeature } from "../static/studio/features/export/index.js";

const project = () => ({
  id: "test",
  settings: {},
  segments: [
    { index: 0, status: "accepted", selected: "a" },
    { index: 1, status: "needs_review", selected: "b" },
  ],
});

test("final approval opens final cut after acceptance and before reload, including accept-only", async () => {
  for (const body of [{ continue: true }, {}]) {
    const events = [];
    const s = new ProjectSession(project(), async (path, method) => {
      events.push(method === "POST" ? "approve" : "reload");
      return project();
    });
    s.subscribe((type) => {
      if (type === "export-started") events.push("final-cut");
    });
    await new ProjectCommands(s, async () => true).run(
      "/segments/1/approve",
      body,
    );
    assert.deepEqual(events, ["approve", "final-cut", "reload"]);
    s.dispose();
  }
});

test("ordinary approval and rejected final approval do not leave review", async () => {
  for (const fail of [false, true]) {
    const p = project();
    if (!fail) p.segments[0].status = "draft";
    const s = new ProjectSession(p, async () => {
      if (fail) throw Error("候选已过期");
      return p;
    });
    let moved = 0;
    s.subscribe((type) => {
      if (type === "export-started") moved++;
    });
    const run = new ProjectCommands(s, async () => true).run(
      "/segments/1/approve",
      { continue: true },
    );
    if (fail) await assert.rejects(run);
    else await run;
    assert.equal(moved, 0);
    s.dispose();
  }
});

test("explicit export opens final cut before submission and failed request stops its clock", async () => {
  const events = [];
  const s = new ProjectSession(project(), async () => {
    events.push("submit");
    throw Error("任务冲突");
  });
  s.subscribe((type) => {
    if (type === "export-started") events.push("final-cut");
  });
  await assert.rejects(new ProjectCommands(s, async () => true).run("/export"));
  assert.deepEqual(events, ["final-cut", "submit"]);
  assert.equal(s.project.runtime.active, false);
  assert.equal(s.project.runtime.error, "任务冲突");
  s.dispose();
});

test("cancelled save never navigates or submits export", async () => {
  const calls = [];
  const s = new ProjectSession(project(), async (path) => {
    calls.push(path);
    return { requires_confirmation: true };
  });
  s.markDirty();
  let moved = 0;
  s.subscribe((type) => {
    if (type === "export-started") moved++;
  });
  await new ProjectCommands(s, async () => false).run("/export");
  assert.equal(moved, 0);
  assert.deepEqual(calls, ["/projects/test/change-plan"]);
  s.dispose();
});

test("automatic export follows state edges once and catches completion between polls", () => {
  const follow = exportNavigation({ status: "generating" });
  assert.equal(follow({ status: "needs_review" }), false);
  assert.equal(follow({ status: "assembling" }), true);
  assert.equal(follow({ status: "assembling" }), false);
  assert.equal(
    follow({ status: "complete", export: { file: "one.mp4" } }),
    true,
  );
  assert.equal(
    follow({ status: "complete", export: { file: "one.mp4" } }),
    false,
  );
  assert.equal(
    exportNavigation({ status: "generating" })({
      status: "complete",
      export: { file: "fast.mp4" },
    }),
    true,
  );
});

test("final cut renders an indeterminate export bar, elapsed time, result and failure without sampling counters", () => {
  const ctx = {
    project: {
      status: "assembling",
      runtime: {
        active: true,
        phase: "合成完整视频与声音",
        started: 1,
        step: 6,
        step_total: 20,
      },
    },
    esc: String,
    elapsed: () => "00:12",
  };
  const feature = createFeature(ctx);
  const running = feature.exportProgressCard();
  assert.match(running, /<progress aria-label="正在合成/);
  assert.match(running, /00:12/);
  assert.doesNotMatch(running, /6 \/ 20|value=/);
  ctx.project.status = "complete";
  ctx.project.export = { url: "done.mp4" };
  assert.match(feature.exportProgressCard(), /value="1" max="1"/);
  ctx.project.status = "failed";
  ctx.project.error = "磁盘空间不足";
  assert.match(feature.exportProgressCard(), /磁盘空间不足/);
  assert.doesNotMatch(feature.exportProgressCard(), /<progress/);
});
