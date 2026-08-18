#!/usr/bin/env python3
"""
EXIT-Toys-C2PA-Tool
-------------------
Lokale desktop-tool die (1) optioneel een zichtbaar AI-icoon/label in elk beeld
van een map brandt en (2) C2PA Content Credentials (AI-generated / AI-modified
provenance) aan die bestanden toevoegt.

Start:  python app.py
Opent automatisch http://localhost:8000

Werkt volledig lokaal/offline. Er verlaat geen data de machine.
"""

import base64
import io
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Vriendelijke check op ontbrekende dependencies
# ---------------------------------------------------------------------------
MISSING = []
try:
    from fastapi import FastAPI, UploadFile, File, Form, HTTPException
    from fastapi.responses import (
        HTMLResponse,
        JSONResponse,
        StreamingResponse,
        FileResponse,
    )
    from fastapi.staticfiles import StaticFiles
except Exception:  # pragma: no cover
    MISSING.append("fastapi")
try:
    import uvicorn
except Exception:  # pragma: no cover
    MISSING.append("uvicorn")
try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:  # pragma: no cover
    MISSING.append("pillow")

try:
    import multipart  # noqa: F401  (python-multipart, nodig voor Form/UploadFile)
except Exception:  # pragma: no cover
    MISSING.append("python-multipart")

if MISSING:
    print("\n\033[91m[!] Ontbrekende Python-pakketten:\033[0m " + ", ".join(MISSING))
    print("    Installeer alle dependencies met:\n")
    print("        python -m pip install -r requirements.txt\n")
    print("    (of, per pakket:  python -m pip install " + " ".join(MISSING) + ")\n")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paden & constanten
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
ICONS_DIR = ROOT / "icons"
TEMPLATES_FILE = ROOT / "templates.json"

ICONS_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

CLAIM_GENERATOR = "EXIT-Toys-C2PA-Tool/1.0"

# Meegeleverd, zelf-ondertekend TEST-certificaat (es256). Bewust "untrusted":
# verifiers tonen de ondertekenaar als niet-vertrouwd. Nooit voor publicatie.
TEST_CERT = ROOT / "certs" / "test" / "es256_certs.pem"
TEST_KEY = ROOT / "certs" / "test" / "es256_private.key"

DIGITAL_SOURCE_TYPES = {
    "volledig": "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
    "composite": "http://cv.iptc.org/newscodes/digitalsourcetype/compositeWithTrainedAlgorithmicMedia",
}

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov"}
SUPPORTED_EXT = IMAGE_EXT | VIDEO_EXT

CORNERS = {"rechtsonder", "linksonder", "rechtsboven", "linksboven"}
ALGORITHMS = {"es256", "ps256", "ed25519"}

PORT = 8000

# ---------------------------------------------------------------------------
# Externe tools detecteren
# ---------------------------------------------------------------------------


def which(name: str):
    return shutil.which(name)


def c2patool_info():
    path = which("c2patool")
    if not path:
        return {"present": False, "path": None, "version": None}
    version = None
    try:
        out = subprocess.run(
            [path, "--version"], capture_output=True, text=True, timeout=15
        )
        version = (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr) else None
    except Exception:
        version = None
    return {"present": True, "path": path, "version": version}


def ffmpeg_present():
    return which("ffmpeg") is not None


# ---------------------------------------------------------------------------
# Standaard-icoon garanderen
# ---------------------------------------------------------------------------


def ensure_default_icon():
    """Maak een eenvoudig AI-badge-icoon aan als icons/ nog leeg is."""
    existing = [p for p in ICONS_DIR.glob("*.png")]
    if existing:
        return
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # ronde badge
    d.ellipse([8, 8, size - 8, size - 8], fill=(17, 24, 39, 235))
    d.ellipse([8, 8, size - 8, size - 8], outline=(255, 255, 255, 255), width=14)
    font = _load_font(int(size * 0.42))
    text = "AI"
    try:
        bbox = d.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(
            ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]),
            text,
            font=font,
            fill=(255, 255, 255, 255),
        )
    except Exception:
        pass
    img.save(ICONS_DIR / "ai-badge.png")


def _load_font(px: int):
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/SFNSDisplay.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, px)
        except Exception:
            continue
    try:
        return ImageFont.load_default(px)  # Pillow >= 10.1
    except Exception:
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Zichtbaar label inbranden (Pillow)
# ---------------------------------------------------------------------------


