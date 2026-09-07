"""Bounded chunk uploads: server-issued paths, resumable offsets, no full video in RAM."""
import json
import os
import time
from pathlib import Path

from .store import uid, encode

CHUNK_BYTES = 8 * 1024 * 1024


class Uploads:
    def __init__(self, library):
        self.lib = library

    def start(self, filename, size, metadata=None, asset=None, revision=None):
        size = int(size)
        if size <= 0 or size > self.lib.max_bytes:
            raise ValueError('文件大小超过允许范围或为空')
        if self.lib.storage()['free_bytes'] < size * 2 + 64 * 1024**2:
            raise ValueError('可用空间不足以暂存并托管该文件')
        suffix = Path(filename).suffix.lower()
        if not suffix or len(suffix) > 8 or any(c not in '.abcdefghijklmnopqrstuvwxyz0123456789' for c in suffix):
            raise ValueError('文件后缀不支持')
        token = uid()
        payload = dict(token=token, filename=Path(filename).name, size=size, metadata=metadata or {},
                       asset=asset, revision=revision, path=f'staging/{token}{suffix}', created=time.time())
        self.lib.store.path(payload['path']).touch(exist_ok=False)
        with self.lib.store.connect() as db:
            db.execute('INSERT INTO operations VALUES(?,?,?,?,?)', (token, 'upload', 'receiving', encode(payload), time.time()))
        return self.status(token)

    def payload(self, token):
        with self.lib.store.connect() as db:
            row = db.execute("SELECT body,state FROM operations WHERE key=? AND type='upload'", (token,)).fetchone()
        if not row:
            raise KeyError('上传会话不存在')
        return json.loads(row['body']), row['state']

    def status(self, token):
        payload, state = self.payload(token)
        path = self.lib.store.path(payload['path'])
        return dict(token=token, name=payload['filename'], size=payload['size'], offset=path.stat().st_size if path.exists() else 0,
                    state=state, chunk_bytes=CHUNK_BYTES)

    def append(self, token, offset, stream, length):
        if length is None or not 0 < int(length) <= CHUNK_BYTES:
            raise ValueError('每块须为1～8MB')
        with self.lib.store.lock:
            payload, state = self.payload(token)
            path = self.lib.store.path(payload['path'])
            if state != 'receiving':
                raise ValueError('上传已提交处理，不能继续写入')
            actual = path.stat().st_size
            if int(offset) != actual or actual + int(length) > payload['size']:
                raise ValueError('上传位置不一致，请查询已接收长度后续传')
            with path.open('r+b') as out:
                out.seek(actual)
                try:
                    received = 0
                    while received < int(length):
                        chunk = stream.read(min(1024 * 1024, int(length) - received))
                        if not chunk:
                            raise ValueError('本次分块传输中断，请重试')
                        out.write(chunk); received += len(chunk)
                    out.flush(); os.fsync(out.fileno())
                except Exception:
                    out.truncate(actual)
                    raise
        return self.status(token)

    def complete(self, token):
        with self.lib.store.lock:
            payload, state = self.payload(token)
            with self.lib.store.connect() as db:
                existing = db.execute('SELECT id FROM local_tasks WHERE key=?', ('upload-task:' + token,)).fetchone()
            if existing:
                return self.lib.tasks.get(existing[0])
            if self.lib.store.path(payload['path']).stat().st_size != payload['size']:
                raise ValueError('文件尚未全部上传')
            if state not in ('receiving', 'processing'):
                raise ValueError('上传状态不允许处理')
            task = self.lib.tasks.submit('ingest', {'upload': token}, key='upload-task:' + token)
            with self.lib.store.connect() as db:
                db.execute("UPDATE operations SET state='processing' WHERE key=? AND state='receiving'", (token,))
            return task

    def process(self, data, progress):
        payload, state = self.payload(data['upload'])
        path = self.lib.store.path(payload['path'])
        item = self.lib.ingest(path, Path(payload['filename']).stem, payload['metadata'], key='upload-result:' + payload['token'],
                               aid=payload.get('asset'), revision=payload.get('revision'), progress=progress)
        with self.lib.store.connect() as db:
            db.execute("UPDATE operations SET state='done' WHERE key=?", (payload['token'],))
        path.unlink(missing_ok=True)
        return item
