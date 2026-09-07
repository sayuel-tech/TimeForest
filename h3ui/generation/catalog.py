"""Persistent catalog cache with an explicit online refresh, never at startup."""
import copy
import json
import threading
import time
from pathlib import Path

from ..studio_progress import write


class EngineCatalog:
    def __init__(self, client, cache, builtin):
        self.client = client
        self.cache = Path(cache)
        self.lock = threading.RLock()
        self.builtin = json.loads(Path(builtin).read_text(encoding="utf-8"))
        self.info = copy.deepcopy(self.builtin)
        self.updated = None
        self.source = "builtin"
        self.connected = False
        self.error = None
        self.devices = []
        try:
            saved = json.loads(self.cache.read_text(encoding="utf-8"))
            if saved.get("url") == self.client.url and isinstance(saved.get("nodes"), dict) and saved["nodes"]:
                self.info = saved["nodes"]
                self.updated = saved.get("updated")
                self.source = "cache"
        except (OSError, ValueError, AttributeError):
            pass

    def status(self):
        return dict(connected=self.connected, updated=self.updated, source=self.source,
                    error=self.error, devices=self.devices,
                    note="最近在线核验结果；生成前会重新检查" if self.connected else "本地编排可用，生成引擎尚未在线核验")

    def connect(self):
        with self.lock:
            try:
                info = self.client._get("/object_info", timeout=10)
                if not isinstance(info, dict) or not info or not all(isinstance(v, dict) for v in info.values()):
                    raise ValueError("引擎返回的节点目录不合法")
                self.info = info
                self.updated = time.time()
                self.source = "online"
                self.connected = True
                self.error = None
                write(self.cache, dict(url=self.client.url, updated=self.updated, nodes=info))
            except Exception as exc:
                self.connected = False
                self.source = "cache" if self.updated else "builtin"
                self.error = str(exc)
                raise ValueError("生成引擎未连接，请启动ComfyUI并检查地址；资产与编排仍可使用") from exc
            return self.status()
