#!/bin/bash
# Bouwt "C2PA AI-labeltool.app" en installeert 'm in /Applications (of ~/Applications).
# Herbruikbaar: draai dit opnieuw na wijzigingen. Vereist dat het project op
# PROJECT_DIR staat en dat c2patool op PATH of op ~/bin/c2patool aanwezig is.
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MACAPP_DIR="$PROJECT_DIR/macapp"
APP_NAME="C2PA AI-labeltool"

# Doelmap: /Applications indien schrijfbaar, anders ~/Applications.
if [ -w "/Applications" ]; then DEST="/Applications"; else DEST="$HOME/Applications"; mkdir -p "$DEST"; fi
APP="$DEST/$APP_NAME.app"

echo "→ Bouwen: $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/bin"

# Info.plist
cp "$MACAPP_DIR/Info.plist" "$APP/Contents/Info.plist"

# Launcher (projectpad invullen)
sed "s#__APP_DIR__#$PROJECT_DIR#g" "$MACAPP_DIR/launcher.sh" > "$APP/Contents/MacOS/launcher"
chmod +x "$APP/Contents/MacOS/launcher"

# Icoon
if [ -f "$MACAPP_DIR/AppIcon.icns" ]; then
  cp "$MACAPP_DIR/AppIcon.icns" "$APP/Contents/Resources/AppIcon.icns"
fi

# c2patool meebundelen (zoek op ~/bin of PATH)
C2=""
[ -x "$HOME/bin/c2patool" ] && C2="$HOME/bin/c2patool"
[ -z "$C2" ] && C2="$(command -v c2patool || true)"
if [ -n "$C2" ]; then
  cp "$C2" "$APP/Contents/Resources/bin/c2patool"
  chmod +x "$APP/Contents/Resources/bin/c2patool"
  echo "→ c2patool meegebundeld vanaf: $C2"
else
  echo "! c2patool niet gevonden — de app werkt pas als c2patool op PATH staat."
fi

# Quarantine weghalen zodat de app zonder Gatekeeper-blok opent.
/usr/bin/xattr -cr "$APP" 2>/dev/null || true
# Finder de nieuwe app/icoon laten oppikken.
/usr/bin/touch "$APP"

echo "✓ Klaar: $APP"