def burn_label(src_img: "Image.Image", settings: dict) -> "Image.Image":
    """Brand icoon (+ optioneel tekstlabel op contrast-pill) in een hoek.

    src_img: PIL Image (elk mode). Retourneert een nieuwe RGBA image.
    settings keys: icon (bestandsnaam), text, corner, size_pct, min_px, max_px,
                   margin_pct, pill (bool), pill_opacity (0-255)
    """
    base = src_img.convert("RGBA")
    W, H = base.size

    # icoon laden + schalen
    icon_name = settings.get("icon") or ""
    icon_path = (ICONS_DIR / icon_name) if icon_name else None
    icon = None
    if icon_path and icon_path.exists():
        try:
            icon = Image.open(icon_path).convert("RGBA")
        except Exception:
            icon = None

    size_pct = float(settings.get("size_pct", 7))
    min_px = int(settings.get("min_px", 28))
    max_px = int(settings.get("max_px", 96))
    icon_w = int(W * size_pct / 100.0)
    icon_w = max(min_px, min(max_px, icon_w))

    icon_scaled = None
    icon_h = 0
    if icon is not None:
        ratio = icon.height / icon.width if icon.width else 1
        icon_h = max(1, int(icon_w * ratio))
        icon_scaled = icon.resize((icon_w, icon_h), Image.LANCZOS)

    # tekst
    text = (settings.get("text") or "").strip()
    text_w = text_h = 0
    font = None
    if text:
        font_px = max(12, int(icon_w * 0.42) if icon_scaled is not None else int(W * 0.02))
        font = _load_font(font_px)
        tmp = ImageDraw.Draw(base)
        bbox = tmp.textbbox((0, 0), text, font=font)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        text_ascent_off = bbox[1]  # om exact te positioneren
    else:
        text_ascent_off = 0

    gap = int(icon_w * 0.25) if (icon_scaled is not None and text) else 0
    content_w = (icon_w if icon_scaled is not None else 0) + gap + text_w
    content_h = max(icon_h, text_h) if (icon_scaled is not None or text) else 0
    if content_w == 0 or content_h == 0:
        return base  # niets te doen

    use_pill = bool(settings.get("pill", True))
    pill_alpha = int(settings.get("pill_opacity", 110))
    pad = int(max(6, icon_w * 0.18)) if use_pill else 0

    group_w = content_w + 2 * pad
    group_h = content_h + 2 * pad

    margin = int(W * float(settings.get("margin_pct", 2)) / 100.0)
    corner = settings.get("corner", "rechtsonder")
    if corner == "rechtsonder":
        gx, gy = W - margin - group_w, H - margin - group_h
    elif corner == "linksonder":
        gx, gy = margin, H - margin - group_h
    elif corner == "rechtsboven":
        gx, gy = W - margin - group_w, margin
    else:  # linksboven
        gx, gy = margin, margin
    gx = max(0, gx)
    gy = max(0, gy)

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    if use_pill:
        radius = int(group_h * 0.28)
        od.rounded_rectangle(
            [gx, gy, gx + group_w, gy + group_h],
            radius=radius,
            fill=(0, 0, 0, pill_alpha),
        )

    cx = gx + pad
    cy = gy + pad
    if icon_scaled is not None:
        iy = cy + (content_h - icon_h) // 2
        overlay.alpha_composite(icon_scaled, (cx, iy))
        cx += icon_w + gap
    if text:
        ty = cy + (content_h - text_h) // 2 - text_ascent_off
        # lichte schaduw voor leesbaarheid als pill uit staat
        if not use_pill:
            od.text((cx + 2, ty + 2), text, font=font, fill=(0, 0, 0, 160))
        od.text((cx, ty), text, font=font, fill=(255, 255, 255, 255))

    return Image.alpha_composite(base, overlay)


def save_like_original(img: "Image.Image", dst_path: Path, original_info: dict):
    """Sla img op met een formaat dat past bij de extensie van dst_path."""
    ext = dst_path.suffix.lower()
    params = {}
    icc = original_info.get("icc_profile")
    if icc:
        params["icc_profile"] = icc
    if ext in {".jpg", ".jpeg"}:
        rgb = img.convert("RGB")
        params.update(quality=95, subsampling=0)  # 4:4:4, geen chroma-verlies
        exif = original_info.get("exif")
        if exif:
            params["exif"] = exif
        rgb.save(dst_path, format="JPEG", **params)
    elif ext == ".png":
        img.save(dst_path, format="PNG", **params)
    elif ext == ".webp":
        params.update(quality=95)
        img.save(dst_path, format="WEBP", **params)
    else:
        img.convert("RGB").save(dst_path)


