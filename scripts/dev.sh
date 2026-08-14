#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

echo "==> Pictale dev (with frontend watchdog)"

if [[ ! -d "$BACKEND/.venv" ]]; then
  echo "==> Creating backend venv"
  python3 -m venv "$BACKEND/.venv"
  "$BACKEND/.venv/bin/pip" install -r "$BACKEND/requirements.txt"
fi

if [[ ! -f "$BACKEND/.env" ]]; then
  cp "$BACKEND/.env.example" "$BACKEND/.env"
fi

if [[ ! -f "$FRONTEND/.env.local" ]]; then
  cp "$FRONTEND/.env.local.example" "$FRONTEND/.env.local"
fi

if [[ ! -d "$FRONTEND/node_modules" ]]; then
  echo "==> Installing frontend deps"
  (cd "$FRONTEND" && npm install)
fi

cleanup() {
  echo ""
  echo "==> Stopping…"
  kill "$BACK_PID" "$WATCH_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> Backend http://127.0.0.1:8000"
(
  cd "$BACKEND"
  "$BACKEND/.venv/bin/uvicorn" app.main:app --reload --host 127.0.0.1 --port 8000
) &
BACK_PID=$!

echo "==> Frontend + watchdog http://127.0.0.1:3000"
bash "$ROOT/scripts/frontend-watchdog.sh" &
WATCH_PID=$!

wait
