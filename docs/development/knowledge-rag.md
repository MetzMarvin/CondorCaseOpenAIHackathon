# Legal and policy retrieval

System 2 owns `backend.ai_service.rag`: synchronous retrieval, no case mutations,
customer messages, or automatic workflow integration. The collection starts empty.

```sh
.venv/bin/python -m pip install -r requirements-rag.txt
docker compose -f compose.rag.yaml up -d
.venv/bin/python -m backend.ai_service.rag init
.venv/bin/python -m backend.ai_service.rag status
```

Qdrant dashboard: http://localhost:6335/dashboard. Port 6335 avoids the existing
Qdrant instance on 6333. A named Docker volume persists data across restarts.
Stop with `docker compose -f compose.rag.yaml down`; omit `-v` to retain data.
Localhost-only deployment, intended for development.

Defaults: OpenAI `text-embedding-3-small`, 1536 dimensions, cosine distance;
FastEmbed `Qdrant/bm25` with its default English tokenizer, k=1.2, b=0.75,
average length=256, and Qdrant IDF weighting. Two candidate lists of 20
(or the requested limit if larger) are fused with Qdrant's RRF; top 5 returned.
These are starting settings, not relevance-tuned legal search.
For a German corpus, configure and reindex with matching German BM25 tokenization
before importing; the current demo defaults to English.

The backend reads `.env` and environment overrides: `OPENAI_API_KEY`,
`QDRANT_URL`, `QDRANT_COLLECTION`, and optional `QDRANT_API_KEY`.
Initialization and empty search need no OpenAI calls. Populated search and ingestion
call OpenAI and may incur embedding costs. FastEmbed downloads BM25 tokenizer
resources on first use. Errors propagate; no fabricated search results.

## Add data later

### Team quick start with the downloaded legal corpus

Prerequisites: Python 3.11+, Docker with Compose and daemon access, and an OpenAI
API key. Share this checkout including `data/legal/raw/`, `data/legal/extracted/`,
and `data/legal/source-manifest.json`; these files are required on each machine.
Do not share `.env`, the virtual environment, or Docker volumes.

Set `OPENAI_API_KEY` in your local `.env` (copy `.env.example` only if `.env` does
not already exist), then run from the repository root:

```sh
bash scripts/setup-legal-rag.sh
QDRANT_COLLECTION=legal_research .venv/bin/python -m backend.ai_service.rag search 'flight delay compensation'
```

The script installs dependencies, verifies the manifest's PDF hashes and page
references, prepares chunks, starts Qdrant, waits for readiness, and imports into
`legal_research`. Each teammate gets their own persistent database on port 6335.
It reuses existing `.env` settings, including `QDRANT_URL` if set; unset that
override to use the local database. Port 6335 must be available.

Seven downloaded sources are included; five unacquired sources and the associated
Commission statement are excluded. Page passages use 2400-character windows with
300-character overlap, preserving physical page numbers, canonical URLs, original
PDF hashes, source type and review status. This is preliminary page-based chunking,
not reviewed article segmentation. Source versions include PDF/extraction hashes
and the splitter version. Repeating the same import overwrites the same point IDs
but still makes embedding API calls. Changed source versions coexist.

The source manifest marks these documents unreviewed. Their payloads retain
`runtime_enabled: false`, and the separate research collection is not connected to
case decisions. This metadata is descriptive, not Qdrant access control. Search
results are for corpus exploration; review and applicability handling remain future
workflow integration work. No company policies have been downloaded here.

To prepare the JSONL without Docker or embedding API calls:

```sh
.venv/bin/python -m backend.ai_service.prepare_legal
```

Output: `data/processed/legal-research.jsonl` (generated and git-ignored).

### Import other passages

Import curated, pre-chunked UTF-8 JSONL, one passage per line (maximum 6000
characters). Start around 256 words per passage with modest overlap, retaining
section boundaries. Extract PDF text before import. Example schema only:

```json
{"source_id":"policy-001","version":"2026-10","chunk_id":"section-1","title":"Baggage policy","source_uri":"https://example.org/policy","kind":"policy","text":"The approved passage goes here."}
```

Use `kind: "legal"` for legal sources and `"policy"` for company policies.

```sh
.venv/bin/python -m backend.ai_service.rag ingest documents.jsonl
.venv/bin/python -m backend.ai_service.rag search 'delayed baggage reimbursement'
.venv/bin/python -m backend.ai_service.rag search 'refund rules' --kind policy --limit 5
```

Repeated source/version/chunk IDs overwrite the same point. New versions coexist;
remove superseded versions explicitly before relying on the collection for current
policy decisions. Imports use batches of 32; a failed import can leave prior batches
stored and can be rerun. Results include passage text, source URI, source/version/
chunk IDs, title, kind, and fusion score. A score is not a legal confidence measure.

Python integration: `KnowledgeRag().search(query)` returns `list[SearchHit]`.
The existing stored-output workflow remains independent. System 1 owns any future
HTTP route exposing retrieval; no shared case contracts were changed.

Validation: `.venv/bin/python -m unittest discover -s tests -p test_rag.py`.
Tests use in-memory Qdrant and deterministic embedding doubles.

References: [Qdrant hybrid retrieval](https://qdrant.tech/documentation/search-tuning/hybrid-search/)
and [OpenAI embeddings](https://developers.openai.com/api/docs/guides/embeddings).