# ---------------------------------------------------------------------------
# C2PA manifest opbouwen
# ---------------------------------------------------------------------------


def build_manifest(cfg: dict) -> dict:
    dst = DIGITAL_SOURCE_TYPES[cfg["bronsoort"]]
    agent_name = cfg["ai_tool"].strip()
    if cfg.get("model", "").strip():
        agent_name = f"{agent_name} {cfg['model'].strip()}"
    when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    use = "allowed" if cfg.get("training_allowed") else "notAllowed"

    manifest = {
        # legacy string (claim v1) + claim_generator_info (claim v2)
        "claim_generator": CLAIM_GENERATOR,
        "claim_generator_info": [
            {"name": "EXIT-Toys-C2PA-Tool", "version": "1.0"}
        ],
        "assertions": [
            {
                "label": "c2pa.actions.v2",
                "data": {
                    "actions": [
                        {
                            "action": "c2pa.created",
                            "digitalSourceType": dst,
                            "softwareAgent": {"name": agent_name},
                            "when": when,
                        }
                    ]
                },
            },
            {
                "label": "stds.schema-org.CreativeWork",
                "data": {
                    "@context": "http://schema.org/",
                    "@type": "CreativeWork",
                    "author": [
                        {"@type": "Organization", "name": cfg.get("organisatie", "").strip()}
                    ],
                },
            },
            {
                "label": "c2pa.ai_generative_training",
                "data": {"use": use},
            },
        ],
    }

    # Ondertekening. Test-modus (checkbox aan óf geen eigen cert opgegeven) →
    # meegeleverd es256 TEST-certificaat. Anders het opgegeven productie-cert.
    use_test = cfg.get("use_test_cert") or not (cfg.get("cert_path") and cfg.get("key_path"))
    if use_test:
        if TEST_CERT.exists() and TEST_KEY.exists():
            manifest["alg"] = "es256"
            manifest["private_key"] = str(TEST_KEY)
            manifest["sign_cert"] = str(TEST_CERT)
        # else: laat weg → c2patool valt terug op eigen ingebouwde test-cert
    else:
        manifest["alg"] = cfg.get("alg", "es256")
        manifest["private_key"] = str(Path(cfg["key_path"]).expanduser().resolve())
        manifest["sign_cert"] = str(Path(cfg["cert_path"]).expanduser().resolve())

    return manifest


