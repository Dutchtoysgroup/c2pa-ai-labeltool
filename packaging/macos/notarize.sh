#!/bin/bash
# Notariseer een .zip of .dmg via de App Store Connect API-sleutel en wacht op
# de uitslag. Gebruik: notarize.sh <bestand>
# Verwacht APPLE_API_KEY (pad naar de .p8), APPLE_API_KEY_ID en APPLE_API_ISSUER.
set -euo pipefail
FILE="$1"
OUT="$(mktemp)"
xcrun notarytool submit "$FILE" --key "$APPLE_API_KEY" --key-id "$APPLE_API_KEY_ID" \
  --issuer "$APPLE_API_ISSUER" --wait --timeout 45m --output-format json > "$OUT" || true
cat "$OUT"; echo
STATUS="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("status", ""))' "$OUT")"
if [ "$STATUS" != "Accepted" ]; then
  ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("id", ""))' "$OUT")"
  [ -n "$ID" ] && xcrun notarytool log "$ID" --key "$APPLE_API_KEY" --key-id "$APPLE_API_KEY_ID" --issuer "$APPLE_API_ISSUER"
  exit 1
fi
