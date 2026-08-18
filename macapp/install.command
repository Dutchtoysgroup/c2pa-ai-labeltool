#!/bin/bash
# Dubbelklik-installer voor "C2PA AI-labeltool".
# Doet alles voor de collega: GitHub-login (1x via browser), app ophalen,
# bouwen en starten. Daarna werkt de app zichzelf bij vanaf GitHub.

set -u
REPO="Dutchtoysgroup/c2pa-ai-labeltool"
REPO_URL="https://github.com/${REPO}.git"
DEST="$HOME/c2pa-ai-tool"

say(){ printf "\n\033[1m%s\033[0m\n" "$1"; }
die(){ printf "\n\033[91m%s\033[0m\n\n" "$1"; echo "Sluit dit venster, los het bovenstaande op en dubbelklik opnieuw op de installer."; echo; read -r -p "Druk op Enter om te sluiten…" _; exit 1; }

clear
say "C2PA AI-labeltool — installatie"
echo "Dit haalt de app op van GitHub, bouwt 'm en start 'm. Eenmalig."
echo

# 1) git (Apple Command Line Tools)
if ! command -v git >/dev/null 2>&1; then
  say "Even Apple's ontwikkeltools installeren (nodig voor git)…"
  xcode-select --install 2>/dev/null || true
  die "Rond het Apple-installatievenster af dat net opende, en dubbelklik dan opnieuw op deze installer."
fi

# 2) gh (GitHub CLI) — voor een makkelijke login op de privé-repo
GH="$(command -v gh || true)"
if [ -z "$GH" ]; then
  say "GitHub-hulpje (gh) downloaden…"
  TOOLS="$HOME/.c2pa-installer"; mkdir -p "$TOOLS"
  ARCH=arm64; [ "$(uname -m)" = "x86_64" ] && ARCH=amd64
  URL="$(curl -fsSL https://api.github.com/repos/cli/cli/releases/latest 2>/dev/null \
        | grep -o "https://[^\"]*_macOS_${ARCH}\.zip" | head -1)"
  if [ -n "$URL" ] && curl -fsSL "$URL" -o "$TOOLS/gh.zip" && /usr/bin/unzip -oq "$TOOLS/gh.zip" -d "$TOOLS"; then
    GH="$(/usr/bin/find "$TOOLS" -type f -name gh -path '*/bin/*' | head -1)"
  fi
  [ -n "$GH" ] || die "Kon het GitHub-hulpje niet downloaden. Controleer je internet en probeer opnieuw."
fi

# 3) inloggen bij GitHub (eenmalig, via de browser)
if ! "$GH" auth status >/dev/null 2>&1; then
  say "Log even in bij GitHub — je browser opent zo. Volg de stappen."
  "$GH" auth login --hostname github.com --git-protocol https --web \
    || die "Inloggen bij GitHub is niet gelukt."
fi
"$GH" auth setup-git >/dev/null 2>&1 || true   # git gebruikt voortaan deze login (ook voor auto-update)

# 4) repo ophalen of bijwerken
if [ -d "$DEST/.git" ]; then
  say "Bestaande installatie bijwerken…"
  git -C "$DEST" pull --ff-only || true
else
  say "App ophalen van GitHub…"
  git clone "$REPO_URL" "$DEST" \
    || die "Ophalen mislukt. Heb je toegang tot de repo? Vraag of je toegevoegd bent tot ${REPO}."
fi

# 5) app bouwen (bouwscript downloadt zelf c2patool)
say "App bouwen…"
bash "$DEST/macapp/build_mac_app.sh" || die "Bouwen van de app is mislukt."

# 6) starten
say "Klaar! De app staat in je map Programma's — en start nu."
open -a "C2PA AI-labeltool" 2>/dev/null \
  || open "/Applications/C2PA AI-labeltool.app" 2>/dev/null \
  || open "$HOME/Applications/C2PA AI-labeltool.app" 2>/dev/null
echo
echo "Je kunt dit venster sluiten. Voortaan open je de app gewoon via Launchpad/Spotlight."
echo
read -r -p "Druk op Enter om te sluiten…" _
