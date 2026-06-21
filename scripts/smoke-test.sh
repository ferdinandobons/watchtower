#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${TMPDIR:-/tmp}/watchtower-smoke-$$.db"
PORT="${WATCHTOWER_SMOKE_PORT:-18765}"
export WATCHTOWER_DB_PATH="$DB_PATH"

cleanup() {
  kill "${SERVER_PID:-}" 2>/dev/null || true
  rm -f "$DB_PATH" "$DB_PATH-shm" "$DB_PATH-wal"
}
trap cleanup EXIT

python -m watchtower serve --host 127.0.0.1 --port "$PORT" --no-notifications >/tmp/watchtower-smoke.log 2>&1 &
SERVER_PID=$!

for _ in $(seq 1 30); do
  if python -m watchtower doctor --url "http://127.0.0.1:$PORT" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

python -m watchtower demo --url "http://127.0.0.1:$PORT"
