"""Schrijft latest.json voor de update-feed uit de bestanden van een release.

    python3 packaging/make_manifest.py <map-met-release-bestanden>

De app leest dit via https://dashboard-exit.com/labeltool/update/latest.json
(zie updater.py) en haalt daarna het bestand voor zijn eigen systeem op.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = {
    "mac-arm64": "-macOS-Apple-Silicon.zip",
    "mac-x64": "-macOS-Intel.zip",
    "windows": "-Windows-Setup.exe",
}


def main() -> None:
    folder = Path(sys.argv[1])
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    files = {}
    for key, suffix in FILES.items():
        name = f"C2PA-AI-labeltool-{version}{suffix}"
        path = folder / name
        if not path.is_file():
            sys.exit(f"ontbreekt: {name}")
        files[key] = {
            "name": name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "size": path.stat().st_size,
        }
    print(json.dumps({"version": version, "files": files}, indent=2))


if __name__ == "__main__":
    main()
