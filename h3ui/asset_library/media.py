"""Probe originals without conversion; make explicit derived browsing files."""
import hashlib
import json
import mimetypes
import subprocess
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def command(args, timeout=120):
    result = subprocess.run([str(x) for x in args], capture_output=True, timeout=timeout,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise ValueError(result.stderr.decode('utf-8', errors='replace')[-1800:] or '媒体处理失败')
    return result.stdout


def records(tags):
    """Only parse actual embedded metadata; never infer a prompt from pixels."""
    out = {}
    for key in ('workflow', 'prompt', 'comment', 'parameters'):
        value = tags.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except ValueError:
                pass
        out[key] = value
    return out


def inspect(path):
    path = Path(path)
    try:
        with Image.open(path) as image:
            image.load()
            fmt = image.format
            info = dict(kind='image', width=image.width, height=image.height,
                        color_mode=image.mode, alpha='A' in image.getbands() or 'transparency' in image.info,
                        bit_depth=16 if '16' in image.mode else 32 if image.mode in ('I', 'F') else 8,
                        has_icc=bool(image.info.get('icc_profile')), frames=getattr(image, 'n_frames', 1),
                        mime=Image.MIME.get(fmt, 'application/octet-stream'),
                        extension={ 'JPEG': '.jpg', 'TIFF': '.tiff' }.get(fmt, '.' + fmt.lower()),
                        generation_records=records(image.info))
            return info
    except (UnidentifiedImageError, OSError):
        pass
    if path.suffix.lower() == '.json':
        if path.stat().st_size > 20 * 1024 * 1024:
            raise ValueError('工作流资料文件过大')
        try:
            data = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(data, dict):
                raise ValueError()
            visual = isinstance(data.get('nodes'), list)
            api = bool(data) and all(isinstance(v, dict) and 'class_type' in v for v in data.values())
            if not visual and not api:
                raise ValueError()
            return dict(kind='workflow', mime='application/json', extension='.json',
                        generation_records={'workflow' if visual else 'prompt': data})
        except (ValueError, UnicodeError) as exc:
            raise ValueError('JSON不是可识别的工作流资料') from exc
    try:
        data = json.loads(command(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path], 45))
    except (ValueError, subprocess.TimeoutExpired) as exc:
        raise ValueError('无法解码该媒体，原件未入库') from exc
    streams = data.get('streams', [])
    video = next((x for x in streams if x['codec_type'] == 'video' and not x.get('disposition', {}).get('attached_pic')), None)
    audio = next((x for x in streams if x['codec_type'] == 'audio'), None)
    duration = float(data.get('format', {}).get('duration') or (video or audio or {}).get('duration') or 0)
    if not (video or audio) or duration <= 0:
        raise ValueError('没有可读取的声画或时长')
    kind = 'video' if video else 'audio'
    suffix = path.suffix.lower()
    valid = {'.mp4', '.mov', '.mkv', '.webm', '.avi', '.wav', '.flac', '.mp3', '.m4a', '.ogg', '.aac', '.opus'}
    if suffix not in valid:
        raise ValueError('媒体已识别，但容器格式尚不支持存档；请使用常见音视频容器')
    return dict(kind=kind, extension=suffix, mime=mimetypes.guess_type('file' + suffix)[0] or 'application/octet-stream',
                duration=duration, width=(video or {}).get('width'), height=(video or {}).get('height'),
                fps=(video or {}).get('avg_frame_rate'), time_base=(video or audio).get('time_base'),
                has_audio=bool(audio), sample_rate=(audio or {}).get('sample_rate'), channels=(audio or {}).get('channels'),
                codec=(video or audio).get('codec_name'), streams=streams,
                generation_records=records(data.get('format', {}).get('tags', {})))


def preview(source, meta, dest):
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if meta['kind'] == 'image':
        with Image.open(source) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((600, 600))
            image.convert('RGBA' if meta.get('alpha') else 'RGB').save(dest, 'PNG')
    elif meta['kind'] == 'video':
        command(['ffmpeg', '-y', '-v', 'error', '-i', source, '-frames:v', '1', '-vf',
                 'scale=600:600:force_original_aspect_ratio=decrease', dest])
    elif meta['kind'] == 'audio':
        command(['ffmpeg', '-y', '-v', 'error', '-i', source, '-filter_complex',
                 'showwavespic=s=600x160:colors=71988c', '-frames:v', '1', dest])
    else:
        return None
    return dest
