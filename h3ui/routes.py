"""Current application entry and read-only access to historical project results.

All creation, generation, editing and model selection use /api/v5.
"""
from __future__ import annotations
import json
from pathlib import Path
from flask import Blueprint, current_app, jsonify, request, send_from_directory
from .config import ROOT

bp = Blueprint("api", __name__)

def ctx() -> dict:
    return current_app.config["H3UI"]


def ok(data: dict = None) -> tuple:
    return jsonify(data or {"ok": True}), 200


def fail(message: str, status: int = 400, code: str = "REQUEST_FAILED", stage: str = "", action: str = ""):
    if code == "REQUEST_FAILED":
        lower = message.casefold()
        rules = (("显存", "OUT_OF_MEMORY", "降低分辨率、关闭加速或检查显存占用"),
                 ("节点", "NODE_MISSING", "安装工作流所需节点后重试"),
                 ("模型", "MODEL_MISSING", "检查底模和LoRA文件是否已安装"),
                 ("帧数", "FRAME_MISMATCH", "保留运行记录并重新生成该镜头"),
                 ("超时", "TASK_TIMEOUT", "先使用找回结果，再决定是否重生成"),
                 ("工作流", "INCOMPATIBLE_CONFIG", "检查当前模式、底模和LoRA是否匹配"),
                 ("视频", "INVALID_ASSET", "检查素材格式后重新上传"))
        for word, mapped, next_action in rules:
            if word in lower:
                code, action = mapped, action or next_action
                break
    return jsonify({"error": message, "code": code, "stage": stage, "action": action}), status


@bp.get("/")
def index():
    return send_from_directory(str(ROOT / "static"), "index.html")


@bp.get("/api/health")
def health():
    return ok({"ok": True, "jobs_busy": ctx()["jobs"].is_busy(),
               "deployment": str(ROOT), "pipeline_version": 5,
               "revision": "time-forest-studio-v5", "modes": ["swap", "image_story", "text_story"],
               "review_modes": ["manual", "automatic"], "lora_slots": 3})


@bp.get("/api/projects")
def list_projects():
    try:
        return ok(ctx()["projects"].list(page=int(request.args.get("page",1)),per_page=min(100,int(request.args.get("per_page",24))),
            mode=request.args.get("mode",""),status=request.args.get("status",""),query=request.args.get("q","")))
    except ValueError:
        return fail("分页参数不正确",400)


@bp.get("/api/projects/<pid>")
def get_project(pid):
    c = ctx()
    snapshot = c["projects"].snapshot(pid)
    if snapshot is None:
        return fail("项目不存在", 404)
    _attach_web_paths(pid, snapshot)
    snapshot["jobs"] = {"busy": c["jobs"].is_busy(), "current": c["jobs"].current()}
    return ok(snapshot)


@bp.get("/api/projects/<pid>/storage")
def project_storage(pid):
    c=ctx(); project=c["projects"].get(pid)
    if project is None:return fail("项目不存在",404,"PROJECT_NOT_FOUND")
    root=c["projects"].project_dir(pid).resolve(); groups={"source":0,"segments":0,"attempts":0,"visuals":0,"output":0,"other":0}
    for path in root.rglob("*"):
        if not path.is_file():continue
        rel=path.relative_to(root).parts; key="other"
        if rel[0]=="source":key="source"
        elif rel[0]=="visuals":key="visuals"
        elif rel[0]=="out":key="output"
        elif rel[0]=="segments":key="attempts" if "attempts" in rel else "segments"
        groups[key]+=path.stat().st_size
    return ok({"bytes":sum(groups.values()),"groups":groups})


@bp.get("/api/projects/<pid>/segments/<int:index>/attempts")
def segment_attempts(pid, index):
    c=ctx(); project=c["projects"].get(pid)
    if project is None:return fail("项目不存在",404,"PROJECT_NOT_FOUND")
    if not 0 <= index < len(project["segments"]):return fail("段索引越界",404,"SEGMENT_NOT_FOUND")
    root=c["projects"].project_dir(pid).resolve(); attempts=root/f"segments/seg{index:02d}/attempts"; items=[]
    if attempts.is_dir():
        for directory in sorted((p for p in attempts.iterdir() if p.is_dir()),reverse=True):
            def read(name):
                path=directory/name
                try:return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
                except (OSError,json.JSONDecodeError):return None
            manifest,request_data,error,qa=read("manifest.json"),read("request.json"),read("error.json"),read("qa.json")
            items.append({"id":directory.name,"bytes":sum(p.stat().st_size for p in directory.rglob("*") if p.is_file()),
                          "status":"failed" if error else "complete" if (directory/"delivery.mp4").is_file() else "submitted" if request_data else "prepared",
                          "prompt_id":(request_data or {}).get("prompt_id"),"seed":(manifest or {}).get("actual_seed"),
                          "error":(error or {}).get("error"),"failures":(qa or {}).get("failures",[])})
    return ok({"attempts":items})


@bp.get("/api/projects/<pid>/diagnostic")
def project_diagnostic(pid):
    c=ctx(); project=c["projects"].get(pid)
    if project is None:return fail("项目不存在",404,"PROJECT_NOT_FOUND")
    return ok({"project_id":pid,"schema_version":project.get("schema_version"),"pipeline_version":project.get("pipeline_version"),
               "status":project.get("status"),"profile":project.get("profile"),"creation_mode":project.get("creation_mode","swap"),
               "resolution":project.get("resolution"),"review_mode":project.get("review_mode"),"current_job":c["jobs"].current(),
               "segments":[{"index":s.get("index"),"status":s.get("status"),"seed_mode":s.get("seed_mode"),
                            "last_seed":s.get("last_seed"),"prompt_id":s.get("prompt_id"),"error":s.get("error")} for s in project.get("segments",[])]})


def _attach_web_paths(pid: str, snapshot: dict) -> None:
    """把段/成品磁盘绝对路径转成浏览器可访问的 URL。"""
    c = ctx()
    base = c["projects"].project_dir(pid).resolve()

    def rel(path_value):
        if not path_value:
            return None
        try:
            rel_path = Path(path_value).resolve().relative_to(base)
        except (ValueError, OSError):
            return None
        return f"/api/projects/{pid}/outputs/{rel_path.as_posix()}"

    for seg in snapshot["segments"]:
        seg["source_url"] = rel(seg.get("slice"))
        seg["pass1_url"] = rel(seg.get("pass1_video"))
        seg["thumb_url"] = rel(seg.get("thumb"))
        seg["delivery_url"] = rel(seg.get("delivery"))
        seg["delivery_with_audio_url"] = rel(seg.get("delivery_with_audio"))
        seg["seam_preview_url"] = rel(seg.get("seam_preview"))
    if snapshot.get("final"):
        snapshot["final_url"] = rel(snapshot["final"])
    snapshot["cover_url"] = rel(snapshot.get("cover"))
    # 上传的参考图 → 可访问 URL
    snapshot["refs_url"] = [rel(p) for p in snapshot.get("refs", [])]


@bp.get("/api/projects/<pid>/outputs/<path:subpath>")
def serve_output(pid, subpath):
    c = ctx()
    directory = c["projects"].project_dir(pid)
    if not directory.is_dir():
        return fail("项目不存在", 404)
    return send_from_directory(directory, subpath, conditional=True)