def sign_with_c2patool(src: Path, dst: Path, manifest_path: Path):
    """Run c2patool om het beeld te ondertekenen. Retourneert (ok, log)."""
    cmd = [
        which("c2patool"),
        str(src),
        "-m",
        str(manifest_path),
        "-o",
        str(dst),
        "-f",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return False, "c2patool time-out (>600s)"
    except Exception as e:
        return False, f"c2patool niet uitvoerbaar: {e}"
    if res.returncode != 0:
        err = (res.stderr or res.stdout or "").strip()
        return False, err.splitlines()[-1] if err else "onbekende c2patool-fout"
    return True, ""


def verify_with_c2patool(path: Path, expected_dst: str):
    """Lees het manifest terug en controleer of de AI-assertie aanwezig is."""
    try:
        res = subprocess.run(
            [which("c2patool"), str(path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except Exception as e:
        return False, f"verificatie mislukt: {e}"
    out = res.stdout or ""
    if res.returncode != 0 and not out:
        return False, (res.stderr or "geen manifest gevonden").strip().splitlines()[-1]
    ok = ("c2pa.created" in out) and (expected_dst in out or "digitalSourceType" in out)
    return ok, "manifest + AI-assertie aanwezig" if ok else "AI-assertie niet gevonden in manifest"


def overlay_video_ffmpeg(src: Path, dst: Path, settings: dict):
    """Brand icoon in een video met ffmpeg. Retourneert (ok, log)."""
    icon_name = settings.get("icon") or ""
    icon_path = ICONS_DIR / icon_name
    if not icon_path.exists():
        return False, "geen icoon voor video-overlay"
    # icoonbreedte relatief aan videobreedte via overlay met scale2ref-achtige aanpak
    size_pct = float(settings.get("size_pct", 7)) / 100.0
    margin_pct = float(settings.get("margin_pct", 2)) / 100.0
    corner = settings.get("corner", "rechtsonder")
    # x/y expressies (main_w/main_h = video, overlay_w/h = icoon)
    m = f"(main_w*{margin_pct})"
    if corner == "rechtsonder":
        pos = f"x=main_w-overlay_w-{m}:y=main_h-overlay_h-{m}"
    elif corner == "linksonder":
        pos = f"x={m}:y=main_h-overlay_h-{m}"
    elif corner == "rechtsboven":
        pos = f"x=main_w-overlay_w-{m}:y={m}"
    else:
        pos = f"x={m}:y={m}"
    filt = (
        f"[1:v]scale=iw:ih[ic];"
        f"[0:v][ic]scale2ref=w=main_w*{size_pct}:h=ow/mdar[base][ov];"
        f"[base][ov]overlay={pos}[out]"
    )
    # Eenvoudiger, robuuster: schaal icoon op basis van videobreedte
    filt = (
        f"[1:v][0:v]scale2ref=w=iw*{size_pct}:h=ow/mdar[ic][base];"
        f"[base][ic]overlay={pos}"
    )
    cmd = [
        which("ffmpeg"),
        "-y",
        "-i",
        str(src),
        "-i",
        str(icon_path),
        "-filter_complex",
        filt,
        "-c:a",
        "copy",
        str(dst),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except Exception as e:
        return False, f"ffmpeg-fout: {e}"
    if res.returncode != 0:
        tail = (res.stderr or "").strip().splitlines()
        return False, tail[-1] if tail else "ffmpeg mislukt"
    return True, ""


# ---------------------------------------------------------------------------
# Batch-verwerking (draait in een aparte thread; stuurt events via een queue)
# ---------------------------------------------------------------------------

JOBS: dict[str, dict] = {}


def collect_files(root: Path, recursive: bool):
    files = []
    if recursive:
        it = root.rglob("*")
    else:
        it = root.glob("*")
    for p in sorted(it):
        if p.is_file() and not p.name.startswith("."):
            files.append(p)
    return files


def process_batch(job_id: str, cfg: dict):
    q: queue.Queue = JOBS[job_id]["queue"]

    def emit(ev: dict):
        q.put(ev)

    def log(status, name, msg, layers=""):
        emit({"type": "log", "status": status, "file": name, "msg": msg, "layers": layers})

    try:
        in_dir = Path(cfg["input_dir"]).expanduser()
        if not in_dir.exists() or not in_dir.is_dir():
            emit({"type": "error", "msg": f"Invoermap bestaat niet: {in_dir}"})
            emit({"type": "done"})
            return

        out_pattern = cfg.get("output_dir", "").strip()
        if not out_pattern:
            out_dir = in_dir / "gelabeld"
        else:
            out_dir = Path(out_pattern.replace("<invoer>", str(in_dir))).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)

        all_files = collect_files(in_dir, cfg.get("recursive", False))
        # negeer bestanden die al in de uitvoermap staan
        all_files = [f for f in all_files if out_dir not in f.parents and f.parent != out_dir]
        work = [f for f in all_files if f.suffix.lower() in SUPPORTED_EXT]
        skipped_unsupported = [f for f in all_files if f.suffix.lower() not in SUPPORTED_EXT]

        total = len(work) + len(skipped_unsupported)
        if total == 0:
            emit({"type": "error", "msg": "Geen bestanden gevonden in de opgegeven map."})
            emit({"type": "done"})
            return

        emit({"type": "start", "total": total, "output": str(out_dir)})

        manifest = build_manifest(cfg)
        do_visible = cfg.get("burn_icon", True)
        do_verify = cfg.get("verify", True)
        have_ffmpeg = ffmpeg_present()
        expected_dst = DIGITAL_SOURCE_TYPES[cfg["bronsoort"]]

        n_signed = n_skipped = n_error = 0
        processed = 0

        for f in skipped_unsupported:
            log("SKIP", f.name, "niet-ondersteund bestandstype")
            n_skipped += 1
            processed += 1
            emit({"type": "progress", "done": processed, "total": total})

        tmpdir = Path(tempfile.mkdtemp(prefix="c2pa_"))
        manifest_path = tmpdir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        try:
            for f in work:
                ext = f.suffix.lower()
                out_file = out_dir / f.name
                layers = []
                try:
                    working = f  # bron voor de C2PA-stap

                    # ----- Stap 1: zichtbaar label -----
                    if do_visible:
                        if ext in IMAGE_EXT:
                            with Image.open(f) as im:
                                info = dict(im.info)
                                labeled = burn_label(im, cfg["label"])
                            working = tmpdir / f.name
                            save_like_original(labeled, working, info)
                            layers.append("icoon")
                        elif ext in VIDEO_EXT:
                            if have_ffmpeg:
                                vtmp = tmpdir / f.name
                                ok, vmsg = overlay_video_ffmpeg(f, vtmp, cfg["label"])
                                if ok:
                                    working = vtmp
                                    layers.append("icoon")
                                else:
                                    log("INFO", f.name, f"video-overlay overgeslagen: {vmsg}")
                            else:
                                log("INFO", f.name, "geen ffmpeg: zichtbaar label overgeslagen voor video")

                    # ----- Stap 2: C2PA ondertekenen -----
                    ok, msg = sign_with_c2patool(working, out_file, manifest_path)
                    if not ok:
                        raise RuntimeError(msg)
                    layers.append("C2PA")

                    # ----- Stap 3: verifiëren -----
                    if do_verify:
                        vok, vmsg = verify_with_c2patool(out_file, expected_dst)
                        if not vok:
                            log("FOUT", f.name, f"verificatie: {vmsg}", " + ".join(layers))
                            n_error += 1
                            processed += 1
                            emit({"type": "progress", "done": processed, "total": total})
                            continue

                    lay = " + ".join(layers) if layers else "-"
                    log("OK", f.name, "getekend" + (" + geverifieerd" if do_verify else ""), lay)
                    n_signed += 1
                except Exception as e:  # noqa: BLE001
                    log("FOUT", f.name, str(e), " + ".join(layers))
                    n_error += 1
                processed += 1
                emit({"type": "progress", "done": processed, "total": total})
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        emit(
            {
                "type": "summary",
                "signed": n_signed,
                "skipped": n_skipped,
                "errors": n_error,
                "output": str(out_dir),
            }
        )
    except Exception as e:  # noqa: BLE001
        emit({"type": "error", "msg": f"Onverwachte fout: {e}"})
    finally:
        emit({"type": "done"})


# ---------------------------------------------------------------------------
# Templates opslag
# ---------------------------------------------------------------------------


def load_templates():
    if not TEMPLATES_FILE.exists():
        return []
    try:
        data = json.loads(TEMPLATES_FILE.read_text(encoding="utf-8") or "[]")
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_templates(items):
    TEMPLATES_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Git-synchronisatie: templates en iconen delen via de repo
# ---------------------------------------------------------------------------


def _git_env():
    return {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",          # nooit interactief om inlog vragen
        "GIT_HTTP_LOW_SPEED_LIMIT": "1000",  # breek af bij trage/hangende verbinding
        "GIT_HTTP_LOW_SPEED_TIME": "20",
    }


def _git(args, timeout=30):
    try:
        return subprocess.run(
            ["git", "-C", str(ROOT), *args],
            capture_output=True, text=True, timeout=timeout, env=_git_env(),
        )
    except Exception:
        return None


def git_sync(paths, message):
    """Commit de opgegeven paden en push ze naar origin, zodat templates en
    iconen voor iedereen beschikbaar zijn. Faalt nooit hard: de lokale
    wijziging blijft altijd bewaard. Retourneert status voor de UI."""
    res = {"synced": False, "pushed": False, "message": ""}
    if not (ROOT / ".git").exists() or not which("git"):
        res["message"] = "Geen git-repo — alleen lokaal opgeslagen."
        return res

    r = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    branch = (r.stdout.strip() if r and r.returncode == 0 else "") or "main"

    _git(["add", "--", *[str(x) for x in paths]])

    # Alleen committen als er daadwerkelijk iets gewijzigd is t.o.v. HEAD.
    staged = _git(["diff", "--cached", "--quiet"])
    if staged is not None and staged.returncode != 0:
        _git(["commit", "-m", message])
    res["synced"] = True

    # Eerst remote-wijzigingen ophalen en erbovenop rebasen, zodat een
    # gelijktijdige wijziging van een collega niet tot een geweigerde push leidt.
    pull = _git(["pull", "--rebase", "--autostash", "origin", branch])
    if pull is not None and pull.returncode != 0:
        _git(["rebase", "--abort"])
        res["message"] = ("Lokaal opgeslagen. Automatisch samenvoegen met GitHub "
                          "mislukt (conflict) \u2014 deel handmatig.")
        return res

    push = _git(["push", "origin", branch])
    if push is not None and push.returncode == 0:
        res["pushed"] = True
        res["message"] = "Opgeslagen en gedeeld via GitHub."
    else:
        last = ""
        if push and push.stderr:
            lines = [l for l in push.stderr.splitlines() if l.strip()]
            last = lines[-1][:200] if lines else ""
        res["message"] = ("Lokaal opgeslagen; push naar GitHub mislukt"
                          + (f": {last}" if last else "."))
    return res


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="EXIT-Toys-C2PA-Tool")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/icons", StaticFiles(directory=str(ICONS_DIR)), name="icons")


@app.get("/", response_class=HTMLResponse)
def index():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/api/status")
def status():
    info = c2patool_info()
    return {
        "c2patool": info,
        "ffmpeg": ffmpeg_present(),
        "claim_generator": CLAIM_GENERATOR,
    }


@app.get("/api/version")
def api_version():
    """Vergelijk de lokale versie met GitHub (origin/<branch>)."""
    if not (ROOT / ".git").exists() or not which("git"):
        return {"git": False}
    env = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",          # nooit interactief om inlog vragen
        "GIT_HTTP_LOW_SPEED_LIMIT": "1000",  # breek af bij trage/hangende verbinding
        "GIT_HTTP_LOW_SPEED_TIME": "8",
    }

    def g(args, timeout=8):
        try:
            return subprocess.run(
                ["git", "-C", str(ROOT), *args],
                capture_output=True, text=True, timeout=timeout, env=env,
            )
        except Exception:
            return None

    local = remote = subject = when = None
    r = g(["rev-parse", "HEAD"])
    if r and r.returncode == 0:
        local = r.stdout.strip()
    r = g(["rev-parse", "--abbrev-ref", "HEAD"])
    branch = (r.stdout.strip() if r and r.returncode == 0 else "") or "main"
    r = g(["log", "-1", "--format=%cI\x1f%s"])
    if r and r.returncode == 0 and r.stdout.strip():
        parts = r.stdout.strip().split("\x1f", 1)
        when = parts[0]
        subject = parts[1] if len(parts) > 1 else None
    # remote-tip ophalen (netwerkcall)
    r = g(["ls-remote", "origin", branch], timeout=10)
    if r and r.returncode == 0 and r.stdout.strip():
        remote = r.stdout.split()[0]

    up = (local == remote) if (local and remote) else None
    return {
        "git": True,
        "branch": branch,
        "local": local[:7] if local else None,
        "remote": remote[:7] if remote else None,
        "up_to_date": up,
        "reachable": remote is not None,
        "subject": subject,
        "when": when,
    }


@app.get("/api/icons")
def api_icons():
    icons = sorted([p.name for p in ICONS_DIR.glob("*.png")] + [p.name for p in ICONS_DIR.glob("*.PNG")])
    return {"icons": icons}


@app.post("/api/icons")
async def upload_icon(file: UploadFile = File(...)):
    name = os.path.basename(file.filename or "icoon.png")
    if not name.lower().endswith(".png"):
        raise HTTPException(400, "Alleen PNG-bestanden (met transparantie) worden ondersteund.")
    data = await file.read()
    try:
        Image.open(io.BytesIO(data)).verify()
    except Exception:
        raise HTTPException(400, "Ongeldig PNG-bestand.")
    dest = ICONS_DIR / name
    dest.write_bytes(data)
    sync = git_sync([f"icons/{name}"], f"Icoon toevoegen/bijwerken: {name}")
    return {"ok": True, "name": name, "sync": sync}


def _applescript_quote(text: str) -> str:
    """Escape een string voor veilig gebruik binnen een AppleScript-literal."""
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


@app.post("/api/pick-folder")
def api_pick_folder(payload: dict | None = None):
    """Open een native macOS-mapkiezer (Finder) en geef het gekozen absolute
    pad terug. Handiger dan het pad handmatig plakken. Alleen op macOS."""
    if sys.platform != "darwin" or not which("osascript"):
        raise HTTPException(400, "De mapkiezer werkt alleen op macOS. Plak het pad hier handmatig.")
    prompt = "Kies een map"
    start = ""
    if isinstance(payload, dict):
        prompt = (payload.get("prompt") or prompt).strip() or prompt
        start = (payload.get("start") or "").strip()

    loc = ""
    if start:
        sp = Path(start).expanduser()
        if sp.is_dir():
            loc = f" default location (POSIX file {_applescript_quote(str(sp))})"

    script = (
        f"set theFolder to choose folder with prompt {_applescript_quote(prompt)}{loc}\n"
        "return POSIX path of theFolder"
    )
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=300,
        )
    except Exception as e:
        raise HTTPException(500, f"Kon de mapkiezer niet openen: {e}")

    if r.returncode != 0:
        err = (r.stderr or "").strip()
        # -128 = gebruiker annuleerde de dialoog: geen fout, gewoon niets kiezen.
        if "-128" in err or "cancel" in err.lower():
            return {"ok": False, "canceled": True}
        raise HTTPException(500, err.splitlines()[-1] if err else "Mapkiezer mislukt.")

    path = r.stdout.strip()
    if len(path) > 1:
        path = path.rstrip("/")   # nette weergave zonder afsluitende slash
    return {"ok": True, "path": path}


@app.get("/api/templates")
def api_get_templates():
    return {"templates": load_templates()}


@app.post("/api/templates")
async def api_save_template(payload: dict):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "Templatenaam ontbreekt.")
    fields = payload.get("fields") or {}
    overwrite = bool(payload.get("overwrite"))
    make_default = bool(payload.get("default"))
    items = load_templates()
    idx = next((i for i, t in enumerate(items) if t.get("name") == name), None)
    if idx is not None and not overwrite:
        raise HTTPException(409, f"Template '{name}' bestaat al.")
    entry = {"name": name, "default": make_default, "fields": fields}
    if idx is not None:
        items[idx] = entry
    else:
        items.append(entry)
    if make_default:
        for t in items:
            t["default"] = t.get("name") == name
    save_templates(items)
    sync = git_sync(["templates.json"], f"Template opslaan: {name}")
    return {"ok": True, "templates": items, "sync": sync}


