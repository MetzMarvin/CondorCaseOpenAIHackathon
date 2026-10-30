# Draft policy research

The customer-service policy pack on `main` contains 49 draft rule records. Prepare
and import it explicitly for research, using the same backend dependencies and
Qdrant service as [legal retrieval](knowledge-rag.md):

```sh
.venv/bin/python -m backend.ai_service.policy_research --allow-draft
QDRANT_COLLECTION=policy_research .venv/bin/python -m backend.ai_service.rag ingest data/processed/policy-research.jsonl
QDRANT_COLLECTION=policy_research .venv/bin/python -m backend.ai_service.rag search 'flight delay compensation' --kind policy
```

Preparation is offline. Import/search call OpenAI for embeddings. The importer
checks each record's content hash, duplicate IDs, and presence of mandatory/related
rules in the release. The full original record is retained in
`policy_provenance.source_record`, including policy version, draft status, legal
profile, jurisdiction scope, mandatory rule IDs, sources and decision tables.
`policy_provenance.runtime_enabled` stays false. Existing legal-page payloads remain
compatible. This does not validate the legal accuracy of the draft.

System 2 can build research queries from a supplied snapshot:

```python
from backend.ai_service.policy_research import research_case
from backend.ai_service.rag import KnowledgeRag

rag = KnowledgeRag(collection='policy_research')
try:
    research = research_case(request.snapshot, rag)
finally:
    rag.client.close()
```

Queries use a fixed vocabulary selected by recognized case issues. Names, booking
references, raw email text, attachment text and arbitrary fact values never enter
the query. The returned hits retain source/version/chunk citations. The same helper
can query `legal_research`; no documents or case records are changed.

These are research candidates, not an applicability-filtered decision context.
The helper explicitly reports `applicability_checked: false` and
`mandatory_support_expanded: false`. No workflow is wired to consume these records.
Before using them for decisions, implement approval/date/regime filtering and exact
version dependency expansion through the approved retrieval interface. A similarity
score alone never establishes entitlement or overrides the synthetic demo policy.
