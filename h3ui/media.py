"""媒体工具: ffprobe/ffmpeg 封装。

包含 24fps 重采样、按段切片(带音频)、取尾帧、缩略图、音频回填、拼接。
所有路径参数用 pathlib.Path。
"""
from __future__ import annotations

import subprocess
import re
import shutil
import io
from pathlib import Path

FPS = 24


class MediaError(RuntimeError):
    pass


def make_project_cover(mode: str, dst: Path, source_video: Path | None = None,
                       reference_image: Path | None = None, fallback: Path | None = None) -> None:
    from PIL import Image, ImageDraw, ImageFilter, ImageOps
    dst.parent.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGB", (1280, 720), "#e9e1d2")
    if source_video and source_video.is_file():
        count=frame_count(source_video); index=max(0,round((count-1)*.25))
        raw=subprocess.check_output(["ffmpeg","-v","error","-i",str(source_video),"-vf",f"select='eq(n\\,{index})'","-frames:v","1","-f","image2pipe","-vcodec","png","-"])
        image=Image.open(io.BytesIO(raw)).convert("RGB")
        bg=ImageOps.fit(image,canvas.size,method=Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(24))
        canvas=Image.blend(bg,Image.new("RGB",canvas.size,"#8b8578"),.18)
        fg=ImageOps.contain(image,(1040,660),method=Image.Resampling.LANCZOS);canvas.paste(fg,((1280-fg.width)//2,(720-fg.height)//2))
    elif reference_image and reference_image.is_file():
        image=Image.open(reference_image).convert("RGB")
        bg=ImageOps.fit(image,canvas.size,method=Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(35))
        canvas=Image.blend(bg,Image.new("RGB",canvas.size,"#f0e9dc"),.55)
        fg=ImageOps.contain(image,(1060,620),method=Image.Resampling.LANCZOS);canvas.paste(fg,((1280-fg.width)//2,(720-fg.height)//2))
    elif fallback and fallback.is_file(): canvas=ImageOps.fit(Image.open(fallback).convert("RGB"),canvas.size,method=Image.Resampling.LANCZOS)
    if mode=="swap" and reference_image and reference_image.is_file():
        ref=Image.open(reference_image).convert("RGB");portrait=ImageOps.fit(ref,(190,190),method=Image.Resampling.LANCZOS,centering=(.2,.35));mask=Image.new("L",portrait.size);ImageDraw.Draw(mask).ellipse((0,0,189,189),fill=255);ImageDraw.Draw(canvas).ellipse((1048,478,1250,680),fill="#f8f4ea",outline="#201e19",width=4);canvas.paste(portrait,(1054,484),mask)
    canvas.save(dst,"WEBP",quality=82,method=6);canvas.resize((640,360),Image.Resampling.LANCZOS).save(dst.with_name("cover-thumb.webp"),"WEBP",quality=78,method=6)


def make_context_strip(video: Path, dst: Path, frames: int = 22) -> None:
    from PIL import Image, ImageOps
    count=frame_count(video);start=max(0,count-frames);indices=[round(start+i*(count-1-start)/3) for i in range(4)]
    strip=Image.new("RGB",(800,112),"#201e19")
    for i,index in enumerate(indices):
        raw=subprocess.check_output(["ffmpeg","-v","error","-i",str(video),"-vf",f"select='eq(n\\,{index})'","-frames:v","1","-f","image2pipe","-vcodec","png","-"])
        image=ImageOps.fit(Image.open(io.BytesIO(raw)).convert("RGB"),(194,104),method=Image.Resampling.LANCZOS)
        strip.paste(image,(4+i*198,4))
    dst.parent.mkdir(parents=True,exist_ok=True);strip.save(dst,"WEBP",quality=76,method=6)


def run(cmd: list[str]) -> None:
    try:
        subprocess.run([str(x) for x in cmd], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip().splitlines()
        raise MediaError(f"命令失败: {' '.join(map(str, cmd))}\n{detail[-3:] if detail else ''}") from exc


def ffprobe(cmd: list[str]) -> str:
    result = subprocess.run(
        [str(x) for x in cmd], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def frame_count(path: Path) -> int:
    return int(ffprobe([
        "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", path,
    ]))


def video_size(path: Path) -> tuple[int, int]:
    w, h = ffprobe([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=p=0", path,
    ]).split(",")
    return int(w), int(h)


def fps_value(path: Path) -> float:
    from fractions import Fraction
    raw = ffprobe([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", path,
    ])
    return float(Fraction(raw))


def has_audio(path: Path) -> bool:
    raw = ffprobe([
        "ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=codec_name", "-of", "csv=p=0", path,
    ])
    return bool(raw)


def fit_resolution(w: int, h: int, max_megapixels: float, multiple: int = 32) -> tuple[int, int]:
    """按源比例推导输出分辨率: 不超过 max_megapixels,并取 32 的倍数。"""
    max_pixels = int(max_megapixels * 1_000_000)
    area = w * h
    if area > max_pixels:
        scale = (max_pixels / area) ** 0.5
        w, h = int(w * scale), int(h * scale)
    w = max(multiple, (w // multiple) * multiple)
    h = max(multiple, (h // multiple) * multiple)
    return w, h


def parse_resolution(value) -> tuple[int, int] | None:
    """解析 'WxH'(也接受 768x1344 / 768*1344 / 768×1344)。返回 (w,h) 或 None(auto)。

    校验: 必须为 32 的倍数(ComfyUI/H3 latent 对齐要求)。
    """
    if not value:
        return None
    text = str(value).strip().lower().replace(" ", "")
    if text in ("auto", "自动", "0"):
        return None
    text = text.replace("*", "x").replace("×", "x").replace("，", ",")
    if "," in text:
        text = text.replace(",", "x")
    try:
        w_text, h_text = text.split("x")
        w, h = int(w_text), int(h_text)
    except (ValueError, IndexError) as exc:
        raise MediaError(f"分辨率格式应为 WxH,例如 768x1344;得到: {value}") from exc
    if w < 32 or h < 32 or w % 32 != 0 or h % 32 != 0:
        raise MediaError(f"分辨率必须是 32 的倍数: {w}x{h}")
    return w, h


def resample_24fps(src: Path, dst: Path, width: int, height: int) -> None:
    """30→24fps 重采样 + 缩放到 width×height(保比例,居中留边),保留音频。"""
    run([
        "ffmpeg", "-y", "-v", "error", "-i", src,
        "-vf", f"fps={FPS},scale={width}:{height}:force_original_aspect_ratio=decrease,"
               f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black",
        "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", dst,
    ])


def slice_segment(src: Path, start: int, raw: int, dst: Path,
                  available: int | None = None) -> None:
    """切出有效源帧，仅在生成输入尾部补齐；原音频保持在母时间线。"""
    available = raw if available is None else available
    if not 0 < available <= raw:
        raise MediaError("切片有效帧数不合法")
    padding = raw - available
    run([
        "ffmpeg", "-y", "-v", "error", "-i", src,
        "-vf", f"trim=start_frame={start}:end_frame={start + available},setpts=PTS-STARTPTS,"
               f"tpad=stop_mode=clone:stop={padding}",
        "-frames:v", str(raw), "-r", str(FPS),
        "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-an", dst,
    ])


def detect_cuts(src: Path, threshold: float = 0.45) -> list[int]:
    """Detect strong cuts on a small preview; generation is never involved."""
    result = subprocess.run([
        "ffmpeg", "-v", "info", "-i", str(src), "-an",
        "-vf", f"scale=160:-2,select='gt(scene,{threshold})',showinfo",
        "-f", "null", "-"], check=True, capture_output=True, text=True)
    times = re.findall(r"pts_time:([0-9.]+)", result.stderr)
    return sorted({round(float(t) * FPS) for t in times})


def trim_delivery(src: Path, dst: Path, prefix: int, frames: int) -> None:
    if prefix < 0 or frames < 1:
        raise MediaError("交付裁切参数不合法")
    run(["ffmpeg", "-y", "-v", "error", "-i", src,
         "-vf", f"trim=start_frame={prefix}:end_frame={prefix + frames},setpts=PTS-STARTPTS",
         "-frames:v", str(frames), "-r", str(FPS), "-an",
         "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", dst])


def extract_tail(src: Path, frames: int, dst: Path) -> None:
    """取视频最后 frames 帧(无音频),用于生成上下文。"""
    count = frame_count(src)
    start = count - frames
    run([
        "ffmpeg", "-y", "-v", "error", "-i", src,
        "-vf", f"select='between(n\\,{start}\\,{count - 1})',setpts=PTS-STARTPTS",
        "-fps_mode", "cfr", "-r", str(FPS),
        "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-an", dst,
    ])


def make_thumbnail(video: Path, dst: Path, seconds: float = 0.0, width: int = 240) -> None:
    run([
        "ffmpeg", "-y", "-v", "error", "-ss", f"{seconds:.3f}", "-i", video,
        "-frames:v", "1", "-vf", f"scale={width}:-1", "-q:v", "6", dst,
    ])


def mux_audio(video: Path, audio: Path, offset_seconds: float, duration_seconds: float, dst: Path) -> None:
    """把 audio 从 offset 起替换/叠加到 video,时长 duration。"""
    if not has_audio(audio):
        shutil.copy2(video, dst)
        return
    run([
        "ffmpeg", "-y", "-v", "error",
        "-i", video, "-ss", f"{offset_seconds:.6f}", "-i", audio,
        "-map", "0:v:0", "-map", "1:a:0",
        "-af", "apad",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-t", f"{duration_seconds:.6f}", "-movflags", "+faststart", dst,
    ])


def concat_videos(paths: list[Path], dst: Path, list_file: Path) -> None:
    """把多个 mp4 平接(相同编码/分辨率/帧率),产物写 dst。"""
    list_file.write_text(
        "".join(f"file '{p.resolve().as_posix().replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n" for p in paths),
        encoding="utf-8",
    )
    run([
        "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
        "-i", list_file, "-c", "copy", dst,
    ])


def make_seam_preview(prev: Path, next_video: Path, dst: Path, tail: int = 6) -> None:
    """做接缝预览: 前段结尾 tail 帧 + 后段开头 tail 帧拼成一个小视频。"""
    import tempfile
    with tempfile.TemporaryDirectory(prefix="h3ui_seam_") as temp:
        temp_dir = Path(temp)
        a, b, c = temp_dir / "a.mp4", temp_dir / "b.mp4", temp_dir / "list.txt"
        prev_count = frame_count(prev)
        run([
            "ffmpeg", "-y", "-v", "error", "-i", prev,
            "-vf", f"select='gte(n\\,{prev_count - tail})',setpts=PTS-STARTPTS",
            "-frames:v", str(tail), "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", a,
        ])
        run([
            "ffmpeg", "-y", "-v", "error", "-i", next_video,
            "-vf", f"select='lte(n\\,{tail - 1})',setpts=PTS-STARTPTS",
            "-frames:v", str(tail), "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", b,
        ])
        c.write_text(f"file '{a.as_posix()}'\nfile '{b.as_posix()}'\n", encoding="utf-8")
        run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
             "-i", c, "-c", "copy", dst])
