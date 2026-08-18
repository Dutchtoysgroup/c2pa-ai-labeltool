#!/bin/bash
# Launcher voor "C2PA AI-labeltool.app"
# Dubbelklikken op de app roept dit script aan: het haalt de nieuwste versie van
# GitHub op, start de lokale server (met de meegebundelde c2patool) en opent de
# tool in de browser.

APP_DIR="__APP_DIR__"
HERE="$(cd "$(dirname "$0")" && pwd)"
RES="$(cd "$HERE/../Resources" 2>/dev/null && pwd)"

# Meegebundelde c2patool + gangbare locaties voorop in PATH.
export PATH="$RES/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

URL="http://localhost:8000"

notify(){ /usr/bin/osascript -e "display notification \"$1\" with title \"C2PA AI-labeltool\"" >/dev/null 2>&1; }
fail(){ /usr/bin/osascript -e "display alert \"C2PA AI-labeltool\" message \"$1\"" >/dev/null 2>&1; exit 1; }

[ -d "$APP_DIR" ] || fail "Projectmap niet gevonden op: $APP_DIR"
cd "$APP_DIR" || fail "Kon niet naar de projectmap gaan."

# Op Apple Silicon de native arm64-architectuur forceren. De universal2
# Python zou anders (via LaunchServices) als x86_64 kunnen starten, waardoor
# arm64-only wheels (pydantic_core, Pillow) niet laden.
ARCHPREFIX=""
if [ "$(/usr/sbin/sysctl -n hw.optional.arm64 2>/dev/null)" = "1" ]; then
  ARCHPREFIX="/usr/bin/arch -arm64"
fi

# --- Auto-update vanaf GitHub (best-effort) ---------------------------------
# Elke start: haal de nieuwste code op. Offline of geen toegang? Dan gewoon
# doorgaan met de huidige lokale versie (nooit blokkeren of falen).
UPDATED=0
if [ -d .git ] && command -v git >/dev/null 2>&1; then
  HEAD_BEFORE="$(git rev-parse HEAD 2>/dev/null)"
  REQ_BEFORE="$(/usr/bin/shasum requirements.txt 2>/dev/null | awk '{print $1}')"
  # GIT_TERMINAL_PROMPT=0: nooit om een wachtwoord vragen (privé-repo → faal snel).
  # LOW_SPEED-limieten: breek af bij een trage/hangende verbinding i.p.v. wachten.
  GIT_TERMINAL_PROMPT=0 GIT_HTTP_LOW_SPEED_LIMIT=1000 GIT_HTTP_LOW_SPEED_TIME=8 \
    git pull --ff-only --quiet 2>/dev/null || true
  HEAD_AFTER="$(git rev-parse HEAD 2>/dev/null)"
  if [ -n "$HEAD_BEFORE" ] && [ "$HEAD_BEFORE" != "$HEAD_AFTER" ]; then
    UPDATED=1
    notify "Nieuwe versie van GitHub opgehaald."
    # dependencies bijwerken als requirements.txt veranderde
    REQ_AFTER="$(/usr/bin/shasum requirements.txt 2>/dev/null | awk '{print $1}')"
    if [ -x ".venv/bin/python" ] && [ "$REQ_BEFORE" != "$REQ_AFTER" ]; then
      $ARCHPREFIX ./.venv/bin/python -m pip install -q -r requirements.txt 2>/dev/null || true
    fi
  fi
fi

# --- Draait de server al? -----------------------------------------------------
if /usr/bin/curl -s -o /dev/null --max-time 2 "$URL/api/status"; then
  if [ "$UPDATED" = "1" ]; then
    # Nieuwe versie opgehaald → server herstarten zodat de nieuwe code laadt.
    PIDS="$(/usr/sbin/lsof -ti tcp:8000 2>/dev/null)"
    [ -n "$PIDS" ] && kill $PIDS 2>/dev/null
    sleep 1
    # (valt hieronder door naar opnieuw starten)
  else
    /usr/bin/open "$URL"
    exit 0
  fi
fi

# --- Eerste start: virtuele omgeving + dependencies opzetten ------------------
if [ ! -x ".venv/bin/python" ]; then
  notify "Eenmalig installeren, een momentje…"
  PY=""
  for c in /usr/local/bin/python3 /opt/homebrew/bin/python3 \
           /Library/Frameworks/Python.framework/Versions/*/bin/python3 /usr/bin/python3; do
    [ -x "$c" ] && { PY="$c"; break; }
  done
  [ -n "$PY" ] || fail "Python 3 niet gevonden. Installeer Python via python.org en probeer opnieuw."
  $ARCHPREFIX "$PY" -m venv .venv || fail "Kon de virtuele omgeving niet aanmaken."
  $ARCHPREFIX ./.venv/bin/python -m pip install -q --upgrade pip
  $ARCHPREFIX ./.venv/bin/python -m pip install -q -r requirements.txt \
    || fail "Installeren van dependencies mislukte (bij de eerste start is internet nodig)."
  notify "Klaar met installeren. De tool opent nu."
fi

# --- Server op de achtergrond starten; wij openen de browser -----------------
/usr/bin/nohup env C2PA_NO_BROWSER=1 $ARCHPREFIX ./.venv/bin/python app.py \
  >/tmp/c2pa-ai-tool.log 2>&1 &
disown 2>/dev/null || true

for _ in $(seq 1 60); do
  if /usr/bin/curl -s -o /dev/null --max-time 2 "$URL/api/status"; then
    /usr/bin/open "$URL"
    exit 0
  fi
  sleep 0.5
done
fail "De server startte niet op tijd. Log: /tmp/c2pa-ai-tool.log"
