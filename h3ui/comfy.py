"""ComfyUI HTTP API 客户端: 提交工作流、轮询结果、取输出文件。"""
from __future__ import annotations

import json
import time
import threading
from urllib.parse import quote
import urllib.error
import urllib.request
from pathlib import Path


class ComfyError(RuntimeError):
    pass


class ComfyCancelled(ComfyError):
    """A requested exact job cancellation has been confirmed by the engine."""


class ComfyClient:
    def __init__(self, url: str, timeout_seconds: int = 5400):
        self.url = url.rstrip("/")
        self.timeout = timeout_seconds
        self._cancelled = set()
        self._cancel_lock = threading.RLock()

    def cancel_job(self, prompt_id):
        with self._cancel_lock:
            result = self._post('/api/jobs/'+quote(prompt_id,safe='')+'/cancel', {})
            if result.get('cancelled') is True:
                self._cancelled.add(prompt_id)
                return True
        return False

    # ---------------- HTTP ----------------
    def _get(self, endpoint: str, timeout: int = 60) -> dict:
        try:
            with urllib.request.urlopen(self.url + endpoint, timeout=timeout) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            raise ComfyError(f"ComfyUI request {endpoint} failed: {exc}") from exc

    def _post(self, endpoint: str, payload: dict) -> dict:
        request = urllib.request.Request(
            self.url + endpoint,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")
            raise ComfyError(f"ComfyUI {endpoint} HTTP {exc.code}: {body}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ComfyError(f"ComfyUI request {endpoint} failed: {exc}") from exc

    # ---------------- 业务 ----------------
    def system_status(self) -> dict:
        return self._get("/system_stats")

    def submit(self, workflow: dict, client_id: str) -> str:
        response = self._post("/prompt", {"prompt": workflow, "client_id": client_id})
        prompt_id = response.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ComfyError(f"ComfyUI rejected workflow: {json.dumps(response, ensure_ascii=False)}")
        return prompt_id

    def wait(self, prompt_id: str, timeout: int | None = None) -> dict:
        """轮询 /history/<id> 直到 success / error / 超时。"""
        deadline = time.monotonic() + (timeout or self.timeout)
        failures = 0
        while time.monotonic() < deadline:
            try:
                history = self._get(f"/history/{prompt_id}")
                failures = 0
            except ComfyError:
                failures += 1
                if failures >= 4:
                    raise
                time.sleep(min(20, 2 ** failures))
                continue
            record = history.get(prompt_id)
            if isinstance(record, dict):
                status = record.get("status", {})
                status_text = status.get("status_str") if isinstance(status, dict) else ""
                if status_text == "success":
                    with self._cancel_lock:self._cancelled.discard(prompt_id)
                    return history
                if status_text == "error":
                    with self._cancel_lock:
                        if prompt_id in self._cancelled:
                            self._cancelled.discard(prompt_id)
                            raise ComfyCancelled('用户停止了本次生成；已有结果保留')
                    raise ComfyError(
                        f"ComfyUI job {prompt_id} failed: "
                        f"{json.dumps(status, ensure_ascii=False)}")
            with self._cancel_lock:
                cancelled = prompt_id in self._cancelled
            if cancelled:
                queue = self._get('/queue')
                if not any(len(r)>1 and r[1]==prompt_id for r in queue.get('queue_running',[])+queue.get('queue_pending',[])):
                    # Completion can race the cancellation response; prefer actual history.
                    final = self._get(f'/history/{prompt_id}')
                    with self._cancel_lock:self._cancelled.discard(prompt_id)
                    if final.get(prompt_id,{}).get('status',{}).get('status_str')=='success':return final
                    raise ComfyCancelled('引擎已确认停止本次任务；未删除历史记录')
            time.sleep(5)
        raise ComfyError(f"Timed out waiting for ComfyUI job {prompt_id}")

    def output_path(self, item: dict, output_root: Path) -> Path:
        filename = item.get("filename")
        subfolder = item.get("subfolder", "")
        if not isinstance(filename, str) or not filename:
            raise ComfyError(f"Invalid ComfyUI output item: {item}")
        candidate = (Path(output_root) / str(subfolder) / filename).resolve()
        root = Path(output_root).resolve()
        if candidate != root and root not in candidate.parents:
            raise ComfyError(f"Refusing output path outside configured output root: {candidate}")
        return candidate

    def first_video(self, history: dict, prompt_id: str, node_id: str, output_root: Path) -> Path:
        """从 history 里取指定节点输出的第一个视频文件(等待其落盘)。"""
        record = history.get(prompt_id)
        if not isinstance(record, dict):
            raise ComfyError(f"ComfyUI history has no record for {prompt_id}")
        outputs = record.get("outputs", {})
        node_outputs = outputs.get(node_id)
        if not isinstance(node_outputs, dict):
            raise ComfyError(f"ComfyUI history has no output for node {node_id}")
        for items in node_outputs.values():
            if not isinstance(items, list):
                continue
            for item in reversed(items):
                if isinstance(item, dict):
                    path = self.output_path(item, output_root)
                    if path.suffix.lower() in {".mp4", ".webm", ".mov", ".mkv", ".avi"}:
                        for _ in range(12):
                            if path.exists() and path.stat().st_size > 0:
                                return path
                            time.sleep(2)
        raise ComfyError(
            f"No local video output found for node {node_id}; check comfy_output_dir")
