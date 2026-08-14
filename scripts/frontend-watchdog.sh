#!/usr/bin/env bash
# Watchdog: keep Next.js frontend alive. Restarts when http://127.0.0.1:3000 hangs.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND="$ROOT/frontend"
HOST="${PICTALE_FE_HOST:-127.0.0.1}"
PORT="${PICTALE_FE_PORT:-3000}"
URL="http://${HOST}:${PORT}/"
CHECK_EVERY="${PICTALE_FE_CHECK_EVERY:-20}"
FAILS_NEED="${PICTALE_FE_FAILS_NEED:-2}"
CURL_TIMEOUT="${PICTALE_FE_CURL_TIMEOUT:-5}"

fail_count=0
front_pid=""

cleanup() {
  if [[ -n "${front_pid}" ]] && kill -0 "$front_pid" 2>/dev/null; then
    kill "$front_pid" 2>/dev/null || true
    wait "$front_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

start_frontend() {
  if [[ -n "${front_pid}" ]] && kill -0 "$front_pid" 2>/dev/null; then
    kill "$front_pid" 2>/dev/null || true
    wait "$front_pid" 2>/dev/null || true
  fi
  # Clear stuck listener
  for p in $(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true); do
    kill -9 "$p" 2>/dev/null || true
  done
  sleep 1
  echo "==> Starting frontend ${URL}"
  (
    cd "$FRONTEND"
    # Cap Node heap a bit so one hung Next is less likely to thrash the whole Mac
    export NODE_OPTIONS="${NODE_OPTIONS:---max-old-space-size=3072}"
    npm run dev -- --hostname "$HOST" --port "$PORT"
  ) &
  front_pid=$!
  fail_count=0
}

healthy() {
  local code
  code="$(curl -s -m "$CURL_TIMEOUT" -o /dev/null -w '%{http_code}' "$URL" || true)"
  [[ "$code" == "200" || "$code" == "304" ]]
}

start_frontend
# Give first compile some room
sleep 8

echo "==> Frontend watchdog on ${URL} (every ${CHECK_EVERY}s)"
while true; do
  if ! kill -0 "$front_pid" 2>/dev/null; then
    echo "==> Frontend process exited — restarting"
    start_frontend
    sleep 8
    continue
  fi
  if healthy; then
    fail_count=0
  else
    fail_count=$((fail_count + 1))
    echo "==> Frontend unhealthy (${fail_count}/${FAILS_NEED})"
    if [[ "$fail_count" -ge "$FAILS_NEED" ]]; then
      echo "==> Restarting hung frontend…"
      start_frontend
      sleep 8
    fi
  fi
  sleep "$CHECK_EVERY"
done
