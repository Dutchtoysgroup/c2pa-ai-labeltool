"""
Gedeelde basis voor de kant-en-klare app: naam, versie, gebruikersmap en de
update-feed op het dashboard.

Alleen standaardbibliotheek (plus certifi als dat er is), zodat app.py dit ook
vanuit de broncode kan importeren zonder extra pakketten.

De feed staat op ``https://dashboard-exit.com/labeltool/update``:

- ``latest.json`` beschrijft de nieuwste release::

      {"version": "2.0.0",
       "files": {"mac-arm64": {"name": "...-macOS-Apple-Silicon.zip", "sha256": "...", "size": 123},
                 "mac-x64":   {...},
                 "windows":   {"name": "...-Windows-Setup.exe", ...}}}

- elk bestand daaruit is op naam op te halen (``<feed>/<name>``); het dashboard
  stuurt door naar het release-bestand op GitHub.
"""

import hashlib
import json
import os
import platform
import ssl
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

APP_NAME = "C2PA AI-labeltool"
FEED_URL = os.environ.get("C2PA_UPDATE_URL", "https://dashboard-exit.com/labeltool/update").rstrip("/")
REQUEST_TIMEOUT = 6


def user_data_dir() -> Path:
    """Map voor eigen templates, iconen en logs van de app-versie."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / APP_NAME


def read_version(root: Path) -> str:
    try:
        return (root / "VERSION").read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def _version_tuple(v: str):
    parts = []
    for p in str(v).strip().lstrip("v").split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts + [0] * (3 - len(parts)))


def is_newer(candidate: str, current: str) -> bool:
    return _version_tuple(candidate) > _version_tuple(current)


def platform_key() -> Optional[str]:
    """Sleutel in ``files`` van latest.json voor dit systeem."""
    if sys.platform == "darwin":
        return "mac-arm64" if platform.machine() == "arm64" else "mac-x64"
    if sys.platform == "win32":
        return "windows"
    return None


def _ssl_context() -> ssl.SSLContext:
    # Een bevroren Python kent de certificaten van de bouwmachine niet; certifi
    # reist mee in de app.
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _open(url: str, version: str, timeout: float = REQUEST_TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": f"C2PA-AI-labeltool/{version}"})
    return urllib.request.urlopen(req, timeout=timeout, context=_ssl_context())


def fetch_manifest(version: str) -> Optional[dict]:
    """latest.json van de feed, of ``None`` (offline, nog geen release, ...)."""
    try:
        with _open(f"{FEED_URL}/latest.json", version) as res:
            data = json.loads(res.read().decode("utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or not data.get("version") or not isinstance(data.get("files"), dict):
        return None
    return data


_manifest_cache = {"at": 0.0, "data": None}


def latest_version(version: str, max_age: float = 600) -> Optional[str]:
    """Nieuwste versie volgens de feed, 10 minuten gecachet (voor de versie-badge)."""
    if time.time() - _manifest_cache["at"] > max_age:
        _manifest_cache["data"] = fetch_manifest(version)
        _manifest_cache["at"] = time.time()
    data = _manifest_cache["data"]
    return data.get("version") if data else None


def download(name: str, dest: Path, sha256: str, version: str, max_bytes: int = 600_000_000) -> None:
    """Haal een bestand uit de feed op en controleer de SHA-256. Gooit bij fouten."""
    digest = hashlib.sha256()
    size = 0
    with _open(f"{FEED_URL}/{urllib.request.quote(name)}", version, timeout=60) as res, open(dest, "wb") as fh:
        while True:
            chunk = res.read(1 << 20)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                raise ValueError("download te groot")
            digest.update(chunk)
            fh.write(chunk)
    if digest.hexdigest().lower() != str(sha256).lower():
        raise ValueError("controlegetal klopt niet")
