"""Populate only an explicitly generation-disabled local validation server."""
import argparse
import io
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw
from h3ui.asset_library.service import Library
from h3ui.asset_library.media import command

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--config', required=True)
args = parser.parse_args()
cfg = json.loads(Path(args.config).read_text(encoding='utf-8-sig'))
if not cfg.get('studio_disable_generation') or cfg['comfy_url'] != 'http://127.0.0.1:1':
    raise SystemExit('Requires a fully isolated, generation-disabled fixture config')
root = Path(args.config).parent / 'fixtures'
root.mkdir(exist_ok=True)
lib = Library(cfg['asset_library_dir'])
for i, (name, category, color) in enumerate([('丹眉 · 透明原图验收', 'character', '#809a8a'), ('沙漠 · 场景验收', 'scene', '#b69d78'), ('陶器 · 道具验收', 'prop', '#a27c69')]):
    path = root / (category + '.png')
    im = Image.new('RGBA', (640, 480), '#eee7da' if i else (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.ellipse((200, 75, 440, 310), fill=color)
    draw.rounded_rectangle((130, 280, 510, 450), radius=80, fill=color)
    im.save(path)
    lib.ingest(path, name, {'categories': [category], 'record_prompt': '隔离验收资料，不应进入任何生成工作流。'}, key='fixture-' + category)
video = root / 'reference.mp4'
command(['ffmpeg', '-y', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=30000/1001',
         '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', '3.5', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', video])
lib.ingest(video, '声画同步 · 视频验收', {'categories': ['video'], 'tags': ['29.97fps', '同步检查']}, key='fixture-video')
audio = root / 'voice.wav'
command(['ffmpeg', '-y', '-v', 'error', '-i', video, '-vn', '-c:a', 'pcm_s16le', audio])
lib.ingest(audio, '声音绑定 · 音频验收', {'categories': ['voice']}, key='fixture-audio')
print(json.dumps({'assets': lib.query({})['total'], 'fixtures': str(root)}, ensure_ascii=False))
