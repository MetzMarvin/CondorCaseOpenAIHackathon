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

## Issue-oriented research search

For a whole complaint, use the optional issue-oriented mode with a 20-passage
budget. Ordinary `search` remains available for focused queries:

```sh
QDRANT_COLLECTION=legal_research .venv/bin/python -m backend.ai_service.rag search \
  'My flight was cancelled due to weather. I paid for a hotel and dinner.' --issues --limit 20
```

Python: `backend.ai_service.legal_search.search_issues(rag, complaint, limit=20)`.
The English keyword planner expands cancellation, flight delay/connections, baggage,
denied boarding, accessibility, downgrade and injury into independent research
queries. These are search leads, not detected legal violations. It retains the
original query and interleaves categories for mixed complaints. Explicitly named
instruments get two source-filtered hits alongside general hybrid results; a
round-robin merge removes duplicate source/version/chunk IDs. This prevents longer
commentaries and judgments from crowding out the underlying provisions. Unknown
wording falls back to the original search. Model/database failures propagate.

This performs multiple sequential embedding/search calls (including targeted source
queries) and therefore costs more and takes longer than a single query. Limits bound
returned passages, not API calls. Returned scores remain per-query fusion scores;
they are neither comparable global rankings nor confidence estimates. Source filters
apply in both dense and sparse candidate retrieval. No collection reindex is needed.

### Measured coverage, 30 October 2026

The live `legal_research` collection was tested at the same 20-passage budget for
both methods. Each check requires a particular source **and a textual passage
anchor**, rather than merely finding the right document:

| Set | Ordinary search | Issue-oriented search |
| --- | --- | --- |
| Six development complaints, 24 checks | 15/24 (62.5%) | 23/24 (95.8%) |
| Four unseen mixed/paraphrased complaints, 23 checks | 10/23 (43.5%) | 21/23 (91.3%) |

Fixtures and recorded source/version/chunk IDs are in
`data/examples/legal-checks/evaluation/retrieval*.json*`. The unseen set was created
and run after the final search change; it was not used for further tuning. Its
checks overlap the development issues, so this is a wording/mixed-topic check,
not independent legal review or a comprehensive coverage estimate. All three
remaining checks concern the absent `icao-limit-revision` source (one issue repeated
across three complaints). They remain in the denominator. Do not infer the current
baggage ceiling from the historical treaty figures returned by this corpus.

The fixtures are synthetic and unreviewed. Passage recall does not establish correct
legal reasoning, event-date applicability, completeness of defenses or safe payout
decisions. Keyword expansion can miss unfamiliar wording. The research results
retain unreviewed provenance and remain separate from the approved-knowledge case
workflow. No System 1/3 contracts, routes or authority rules were changed.

Reproduce the comparisons (requires local Qdrant and embedding access):

```sh
.venv/bin/python -m backend.ai_service.evaluation.legal_retrieval --output /tmp/retrieval.json
.venv/bin/python -m backend.ai_service.evaluation.legal_retrieval \
  --cases data/examples/legal-checks/evaluation/retrieval-holdout.jsonl \
  --output /tmp/retrieval-holdout.json
```

The evaluator explicitly uses `legal_research`, prints coverage and writes the exact
retrieved passage IDs and per-check outcomes. Unit checks use deterministic doubles;
the recorded coverage numbers come from real embeddings and the live collection.
