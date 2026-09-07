"""项目注册表: 多项目 + 历史。

每个项目一个目录 data/<id>/,内有 state.json(项目状态)。
内存里保留权威副本(engine 直接改),路由用 snapshot() 拿深拷贝序列化。
"""
from __future__ import annotations

import copy
import json
import shutil
import threading
import time
import uuid
from pathlib import Path

from .config import resolve_path


class Registry:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        # 数据目录: config.data_dir(相对项目根)或默认 ROOT/data
        from .config import ROOT
        self.data_dir = Path(cfg["data_dir"]) if cfg.get("data_dir") else (ROOT / "data")
        self.data_dir = self.data_dir if self.data_dir.is_absolute() else (ROOT / self.data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.data_dir / "projects.json"
        self._lock = threading.RLock()
        self._projects: dict[str, dict] = {}
        self._load()

    # ---------------- 持久化 ----------------
    def _load(self) -> None:
        if not self.index_file.is_file():
            return
        try:
            index = json.loads(self.index_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            index = []
        for entry in index if isinstance(index, list) else []:
            pid = entry.get("id")
            if not pid:
                continue
            state_path = self.project_dir(pid) / "state.json"
            if state_path.is_file():
                try:
                    project = json.loads(state_path.read_text(encoding="utf-8"))
                    self._projects[pid] = project
                except json.JSONDecodeError:
                    continue

    def save(self, project: dict) -> None:
        with self._lock:
            project["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            self._projects[project["id"]] = project
            self._write_disk(project)

    def _write_disk(self, project: dict) -> None:
        directory = self.project_dir(project["id"])
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "state.json").write_text(
            json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
        self._write_index()

    def _write_index(self) -> None:
        entries = []
        for pid, proj in self._projects.items():
            entries.append({"id": pid, "name": proj.get("name", pid),
                            "created_at": proj.get("created_at", ""),
                            "status": proj.get("status", "idle")})
        entries.sort(key=lambda e: e["created_at"], reverse=True)
        self.index_file.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    def trash(self, pid: str, restore=False):
        with self._lock:
            current=self._projects.get(pid)
            if not current:raise KeyError('旧项目不存在')
            if current.get('status') in ['running','generating','preparing','assembling']:raise ValueError('旧项目仍在运行，请完成任务后再删除')
            project=copy.deepcopy(current)
            if restore:project.pop('deleted_at',None)
            else:project['deleted_at']=time.time()
            self.save(project)
            return project

    def delete(self, pid: str) -> bool:
        """删除项目: 移出注册表并删除整个数据目录。"""
        with self._lock:
            project = self._projects.pop(pid, None)
            if project is None:
                return False
            directory = self.project_dir(pid)
            if directory.is_dir():
                shutil.rmtree(directory, ignore_errors=True)
            self._write_index()
            return True

    # ---------------- 访问 ----------------
    def project_dir(self, pid: str) -> Path:
        return self.data_dir / pid

    def create(self, project: dict) -> str:
        with self._lock:
            pid = project["id"]
            directory = self.project_dir(pid)
            directory.mkdir(parents=True, exist_ok=True)
            self._projects[pid] = project
            self._write_disk(project)
            return pid

    def get(self, pid: str) -> dict | None:
        with self._lock:
            return self._projects.get(pid)

    def snapshot(self, pid: str) -> dict | None:
        with self._lock:
            project = self._projects.get(pid)
            if project is None:
                return None
            snapshot = copy.deepcopy(project)
        # 计算解锁状态(前段完成后解锁下一段)
        snapshot["needs_rebuild"] = snapshot.get("pipeline_version") != 4
        prev_ok = True
        for seg in snapshot["segments"]:
            status = seg["status"]
            seg["unlocked"] = bool(prev_ok)
            seg["can_generate"] = not snapshot["needs_rebuild"] and bool(prev_ok) and status in ("pending", "ready", "failed", "interrupted")
            seg["can_approve"] = not snapshot["needs_rebuild"] and status == "needs_review"
            seg["can_recover"] = not snapshot["needs_rebuild"] and status == "interrupted" and bool(seg.get("prompt_id"))
            seg["can_concat_all"] = False
            if status in ("done", "approved"):
                prev_ok = True
            else:
                prev_ok = False
        snapshot["all_done"] = bool(snapshot["segments"]) and all(s["status"] in ("done", "approved") for s in snapshot["segments"])
        snapshot["can_concat"] = snapshot["all_done"] and not bool(project.get("final"))
        return snapshot

    def list(self, page: int = 1, per_page: int = 24, mode: str = "", status: str = "", query: str = "", trash: bool = False) -> dict:
        with self._lock:
            items=[]
            for pid, proj in self._projects.items():
                if bool(proj.get("deleted_at")) != trash: continue
                if mode and proj.get("creation_mode", "swap") != mode: continue
                if status and proj.get("status", "idle") != status: continue
                if query and query.casefold() not in proj.get("name", pid).casefold(): continue
                segments=proj.get("segments",[]); complete=sum(s.get("status") in ("done","approved") for s in segments)
                reference_url=None
                refs=proj.get("refs") or []
                if refs:
                    try:
                        relative=Path(refs[0]).resolve().relative_to(self.project_dir(pid).resolve())
                        if (self.project_dir(pid)/relative).is_file():reference_url=f"/api/projects/{pid}/outputs/{relative.as_posix()}"
                    except (ValueError,OSError):
                        reference_url=None
                items.append({"id":pid,"name":proj.get("name",pid),"created_at":proj.get("created_at",""),
                    "updated_at":proj.get("updated_at",proj.get("created_at","")),"status":proj.get("status","idle"),
                    "creation_mode":proj.get("creation_mode","swap"),"profile":proj.get("profile"),
                    "duration_seconds":proj.get("source_frames",0)/max(proj.get("fps",24),1),
                    "segment_count":len(segments),"complete_segments":complete,
                    "progress":complete/len(segments) if segments else 0,"all_done":bool(segments) and complete==len(segments),
                    "cover":proj.get("cover"),"cover_url":(f"/api/projects/{pid}/outputs/visuals/cover-thumb.webp" if proj.get("cover") else None),
                    "reference_url":reference_url})
            items.sort(key=lambda x:x["updated_at"],reverse=True)
            total=len(items);start=max(0,(max(1,page)-1)*per_page)
            return {"projects":items[start:start+per_page],"page":max(1,page),"per_page":per_page,"total":total,
                    "pages":max(1,(total+per_page-1)//per_page)}

    # ---------------- 新建 ----------------
    @staticmethod
    def new_id() -> str:
        return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