@app.put("/api/templates/{name}")
async def api_update_template(name: str, payload: dict):
    items = load_templates()
    idx = next((i for i, t in enumerate(items) if t.get("name") == name), None)
    if idx is None:
        raise HTTPException(404, f"Template '{name}' niet gevonden.")
    items[idx]["fields"] = payload.get("fields") or {}
    if "default" in payload:
        md = bool(payload["default"])
        if md:
            for t in items:
                t["default"] = t.get("name") == name
        else:
            items[idx]["default"] = False
    save_templates(items)
    sync = git_sync(["templates.json"], f"Template bijwerken: {name}")
    return {"ok": True, "templates": items, "sync": sync}


@app.delete("/api/templates/{name}")
def api_delete_template(name: str):
    items = load_templates()
    new = [t for t in items if t.get("name") != name]
    if len(new) == len(items):
        raise HTTPException(404, f"Template '{name}' niet gevonden.")
    save_templates(new)
    sync = git_sync(["templates.json"], f"Template verwijderen: {name}")
    return {"ok": True, "templates": new, "sync": sync}


@app.post("/api/preview")
async def api_preview(payload: dict):
    """Genereer een preview (PNG data-URL) van één voorbeeldbeeld met labelinstellingen."""
    label = payload.get("label") or {}
    input_dir = (payload.get("input_dir") or "").strip()
    sample = None
    if input_dir:
        p = Path(input_dir).expanduser()
        if p.is_dir():
            for f in sorted(p.glob("*")):
                if f.suffix.lower() in IMAGE_EXT and not f.name.startswith("."):
                    sample = f
                    break
            if sample is None and payload.get("recursive"):
                for f in sorted(p.rglob("*")):
                    if f.suffix.lower() in IMAGE_EXT and not f.name.startswith("."):
                        sample = f
                        break

    if sample is not None:
        try:
            src = Image.open(sample)
            src.load()
        except Exception:
            src = _placeholder_image()
        source_name = sample.name
    else:
        src = _placeholder_image()
        source_name = "voorbeeld (geen beeld in map)"

    # verkleinen voor snelle preview, maar labelverhoudingen kloppen (op basis van breedte %)
    src = src.convert("RGBA")
    max_w = 900
    if src.width > max_w:
        ratio = max_w / src.width
        src = src.resize((max_w, int(src.height * ratio)), Image.LANCZOS)

    if payload.get("enabled", True):
        out = burn_label(src, label)
    else:
        out = src
    buf = io.BytesIO()
    out.convert("RGBA").save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return {"image": f"data:image/png;base64,{b64}", "source": source_name}


