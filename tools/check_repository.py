"""Check staged repository content only. No inference or network calls."""
import json
import re
import subprocess
import sys
from pathlib import PurePosixPath


def git(*args):
    return subprocess.check_output(["git", *args])


def main():
    paths = git("ls-files", "-z").decode("utf-8").split("\0")
    blocked_roots = {"data", "data_v5", ".venv", "node_modules", "TimeForestAssets", "asset_library", "backups", "ComfyUI"}
    blocked_suffixes = {".sqlite", ".sqlite3", ".db", ".safetensors", ".ckpt", ".pt", ".pth", ".gguf", ".log", ".pem", ".key", ".zip", ".7z", ".rar"}
    companion_files = {f"h3ui/studio_sources/{name}.json" for name in ("dance", "impact", "official_r2v", "official_t2v", "wenxi")}
    companion_files.add("h3ui/image_studio/sources/krea-edit.json")
    secret = re.compile(rb"(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9]{35,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY)")
    errors = []
    total = 0
    count = 0
    for name in filter(None, paths):
        path = PurePosixPath(name)
        if name in companion_files:
            errors.append((name, "companion workflow must remain outside GitHub"))
        if path.parts[0] in blocked_roots or path.suffix in blocked_suffixes or path.name == "config.json" or path.name.startswith(".env") and path.name != ".env.example":
            errors.append((name, "runtime/private file tracked"))
        if name.startswith("h3ui/studio_sources/compiled-preview/") or name == "h3ui/studio_sources/object_info.json":
            errors.append((name, "local workflow/cache file tracked"))
        data = git("show", ":" + name)
        total += len(data)
        count += 1
        if len(data) > 10 * 1024 * 1024:
            errors.append((name, "file exceeds repository 10 MiB review threshold"))
        if secret.search(data):
            errors.append((name, "possible credential; inspect locally"))
        if path.suffix == ".json":
            try:
                json.loads(data)
            except (ValueError, UnicodeError):
                errors.append((name, "invalid JSON"))
    print(json.dumps({"staged_files": count, "bytes": total, "errors": errors}, ensure_ascii=False, indent=2))
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
