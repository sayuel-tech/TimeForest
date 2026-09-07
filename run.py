#!/usr/bin/env python3
"""H3 分链视频生成 Web 界面入口。

用法:
    python run.py [--config config.json] [--host 127.0.0.1] [--port 5093]
"""
import argparse
import os
import shutil
import sys

# 重要: ComfyUI 便携版的 python_embeded 带 python313._pth,把 ../ComfyUI
# 硬塞进 sys.path[0],且屏蔽 PYTHONPATH。必须先把自己的项目根插到最前,
# 否则 `import h3ui` 会被 ComfyUI 同名/其它包干扰。
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from h3ui import create_app


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None, help="config.json 路径")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--no-browser", action="store_true", help="仅启动本地服务，不额外打开浏览器")
    parser.add_argument("--no-startup-recovery", action="store_true", help="本次启动不恢复或唤醒已有任务；不修改配置，后续主动操作保持原样")
    args = parser.parse_args()

    # 首次运行: 若 config.json 不存在,从示例拷贝一份供编辑
    from h3ui.config import ROOT
    if args.config is None and not (ROOT / "config.json").exists():
        shutil.copy(ROOT / "config.example.json", ROOT / "config.json")

    app = create_app(args.config, recover_tasks=not args.no_startup_recovery)
    cfg = app.config["H3UI"]["cfg"]
    host = args.host or cfg.get("host", "127.0.0.1")
    port = args.port or int(cfg.get("port", 5093))
    print(f"\n  H3 Video Chain UI: http://{host}:{port}\n")
    # 启动后自动打开浏览器(config.open_browser=false 可关闭)
    if cfg.get("open_browser", True) and not args.no_browser:
        import threading
        import webbrowser
        threading.Timer(2.0, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    app.run(host=host, port=port, threaded=True, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