def _placeholder_image():
    W, H = 900, 600
    img = Image.new("RGB", (W, H), (60, 64, 72))
    d = ImageDraw.Draw(img)
    for y in range(H):
        shade = int(50 + 40 * (y / H))
        d.line([(0, y), (W, y)], fill=(shade, shade + 4, shade + 10))
    font = _load_font(40)
    txt = "Voorbeeld"
    bbox = d.textbbox((0, 0), txt, font=font)
    d.text(((W - (bbox[2] - bbox[0])) / 2, (H - (bbox[3] - bbox[1])) / 2), txt, font=font, fill=(200, 205, 215))
    return img


@app.post("/api/process")
async def api_process(cfg: dict):
    info = c2patool_info()
    if not info["present"]:
        raise HTTPException(400, "c2patool niet gevonden. Installeer het eerst.")

    # ---- validatie ----
    input_dir = (cfg.get("input_dir") or "").strip()
    if not input_dir:
        raise HTTPException(400, "Mappad (invoer) is verplicht.")
    if not Path(input_dir).expanduser().is_dir():
        raise HTTPException(400, f"Invoermap bestaat niet: {input_dir}")
    if cfg.get("bronsoort") not in DIGITAL_SOURCE_TYPES:
        raise HTTPException(400, "Ongeldige bronsoort.")
    if not (cfg.get("ai_tool") or "").strip():
        raise HTTPException(400, "AI-tool (softwareAgent) is verplicht.")
    if cfg.get("alg", "es256") not in ALGORITHMS:
        raise HTTPException(400, "Ongeldig algoritme.")

    use_test = bool(cfg.get("use_test_cert"))
    cert = (cfg.get("cert_path") or "").strip()
    key = (cfg.get("key_path") or "").strip()
    if not use_test:
        if bool(cert) != bool(key):
            raise HTTPException(400, "Certificaat én private key zijn samen vereist (of gebruik test-certificaat).")
        if cert and not Path(cert).expanduser().exists():
            raise HTTPException(400, f"Certificaatbestand niet gevonden: {cert}")
        if key and not Path(key).expanduser().exists():
            raise HTTPException(400, f"Private-keybestand niet gevonden: {key}")

    label = cfg.get("label") or {}
    label.setdefault("corner", "rechtsonder")

    job_cfg = {
        "input_dir": input_dir,
        "output_dir": cfg.get("output_dir", ""),
        "recursive": bool(cfg.get("recursive")),
        "bronsoort": cfg["bronsoort"],
        "ai_tool": cfg["ai_tool"],
        "model": cfg.get("model", ""),
        "organisatie": cfg.get("organisatie", ""),
        "training_allowed": bool(cfg.get("training_allowed")),
        "use_test_cert": use_test,
        "cert_path": cert,
        "key_path": key,
        "alg": cfg.get("alg", "es256"),
        "verify": bool(cfg.get("verify", True)),
        "burn_icon": bool(cfg.get("burn_icon", True)),
        "label": label,
    }

    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"queue": queue.Queue(), "done": False}
    t = threading.Thread(target=process_batch, args=(job_id, job_cfg), daemon=True)
    JOBS[job_id]["thread"] = t
    t.start()
    return {"job_id": job_id}


