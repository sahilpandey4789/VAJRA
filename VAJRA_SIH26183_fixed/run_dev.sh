#!/usr/bin/env bash
# One-command dev launcher - starts backend (FastAPI, :8000) and
# frontend (Vite, :5173) together, so a demo doesn't start with two
# terminals and a "wait, which folder" moment.
#
# Usage:  ./run_dev.sh
# Stop:   Ctrl+C (kills both processes)
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() {
  echo ""
  echo "Stopping VAJRA (backend + frontend)…"
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "== VAJRA dev launcher =="

if [ ! -d "$ROOT_DIR/backend/.venv" ] && ! python3 -c "import fastapi" 2>/dev/null; then
  echo "-> backend deps not found, installing (pip install -r backend/requirements.txt)…"
  pip install -r "$ROOT_DIR/backend/requirements.txt"
fi

if [ ! -d "$ROOT_DIR/frontend/node_modules" ]; then
  echo "-> frontend deps not found, installing (npm install)…"
  (cd "$ROOT_DIR/frontend" && npm install)
fi

echo "-> starting backend on http://localhost:8000"
(cd "$ROOT_DIR/backend" && python3 main.py) &
BACKEND_PID=$!

sleep 1

echo "-> starting frontend on http://localhost:5173"
(cd "$ROOT_DIR/frontend" && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "VAJRA is starting - open http://localhost:5173"
echo "(Ctrl+C here stops both servers.)"
wait
