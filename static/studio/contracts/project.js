export const authoredFields = [
  "prompt_sources",
  "prompt",
  "prompt_mode",
  "voice",
  "speaker_order",
  "staging",
  "beats",
  "soundscape",
  "music",
  "ending",
  "assets",
  "inherit_ids",
  "asset_mode",
  "swap_prompt_mode",
  "swap_custom_prompt",
  "seed",
  "seed_mode",
];
/** Preserve backend IDs and schema; normalize only missing optional display fields. */
export function normalizeProject(p) {
  return {
    ...p,
    asset_library: p.asset_library || [],
    segments: (p.segments || []).map((s) => ({
      ...s,
      assets: s.assets || [],
      inherit_ids: s.inherit_ids || [],
      asset_mode: s.asset_mode || "auto",
      attempts: s.attempts || [],
    })),
  };
}
export const signature = (p) =>
  JSON.stringify([
    p.status,
    p.error,
    p.busy,
    p.segments.map((s) => [s.status, s.last_seed, s.selected]),
    p.export?.file,
  ]);
