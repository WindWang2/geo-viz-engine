#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

GEOVIZ_API_TOKEN="$(grep '^VITE_DEV_API_TOKEN=' "$ROOT_DIR/src-web/.env.development" | cut -d= -f2)"
export GEOVIZ_API_TOKEN

echo "[geo-viz] Starting Python backend on :8000 ..."
cd "$ROOT_DIR/src-python"
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
PYTHON_PID=$!

echo "[geo-viz] Starting Vite frontend on :5173 ..."
cd "$ROOT_DIR/src-web"
npm run dev &
VITE_PID=$!

echo "[geo-viz] Waiting for backend ..."
for i in $(seq 1 30); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}"     -H "X-API-Token: $GEOVIZ_API_TOKEN"     http://127.0.0.1:8000/api/system/status 2>/dev/null || echo "000")
  if [ "$STATUS" = "200" ]; then
    echo "[geo-viz] Backend ready."
    break
  fi
  sleep 1
done

echo "[geo-viz] Starting Tauri dev ..."
cd "$ROOT_DIR/src-tauri"
GEOVIZ_MODE=dev cargo tauri dev

kill "$PYTHON_PID" "$VITE_PID" 2>/dev/null || true
