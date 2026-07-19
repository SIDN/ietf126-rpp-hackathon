#!/usr/bin/env bash
# Starts a registrar portal instance (FastAPI backend + Vite frontend).
#
# Usage:
#   ./start.sh [--port PORT] [--frontend-port PORT] [--name REGISTRAR_NAME] [--registry-url URL]
#
# Run multiple instances with different --port/--frontend-port/--name values
# to simulate multiple registrars transferring domains between each other.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

BACKEND_PORT=8001
FRONTEND_PORT=5174
REGISTRAR_NAME="Registrar A"
REGISTRY_URL="http://localhost:8000/api"
ENV_FILE=""

usage() {
  echo "Usage: $0 [--port PORT] [--frontend-port PORT] [--name REGISTRAR_NAME] [--registry-url URL] [--env-file PATH]"
  echo
  echo "  --port PORT           Backend (FastAPI) port. Default: 8001"
  echo "  --frontend-port PORT  Frontend (Vite) port. Default: 5174"
  echo "  --name NAME           Registrar identity for this instance. Default: 'Registrar A'"
  echo "  --registry-url URL    Registry API base URL. Default: http://localhost:8000/api"
  echo "  --env-file PATH       Extra env file to load (e.g. .env.registrar-b) for"
  echo "                        settings not overridden by the other flags, such as"
  echo "                        OAUTH2_CLIENT_ID/OAUTH2_CLIENT_SECRET/OAUTH2_ISSUER."
  echo "                        Default: backend/.env only."
  echo
  echo "OAuth2 login uses http://localhost:<port>/api/auth/callback as its"
  echo "redirect URI, so a custom --port must also be added as a redirect"
  echo "URI on the Authentik provider (see README.md)."
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      BACKEND_PORT="$2"; shift 2 ;;
    --frontend-port)
      FRONTEND_PORT="$2"; shift 2 ;;
    --name)
      REGISTRAR_NAME="$2"; shift 2 ;;
    --registry-url)
      REGISTRY_URL="$2"; shift 2 ;;
    --env-file)
      ENV_FILE="$2"; shift 2 ;;
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
  echo "Stopping $REGISTRAR_NAME portal (backend + frontend)..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT INT TERM

echo "Starting '$REGISTRAR_NAME' backend on port $BACKEND_PORT (registry: $REGISTRY_URL)..."
(
  cd "$BACKEND_DIR"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  export REGISTRAR_NAME
  export REGISTRY_API_URL="$REGISTRY_URL"
  export CORS_ORIGINS="[\"http://localhost:$FRONTEND_PORT\",\"http://127.0.0.1:$FRONTEND_PORT\"]"
  # These must match the ports this instance actually runs on, not whatever
  # is baked into .env - otherwise the OAuth2 callback (registered on the
  # Authentik provider) and the post-login redirect would target the wrong
  # port when --port/--frontend-port override the defaults.
  export OAUTH2_REDIRECT_URI="http://localhost:$BACKEND_PORT/api/auth/callback"
  export FRONTEND_URL="http://localhost:$FRONTEND_PORT/"
  # Cookies are scoped by domain, not port - two instances both running on
  # "localhost" would otherwise share (and overwrite) the same session
  # cookie. Give each instance its own cookie name so they can't collide.
  export SESSION_COOKIE_NAME="registrar_session_$BACKEND_PORT"
  # This instance's own externally-reachable base URL, used to compute the
  # transfer authorize/complete URLs it self-registers with the registry
  # directory (see api/transfer_routes.py) - must match the port it's
  # actually running on.
  export PUBLIC_BASE_URL="http://localhost:$BACKEND_PORT"
  # backend/.env is always loaded (see core/config.py); --env-file adds a
  # second file on top of it (e.g. .env.registrar-b) for anything not
  # already exported above - env vars set here always win over both files.
  if [[ -n "$ENV_FILE" ]]; then
    exec uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" --env-file "$ENV_FILE"
  else
    exec uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT"
  fi
) &
PIDS+=($!)

echo "Starting '$REGISTRAR_NAME' frontend on port $FRONTEND_PORT..."
(
  cd "$FRONTEND_DIR"
  export VITE_API_URL="http://localhost:$BACKEND_PORT/api"
  exec npm run dev -- --port "$FRONTEND_PORT" --strictPort
) &
PIDS+=($!)

echo
echo "'$REGISTRAR_NAME' backend:  http://localhost:$BACKEND_PORT (docs at /docs)"
echo "'$REGISTRAR_NAME' frontend: http://localhost:$FRONTEND_PORT"
echo "Press Ctrl+C to stop both."

wait
