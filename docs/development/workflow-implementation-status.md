# Knowledge and evidence workflow implementation status

Status: 2026-10-30. This ledger describes the isolated System 2 implementation,
not completion of the application or legal validation. All accepted policy,
receipt, CRM and operational examples are synthetic. Expected outcomes and
simulated future replies remain in tests/evaluation, outside approved knowledge
and model input. English content follows root `AGENTS.md`; existing `_de`
contract fields are unchanged.

| Ticket | Local status | Implemented boundary / remaining owner work |
|---|---|---|
| KA01 | System 2 complete | Evidence requirements, strict scoped read contracts, fake readers and unavailable defaults. System 1 must implement and authorize actual readers. |
| KA02 | Owner integration pending | System 1 owns matching, case-authorized CRM records and ambiguity handling. Synthetic found/not-found/ambiguous results test consumption only. |
| KA03 | Owner integration pending | System 1 owns operational sources and authoritative freshness. System 2 consumes sourced current results; internal gaps/failures never become customer questions. |
| KA04 | Owner integration pending | System 1 owns opaque reference resolution, authorization, byte/media limits and actual attachment storage. System 2 rejects scope mismatches and consumes verified reader results. |
| KA05 | System 2 complete | Labelled receipt extraction, provenance and conflict preservation; text, optional text-PDF, injectable OCR. Real OCR and representative documents remain external inputs. |
| KA06 | System 2 complete | Versioned local registry, content hashes, approval/applicability metadata and synthetic policy v2. Real legal/company approval remains unavailable. |
| KA07 | System 2 complete | Filtered deterministic retrieval with mandatory prerequisites/exceptions, conflicts and explicit failures. No vector service needed for the synthetic corpus. |
| KA08 | System 2 complete | Read-only preparation, source authority, partial replies, focused questions, internal failures and concrete handoffs. |
| KA09 | System 2 complete | Configured synchronous processing, bounded model context, exact supported policy/template validation and no live-to-offline fallback. Fake-model tests cover invalid citations/drafts/provider errors. |
| KA10 | System 2 fixtures complete; execution pending | System 1 owns actual reply intake, current-version/owner validation, idempotency, action execution and case mutation. No execution-level takeover race or duplicate-effects result is claimed. |
| KA11 | Diagnostics integration in progress | Safe manifest generation is being integrated separately. System 1 remains responsible for durable storage, case-scoped access and retention. |
| KA12 | Owner integration pending | System 3 owns evidence/source display through System 1; this work does not change the console. |
| KA13 | System 2 offline coverage complete; E2E pending | Public-entry acceptance covers three flows and evidence/retrieval failures without network or model access. System 1 execution and System 3 display checks remain owner dependencies. |

## Public factory setup

Install the existing backend requirements in a virtual environment, then select
offline mode explicitly. `AI_MODE=auto` can select live mode when credentials
exist, so it is inappropriate for a guaranteed offline run.

```sh
python -m pip install -r requirements.txt
AI_MODE=offline OPENAI_API_KEY= python -m backend.ai_service
```

The default `backend.ai_service.service.process_case(request, emit_progress)`
consumes System 1's supplied snapshot facts. System 1 can bind authorized readers
once and retain the same synchronous two-argument calling convention:

```python
from backend.ai_service.evidence import create_evidence_adapters
from backend.ai_service.service import create_processor
from backend.ai_service.settings import Settings

processor = create_processor(
    settings=Settings(mode='offline', api_key=''),
    adapters=create_evidence_adapters(
        crm=crm_reader, operational=operational_reader,
        attachments=attachment_reader,
    ),
)
result = processor(request, emit_progress)
```

The reader variables above are System 1 implementations of the contracts in
[`evidence.py`](../../backend/ai_service/evidence.py), or explicit synthetic fake
readers for tests. Omitted required readers fail rather than inventing records.
The factory also accepts `extractor` and `retriever`; a custom registry is bound
with `lambda query: retrieve(query, registry_loader)`. Loading an approved card
does not implement additional entitlement logic: only the reviewed synthetic
expense policy supports automatic resolution. See
[`PROCESSING.md`](../../backend/ai_service/PROCESSING.md).

Text receipts need no extraction extra. For text-PDF parsing install
`python -m pip install -r requirements-extraction.txt` (`pypdf>=5,<7`). Missing
PDF support produces `PDF_ADAPTER_UNCONFIGURED`; scanned PDFs/images require an
injected OCR adapter. `FakeOCR` returns labelled synthetic output and does not
interpret images. No production OCR provider is included.

## Checks actually performed

Run from the checkout root, using its Python environment:

```sh
AI_MODE=offline OPENAI_API_KEY= python -m unittest discover -s tests -p 'test_offline_acceptance.py' -v
AI_MODE=offline OPENAI_API_KEY= python -m unittest discover -s tests -v
```

At integration base `25ee3d9` plus KA13 changes, the focused command passed all
8 tests. The full suite ran 107 tests successfully, with one skip because the
optional `pypdf` package was not installed. This does not claim actual PDF parsing
was exercised in that environment. No dependency installation or live provider
call was performed for these checks.

The focused suite forbids socket connections and OpenAI client construction and
asserts no attempts occurred, including attempts caught as workflow failures.
It runs the existing 19-scenario behavioral catalog through both
`service.process_case` and `create_processor`, checking proposals, remaining
fields, reason codes, amounts, identities, source versions, unchanged snapshots
and repeatability. Additional cases cover fake CRM unique/no/ambiguous matches,
operational outage, prior payment, partial extraction/reply, conflicting receipts,
cross-case references, malicious document instructions and expired/absent policy.
These regression tests passed against the existing integrated behavior; no new
production behavior was required to make them pass.

The full suite also covers fake-model refusal, invalid output, altered money,
execution claims, omitted questions, incorrect source versions/passages and
context overflow. Network guards apply to the focused acceptance suite; the
other model tests inject fake providers. All financial outputs remain proposals:
no sends, payments or case mutations are implemented by System 2. Deterministic
repeatability is not proof of System 1 execution idempotency.
