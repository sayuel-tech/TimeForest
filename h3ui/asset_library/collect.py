"""User-initiated folder collection; never watch or recursively crawl disks by default."""
import hashlib
import json
import time
from pathlib import Path

from .store import encode

EXTENSIONS = {'.png','.jpg','.jpeg','.webp','.gif','.tif','.tiff','.bmp','.mp4','.mov','.mkv','.webm','.avi','.wav','.mp3','.flac','.m4a','.ogg','.opus','.aac'}


def scan(library, data, progress):
    root = Path(data['directory']).expanduser().resolve()
    if not root.is_dir() or root == Path(root.anchor) or len(root.parts) < 3:
        raise ValueError('请选择具体素材文件夹，不能扫描整块磁盘或用户根目录')
    if root.name.lower() in ('users','windows','program files','programdata'):
        raise ValueError('请选择具体输出文件夹')
    items, skipped, total = [], [], 0
    files = root.rglob('*') if data.get('recursive', False) else root.iterdir()
    for index, entry in enumerate(files):
        if index >= 20000 or len(items) >= 5000:
            skipped.append({'name':'剩余项目','reason':'本次达到5000项／20000目录项上限，请缩小范围继续收集'})
            break
        if not entry.is_file() or entry.suffix.lower() not in EXTENSIONS:
            continue
        path = entry.resolve()
        if root not in path.parents:
            skipped.append(dict(name=entry.name,reason='链接目标在所选文件夹之外')); continue
        stat = path.stat()
        if stat.st_size == 0 or time.time() - stat.st_mtime < 2:
            skipped.append(dict(name=entry.name,reason='可能仍在写入，稍后重试')); continue
        if stat.st_size > library.max_bytes:
            skipped.append(dict(name=entry.name,reason='超过单文件限制')); continue
        progress(min(.95, len(items)/5000), f'检查待整理文件：{entry.name}')
        from .media import digest
        sha = digest(path)
        with library.store.connect() as db:
            duplicate = bool(db.execute('SELECT 1 FROM objects WHERE hash=?',(sha,)).fetchone())
        token = hashlib.sha256((str(path)+str(stat.st_mtime_ns)+sha).encode()).hexdigest()
        payload = dict(path=str(path),root=str(root),name=entry.stem,hash=sha,mtime=stat.st_mtime_ns,size=stat.st_size)
        sidecar = path.with_suffix('.json')
        if sidecar.is_file() and sidecar.stat().st_size <= 20*1024**2 and root in sidecar.resolve().parents:
            try:
                value=json.loads(sidecar.read_text(encoding='utf-8-sig'))
                if isinstance(value,dict):payload['sidecar']=value
            except (ValueError,OSError):
                pass
        with library.store.connect() as db:
            db.execute('INSERT OR REPLACE INTO operations VALUES(?,?,?,?,?)',(token,'scan_file','registered',encode(payload),time.time()))
        items.append(dict(id=token,name=str(entry.relative_to(root)),bytes=stat.st_size,duplicate=duplicate))
        total+=stat.st_size
    return dict(directory=str(root),items=items,skipped=skipped,bytes=total)


def import_scan(library, data, progress):
    with library.store.connect() as db:
        row=db.execute("SELECT body FROM operations WHERE key=? AND type='scan_file'",(data['file'],)).fetchone()
    if not row:raise ValueError('文件未在本次收集中登记')
    item=json.loads(row[0]);path=Path(item['path'])
    from .media import digest
    if not path.is_file() or path.stat().st_mtime_ns!=item['mtime'] or digest(path)!=item['hash']:
        raise ValueError('文件仍在变化或已移动，请重新收集；不会导入不完整输出')
    provenance=dict(type='comfy_output',original_name=path.name,scan_directory=item['root'])
    if item.get('sidecar'):provenance['sidecar']=item['sidecar']
    return library.ingest(path,data.get('name') or item['name'],data.get('metadata',{}),provenance,
                          key='scan-result:'+data['file'],progress=progress)
