"""Managed media ingestion and portable local backups; no engine calls."""
import copy
import json
import os
import shutil
import sqlite3
import tempfile
import time
from contextlib import closing
from pathlib import Path

from . import media
from .store import LibraryStore, uid, encode


class Library:
    def complete_usage(self, project, entries, operation, used_at=None):
        from .usage import complete
        return complete(self, project, entries, operation, used_at)

    def record_usage(self, project, entries, operation, used_at=None):
        from .usage import record
        return record(self, project, entries, operation, used_at)

    def __init__(self, root, cfg=None):
        self.store = LibraryStore(root)
        self.root = self.store.root
        self.cfg = cfg or {}
        self.max_bytes = int(self.cfg.get('asset_max_file_bytes', 32 * 1024**3))
        for name in ('objects', 'previews', 'manifests', 'staging', 'backups'):
            (self.root / name).mkdir(exist_ok=True)

    def stage(self, stream, filename, progress=None):
        suffix = Path(filename or '').suffix.lower()
        if suffix not in ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.tif', '.tiff', '.bmp', '.mp4', '.mov',
                          '.webm', '.mkv', '.avi', '.wav', '.flac', '.mp3', '.m4a', '.ogg', '.aac', '.opus', '.json'):
            raise ValueError('文件格式暂不支持')
        dest = self.root / 'staging' / (uid() + suffix)
        count = 0
        try:
            with dest.open('xb') as out:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    count += len(block)
                    if count > self.max_bytes:
                        raise ValueError('文件超过本站单文件上限')
                    out.write(block)
                    if progress:
                        progress(count)
                out.flush()
                os.fsync(out.fileno())
            if count == 0:
                raise ValueError('文件为空')
            return dest
        except Exception:
            dest.unlink(missing_ok=True)
            raise

    def ingest(self, path, name, metadata=None, provenance=None, key=None, aid=None, revision=None, progress=None, primary=False):
        """Caller passes a trusted staged path; APIs never accept arbitrary input paths."""
        path = Path(path)
        progress = progress or (lambda value, note: None)
        if key:
            with self.store.connect() as db:
                done = db.execute("SELECT body FROM operations WHERE key=? AND state='done'", (key,)).fetchone()
            if done:
                return self.public(self.store.get(json.loads(done[0])['asset']))
        progress(.1, '读取原件与媒体信息')
        info = media.inspect(path)
        sha = media.digest(path)
        relative = f"objects/{sha[:2]}/{sha}{info['extension']}"
        original = self.store.path(relative)
        original.parent.mkdir(parents=True, exist_ok=True)
        progress(.45, '保存原件')
        if original.exists():
            if media.digest(original) != sha:
                raise ValueError('库内同名哈希文件损坏，请先从备份恢复')
        else:
            fd, temp = tempfile.mkstemp(dir=original.parent, suffix='.tmp')
            os.close(fd)
            temp = Path(temp)
            try:
                shutil.copyfile(path, temp)
                if media.digest(temp) != sha:
                    raise ValueError('原件复制校验失败')
                os.replace(temp, original)
            finally:
                temp.unlink(missing_ok=True)
        old = self.store.get(aid)['snapshot'] if aid else {}
        fields = {k: v for k, v in (metadata or {}).items() if k in ('record_prompt', 'description', 'categories', 'tags', 'favorite', 'state')}
        data = {**old, **fields, 'name': name, 'media': [*old.get('media', []),
                dict(id=uid(), hash=sha, role='alternate' if old else 'primary', name=Path(path).name)]}
        if primary:
            data['media'] = [{**m, 'role': 'primary' if i == len(data['media'])-1 else 'alternate'} for i,m in enumerate(data['media'])]
            data['cover_hash'] = sha
        # Provenance is separate from editable text and never overwritten by a metadata PATCH.
        data.setdefault('bindings', [])
        origin = copy.deepcopy(provenance or {'type': 'local'})
        embedded = info.get('generation_records', {})
        if embedded:
            if origin.get('records'):
                origin['embedded_records'] = embedded
            else:
                origin['records'] = embedded
        origin.setdefault('records', {})
        origin['metadata_status'] = 'present' if origin['records'] or embedded else 'absent'
        data.setdefault('provenance', origin)
        data['media'][-1]['provenance'] = origin
        obj = dict(hash=sha, path=relative, bytes=path.stat().st_size, meta=info)
        result = self.store.save(data, aid, revision, objects=[obj], key=key)
        self.write_manifest(result)
        progress(.8, '制作浏览预览')
        try:
            media.preview(original, info, self.root / 'previews' / sha / 'cover.png')
        except Exception as exc:
            # A browser derivative can be rebuilt; it must not invalidate a saved original.
            (self.root / 'previews' / sha).mkdir(exist_ok=True)
            (self.root / 'previews' / sha / 'error.txt').write_text(str(exc), encoding='utf-8')
        progress(1, '资产已入库')
        return self.public(result)

    def write_manifest(self, item):
        dest = self.root / 'manifests' / item['id'] / (item['snapshot']['id'] + '.json')
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            # SQLite is authoritative if a crash occurs before this rebuildable manifest.
            try:
                dest.write_text(encode(item['snapshot']), encoding='utf-8')
            except OSError:
                pass

    def public(self, item, compact=False, objects=None):
        item = copy.deepcopy(item)
        if compact:
            for field in ('record_prompt', 'description'):
                item['snapshot'].pop(field, None)
            item['snapshot']['provenance'] = {k:v for k,v in item['snapshot'].get('provenance', {}).items() if k in ('type', 'metadata_status', 'project', 'candidate')}
        for entry in item['snapshot']['media']:
            if compact:
                entry.pop('provenance', None)
            obj = self.store.object(entry['hash']) if objects is None else objects[entry['hash']]
            entry['meta'] = {k: v for k, v in obj.items() if k not in ('path', 'generation_records')}
            entry['url'] = f"/api/v5/library/media/{entry['hash']}"
            if (self.root / 'previews' / entry['hash'] / 'cover.png').is_file():
                entry['preview_url'] = f"/api/v5/library/media/{entry['hash']}/preview"
            if entry.get('role') == 'primary' and item['snapshot'].get('cover_hash'):
                entry['preview_url'] = f"/api/v5/library/media/{item['snapshot']['cover_hash']}"
        return item

    def query(self, filters):
        result = self.store.query(filters)
        objects=self.store.objects(m['hash'] for x in result['items'] for m in x['snapshot']['media'])
        result['items'] = [self.public(x, compact=True, objects=objects) for x in result['items']]
        return result

    def update(self, aid, revision, changes):
        item = self.store.get(aid)
        allowed = {'name', 'record_prompt', 'description', 'categories', 'tags', 'favorite', 'state', 'bindings', 'primary_media', 'cover_hash'}
        if set(changes) - allowed:
            raise ValueError('存在不能直接编辑的资产字段')
        snapshot = {**item['snapshot'], **copy.deepcopy(changes)}
        if 'primary_media' in changes:
            chosen = changes['primary_media']
            if chosen not in [m['id'] for m in snapshot['media']]:
                raise ValueError('主媒体必须属于当前资产版本')
            snapshot['media'].sort(key=lambda m: m['id'] != chosen)
            for m in snapshot['media']:
                m['role'] = 'primary' if m['id'] == chosen else 'alternate'
            snapshot.pop('primary_media', None)
        if changes.get('cover_hash') and self.store.object(changes['cover_hash'])['kind'] != 'image':
            raise ValueError('封面必须是库内图片')
        result = self.store.save(snapshot, aid, revision)
        self.write_manifest(result)
        return self.public(result)

    def backup(self, target=None):
        """SQLite backup pins the exact immutable object set; does not copy WAL files."""
        dest = Path(target) if target else self.root / 'backups' / (time.strftime('%Y%m%d-%H%M%S') + '-' + uid()[:8])
        if dest.exists():
            raise ValueError('备份目标已存在，请使用空目录')
        dest.mkdir(parents=True)
        try:
            with self.store.connect() as source, closing(sqlite3.connect(dest / 'library.sqlite3')) as out:
                source.backup(out)
            with closing(sqlite3.connect(dest / 'library.sqlite3')) as db:
                rows = db.execute('SELECT hash,path,bytes FROM objects').fetchall()
            manifest = []
            for sha, relative, size in rows:
                path = self.store.path(relative)
                output = dest / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, output)
                if media.digest(output) != sha:
                    raise ValueError('备份媒体校验失败')
                manifest.append(dict(hash=sha, path=relative, bytes=size))
            manifest.append(dict(path='library.sqlite3', hash=media.digest(dest / 'library.sqlite3')))
            (dest / 'backup.json').write_text(encode(dict(schema_version=1, created=time.time(), files=manifest)), encoding='utf-8')
            return dict(path=str(dest), files=len(rows), bytes=sum(r[2] for r in rows))
        except Exception:
            # Keep failed backup for diagnosis; never switch config on partial copies.
            (dest / 'INCOMPLETE').write_text('Backup incomplete; do not restore.', encoding='utf-8')
            raise

    def verify_backup(self, directory):
        directory = Path(directory).resolve()
        if (directory / 'INCOMPLETE').exists():
            raise ValueError('备份没有完成')
        data = json.loads((directory / 'backup.json').read_text(encoding='utf-8'))
        for entry in data['files']:
            path = (directory / entry['path']).resolve()
            if directory not in path.parents or not path.is_file() or media.digest(path) != entry['hash']:
                raise ValueError('备份缺失或哈希不符：' + entry['path'])
        with closing(sqlite3.connect(directory / 'library.sqlite3')) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('备份数据库完整性检查失败')
        return data

    def storage(self):
        usage = shutil.disk_usage(self.root)
        with self.store.connect() as db:
            count, size = db.execute('SELECT count(*),coalesce(sum(bytes),0) FROM objects').fetchone()
        return dict(directory=str(self.root), free_bytes=usage.free, stored_bytes=size, objects=count,
                    max_file_bytes=self.max_bytes, schema_version=1)

    def attach_tasks(self, jobs, *, recover_tasks=True):
        from ..local_tasks import LocalTasks
        from .uploads import Uploads
        self.tasks = LocalTasks(self.store, jobs, recover_tasks=recover_tasks)
        self.uploads = Uploads(self)
        self.tasks.handlers.update(ingest=self.uploads.process, backup=lambda data, progress: self.backup())
        from .derive import derive
        self.tasks.handlers['derive'] = lambda data, progress: derive(self, data, progress)
        from .collect import scan, import_scan
        from .packs import Packs
        self.packs = Packs(self)
        self.tasks.handlers.update(scan=lambda data, progress: scan(self, data, progress),
                                   scan_import=lambda data, progress: import_scan(self, data, progress),
                                   pack=self.packs.export, pack_import=self.packs.import_pack)
