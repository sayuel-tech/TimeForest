"""Separate image records in the existing database; conditional draft writes."""
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from ..studio_store import Conflict


def uid(): return uuid.uuid4().hex
def encode(value): return json.dumps(value, ensure_ascii=False)


class ImageStore:
    TABLES = {'projects', 'tasks', 'inputs', 'runs', 'outputs'}

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / 'studio.sqlite3'
        self.lock = threading.RLock()
        with self.connect() as db:
            for table in self.TABLES:
                db.execute(f'CREATE TABLE IF NOT EXISTS image_{table}(id TEXT PRIMARY KEY, project TEXT NOT NULL, body TEXT NOT NULL)')
                db.execute(f'CREATE INDEX IF NOT EXISTS image_{table}_project ON image_{table}(project)')
            db.execute('CREATE TABLE IF NOT EXISTS image_changes(token TEXT PRIMARY KEY, project TEXT, revision INTEGER, body TEXT, expires REAL, applied INTEGER DEFAULT 0)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db, timeout=30)
        try:
            with db: yield db
        finally: db.close()

    def directory(self, pid):
        if not pid or any(c not in '0123456789abcdef-' for c in pid): raise ValueError('项目ID无效')
        return self.root / pid

    def get(self, table, key, pid=None):
        assert table in self.TABLES
        with self.connect() as db:
            row = db.execute(f'SELECT body FROM image_{table} WHERE id=?', (key,)).fetchone()
        if not row: raise KeyError('图片记录不存在')
        item = json.loads(row[0])
        if pid and item['project'] != pid: raise ValueError('记录不属于当前图片项目')
        return item

    def exists(self, pid):
        with self.connect() as db: return db.execute('SELECT 1 FROM image_projects WHERE id=?', (pid,)).fetchone() is not None

    def all(self, table, pid=None):
        assert table in self.TABLES
        with self.connect() as db:
            rows = db.execute(f'SELECT body FROM image_{table}'+(' WHERE project=?' if pid else ''), (pid,) if pid else ()).fetchall()
        return [json.loads(r[0]) for r in rows]

    def put(self, table, item, db=None):
        assert table in self.TABLES
        if db is None:
            with self.lock, self.connect() as conn: return self.put(table, item, conn)
        db.execute(f'INSERT OR REPLACE INTO image_{table} VALUES(?,?,?)', (item['id'], item['project'], encode(item)))
        return item

    def project(self, pid, deleted=False):
        p = self.get('projects', pid)
        if p.get('deleted_at') and not deleted: raise KeyError('项目已删除，请先恢复')
        return p

    def mutate(self, table, key, fn):
        with self.lock:
            item = self.get(table, key)
            fn(item)
            self.put(table, item)
            return item

    def plan(self, pid, body):
        with self.lock:
            p = self.project(pid)
            if body['revision'] != p['revision']: raise Conflict('项目已更新，请刷新后重新保存；当前草稿保留')
            token = uid()
            with self.connect() as db:
                db.execute('DELETE FROM image_changes WHERE expires<? AND applied=0', (time.time(),))
                db.execute('INSERT INTO image_changes VALUES(?,?,?,?,?,0)', (token, pid, p['revision'], encode(body), time.time()+600))
            return dict(token=token, revision=p['revision'], summary=['保存图片草稿，已有运行与候选保持原快照'], ready=True)

    def apply(self, pid, token):
        with self.lock, self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT revision,body,expires,applied FROM image_changes WHERE token=? AND project=?', (token, pid)).fetchone()
            if not row: raise Conflict('保存计划不存在，请重新保存')
            if row[3]: return
            p = self.project(pid)
            if row[0] != p['revision'] or row[2] < time.time(): raise Conflict('保存计划过期，请重新保存')
            body = json.loads(row[1])
            for task in body['tasks']: self.put('tasks', task, db)
            p.update(name=body['name'], current_task=body['current_task'], revision=p['revision']+1, updated=time.time())
            self.put('projects', p, db)
            db.execute('UPDATE image_changes SET applied=1 WHERE token=?', (token,))
