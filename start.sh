#!/usr/bin/env bash
# Start the integrated Condor demo; Ctrl+C stops both servers.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$ROOT"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
if [[ "${1:-}" == "--help" ]]; then
  echo 'Usage: ./start.sh'
  echo 'Starts live AI with explicit offline fallback, backend and frontend.'
  echo 'Optional: BACKEND_PORT=8002 FRONTEND_PORT=5174 ./start.sh'
  echo 'Put OPENAI_API_KEY in the project .env or your environment.'
  exit 0
fi
cd "$PROJECT"
command -v node >/dev/null && command -v npm >/dev/null || {
  echo 'Install Node.js 22.12+ (including npm) first.' >&2; exit 1;
}
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 22 || (major === 22 && minor < 12)) process.exit(1)' || {
  echo 'Node.js 22.12+ is required.' >&2; exit 1;
}
if [[ ! -x .venv/bin/python ]]; then
  command -v python3.13 >/dev/null || { echo 'Install Python 3.13 first.' >&2; exit 1; }
  python3.13 -m venv .venv
fi
.venv/bin/python -c 'import sys; assert sys.version_info >= (3, 11), "Recreate .venv using Python 3.11+"'
.venv/bin/python - "$BACKEND_PORT" "$FRONTEND_PORT" <<'PY'
import socket
import sys

ports = [int(value) for value in sys.argv[1:]]
if len(set(ports)) != 2 or any(not 0 < port < 65536 for port in ports):
    sys.exit('Choose two different ports between 1 and 65535.')
for port in ports:
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', port))
        except OSError:
            sys.exit(f'Port {port} is in use. Stop the old server or set BACKEND_PORT / FRONTEND_PORT.')
PY
if ! .venv/bin/python -c 'import fastapi, uvicorn, sqlalchemy, pydantic, openai, dotenv, multipart, httpx' 2>/dev/null; then
  .venv/bin/python -m pip install -r requirements.txt -r demo_backend/requirements.txt
fi
if [[ ! -f frontend/node_modules/vite/bin/vite.js ]]; then
  (cd frontend && npm ci)
fi

backend_pid=''
frontend_pid=''
cleanup() {
  trap - EXIT INT TERM
  [[ -z "$frontend_pid" ]] || kill "$frontend_pid" 2>/dev/null || true
  [[ -z "$backend_pid" ]] || kill "$backend_pid" 2>/dev/null || true
  [[ -z "$frontend_pid" ]] || wait "$frontend_pid" 2>/dev/null || true
  [[ -z "$backend_pid" ]] || wait "$backend_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo 'Starting live AI; configuration/provider failures will use labelled offline demo decisions.'
echo 'Credentials: project .env or OPENAI_API_KEY. Existing case progress is preserved.'
AI_MODE=openai AI_FALLBACK_OFFLINE=1 \
  .venv/bin/uvicorn demo_backend.app:app --host 127.0.0.1 --port "$BACKEND_PORT" &
backend_pid=$!
(
  cd frontend
  export API_PROXY_TARGET="http://127.0.0.1:$BACKEND_PORT"
  exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort
) &
frontend_pid=$!

# Wait for both HTTP services, checking for early startup failures.
ready=0
for ((attempt=0; attempt<60; attempt++)); do
  if ! kill -0 "$backend_pid" 2>/dev/null || ! kill -0 "$frontend_pid" 2>/dev/null; then
    echo 'A server failed to start; see its error above.' >&2; exit 1
  fi
  if .venv/bin/python - "$BACKEND_PORT" "$FRONTEND_PORT" <<'PY' 2>/dev/null
import sys
from urllib.request import urlopen

for port, path in zip(sys.argv[1:], ('/api/cases', '/')):
    with urlopen(f'http://127.0.0.1:{port}{path}', timeout=0.5) as response:
        assert response.status == 200
PY
  then
    ready=1; break
  fi
  sleep 0.5
done
[[ "$ready" == 1 ]] || { echo 'Servers did not become ready in time.' >&2; exit 1; }
echo "Demo ready: http://127.0.0.1:$FRONTEND_PORT/"
echo "API docs:   http://127.0.0.1:$BACKEND_PORT/docs"
echo 'Press Ctrl+C to stop both servers.'
while kill -0 "$backend_pid" 2>/dev/null && kill -0 "$frontend_pid" 2>/dev/null; do
  sleep 1
done
echo 'A server stopped; shutting down the demo.' >&2
exit 1