@app.get("/api/stream/{job_id}")
def api_stream(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(404, "Onbekende job.")
    q: queue.Queue = JOBS[job_id]["queue"]

    def gen():
        while True:
            try:
                ev = q.get(timeout=1.0)
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
            if ev.get("type") == "done":
                break
        JOBS.pop(job_id, None)

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Opstarten
# ---------------------------------------------------------------------------


def open_browser():
    time.sleep(1.2)
    try:
        webbrowser.open(f"http://localhost:{PORT}")
    except Exception:
        pass


def main():
    ensure_default_icon()
    info = c2patool_info()
    banner = "=" * 64
    print(f"\n{banner}\n  EXIT-Toys-C2PA-Tool  —  lokaal, offline\n{banner}")
    if info["present"]:
        print(f"  c2patool : \033[92mgevonden\033[0m ({info.get('version') or 'versie onbekend'})")
    else:
        print("  c2patool : \033[91mNIET gevonden\033[0m")
        print("             Installeer met:  cargo install c2patool")
        print("             of download een binary van github.com/contentauth/c2pa-rs")
        print("             De Start-knop blijft uitgeschakeld tot c2patool beschikbaar is.")
    print(f"  ffmpeg   : {'gevonden (video-overlay mogelijk)' if ffmpeg_present() else 'niet gevonden (video krijgt geen zichtbaar label)'}")
    print(f"\n  Open in de browser:  http://localhost:{PORT}\n{banner}\n")

    # De macOS-app opent de browser zelf zodra de server klaar is; dan slaan we
    # onze eigen auto-open over (C2PA_NO_BROWSER=1) om dubbele tabs te voorkomen.
    if not os.environ.get("C2PA_NO_BROWSER"):
        threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
