"""Frame-exact source coverage; independent starts at detected hard cuts."""
from __future__ import annotations


def plan_segments(frame_count: int, raw_default: int = 124, context: int = 22,
                  cuts: list[int] | None = None) -> list[dict]:
    if raw_default < 56 or raw_default % 17 != 5 or context != 22:
        raise ValueError("16G工作流要求17k+5段长、22帧上下文，常规段长至少56帧")
    if frame_count < 1:
        return []
    boundaries = [0] + sorted({int(c) for c in (cuts or []) if 0 < int(c) < frame_count}) + [frame_count]
    segments = []
    for scene, (scene_start, scene_end) in enumerate(zip(boundaries, boundaries[1:])):
        cursor = scene_start
        while cursor < scene_end:
            prefix = 0 if cursor == scene_start else context
            deliver = min(raw_default - prefix, scene_end - cursor)
            available = prefix + deliver
            raw = max(5, available)
            raw += (5 - raw % 17) % 17
            segments.append({
                "index": len(segments), "scene": scene, "scene_start": scene_start,
                "start": cursor - prefix, "content_start": cursor,
                "source_end": cursor + deliver, "source_frames": available,
                "context_frames": prefix, "raw": raw, "deliver": deliver,
                "pad_frames": raw - available, "independent": prefix == 0,
            })
            cursor += deliver
    return segments


def audio_offset(seg: dict, context: int = 22, fps: float = 24.0) -> tuple[float, float]:
    prefix = int(seg.get("context_frames", 0 if seg["index"] == 0 else context))
    return (seg["start"] + prefix) / fps, seg["deliver"] / fps
