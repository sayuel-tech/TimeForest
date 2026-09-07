"""Profile-specific MiniMax H3 Ref2VA prompts."""
from __future__ import annotations
import json
import re
from .config import ROOT

FIELDS = ("subject_definitions", "summary", "retention_analysis",
          "detailed_description", "overall_soundscape", "non_diegetic_music")

COMMON_SUBJECT = (
    "<Subject 1> is the single replacement character whose entire visible appearance comes from "
    "{PICTURE_LIST}: facial identity, hairstyle, body build, skin appearance, complete clothing, "
    "accessories and footwear. If one picture contains several views, they all show the same person.\n"
    "<Subject 2> is the performance in <Video 1>: the ordered poses, gestures, steps, turns, facial "
    "performance, movement timing, rhythm and screen position, excluding the source performer's appearance.\n"
    "<Subject 3> is the environment in <Video 1>: background, set, lighting and objects that are not "
    "worn or carried by the source performer.\n"
    "<Video 1> is the source video being edited. It supplies <Subject 2>, <Subject 3>, framing, camera "
    "movement, cut timing and the target duration. The source performer's identity, hair, body appearance, "
    "clothes, accessories and footwear must not appear in the target video."
)

OFFICIAL_PROMPT = {
    "subject_definitions": COMMON_SUBJECT,
    "summary": (
        "[video editing + reference generation] The target video is an edited version of <Video 1>. "
        "Cast <Subject 1> as the only main performer and transfer <Subject 2> onto that character. "
        "Preserve <Subject 3>, framing, camera movement, shot order and duration. Completely remove the "
        "source performer's visual identity and wardrobe."),
    "retention_analysis": (
        "<Subject 1> (appears throughout [Shot 1]): fully_preserved - keep every visible identity and "
        "wardrobe attribute from {PICTURE_LIST} consistent at all angles and distances.\n"
        "<Subject 2> (appears throughout [Shot 1]): attribute_transfer - transfer only the complete "
        "performance, pose sequence, expressions, contacts, timing and screen trajectory to <Subject 1>.\n"
        "<Subject 3> (appears throughout [Shot 1]): fully_preserved - retain the source environment, "
        "lighting and background objects while adapting shadows and occlusions around <Subject 1>.\n"
        "<Video 1> (source video edit): partially_preserved - preserve its performance timeline, framing, "
        "camera path, cuts and environment; discard the source performer's face, hair, body appearance, "
        "clothing, accessories and footwear."),
    "detailed_description": (
        "The target video is a coherent photorealistic character-replacement edit.\n"
        "[Shot 1] From the opening frame, <Subject 1> completely occupies the role and screen position of "
        "the source performer in <Subject 3>. The face, hair, body build, skin, complete outfit, accessories "
        "and footwear remain faithful to {PICTURE_LIST}; no visual attribute from the source performer remains. "
        "<Subject 1> performs <Subject 2> in exact chronological order, matching every pose, hand gesture, step, "
        "turn, expression, movement direction, speed, rhythm and contact point at the corresponding source time. "
        "Keep the source framing and camera movement. Preserve correct foreground and hand occlusions while "
        "maintaining the replacement identity through close-ups, profile views, back views and motion. Hair and "
        "fabric react naturally. Retain <Subject 3> without copying the source performer's wardrobe or accessories. "
        "Show exactly one main performer. Do not create a character sheet, split screen, duplicate body, extra "
        "limbs, identity morph, wardrobe drift, action replay or premature ending."),
    "overall_soundscape": "No generated dialogue, ambience or physical sound effects; source audio is restored after generation.",
    "non_diegetic_music": "N/A",
}

DANCE_PROMPT = {
    "subject_definitions": COMMON_SUBJECT,
    "summary": (
        "[video editing + reference generation] Replace the main performer in <Video 1> completely with "
        "<Subject 1>. Transfer only <Subject 2>; retain <Subject 3> and the camera. The source performer, "
        "including the original face, hair, body appearance and entire wardrobe, is absent from the output."),
    "retention_analysis": OFFICIAL_PROMPT["retention_analysis"],
    "detailed_description": (
        "The output is a clean photorealistic replacement, not a variation of the source performer.\n"
        "[Shot 1] <Subject 1> from {PICTURE_LIST} replaces the source performer from the first frame to the "
        "last. Keep the referenced face, hair, proportions, skin, full outfit, accessories and shoes stable. "
        "Transfer <Subject 2> moment by moment: all poses, steps, turns, hand motion, expressions, speed, rhythm "
        "and screen position. Preserve <Subject 3>, framing, camera motion and scene lighting. Maintain natural "
        "occlusion, anatomy, hair and fabric motion. Never retain or regenerate the source performer's face, hair, "
        "body appearance, clothing, headdress, jewellery or footwear. One performer only; no collage, duplicates, "
        "morphing, frozen frames, action replay or skipped motion."),
    "overall_soundscape": OFFICIAL_PROMPT["overall_soundscape"],
    "non_diegetic_music": "N/A",
}

