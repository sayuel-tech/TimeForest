"""Durable local task queue with explicit retries and shared media concurrency."""
import json
import threading
import time

from ..asset_library.store import uid, encode


class LocalTasks:
    def __init__(self, store, jobs, *, recover_tasks=True):
        self.store, self.jobs = store, jobs
        self.handlers = {}
        self.lock = threading.RLock()
        self.thread = None
        self.stop_event = threading.Event()
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS local_tasks(id TEXT PRIMARY KEY, key TEXT UNIQUE, action TEXT, payload TEXT, state TEXT, progress REAL, note TEXT, result TEXT, created REAL, updated REAL)')
            if recover_tasks:
                db.execute("UPDATE local_tasks SET state='interrupted',note='网站重启，原件保留；可重试本地任务' WHERE state='running'")

    def get(self, tid):
        with self.store.connect() as db:
            row = db.execute('SELECT * FROM local_tasks WHERE id=?', (tid,)).fetchone()
        if not row:
            raise KeyError('本地任务不存在')
        return {**{k: row[k] for k in row.keys() if k not in ('payload', 'result')}, 'result': json.loads(row['result']) if row['result'] else None}

    def list(self):
        with self.store.connect() as db:
            rows = db.execute("SELECT id FROM local_tasks WHERE state IN ('queued','running','failed','interrupted') OR id IN (SELECT id FROM local_tasks ORDER BY created DESC LIMIT 100) ORDER BY created DESC").fetchall()
        return [self.get(r[0]) for r in rows]

    def cancel(self, tid):
        with self.lock, self.store.connect() as db:
            changed=db.execute("UPDATE local_tasks SET state='cancelled',note='用户取消排队，原件保留',updated=? WHERE id=? AND state='queued'", (time.time(),tid)).rowcount
            if not changed:raise ValueError('本地任务已开始或结束，请刷新状态；运行中的文件处理会完成当前操作')

    def submit(self, action, payload, key=None):
        if action not in self.handlers:
            raise ValueError('本地处理类型不支持')
        with self.lock, self.store.connect() as db:
            existing = db.execute('SELECT id,action,payload FROM local_tasks WHERE key=?', (key,)).fetchone() if key else None
            if existing:
                if existing['action'] != action or json.loads(existing['payload']) != payload:
                    raise ValueError('该操作标识已用于不同任务，请使用新的操作标识')
                return self.get(existing['id'])
            tid, now = uid(), time.time()
            db.execute('INSERT INTO local_tasks VALUES(?,?,?,?,?,?,?,?,?,?)', (tid, key, action, encode(payload), 'queued', 0, '等待本地处理', None, now, now))
        self.wake()
        return self.get(tid)

    def wake(self):
        with self.lock:
            if not self.thread or not self.thread.is_alive():
                self.thread = threading.Thread(target=self.dispatch, daemon=True, name='library-local-tasks')
                self.thread.start()

    def dispatch(self):
        while not self.stop_event.is_set():
            with self.store.connect() as db:
                queued = db.execute("SELECT id,payload FROM local_tasks WHERE state='queued' ORDER BY created").fetchall()
            if not queued:
                # A submit cannot race the dispatcher exit while holding the same lock.
                with self.lock, self.store.connect() as db:
                    if not db.execute("SELECT 1 FROM local_tasks WHERE state='queued'").fetchone():
                        self.thread = None
                        return
                continue
            for row in queued:
                tid = row[0]
                project = json.loads(row['payload']).get('project')
                lease = self.jobs._reserve('library_media', project or 'library:' + tid)
                if lease is None:
                    continue
                with self.store.connect() as db:
                    changed = db.execute("UPDATE local_tasks SET state='running',updated=? WHERE id=? AND state='queued'", (time.time(), tid)).rowcount
                if not changed:
                    self.jobs._release(lease)
                    continue
                threading.Thread(target=self.run, args=(tid, lease), daemon=True, name='library-' + tid[:8]).start()
            self.stop_event.wait(.3)

    def run(self, tid, lease):
        try:
            with self.store.connect() as db:
                row = db.execute('SELECT action,payload FROM local_tasks WHERE id=?', (tid,)).fetchone()
            def progress(value, note):
                with self.store.connect() as db:
                    db.execute('UPDATE local_tasks SET progress=?,note=?,updated=? WHERE id=?', (max(0, min(1, value)), str(note), time.time(), tid))
            result = self.handlers[row['action']](json.loads(row['payload']), progress)
            # A visible completion must mean the project can accept the next action.
            self.jobs._release(lease)
            with self.store.connect() as db:
                db.execute("UPDATE local_tasks SET state='done',progress=1,note='已完成',result=?,updated=? WHERE id=?", (encode(result), time.time(), tid))
        except Exception as exc:
            with self.store.connect() as db:
                db.execute("UPDATE local_tasks SET state='failed',note=?,updated=? WHERE id=?", (str(exc), time.time(), tid))
        finally:
            self.jobs._release(lease)

    def retry(self, tid):
        with self.lock, self.store.connect() as db:
            if db.execute("UPDATE local_tasks SET state='queued',note='等待重试',updated=? WHERE id=? AND state IN ('failed','interrupted')", (time.time(), tid)).rowcount != 1:
                raise ValueError('该任务不需要重试')
        self.wake()
        return self.get(tid)
