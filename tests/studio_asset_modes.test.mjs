import test from "node:test";
import assert from "node:assert/strict";
import { createFeature } from "../static/studio/features/assets/index.js";
import { ProjectSession } from "../static/studio/core/project-session.js";

test("auto, explicit subset and no references resolve independently from scene continuity", () => {
  let dirty = 0,
    rendered = 0;
  const shot = {
    id: "p2",
    index: 1,
    head: 22,
    boundary: "continue",
    assets: [],
    inherit_ids: [],
  };
  const ctx = {
    catalog: { asset_reference_modes: ["auto", "custom", "none"] },
    project: {
      mode: "image_story",
      segments: [{ assets: ["image", "voice"] }, shot],
      asset_library: [{ id: "image" }, { id: "voice" }],
    },
    setDirty: () => dirty++,
    renderEdit: () => rendered++,
  };
  const feature = createFeature(ctx);
  assert.deepEqual(
    feature.localAssets(shot).map((a) => a.id),
    ["image", "voice"],
  );
  shot.inherit_ids = ["voice"];
  feature.setAssetMode("p2", "custom");
  assert.deepEqual(
    feature.localAssets(shot).map((a) => a.id),
    ["voice"],
  );
  feature.setAssetMode("p2", "none");
  assert.deepEqual(feature.localAssets(shot), []);
  assert.equal(shot.head, 22);
  assert.equal(shot.boundary, "continue");
  assert.deepEqual(shot.inherit_ids, ["voice"]);
  feature.setAssetMode("p2", "auto");
  assert.equal(feature.localAssets(shot).length, 2);
  assert.equal(dirty, 3);
  assert.equal(rendered, 3);
});

test("older backend does not expose an unsupported reference control", () => {
  const feature = createFeature({
    catalog: {},
    project: { mode: "image_story" },
  });
  assert.equal(feature.assetModeControl({ index: 1 }), "");
});

test("preview and save preserve explicit no-reference choice", async () => {
  const p = {
    id: "fixture",
    revision: 1,
    duration: 30,
    storyboard_version: 1,
    settings: {},
    segments: [
      { id: "p2", index: 1, assets: [], inherit_ids: [], asset_mode: "none" },
    ],
  };
  let submitted;
  const s = new ProjectSession(p, async (path, method, body) => {
    if (path.endsWith("/preview"))
      return { segments: [{ ...p.segments[0], asset_mode: "auto" }] };
    if (path.endsWith("/change-plan")) {
      submitted = body;
      return { requires_confirmation: false, token: "t" };
    }
    return p;
  });
  await s.preview();
  assert.equal(s.project.segments[0].asset_mode, "none");
  await s.save(async () => true);
  assert.equal(submitted.segments[0].asset_mode, "none");
  s.dispose();
});
