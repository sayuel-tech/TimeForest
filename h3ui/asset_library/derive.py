"""Non-destructive CPU media tools with explicit source-version provenance."""
import math
from pathlib import Path

from PIL import Image, ImageOps

from .media import command
from .store import uid


def number(value, low, high, label):
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label}须在{low:g}～{high:g}之间')
    return value


def derive(library, data, progress):
    asset = library.store.get(data['asset'], data.get('version'))
    snap = asset['snapshot']
    m = next((x for x in snap['media'] if x['id'] == data.get('media')), None)
    if not m:
        raise ValueError('请选择这个资产版本里的媒体')
    obj = library.store.object(m['hash'])
    source = library.store.path(obj['path'])
    action, params = data['operation'], data.get('params', {})
    if action not in ('image_transform', 'frame', 'clip', 'audio', 'audio_clip', 'convert'):
        raise ValueError('本地处理操作不支持')
    progress(.05, '读取原件与处理范围')
    token = data.setdefault('operation_id', uid())
    directory = library.root / 'staging' / token
    directory.mkdir(exist_ok=True)
    tool_params = {}
    if action == 'image_transform':
        if obj['kind'] != 'image':
            raise ValueError('此操作需要图片')
        output = directory / 'image.png'
        with Image.open(source) as raw:
            image = ImageOps.exif_transpose(raw)
            width, height = image.size
            x = int(number(params.get('x', 0), 0, width - 1, '裁切X'))
            y = int(number(params.get('y', 0), 0, height - 1, '裁切Y'))
            w = int(number(params.get('crop_width') or width - x, 1, width - x, '裁切宽度'))
            h = int(number(params.get('crop_height') or height - y, 1, height - y, '裁切高度'))
            image = image.crop((x, y, x + w, y + h))
            rotation = int(params.get('rotation', 0))
            if rotation not in (0, 90, 180, 270):
                raise ValueError('旋转角度须为0、90、180或270')
            if rotation:
                image = image.rotate(-rotation, expand=True)
            resize_width = int(number(params.get('width') or image.width, 1, 16384, '输出宽度'))
            resize_height = int(number(params.get('height') or round(image.height * resize_width / image.width), 1, 16384, '输出高度'))
            if resize_width * resize_height > 64000000:
                raise ValueError('输出画布过大，请减少尺寸')
            if image.size != (resize_width, resize_height):
                image = image.resize((resize_width, resize_height), Image.Resampling.LANCZOS)
            if image.mode not in ('1','L','LA','P','RGB','RGBA','I','I;16'):
                image = image.convert('RGBA' if obj.get('alpha') else 'RGB')
            progress(.45, '保存派生图片')
            image.save(output, icc_profile=raw.info.get('icc_profile'))
            tool_params = dict(crop=[x,y,w,h], rotation=rotation, size=[resize_width,resize_height])
    else:
        kind = obj['kind']
        if kind not in ('audio', 'video'):
            raise ValueError('此操作需要声音或视频')
        duration = obj['duration']
        start = number(params.get('start', 0), 0, max(0, duration - .001), '入点')
        end = number(params.get('end') or duration, start + .001, duration + .01, '出点')
        tool_params = dict(requested_start_seconds=start, requested_end_seconds=end,
                           source_time_base=obj.get('time_base'), source_fps=obj.get('fps'), time_units='seconds')
        args = ['ffmpeg', '-y', '-v', 'error', '-ss', start, '-i', source]
        if action == 'frame':
            if kind != 'video':
                raise ValueError('抽帧需要视频')
            output = directory / 'frame.png'
            args += ['-map', '0:v:0', '-frames:v', '1', output]
            tool_params['selection'] = 'first decoded frame at or after requested presentation time'
            if params.get('position') == 'last':
                # Decode the tail and keep the final presented frame, including VFR sources.
                args = ['ffmpeg', '-y', '-v', 'error', '-sseof', -min(10, duration), '-i', source,
                        '-map', '0:v:0', '-an', '-fps_mode', 'passthrough', '-update', '1', output]
                tool_params['selection'] = 'last presented frame of original video; no FPS-derived frame index'
        elif action in ('audio', 'audio_clip'):
            if not obj.get('has_audio'):
                raise ValueError('原件没有音轨')
            output = directory / 'audio.wav'
            args += ['-t', end - start, '-map', '0:a:0', '-vn', '-c:a', 'pcm_s24le', output]
        elif action in ('clip', 'convert') and kind == 'video':
            output = directory / 'video.mp4'
            args += ['-t', end - start, '-map', '0:v:0', '-map', '0:a?', '-c:v', 'libx264', '-crf', '18',
                     '-pix_fmt', 'yuv420p', '-fps_mode', 'passthrough', '-c:a', 'aac', '-movflags', '+faststart', output]
        elif action == 'convert' and kind == 'audio':
            output = directory / 'audio.wav'
            args += ['-t', end - start, '-vn', '-c:a', 'pcm_s24le', output]
        else:
            raise ValueError('所选操作与媒体类型不匹配')
        progress(.2, '本地处理媒体，原件保持不变')
        command(args, 7200)
    provenance = dict(type='derived', parent=dict(asset=asset['id'], version=snap['id'], media=m['id'], hash=m['hash']),
                      operation=action, parameters=tool_params,
                      tool='Pillow' if action == 'image_transform' else command(['ffmpeg', '-version']).decode(errors='replace').splitlines()[0])
    result = library.ingest(output, data.get('name') or snap['name'] + ' · 派生',
                            data.get('metadata', {}), provenance, key='derive:' + token,
                            progress=lambda value,note: progress(.7 + value*.3,note))
    return result
