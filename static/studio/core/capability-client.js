/** Pure projections of the backend's parameter and capability contract. */
export function visibleParameters(recipe, settings) {
  return (recipe.parameters || []).filter(
    (f) =>
      !f.when || Object.entries(f.when).every(([k, v]) => settings[k] === v),
  );
}
export function choicesFor(f, s, p, c) {
  const k = f.key;
  const keepCurrent = (items = []) =>
    !s[k] || items.includes(s[k])
      ? items
      : [[s[k], `${s[k]}（目录未列出，保留当前选择）`], ...items];
  if (k === "recipe")
    return c.recipes
      .filter((r) => r.modes.includes(p.mode))
      .map((r) => [r.id, r.name]);
  if (k === "model") return keepCurrent(c.models);
  if (k === "clip") return keepCurrent(c.clips);
  if (f.type === "vae") return keepCurrent(c.vaes);
  if (f.type === "sampler") return c.samplers;
  if (f.type === "scheduler") return c.schedulers;
  if (k === "accel_file") return keepCurrent(c.loras);
  return {
    size_mode: [
      ["area", "面积＋比例"],
      ["custom", "自定义宽高"],
    ],
    aspect: ["9:16", "16:9", "1:1", "4:3", "3:4"],
    reference_size: [
      ["match", "匹配画布"],
      ["max", "原参考细节（更耗显存）"],
    ],
    export_fps: [24, 25, 30, 50, 60],
    audio_policy:
      p.mode === "swap"
        ? [
            ["source", "源视频原声"],
            ["native", "H3生成声音"],
          ]
        : [["native", "H3生成声音"]],
  }[k];
}
function even(n) {
  const floor = Math.floor(n);
  return n - floor === 0.5
    ? floor % 2 === 0
      ? floor
      : floor + 1
    : Math.round(n);
}
export function geometryPreview(s, r) {
  const ratio =
    { "9:16": 9 / 16, "16:9": 16 / 9, "1:1": 1, "4:3": 4 / 3, "3:4": 3 / 4 }[
      s.aspect
    ] || 9 / 16;
  const w =
    s.size_mode === "custom"
      ? Number(s.width)
      : even(Math.sqrt(s.megapixels * 1e6 * ratio) / 32) * 32;
  const h =
    s.size_mode === "custom"
      ? Number(s.height)
      : even(Math.sqrt((s.megapixels * 1e6) / ratio) / 32) * 32;
  return {
    w,
    h,
    ow: r.two_pass ? even((w * s.scale) / 32) * 32 : w,
    oh: r.two_pass ? even((h * s.scale) / 32) * 32 : h,
  };
}
