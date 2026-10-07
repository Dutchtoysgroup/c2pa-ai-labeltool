# -*- mode: python ; coding: utf-8 -*-
# PyInstaller-recept voor de kant-en-klare app (macOS .app / Windows-map).
#
#   pyinstaller --noconfirm --distpath dist --workpath build/pyinstaller packaging/c2pa-labeltool.spec
#
# Verwacht c2patool in build/c2patool/ (de workflow downloadt hem). Omgeving:
#   C2PA_TARGET_ARCH        arm64 of x86_64 (macOS)
#   C2PA_CODESIGN_IDENTITY  Developer ID om mee te ondertekenen (macOS); leeg =
#                           ad-hoc, voor testbuilds
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parent
APP_NAME = "C2PA AI-labeltool"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

c2patool = ROOT / "build" / "c2patool" / ("c2patool.exe" if IS_WIN else "c2patool")
if not c2patool.is_file():
    raise SystemExit(f"c2patool ontbreekt: {c2patool}")

datas = [
    (str(ROOT / "static"), "static"),
    (str(ROOT / "icons"), "icons"),
    (str(ROOT / "templates.json"), "."),
    (str(ROOT / "VERSION"), "."),
    (str(ROOT / "certs" / "test" / "es256_certs.pem"), "certs/test"),
    (str(ROOT / "certs" / "test" / "es256_private.key"), "certs/test"),
]

# uvicorn laadt zijn loop/protocol/lifespan-modules op naam; die ziet de
# analyse niet. app.py wordt pas in --server-modus geïmporteerd.
hiddenimports = (
    ["app", "updater", "certifi"]
    + collect_submodules("uvicorn", filter=lambda name: ".workers" not in name)
    + collect_submodules("python_multipart")
)

a = Analysis(
    [str(ROOT / "desktop.py")],
    pathex=[str(ROOT)],
    binaries=[(str(c2patool), "bin")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter"],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    upx=False,
    icon=str(ROOT / ("macapp/AppIcon.icns" if IS_MAC else "winapp/AppIcon.ico")),
    target_arch=os.environ.get("C2PA_TARGET_ARCH") or None,
    codesign_identity=os.environ.get("C2PA_CODESIGN_IDENTITY") or None,
    entitlements_file=str(ROOT / "packaging" / "macos" / "entitlements.plist") if IS_MAC else None,
)

coll = COLLECT(exe, a.binaries, a.datas, name=APP_NAME, upx=False)

if IS_MAC:
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=str(ROOT / "macapp" / "AppIcon.icns"),
        bundle_identifier="com.dutchtoysgroup.c2pa-ai-labeltool",
        version=VERSION,
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "11.0",
            # Geen Dock-icoon: de app start de server en opent de browser, en is
            # dan meteen weer klaar.
            "LSUIElement": True,
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "Dutch Toys Group",
        },
    )
