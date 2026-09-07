"""配置加载: config.json(机器特定)> 环境变量 H3UI_CONFIG > 默认值。"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULTS = {
    "host": "127.0.0.1",
    "port": 5093,
    "comfy_url": "http://127.0.0.1:8188",
    "comfy_input_dir": "ComfyUI/input",
    "comfy_output_dir": "ComfyUI/output",
    "model": {
        "unet": "minimax_h3_hybrid_fl2va_ref2va_b25-49-int8.safetensors",
        "clip": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
        "video_vae": "minimax_h3_video_vae_int8_convrot.safetensors",
        "audio_vae": "minimax_h3_audio_vae_fp32.safetensors",
    },
    "output": {"max_megapixels": 0.3, "width": 416, "height": 736},
    "segment": {"raw_frames": 124, "context_frames": 22, "steps": 12,
                "detect_cuts": True, "scene_threshold": 0.45},
    "taper": {"alpha": 0.45, "alpha_end": 0.1, "ramp_frames": 3},
    "gates": {
        "max_abs_phase_offset": 2,
        "min_phase_ncc": 0.3,
        "max_seam_diff": 0.04,
        "min_sharpness_ratio": 0.75,
        "min_source_rms_difference": 8.0,
    },
    "nodes": {
        "initial": {"ref2va": "20", "source_video": "43", "save_raw": "19", "random_noise": "12"},
        "taper": {"ref2va": "20", "source_video": "43", "context_video": "101",
                  "plan": "100", "raw_output": "19", "delivery_output": "108"},
    },
    "seed_base": 730000,
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def resolve_path(cfg: dict, key: str) -> Path:
    """把配置里的相对路径解析成绝对路径(相对项目根)。"""
    value = cfg.get(key, "")
    path = Path(os.path.expanduser(str(value)))
    return path if path.is_absolute() else (ROOT / path)


def load_config(path: str | None = None) -> dict:
    cfg = dict(DEFAULTS)
    if path is None:
        env = os.environ.get("H3UI_CONFIG")
        path = env if env else str(ROOT / "config.json")
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as handle:
                cfg = _deep_merge(cfg, json.load(handle))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"config.json 解析失败: {path}: {exc}") from exc
    return cfg
