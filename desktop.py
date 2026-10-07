"""
Startpunt van de kant-en-klare app (macOS .app en Windows .exe, gebouwd met
PyInstaller; zie packaging/).

Dubbelklikken op de app:

1. kijkt op de update-feed of er een nieuwere versie is en installeert die
   (macOS: de ondertekende app vervangen; Windows: de setup stil draaien);
2. hergebruikt een server die al draait als dat dezelfde versie is, en stopt
   hem anders (ook een server van de oude git-installatie);
3. start de server op de achtergrond (dezelfde executable met ``--server``) en
   opent de tool in de browser zodra hij antwoordt. Daarna stopt dit proces;
   de server blijft draaien, net als bij de oude launcher.

``--selftest`` controleert in CI of de bevroren app compleet is.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Optional

import updater
from updater import APP_NAME

PORT = 8000
URL = f"http://localhost:{PORT}"
STATUS_URL = f"http://127.0.0.1:{PORT}/api/status"
FROZEN = bool(getattr(sys, "frozen", False))
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
VERSION = updater.read_version(ROOT)
DATA_DIR = updater.user_data_dir()
LOG_DIR = DATA_DIR / "logs"
# Team-ID van het Developer ID-certificaat waarmee de Mac-app is ondertekend.
# Een update wordt alleen geïnstalleerd als die door hetzelfde team is
# ondertekend en door Apple is gecontroleerd.
MAC_TEAM_ID = "VAM683M962"


# ---------------------------------------------------------------------------
# Meldingen
# ---------------------------------------------------------------------------


def log(msg: str) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / "launcher.log", "a", encoding="utf-8") as fh:
            fh.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
    except OSError:
        pass


def _applescript_str(text: str) -> str:
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def notify(msg: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(
            ["osascript", "-e", f"display notification {_applescript_str(msg)} with title {_applescript_str(APP_NAME)}"],
            capture_output=True,
        )


def alert(msg: str) -> None:
    log(f"melding: {msg}")
    if sys.platform == "darwin":
        subprocess.run(
            ["osascript", "-e", f"display alert {_applescript_str(APP_NAME)} message {_applescript_str(msg)}"],
            capture_output=True,
        )
    elif sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, msg, APP_NAME, 0x40)


# ---------------------------------------------------------------------------
# De lokale server
# ---------------------------------------------------------------------------


def server_status() -> Optional[dict]:
    """Status van een C2PA-server op de poort, of None als daar niets (van ons) draait."""
    try:
        with urllib.request.urlopen(STATUS_URL, timeout=2) as res:
            data = json.loads(res.read().decode("utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) and "c2patool" in data else None


def _port_pids() -> list:
    """PID's die op de poort luisteren (voor een server van de oude installatie)."""
    try:
        if sys.platform == "win32":
            out = subprocess.run(
                ["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout
            return [
                int(parts[-1]) for parts in (line.split() for line in out.splitlines())
                if len(parts) >= 5 and parts[1].endswith(f":{PORT}") and parts[3].upper() == "LISTENING"
            ]
        out = subprocess.run(["lsof", "-ti", f"tcp:{PORT}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout
        return [int(x) for x in out.split()]
    except Exception:
        return []


def stop_server(status: dict) -> bool:
    """Stop de draaiende server. False als hij nog aan het verwerken is."""
    if "version" in status:
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/shutdown", data=b"", method="POST")
            with urllib.request.urlopen(req, timeout=5) as res:
                if not json.loads(res.read().decode("utf-8")).get("ok"):
                    return False
        except Exception:
            pass
    else:
        # Oude git-installatie: die kent geen /api/shutdown.
        for pid in _port_pids():
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                else:
                    os.kill(pid, 9)
            except Exception:
                pass
    for _ in range(50):
        if server_status() is None:
            return True
        time.sleep(0.1)
    return server_status() is None


def start_server() -> None:
    args = [sys.executable, "--server"] if FROZEN else [sys.executable, str(Path(__file__).resolve()), "--server"]
    kwargs = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED | NEW_GROUP | NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(args, **kwargs)


def run_server() -> None:
    """De server zelf (``--server``). Een app zonder console heeft geen stdout;
    uvicorn heeft er wel een nodig, dus alles gaat naar een logbestand."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / "server.log"
    try:
        if path.exists() and path.stat().st_size > 2_000_000:
            path.unlink()
    except OSError:
        pass
    fh = open(path, "a", buffering=1, encoding="utf-8")
    sys.stdout = sys.stderr = fh
    os.environ["C2PA_NO_BROWSER"] = "1"
    import app as tool

    tool.main()


# ---------------------------------------------------------------------------
# Updates
# ---------------------------------------------------------------------------


def mac_bundle_path() -> Optional[Path]:
    """De .app waar deze executable in zit."""
    exe = Path(sys.executable).resolve()
    for parent in exe.parents:
        if parent.suffix == ".app":
            return parent
    return None


def mac_can_replace(app_path: Path) -> bool:
    # Niet vanaf de .dmg en niet vanuit een "vertaalde" kopie (app nog in
    # Downloads met quarantaine): dan is er niets blijvends te vervangen.
    p = str(app_path)
    if p.startswith("/Volumes/") or "AppTranslocation" in p:
        return False
    return os.access(app_path.parent, os.W_OK) and os.access(app_path, os.W_OK)


def mac_verify(app_path: Path) -> bool:
    """Ondertekend door ons team en door Apple gecontroleerd (notarisatie)."""
    if subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app_path)], capture_output=True).returncode:
        return False
    info = subprocess.run(["codesign", "-dv", "--verbose=2", str(app_path)], capture_output=True, text=True)
    if f"TeamIdentifier={MAC_TEAM_ID}" not in (info.stderr or ""):
        return False
    return subprocess.run(["spctl", "--assess", "--type", "execute", str(app_path)], capture_output=True).returncode == 0


def try_update() -> bool:
    """Installeer een nieuwere versie als die er is. True als de nieuwe versie
    het overneemt (dan moet dit proces stoppen)."""
    if not FROZEN or os.environ.get("C2PA_NO_UPDATE"):
        return False
    manifest = updater.fetch_manifest(VERSION)
    if not manifest or not updater.is_newer(manifest["version"], VERSION):
        return False
    entry = manifest["files"].get(updater.platform_key() or "")
    if not isinstance(entry, dict) or not entry.get("name") or not entry.get("sha256"):
        return False
    new_version = manifest["version"]

    app_path = None
    if sys.platform == "darwin":
        app_path = mac_bundle_path()
        if not app_path or not mac_can_replace(app_path):
            log(f"update {new_version} overgeslagen: app niet te vervangen ({app_path})")
            return False

    # Een draaiende server stoppen we pas vlak voor het vervangen; loopt er een
    # verwerking, dan wacht de update tot de volgende start.
    status = server_status()

    notify(f"Versie {new_version} wordt geïnstalleerd…")
    log(f"update {VERSION} -> {new_version}: {entry['name']}")
    work = Path(tempfile.mkdtemp(prefix="c2pa-update-"))
    try:
        target = work / entry["name"]
        updater.download(entry["name"], target, entry["sha256"], VERSION)

        if sys.platform == "darwin":
            unpacked = work / "nieuw"
            subprocess.run(["ditto", "-x", "-k", str(target), str(unpacked)], check=True, capture_output=True)
            new_app = next(unpacked.glob("*.app"), None)
            if not new_app or not mac_verify(new_app):
                log("update geweigerd: handtekening of notarisatie klopt niet")
                return False
            if status is not None and not stop_server(status):
                log("update uitgesteld: er loopt een verwerking")
                return False
            old = work / "oud.app"
            os.rename(app_path, old)
            try:
                os.rename(new_app, app_path)
            except OSError:
                os.rename(old, app_path)
                raise
            subprocess.Popen(["open", "-n", str(app_path)])
            return True

        if sys.platform == "win32":
            if status is not None and not stop_server(status):
                log("update uitgesteld: er loopt een verwerking")
                return False
            # De setup vervangt de bestanden zodra dit proces is gestopt en
            # start daarna zelf de nieuwe versie ([Run] in installer.iss).
            subprocess.Popen(
                [str(target), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                creationflags=0x00000008 | 0x00000200,
                close_fds=True,
            )
            return True
    except Exception as e:  # noqa: BLE001
        log(f"update mislukt: {e}")
    finally:
        if sys.platform == "darwin":
            shutil.rmtree(work, ignore_errors=True)
    return False


# ---------------------------------------------------------------------------
# Starten
# ---------------------------------------------------------------------------


def launch() -> None:
    log(f"start {VERSION}")
    try:
        if try_update():
            return
    except Exception as e:  # noqa: BLE001
        log(f"update-check mislukt: {e}")

    status = server_status()
    if status is not None:
        if status.get("version") == VERSION:
            webbrowser.open(URL)
            return
        log(f"andere server draait ({status.get('version') or 'oude installatie'}); stoppen")
        if not stop_server(status):
            # Hij is nog aan het verwerken: laat hem afmaken.
            webbrowser.open(URL)
            return

    start_server()
    for _ in range(120):
        time.sleep(0.5)
        if server_status() is not None:
            webbrowser.open(URL)
            return
    if _port_pids():
        alert(f"Poort {PORT} is bezet door een ander programma. Sluit dat en open de app opnieuw.")
    else:
        alert(f"De tool startte niet op tijd. Kijk in het logbestand: {LOG_DIR / 'server.log'}")


def selftest() -> int:
    """Voor CI: laadt de server-module en de update-feed (TLS) en meldt wat er mist."""
    os.environ["C2PA_NO_BROWSER"] = "1"
    import app as tool

    result = {
        "version": VERSION,
        "frozen": FROZEN,
        "c2patool": tool.c2patool_info(),
        "icons": tool.list_icons(),
        "templates": [t.get("name") for t in tool.load_templates()],
    }
    try:
        with updater._open(f"{updater.FEED_URL}/latest.json", VERSION):
            pass
        result["feed"] = "ok"
    except urllib.error.HTTPError as e:
        result["feed"] = f"http {e.code}"  # TLS werkt; de feed bestaat misschien nog niet
    except Exception as e:  # noqa: BLE001
        result["feed"] = f"FOUT: {e}"
    text = json.dumps(result, indent=2)
    # Een app zonder console (Windows) heeft geen stdout; CI leest het bestand.
    out = os.environ.get("C2PA_SELFTEST_OUT")
    if out:
        Path(out).write_text(text, encoding="utf-8")
    if sys.stdout:
        print(text)
    ok = result["c2patool"]["present"] and result["icons"] and not str(result["feed"]).startswith("FOUT")
    return 0 if ok else 1


def main() -> None:
    if "--server" in sys.argv:
        run_server()
    elif "--selftest" in sys.argv:
        sys.exit(selftest())
    else:
        launch()


if __name__ == "__main__":
    main()
