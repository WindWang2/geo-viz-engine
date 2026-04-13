#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[geo-viz] Building Python backend with PyInstaller ..."
cd "$ROOT_DIR/src-python"
source venv/bin/activate
pip install -r requirements-build.txt --quiet
pyinstaller --onefile --name geoviz-backend app/main.py   --distpath "$ROOT_DIR/src-tauri/binaries"

TARGET_TRIPLE=$(rustc -Vv | grep 'host:' | awk '{print $2}')
BINARY="$ROOT_DIR/src-tauri/binaries/geoviz-backend"
if [[ "$OSTYPE" == "msys"* || "$OSTYPE" == "win"* ]]; then
  mv "$BINARY.exe" "${BINARY}-${TARGET_TRIPLE}.exe"
else
  mv "$BINARY" "${BINARY}-${TARGET_TRIPLE}"
fi
echo "[geo-viz] Python binary -> geoviz-backend-${TARGET_TRIPLE}"

echo "[geo-viz] Building Vite frontend ..."
cd "$ROOT_DIR/src-web"
npm run build

echo "[geo-viz] Building Tauri app ..."
cd "$ROOT_DIR/src-tauri"
GEOVIZ_MODE=prod cargo tauri build

echo "[geo-viz] Build complete. Artifacts in src-tauri/target/release/bundle/"
