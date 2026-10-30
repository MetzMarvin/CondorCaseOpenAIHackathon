#!/usr/bin/env bash
# Start the shared backend and both frontends; Ctrl+C stops all three servers.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$ROOT"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
PORTAL_PORT="${PORTAL_PORT:-5174}"
if [[ "${1:-}" == "--help" ]]; then
  echo 'Usage: ./start.sh'
  echo 'Starts the unified backend, operations frontend and customer portal.'
  echo 'Set AI_MODE=offline CONDOR_PREPARATION_MODE=offline for a stored demo.'
  echo 'Ports: BACKEND_PORT=8000 FRONTEND_PORT=5173 PORTAL_PORT=5174'
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
.venv/bin/python - "$BACKEND_PORT" "$FRONTEND_PORT" "$PORTAL_PORT" <<'PY'
import socket
import sys

ports = [int(value) for value in sys.argv[1:]]
if len(set(ports)) != 3 or any(not 0 < port < 65536 for port in ports):
    sys.exit('Choose three different ports between 1 and 65535.')
for port in ports:
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('127.0.0.1', port))
        except OSError:
            sys.exit(f'Port {port} is in use. Stop the old server or set BACKEND_PORT / FRONTEND_PORT / PORTAL_PORT.')
PY
if ! .venv/bin/python -c 'import fastapi, uvicorn, sqlalchemy, pydantic, openai, dotenv, multipart, httpx, pypdf, PIL, pypdfium2' 2>/dev/null; then
  .venv/bin/python -m pip install -r backend/requirements-lock.txt
fi
if [[ ! -f frontend/node_modules/vite/bin/vite.js ]]; then
  (cd frontend && npm ci)
fi

backend_pid=''
frontend_pid=''
portal_pid=''
cleanup() {
  trap - EXIT INT TERM
  [[ -z "$portal_pid" ]] || kill "$portal_pid" 2>/dev/null || true
  [[ -z "$frontend_pid" ]] || kill "$frontend_pid" 2>/dev/null || true
  [[ -z "$backend_pid" ]] || kill "$backend_pid" 2>/dev/null || true
  [[ -z "$frontend_pid" ]] || wait "$frontend_pid" 2>/dev/null || true
  [[ -z "$backend_pid" ]] || wait "$backend_pid" 2>/dev/null || true
  [[ -z "$portal_pid" ]] || wait "$portal_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

echo 'Starting AI; live configuration/provider failures remain failed runs. Use AI_MODE=offline CONDOR_PREPARATION_MODE=offline for the deterministic demo.'
echo 'Credentials: project .env or OPENAI_API_KEY. Existing case progress is preserved.'
AI_MODE="${AI_MODE:-openai}" \
  .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port "$BACKEND_PORT" &
backend_pid=$!
(
  cd frontend
  export API_PROXY_TARGET="http://127.0.0.1:$BACKEND_PORT"
  exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort
) &
frontend_pid=$!
(
  cd frontend
  export API_PROXY_TARGET="http://127.0.0.1:$BACKEND_PORT"
  exec node node_modules/vite/bin/vite.js --host 127.0.0.1 --port "$PORTAL_PORT" --strictPort
) &
portal_pid=$!

# Wait for all HTTP services, checking for early startup failures.
ready=0
for ((attempt=0; attempt<60; attempt++)); do
  if ! kill -0 "$backend_pid" 2>/dev/null || ! kill -0 "$frontend_pid" 2>/dev/null || ! kill -0 "$portal_pid" 2>/dev/null; then
    echo 'A server failed to start; see its error above.' >&2; exit 1
  fi
  if .venv/bin/python - "$BACKEND_PORT" "$FRONTEND_PORT" "$PORTAL_PORT" <<'PY' 2>/dev/null
import sys
from urllib.request import urlopen

for port, path in zip(sys.argv[1:], ('/api/health', '/', '/portal')):
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
echo "Customer portal: http://127.0.0.1:$PORTAL_PORT/portal"
echo "API docs:   http://127.0.0.1:$BACKEND_PORT/docs"
echo 'Both frontends share one backend and case database; System 2 runs inside it.'
echo 'Press Ctrl+C to stop all three servers.'
while kill -0 "$backend_pid" 2>/dev/null && kill -0 "$frontend_pid" 2>/dev/null && kill -0 "$portal_pid" 2>/dev/null; do
  sleep 1
done
echo 'A server stopped; shutting down the demo.' >&2
exit 1