DEFAULTS = {"dance16g": DANCE_PROMPT, "official_swap_lowvram": OFFICIAL_PROMPT}
LABELS = {"dance16g": "16G版 · 强换人提示词", "official_swap_lowvram": "官方Ref2VA版 · 完整参考提示词"}


class PromptStore:
    def __init__(self, cfg: dict):
        self.path = ROOT / "h3ui/templates/prompts.json"

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.is_file() else {}
        except (json.JSONDecodeError, OSError):
            data = {}
        return data.get("presets", {}) if isinstance(data, dict) else {}

    def get_current_fields(self, profile_id: str = "dance16g") -> dict:
        if profile_id not in DEFAULTS:
            raise ValueError("提示词工作流不存在")
        fields = dict(DEFAULTS[profile_id])
        stored = self._read().get(profile_id, {})
        if isinstance(stored, dict):
            fields.update({k: str(v) for k, v in stored.items() if k in FIELDS and str(v).strip()})
        return fields

    def load(self, profile_id: str = "dance16g") -> dict:
        return {"current": profile_id, "presets": {profile_id: self.get_current_fields(profile_id)},
                "meta": {profile_id: LABELS[profile_id]}}

    def save_fields(self, fields: dict, profile_id: str = "dance16g") -> dict:
        if profile_id not in DEFAULTS:
            raise ValueError("提示词工作流不存在")
        presets = self._read()
        merged = self.get_current_fields(profile_id)
        merged.update({k: str(v) for k, v in fields.items() if k in FIELDS})
        presets[profile_id] = merged
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".json.tmp")
        temp.write_text(json.dumps({"presets": presets}, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)
        return {"current": profile_id, "fields": merged}

    def switch(self, preset_id: str) -> bool:
        return preset_id in DEFAULTS

    def build_full(self, fields: dict | None = None, picture_count: int | None = None,
                   segment: dict | None = None) -> str:
        fields = dict(fields or DANCE_PROMPT)
        count = 1 if picture_count is None else int(picture_count)
        if not 1 <= count <= 4:
            raise ValueError("需要1~4张同一角色的参考图")
        tags = ", ".join(f"<Picture {n}>" for n in range(1, count + 1))
        text = "\n\n".join(f"{key}:\n{fields.get(key, '')}" for key in FIELDS).replace("{PICTURE_LIST}", tags)
        missing = {int(n) for n in re.findall(r"<Picture\s+(\d+)>", text) if not 1 <= int(n) <= count}
        if missing:
            raise ValueError(f"提示词引用了未上传的参考图：{sorted(missing)}")
        if segment is not None:
            note = ("This segment starts a new source shot; establish <Subject 1> immediately."
                    if segment.get("independent") else
                    "The leading frames overlap the previous delivery; continue the same <Subject 1> identity, "
                    "wardrobe and motion phaseline, then follow this segment of <Video 1> without replaying action.")
            text = text.replace("\n\noverall_soundscape:", f"\n{note}\n\noverall_soundscape:")
        return text

    def build_image_story(self, user_prompt: str, picture_count: int, segment: dict) -> str:
        tags = ", ".join(f"<Picture {n}>" for n in range(1, picture_count + 1))
        continuity = ("Establish the referenced character immediately." if segment.get("independent") else
                      "Continue the same character identity, wardrobe, scene state and motion from the leading context.")
        return (
            f"subject_definitions:\n<Subject 1> is the single character from {tags}. Preserve the complete identity, "
            "face, hair, body build, clothing, accessories and footwear. Multiple views in one picture show the same person.\n\n"
            f"summary:\n[reference generation] Generate this requested scene with <Subject 1>: {user_prompt}\n\n"
            f"retention_analysis:\n<Subject 1> (appears throughout [Shot 1]): fully_preserved - keep all visible identity "
            f"and wardrobe attributes from {tags} consistent.\n\n"
            f"detailed_description:\n[Shot 1] {user_prompt}\n{continuity} Show one coherent character, natural motion, stable anatomy "
            "and consistent appearance. Do not reproduce a character-sheet layout or duplicate views.\n\n"
            "overall_soundscape:\nGenerate natural ambience and physical sounds appropriate to the user's scene.\n\n"
            "non_diegetic_music:\nUse music only when the user's prompt requests it."
        )

    def build_text_story(self, user_prompt: str, segment: dict) -> str:
        continuity = ("Establish the scene and subjects immediately." if segment.get("independent") else
                      "Continue the same subjects, wardrobe, location, lighting and motion from the leading context.")
        return (f"integrated_multimodal_description:\n[Shot 1] {user_prompt}\n{continuity} Maintain coherent identities, "
                "natural movement, stable anatomy and a continuous visual state.\n\n"
                "overall_soundscape:\nGenerate synchronized dialogue, ambience and physical sounds only as described.\n\n"
                "non_diegetic_music:\nUse music only when requested by the user prompt.")
