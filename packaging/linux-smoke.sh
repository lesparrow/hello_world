#!/usr/bin/env bash
# Vérifie une installation Linux de STATPFE : moteur installé, lancement réel de l'application
# (sous un écran virtuel), démarrage du moteur par l'application, arrêt propre.
# Usage : packaging/linux-smoke.sh <commande de l'application> <chemin du moteur> [capture.png]
set -euo pipefail
APP="$1"; ENGINE="$2"; SHOT="${3:-}"
export STATPFE_CONFIG_DIR="${STATPFE_CONFIG_DIR:-$(mktemp -d)}"

echo "== Diagnostic du moteur installé ($ENGINE)"
out=$(printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"engine.selfcheck"}' | "$ENGINE" 2>/dev/null)
echo "$out" | python3 -c 'import json,sys; d=json.loads(sys.stdin.readline())["result"]; [print(" ", c["key"], "ok" if c["ok"] else "ÉCHEC", c["version"] or "", c["detail"][:60]) for c in d["checks"]]; sys.exit(0 if d["ok"] else 1)'

echo "== Lancement de l'application sous un écran virtuel"
Xvfb :99 -screen 0 1440x900x24 >/dev/null 2>&1 &
XVFB=$!
trap 'kill $XVFB 2>/dev/null || true' EXIT
sleep 1
DISPLAY=:99 $APP >/tmp/statpfe-app.log 2>&1 &
APP_PID=$!
ok=0
for i in $(seq 1 60); do
  if pgrep -x statpfe-engine >/dev/null; then ok=1; break; fi
  if ! kill -0 $APP_PID 2>/dev/null; then echo "L'application s'est arrêtée :"; cat /tmp/statpfe-app.log; exit 1; fi
  sleep 1
done
[ $ok = 1 ] || { echo "Le moteur n'a pas été démarré par l'application"; cat /tmp/statpfe-app.log; exit 1; }
echo "  application lancée, moteur démarré par l'application (après ${i} s)"
sleep 6
if [ -n "$SHOT" ] && command -v import >/dev/null; then DISPLAY=:99 import -window root "$SHOT" && echo "  capture : $SHOT"; fi
kill $APP_PID 2>/dev/null || true; pkill -x statpfe || true  # AppImage : le lanceur et l'application sont deux processus
for i in $(seq 1 20); do pgrep -x statpfe-engine >/dev/null || break; sleep 1; done
if pgrep -x statpfe-engine >/dev/null; then echo "Le moteur est resté actif après la fermeture"; exit 1; fi
echo "  fermeture : le moteur s'est arrêté avec l'application"
