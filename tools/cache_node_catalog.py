"""Explicit, read-only catalog refresh for a configured local ComfyUI installation."""
import argparse
import json
import os
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="ComfyUI server URL; no inference is submitted")
    parser.add_argument("--output", help="Catalog destination (defaults to data_v5/engine-catalog.json)")
    args = parser.parse_args()
    with urlopen(args.url.rstrip("/") + "/object_info", timeout=30) as response:
        data = json.load(response)
    if not isinstance(data, dict) or not data or not all(isinstance(v, dict) for v in data.values()):
        raise ValueError("The server did not return a valid node catalog")
    target = Path(args.output) if args.output else Path(__file__).resolve().parents[1] / "data_v5/engine-catalog.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, suffix=".tmp", delete=False) as handle:
            temp = Path(handle.name)
            json.dump(dict(url=args.url.rstrip('/'),updated=time.time(),nodes=data), handle, ensure_ascii=False)
        os.replace(temp, target)
    finally:
        if temp and temp.exists():
            temp.unlink()
    print(f"Saved {len(data)} node definitions to {target}. No generation was submitted.")


if __name__ == "__main__":
    main()
