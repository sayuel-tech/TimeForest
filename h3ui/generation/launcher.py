"""Optional, explicitly configured Python ComfyUI launch; never runs on site visit."""
import hashlib
import json
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from ..studio_progress import write


class EngineLauncher:
    def __init__(self, studio):
        self.studio = studio
        self.path = studio.root / 'engine-launch.json'
        self.lock = threading.Lock()
        self.process = None

    def validate(self, data):
        exe = Path(data.get('python', '')).resolve()
        script = Path(data.get('script', '')).resolve()
        if not exe.is_file() or not exe.name.lower().startswith('python') or exe.suffix.lower() != '.exe':
            raise ValueError('请选择本机 ComfyUI 使用的 Python 可执行文件')
        if not script.is_file() or script.name != 'main.py' or not (script.parent / 'server.py').is_file() or not (script.parent / 'comfy').is_dir():
            raise ValueError('请定位实际 ComfyUI 目录中的 main.py；启动文件结构检查未通过')
        args = data.get('args', [])
        if not isinstance(args, list) or any(not isinstance(a, str) or len(a) > 500 or '\x00' in a for a in args) or len(args) > 100:
            raise ValueError('启动参数须为字符串数组，不是终端命令')
        if urlparse(self.studio.comfy.url).hostname not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('自动启动仅支持本机生成引擎地址')
        return dict(enabled=bool(data.get('enabled')), python=str(exe), script=str(script), args=args,
                    script_hash=hashlib.sha256(script.read_bytes()).hexdigest())

    def status(self):
        if not self.path.is_file():
            return dict(enabled=False, verified=False, note='默认手动启动引擎；设置前不会猜测启动路径')
        saved = json.loads(self.path.read_text(encoding='utf-8'))
        try:
            checked = self.validate(saved)
            if saved['script_hash'] != checked['script_hash']:
                raise ValueError('启动脚本已变化，请重新核对并保存设置')
            return dict(**saved, verified=True, note='启动文件已核对；仅生成请求失败且启用此选项时尝试启动，不代表已完成模型生成核验')
        except (ValueError, OSError) as exc:
            return dict(**saved, verified=False, note=str(exc))

    def save(self, data):
        if not data.get('enabled') and not data.get('python'):
            self.path.unlink(missing_ok=True)
            return self.status()
        result = self.validate(data)
        write(self.path, result)
        return self.status()

    def connect_for_generation(self):
        st = self.studio
        try:
            return st.recipes.connect()
        except ValueError:
            status = self.status()
            if not status.get('enabled'):
                raise
        if st.ctx['cfg'].get('studio_disable_generation'):
            raise ValueError('验收环境不允许启动生成引擎')
        if not status['verified']:
            raise ValueError(status['note'])
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                log = st.root / 'engine-start.log'
                with log.open('ab') as output:
                    self.process = subprocess.Popen([status['python'], status['script'], *status['args']],
                        cwd=str(Path(status['script']).parent), stdin=subprocess.DEVNULL, stdout=output,
                        stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise ValueError('ComfyUI启动退出，请查看本地 engine-start.log；没有提交生成')
            time.sleep(2)
            try:
                return st.recipes.connect()
            except ValueError:
                pass
        raise ValueError('引擎尚未就绪，请查看启动日志，准备好后重新点击生成；本次没有提交任务')
