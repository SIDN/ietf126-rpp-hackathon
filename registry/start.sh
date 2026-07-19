#!/usr/bin/env bash
# Starts the registry backend (FastAPI) and frontend (Vite) together.
#
# Usage:
#   ./start.sh [--port PORT] [--frontend-port PORT]
#
# Run with different --port/--frontend-port values to start additional,
# independent registry instances side by side.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

BACKEND_PORT=8000
FRONTEND_PORT=5173

usage() {
  echo "Usage: $0 [--port PORT] [--frontend-port PORT]"
  echo
  echo "  --port PORT           Backend (FastAPI) port. Default: 8000"
  echo "  --frontend-port PORT  Frontend (Vite) port. Default: 5173"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      BACKEND_PORT="$2"; shift 2 ;;
    --frontend-port)
      FRONTEND_PORT="$2"; shift 2 ;;
    -h|--help)
      usage ;;
    *)
      echo "Unknown argument: $1"
      usage ;;
  esac
done

if [[ ! -d "$BACKEND_DIR/.venv" ]]; then
  echo "Creating backend virtual environment..."
  python3 -m venv "$BACKEND_DIR/.venv"
  "$BACKEND_DIR/.venv/bin/pip" install --upgrade pip -q
  "$BACKEND_DIR/.venv/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "Installing frontend dependencies..."
  (cd "$FRONTEND_DIR" && npm install)
fi

PIDS=()
cleanup() {
  echo
  echo "Stopping registry (backend + frontend)..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

echo "Starting registry backend on port $BACKEND_PORT..."
(
  cd "$BACKEND_DIR"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  export REGISTRY_CORS_ORIGINS="[\"http://localhost:$FRONTEND_PORT\",\"http://127.0.0.1:$FRONTEND_PORT\"]"
  exec uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT"
) &
PIDS+=($!)

echo "Starting registry frontend on port $FRONTEND_PORT..."
(
  cd "$FRONTEND_DIR"
  export VITE_API_URL="http://localhost:$BACKEND_PORT/api"
  exec npm run dev -- --port "$FRONTEND_PORT" --strictPort
) &
PIDS+=($!)

echo
echo "Registry backend:  http://localhost:$BACKEND_PORT (docs at /docs)"
echo "Registry frontend: http://localhost:$FRONTEND_PORT"
echo "Press Ctrl+C to stop both."

wait
