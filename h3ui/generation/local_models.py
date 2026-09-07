"""Read model filenames locally; never import or launch ComfyUI or load weights."""
import os
import time
from pathlib import Path
import yaml

# Standard ComfyUI loader folders and supported weight extensions.
FOLDERS = {'models': ('unet', 'diffusion_models'), 'loras': ('loras',),
           'vaes': ('vae',), 'clips': ('text_encoders', 'clip')}
EXTENSIONS = {'.ckpt', '.pt', '.pt2', '.bin', '.pth', '.safetensors', '.pkl', '.sft'}

class LocalModels:
    def __init__(self, cfg):
        self.cfg = cfg
        from ..config import ROOT, resolve_path
        self.base = (ROOT / Path(cfg['comfy_base_dir'])).resolve() if cfg.get('comfy_base_dir') else resolve_path(cfg, 'comfy_input_dir').parent.resolve()

    def scan(self):
        cfg = self.cfg
        model_root = self.base / Path(cfg.get('comfy_models_dir') or 'models')
        roots = {key: [model_root / folder for folder in folders] for key, folders in FOLDERS.items()}
        errors = []
        extra = cfg.get('comfy_extra_model_paths', [])
        if isinstance(extra, str): extra = [extra]
        files = [self.base / 'extra_model_paths.yaml', self.base / 'extra_models_config.yaml', *[self.base / Path(p) for p in extra]]
        desktop = Path(os.environ.get('APPDATA', str(self.base))) / 'ComfyUI/extra_models_config.yaml'
        if desktop.is_file(): files.append(desktop)
        seen_files = set()
        for file in files:
            file = file.resolve()
            if file in seen_files or not file.is_file(): continue
            seen_files.add(file)
            try:
                data = yaml.safe_load(file.read_text(encoding='utf-8-sig')) or {}
                if not isinstance(data, dict): raise ValueError('需要路径分组')
                groups = [v for v in data.values() if isinstance(v, dict)]
                def base_path(group):
                    raw = os.path.expandvars(os.path.expanduser(str(group.get('base_path', '.'))))
                    return (file.parent / raw).resolve()
                # Desktop configuration is implicit only for this configured installation.
                if file == desktop.resolve() and file not in [(self.base / Path(p)).resolve() for p in extra] and not any(base_path(g) == self.base for g in groups): continue
                for group in groups:
                    base = base_path(group)
                    for key, folders in FOLDERS.items():
                        for folder in folders:
                            paths = group.get(folder, '')
                            if not isinstance(paths, str): raise ValueError(f'{folder}须为路径文本')
                            for relative in paths.splitlines():
                                if relative.strip(): roots[key].append(base / relative.strip())
            except (OSError, ValueError, yaml.YAMLError) as exc:
                errors.append(f'{file}: {exc}')
        result = {}
        for key, paths in roots.items():
            paths = list(dict.fromkeys(p.resolve() for p in paths))
            roots[key] = [str(p) for p in paths]
            names = set()
            for root in paths:
                if not root.is_dir(): continue
                visited = set()
                def error(exc): errors.append(str(exc))
                for directory, dirs, filenames in os.walk(root, followlinks=True, onerror=error):
                    resolved = Path(directory).resolve()
                    if resolved in visited:
                        dirs[:] = []; continue
                    visited.add(resolved)
                    dirs[:] = [d for d in dirs if d not in {'.git', '.cache', '__pycache__'}]
                    for name in filenames:
                        if Path(name).suffix.lower() in EXTENSIONS:
                            names.add(str((Path(directory) / name).relative_to(root)))
            result[key] = sorted(names, key=str.casefold)
        result['local_models'] = dict(updated=time.time(), roots=roots, errors=errors, source='filesystem')
        return result
