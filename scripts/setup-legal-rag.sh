#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Run from any directory. Reuses an existing virtual environment and .env.
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -r requirements-rag.txt
.venv/bin/python -m backend.ai_service.prepare_legal
# Validate credentials before starting an import; never print the key.
.venv/bin/python - <<'PY'
import os
from dotenv import dotenv_values
if not ({**dotenv_values('.env'), **os.environ}.get('OPENAI_API_KEY') or '').strip():
    raise SystemExit('Set OPENAI_API_KEY in .env or your environment, then rerun this script.')
PY
docker compose -f compose.rag.yaml up -d
export QDRANT_COLLECTION=legal_research
.venv/bin/python - <<'PY'
import time
from backend.ai_service.rag import KnowledgeRag
rag = KnowledgeRag()
try:
    for attempt in range(30):
        try:
            rag.client.get_collections()
            break
        except Exception:
            if attempt == 29:
                raise
            time.sleep(1)
finally:
    rag.client.close()
PY
.venv/bin/python -m backend.ai_service.rag ingest data/processed/legal-research.jsonl
.venv/bin/python -m backend.ai_service.rag status
echo 'Ready: QDRANT_COLLECTION=legal_research .venv/bin/python -m backend.ai_service.rag search "flight delay compensation"'
