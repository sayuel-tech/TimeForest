"""Immutable originals, normalized RGB copies and separate logical masks."""
import hashlib
import shutil
from pathlib import Path
from PIL import Image, ImageOps
from .store import uid
from .compiler import active_slots


def prepare(store, pid, stream, name, provenance=None, mask=False):
    store.project(pid)
    key = uid()
    directory = store.directory(pid) / 'image_inputs' / key
    directory.mkdir(parents=True)
    original = directory / 'original'
    try:
        with original.open('wb') as out:
            count = 0
            for block in iter(lambda: stream.read(1024*1024), b''):
                count += len(block)
                if count > 40*1024*1024: raise ValueError('图片不能超过40MB')
                out.write(block)
        with Image.open(original) as source:
            if source.width*source.height > 40*1024*1024: raise ValueError('图片像素过大')
            source.load()
            fmt = (source.format or 'PNG').lower()
            picture = ImageOps.exif_transpose(source)
            has_alpha = picture.mode in ('RGBA', 'LA') or 'transparency' in picture.info
            if mask:
                picture = picture.convert('L')
            else:
                rgba = picture.convert('RGBA')
                background = Image.new('RGBA', rgba.size, 'white')
                picture = Image.alpha_composite(background, rgba).convert('RGB')
            path = directory / ('mask.png' if mask else 'image.png')
            picture.save(path)
        original.rename(directory / ('original.'+('jpg' if fmt=='jpeg' else fmt)))
        record = dict(id=key, project=pid, name=str(name)[:200], path=str(path), width=picture.width,
                      height=picture.height, hash=hashlib.sha256(path.read_bytes()).hexdigest(),
                      provenance=provenance or {}, mask=mask, alpha_flattened=has_alpha and not mask)
        if mask: record['area'] = sum(picture.histogram()[1:])/(picture.width*picture.height)
        store.put('inputs', record)
        return record
    except Exception:
        # Only this newly created, unreferenced upload directory.
        shutil.rmtree(directory)
        raise


def execution_inputs(store, pid, task, directory):
    if task['submode']=='text':return {}
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    result = {}
    for slot in active_slots(task):
        if not task.get(slot): continue
        record = store.get('inputs', task[slot], pid)
        dest = directory / (slot+'.png')
        if slot == 'A' and task['submode'] == 'region':
            mark = store.get('inputs', task['mask'], pid)
            with Image.open(record['path']) as image, Image.open(mark['path']) as mask:
                if image.size != mask.size: raise ValueError('遮罩与原图尺寸不同')
                image = image.convert('RGBA')
                # LoadImage yields 1-alpha as MASK; source RGB remains untouched.
                image.putalpha(ImageOps.invert(mask.convert('L')))
                image.save(dest)
        else: shutil.copyfile(record['path'], dest)
        result[slot] = dest
    return result
