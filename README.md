# Condor Care Hub · Out of The Dark

Hackathon demo with an English React/Vite service console and process replay. The customer view belongs to System 1; System 3 provides Dashboard & Service and Process view only. System 1 owns FastAPI/SQLite state and simulated effects; System 2 supplies structured decisions; System 3 displays the outcome and recorded workflow. All demo labels and messages use English. All data, messages and financial actions are synthetic.

## Start locally

Use **Python 3.11 or newer** and Node.js 22.12+. The project environment now uses **Python 3.13.16**; `.python-version` selects 3.13. Do not use macOS system Python 3.9. Run these commands from `CondorCaseOpenAIHackathon/`:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r demo_backend/requirements.txt
.venv/bin/python --version
cd frontend
npm ci
```

The previous local environment is preserved in the ignored `.venv-python39-backup/`; all normal commands use `.venv/`.

Terminal 1, from the project root:

```sh
AI_MODE=offline .venv/bin/uvicorn demo_backend.app:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```sh
cd frontend
npm run dev -- --port 5173 --strictPort
```

Open [the demo](http://127.0.0.1:5173/) and [the API documentation](http://127.0.0.1:8000/docs). Stop and restart an existing backend after upgrading Python; a running Python 3.9 process does not change interpreter when `.venv` is replaced.

## Data and integration

The [Customer Service Operator Policy](docs/policies/customer-service/README.md) provides an English, RAG-ready policy draft for calls and email. It includes legal source references, structured rules, decision tables and message templates. It requires legal and business review before production use. The demo does not load this package automatically.

The backend creates `demo_backend/demo.sqlite` and six synthetic cases on a fresh database. `DEMO_DB=/absolute/path/demo.sqlite` selects an isolated database. Attachments are local under `demo_backend/attachments/`; no OCR is performed. Use the explicit demo reset control only when you want to replace demo case progress. Old uploaded files may remain locally after a reset.

Older booking-confirmation mock records are preserved. They return `409 LEGACY_DEMO_DATA` with an explicit reset instruction instead of being silently overwritten. Use a new `DEMO_DB` path to keep those records and start an integrated rehearsal, or deliberately use **Reset demo** to replace them with the six expense scenarios.

The common Pydantic contracts in `backend/contracts.py` are authoritative: JSON uses `caseId`, `version` and nested `snapshot` fields. `frontend/src/api.js` adapts display fields without making business decisions. The System 3 console calls only System 1 over `/api/*`. The standalone customer component remains available for System 1 and is not mounted in the System 3 console. System 1 invokes System 2 synchronously, records progress, validates ownership/version/authority, and persists accepted actions and simulated financial effects. Repeated command IDs with the same payload return the original response; conflicting payloads or stale versions return 409.

The demo scenarios use a meal expense of **42.00 EUR**. The incomplete case asks for receipt amount and currency; the prepared reply `42.00 EUR` supplies those facts on the same case. This is deterministic demo evidence extraction, not general text understanding or receipt parsing. Internal eligibility and previous-payment checks are synthetic sourced records owned by System 1; customers cannot grant financial authority.

For another compatible System 1 backend, set `API_PROXY_TARGET=http://127.0.0.1:8001` in `frontend/.env.local` and restart Vite. Set `VITE_DEMO_CONTROLS=false` to hide the local reset extension. API errors never silently switch to mock data.

## Four-minute pitch

1. **0:00–0:25:** show dashboard case counts and explain the shared case.
2. **0:25–1:10:** select the evidence scenario, start assessment in the console, and use **Simulate customer reply** with `42.00 EUR`, then **Submit reply & assess** (optionally add a synthetic receipt).
3. **1:10–2:20:** return to the same case in the service console. Show evidence, sources, accepted resolution and simulated reimbursement; replay a short part of the recorded workflow.
4. **2:20–2:45:** show the service reply and resolved status in the console message history. Use System 1 for the customer-facing view.
5. **2:45–3:35:** select the serious scenario, process it, show the specific handoff reason and context, then demonstrate human takeover.
6. **3:35–4:00:** return to dashboard counts and explain the benefit.

Also rehearse the complete clear-case → automatic reply path and handoff → takeover → human resolution path. Missing evidence and negative sentiment alone do not trigger handoff. Recorded-event animation is labelled replay; it is not live model streaming. Prepare/reset the demo before presenting, and keep both servers running.

## Checks

```sh
.venv/bin/python -m pip check
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m unittest demo_backend.test_api -v
cd frontend
npm test
npm run build
```

Backend tests use temporary databases. See [the verification record](docs/planning/demo-verification.md) for checks actually performed and limits. Real email, payments, Salesforce, authentication and OCR remain outside this mockup.

## Shared backend and data work

The shared backend, AI workflow and console use the same Python environment and contracts. The data explorer below remains an independent review tool.

## Start working

Use the Python 3.11+ project `.venv` for the shared backend and pipeline; the installed local interpreter is Python 3.13.16.

```sh
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Set OPENAI_API_KEY in .env to enable live experts.
.venv/bin/python -m backend.ai_service
.venv/bin/python -m unittest discover -s tests -v
```

| Path | Purpose |
|---|---|
| `backend/contracts.py` | Shared executable Pydantic contracts |
| `backend/ai_service/` | System 2 processor, snapshots and recorded outputs |
| `tests/` | Contract, AI flow and data pipeline checks |
| `pipeline/`, `config/` | Existing synthetic data generator |
| `data/` | Pinned source data, review fixtures and read-only prototype |
| `docs/architecture/` | Current subsystem agreement and contract maps |
| `docs/planning/`, `contracts/workflow.ts` | Planning and earlier interface exploration |

[Open the module visualization](docs/architecture/module-contracts.html) or read
[the executable contract guide](docs/architecture/module-contracts.md).

## Current work and next steps

| Area | What exists | Status |
|---|---|---|
| Data pipeline | Pinned source snapshot, deterministic DE/EN generator, PDF/PNG evidence, validation and tests | Runnable locally |
| Review fixtures | 30 mixed complaints and 13 baggage cases, including held-back replies/uploads | Included in `data/examples/` |
| Complaint explorer | Three read-only views and a recorded missing-evidence walkthrough | [Throwaway prototype](data/complaint-explorer.prototype/README.md) |
| Application architecture | Three subsystem owners, demo endpoints and event contracts | [Current implementation guide](docs/architecture/subsystems-and-contracts.md) |
| Shared Python contracts | Pydantic action, AI, HTTP and event models; synchronous AI protocol | [Contract map and setup](docs/architecture/module-contracts.md) |
| Earlier interface exploration | Detailed workflow contract and interactive ownership map | Design references; not implemented application code |

The demo integration connects the shared AI processor to the FastAPI case service and the React console. Continue to use the subsystem ownership and contracts when adding features. Broader dataset tooling and the complaint explorer are review utilities, not dependencies of the six-case pitch.

## Preview the existing work

```sh
python3 data/complaint-explorer.prototype/serve.py --data data/examples/baggage
```

Open http://localhost:8787/?variant=B for the baggage evidence walkthrough.

## Build the complaint fixtures

Python 3.11+; no packages or API keys required. The pinned τ² source snapshot is included.

```sh
python3 -m pipeline normalize
python3 -m pipeline build
python3 -m pipeline validate
python3 -m unittest discover -s tests -p 'test_pipeline.py' -v
```

This creates 3,000 DE/EN synthetic complaints in `data/processed/complaints/`.
A smaller review set is included at `data/examples/complaints/`.
Edit `config/complaints.json` and `config/wording.json` to change scenarios and wording.
Give the application only the generated `runtime/` folder; keep `evaluation/` for tests.

Upstream data: Sierra Research τ²-bench (MIT), pinned in `data/source-lock.json`.
Generated expectations describe a demo workflow and have not been legally reviewed.

## System 2 integration

Install `requirements.txt` in a virtual environment, then run
`python -m backend.ai_service` for the included contract flows (three API calls per
successful case in live mode).
The backend reads the repository-root `.env` automatically; shell variables take
precedence. Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY`. No key is
committed or sent to the frontend. `AI_MODE=auto` enables OpenAI when a key is
present; `AI_MODE=openai` requires a key; `AI_MODE=offline` explicitly runs the
deterministic demo without API access. `OPENAI_MODEL` and the per-call
`OPENAI_TIMEOUT_SECONDS` are configurable. Restart any hosting backend after editing.

Live processing calls OpenAI for evidence review, policy review, and assessment/
customer wording through the Responses API with typed structured outputs. Code
retains the approved synthetic policy, permitted action, IDs, source references
and financial positions. Expert disagreement, refusal, invalid output or API
failure returns a failed run; it never silently falls back to a simulated decision.
Live results/events have `simulation=false`; downstream sending and payments
remain simulated and owned by System 1. Legacy `questionDe`/`replyDe` contract
field names remain compatible, while live wording is English per project guidance.
Attachments are sent as metadata only; extracting their contents still requires
System 1's case-scoped evidence adapter. Live experts do not expand the approved
demo entitlement rules or independently execute actions.

When live processing returns `REQUEST_INFORMATION`, the third expert automatically
generates a customer follow-up email. It includes a case-reference subject, an
empathetic opening, one question per outstanding fact, reply instructions and a
signature. Missing, extra or duplicate question IDs fail validation. The complete
plain-text draft (including its `Subject:` line) is returned in the existing
`proposedAction.payload.questionDe` field, so no shared contract changes are needed.
`request_information` progress events indicate draft generation, not delivery.
System 1 must validate and record/send the simulated outbound message and retain
the case/thread association. Specialist `HANDOFF` actions do not generate customer
follow-up emails. Offline mode retains the reviewed deterministic question body.

A synthetic email generated during a live smoke test is saved in
[`backend/ai_service/customer_email_example.txt`](backend/ai_service/customer_email_example.txt)
for review without model access. No email was sent during that test.

The integration follows the official
[OpenAI structured output guide](https://developers.openai.com/api/docs/guides/structured-outputs).
Run `python -m unittest discover -s tests -p 'test_ai_service.py' -v` to check the
processor boundary. Recorded results and progress are in
`backend/ai_service/stored_outputs.jsonl` for replay without model access.

System 1 imports the real entry point:

```python
from backend.ai_service import process_case

# request: shared RunRequest assembled by System 1 from its current case.
# record_progress: System 1 callback that persists shared ProgressUpdate values.
result = process_case(request, record_progress)
```

The processor resolves synthetic `expense_reimbursement` claims with sourced
`receipt_amount_minor`, `receipt_currency` and `expense_purpose` facts, a sourced
internal eligibility/reimbursement-history check, and sufficient financial authority.
The policy is a demo fixture, not real entitlement advice. A receipt alone never
establishes eligibility. Flight delay/cancellation, denied boarding, baggage
delay/damage/loss and service complaints support evidence collection, then hand
off to a specialist for adjudication outside the demo reimbursement policy.

### Failure modes and customer messages

`backend/ai_service/assessment.py` routes structured facts and issues;
`questions.py` owns the reviewed English message templates. Existing
`questionDe`/`replyDe` wire fields are unchanged. Free-text messages, sentiment
and attachment contents are not interpreted by this deterministic layer.
System 1 must supply extracted facts and structured issues, rather than expect
keyword detection. Source references must resolve to case-scoped evidence.

| Condition | Result |
|---|---|
| Missing/unreadable receipt, unclear amount/currency/purpose, booking, representation, baggage timeline or remedy choice | `REQUEST_INFORMATION`, with targeted, courteous questions |
| Partial customer reply | Keep sourced answers; ask only for outstanding facts, deduplicating stale missing entries |
| Conflicting customer evidence | Ask for clarification first; escalate a sourced, unresolved conflict after clarification |
| Serious injury, safety, discrimination, accessibility failure or credible threat | `HANDOFF` / `SERIOUS_ISSUE` |
| Legal review required or expense eligibility not established by an approved rule | `HANDOFF` / `UNCLEAR_RULE` |
| Amount above authority, approval needed, or required action not permitted | `HANDOFF` / `AUTHORITY_LIMIT`; never reduce entitlement to fit the limit |
| Unsupported action or unrecognized evidence requirement | `HANDOFF` / `UNSUPPORTED_ACTION` |
| Internal evidence unavailable, parser failure, scoped-access violation or callback failure | `FAILED`, without a business proposal |

All handoffs retain the existing `demo-specialists` queue ID and include sources,
facts, unresolved questions and previous AI messages. System 1 may map that queue
to its human routing configuration. No external authority is contacted, and a
handoff summary is internal context, not an outbound customer message.
Missing evidence, anger, silence and message count alone never cause rejection
or handoff. There is no automatic reminder timer or automatic closure on silence.

### Snapshot fact vocabulary for System 1

The following names extend the contents of existing `Fact`/`MissingFact` values;
no shared Pydantic fields, statuses or action types changed. System 1 must populate
these deliberately from its internal checks, never by copying customer claims:

| Sourced fact in `booking_context` or `flight_context` | Meaning |
|---|---|
| `expense_eligibility = "eligible"` | Approved demo eligibility check, including the expense's relationship to the disruption; other values require specialist review |
| `payment_history = "no_prior_reimbursement"` | Internal reconciliation found no previous reimbursement; other values require specialist reconciliation before payment |
| `legal_review_required = true` | Applicable rule/exception needs legal review; optional boolean |
| `conflict_review_status = "unresolved"` | Material evidence still conflicts after clarification; a question-count threshold is insufficient |
| `evidence_access_status` | Optional `available`, `timeout`, `parser_error` or `cross_case_reference`; adapter failures are not customer evidence gaps |
| `policy_status` | Optional `available`; other values indicate unavailable approved policy data |

Absent eligibility/payment checks yield `INTERNAL_EVIDENCE_REQUIRED` once customer
evidence is complete. Enrich the snapshot and start a fresh run; blind retries of
unchanged evidence will not help. Unsourced facts do not satisfy checks, and
customer-facing `known_facts` cannot grant eligibility or set internal controls.
These status facts report adapter outcomes; System 2 itself does not open files
or implement an attachment parser. Duplicate execution and takeover remain System 1 checks.

Customer evidence names and wording are enumerated in `questions.py`; a missing
fact's supplied reason is never copied into an outbound message. Operational
gaps such as `actual_arrival`, `disruption_cause`, `notification_log`,
`payment_history`, `operating_carrier`, `flight_distance`, `legal_regime` and
`reasonable_measures` require internal enrichment, not customer questions.

Ten offline fixtures and recorded outputs cover clear/missing/reply, serious,
unsupported, unreadable receipt, partial reply, legal review, authority and
conflict cases. `missing`, `partial_reply` and `reply` are successive versions of
the same case. Generate the demo with `AI_MODE=offline python -m backend.ai_service`.
Run `python -m unittest discover -s tests -p 'test_ai*.py' -v` for routing and
contract-flow checks. The [research catalogue](docs/research/airline-legal-checks.md)
describes broader legal requirements; no EU261 or Montreal entitlement calculator
is implemented here.

System 1 must create the run, supply an AI-owned IN_PROGRESS snapshot, persist
progress/results, and validate/apply proposals atomically with ownership, version,
idempotency and authority checks. The processor never sends messages, pays money,
changes case state or reads arbitrary attachment paths. The FastAPI routes in `demo_backend/` call this shared processor and expose the common Pydantic HTTP contracts to `frontend/`. Run with `AI_MODE=offline` for deterministic pitch rehearsals.

## Visual workflow review for development

Generate a repeatable offline System 2 report with scenario checks, recorded
progress, proposals, an SVG PR preview and a JSON baseline:

```sh
.venv/bin/python -m backend.ai_service.evaluation --output /tmp/ai-review --open
# After a code change, compare against the saved results:
.venv/bin/python -m backend.ai_service.evaluation --output /tmp/ai-next --baseline /tmp/ai-review/results.json --open
```

See [the workflow evaluation guide](docs/development/workflow-evaluation.md) for
PR artifacts, failure checks, baseline comparison and adding scenarios.
