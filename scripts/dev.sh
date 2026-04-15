#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export PATH="$HOME/.cargo/bin:$PATH"

GEOVIZ_API_TOKEN=$(grep VITE_DEV_API_TOKEN "$ROOT_DIR/src-web/.env.development" | cut -d= -f2)
export GEOVIZ_API_TOKEN

# Check if ports are already in use
port_in_use() {
  nc -z 127.0.0.1 "$1" 2>/dev/null
  return $?
}

PYTHON_PID=""
VITE_PID=""

if ! port_in_use 8000; then
  echo "[geo-viz] Starting Python backend on :8000 ..."
  cd "$ROOT_DIR/src-python"
  source venv/bin/activate
  uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
  PYTHON_PID=$!
else
  echo "[geo-viz] Python backend already running on :8000, skipping..."
fi

if ! port_in_use 5173; then
  echo "[geo-viz] Starting Vite frontend on :5173 ..."
  cd "$ROOT_DIR/src-web"
  npm run dev &
  VITE_PID=$!
else
  echo "[geo-viz] Vite frontend already running on :5173, skipping..."
fi

echo "[geo-viz] Waiting for backend ..."
for i in $(seq 1 30); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Token: $GEOVIZ_API_TOKEN" http://127.0.0.1:8000/api/system/status 2>/dev/null || echo "000")
  if [ "$STATUS" = "200" ]; then
    echo "[geo-viz] Backend ready."
    break
  fi
  sleep 1
done

echo "[geo-viz] Starting Tauri dev ..."
cd "$ROOT_DIR/src-tauri"
WEBKIT_DISABLE_COMPOSITING_MODE=1 GDK_BACKEND=x11 WEBKIT_DISABLE_DMABUF_RENDERER=1 GEOVIZ_MODE=dev cargo tauri dev

if [ -n "$PYTHON_PID" ]; then
  kill "$PYTHON_PID" 2>/dev/null || true
fi
if [ -n "$VITE_PID" ]; then
  kill "$VITE_PID" 2>/dev/null || true
fi
