"""Separate GPU and bounded local-media work; a project owns one mutation lease."""
import threading
import time
import uuid


class JobManager:
    def __init__(self, cfg):
        self.cfg = cfg
        self._lock = threading.RLock()
        self._jobs = {}
        self.gpu_guards = []

    def is_busy(self, project_id=None):
        with self._lock:
            return any(project_id is None or j["project_id"] == project_id for j in self._jobs.values())

    def current(self, project_id=None):
        with self._lock:
            jobs = [j for j in self._jobs.values() if project_id is None or j["project_id"] == project_id]
            return dict(jobs[0]) if jobs else None

    def snapshot(self):
        with self._lock:
            return [dict(j) for j in self._jobs.values()]

    def _reserve(self, kind, project_id, lane=None):
        lane = lane or ("gpu" if any(value in kind for value in ('generate','resume','recover')) else "media")
        with self._lock:
            if lane == 'gpu' and any(not guard(kind, project_id) for guard in self.gpu_guards):
                return None
            if self.is_busy(project_id):
                return None
            limit = 1 if lane == "gpu" else max(1, int(self.cfg.get("media_workers", 2)))
            if sum(j["lane"] == lane for j in self._jobs.values()) >= limit:
                return None
            key = uuid.uuid4().hex
            self._jobs[key] = dict(id=key, kind=kind, project_id=project_id, lane=lane, started=time.time())
            return key

    def _release(self, key):
        with self._lock:
            self._jobs.pop(key, None)

    def run_inline(self, kind, project_id, fn):
        key = self._reserve(kind, project_id)
        if key is None:
            raise RuntimeError("当前项目或处理通道忙碌，请稍后")
        try:
            return fn()
        finally:
            self._release(key)

    def start(self, kind, project_id, fn, lane=None):
        key = self._reserve(kind, project_id, lane)
        if key is None:
            return False
        def wrapper():
            try:
                fn()
            except Exception as exc:
                print(f"[job:{kind}] {exc}", flush=True)
            finally:
                self._release(key)
        threading.Thread(target=wrapper, daemon=True).start()
        return True
