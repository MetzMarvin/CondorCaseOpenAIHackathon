# Condor Care Hub · Out of The Dark

An English-language React/Vite service console and Condor-inspired presentation demo by **Out of The Dark** for the **OpenAI Codex Enterprise Hackathon**. A replaceable FastAPI service simulates Systems 1 and 2. All cases, AI decisions, customer messages, integrations and payments are synthetic. No model access is required. This is not an official Condor product.

## Start locally

Requirements for the standalone console mock: Python 3.9+ and Node.js 22.12+. The shared backend and data pipeline below require Python 3.11+ (including ISO timestamps ending in `Z`). Tested with Python 3.9.6 and Node 26.12.0. Run from `CondorCaseOpenAIHackathon/`.

Terminal 1 — mock backend:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r demo_backend/requirements.txt
uvicorn demo_backend.app:app --host 127.0.0.1 --port 8000
```

Terminal 2 — frontend:

```sh
cd frontend
npm ci
npm run dev
```

Open the [demo](http://127.0.0.1:5173/), [interactive API documentation](http://127.0.0.1:8000/docs) or [OpenAPI schema](http://127.0.0.1:8000/openapi.json). Stop each server with Ctrl+C.

The backend automatically creates `demo_backend/demo.sqlite` and seeds six cases. Set `DEMO_DB=/absolute/path/demo.sqlite` to use another database. Synthetic uploads are stored in `demo_backend/attachments/`. **Reset demos** replaces mock cases, commands and events with the six initial cases. Previously uploaded files remain locally but are no longer referenced.

## Open the app for a presentation

Complete the one-time installation under **Start locally** first. On presentation day, open two terminals in `CondorCaseOpenAIHackathon/` and leave both running:

Terminal 1 — start the mock backend:

```sh
.venv/bin/uvicorn demo_backend.app:app --host 127.0.0.1 --port 8000
```

Terminal 2 — start the presentation frontend:

```sh
cd frontend
npm run dev -- --port 5173 --strictPort
```

1. Open [http://127.0.0.1:5173/](http://127.0.0.1:5173/) in your presentation browser. If either server reports that its port is occupied, check whether the app is already running before starting another copy.
2. Choose the **Presentation** tab. The presentation identifies **Out of The Dark** at the **OpenAI Codex Enterprise Hackathon**.
3. Set **Format** to **16:9** for a standard widescreen projector. Choose **Fullscreen** where supported; press Esc to leave fullscreen. Use **16:10** or **4:3** if that matches the display.
4. For a fresh rehearsal, click **Reset demos**. This replaces the local mock case progress with the six starting cases. If the button is hidden, use the default mock backend and set `VITE_DEMO_CONTROLS=true` in `frontend/.env.local`, then restart Vite.
5. Select a **DEMO SCENARIO**, then click **Start demo**. Use **Replay history** for a completed case, or pause and step through individual events while explaining the flow.
6. For the human handoff scenario, switch to **Service console**, choose **Take over case**, then **Send reply & resolve**. Return to **Presentation** to replay the resulting history.

All customer data, AI decisions, email deliveries and payments are simulated. The visualizer replays recorded workflow events after synchronous processing; it is not live AI streaming. Keep both terminals running throughout the presentation and stop them with Ctrl+C afterwards.

## Presentation scenarios

Select a scenario, then **Start demo**. Processing is synchronous. The animation is explicitly labelled **replay of recorded events**, not live AI streaming. Current backend status is separate from the historical playback step.

- **01 Automatically resolved:** automatically simulates resending a booking confirmation.
- **02 The evidence loop:** asks for a booking reference; the presentation control simulates an `ABC123` reply and resolves the same case. To demonstrate each action manually, use **Start AI processing**, then **Submit reply & assess** in the service console.
- **03 A human takes over:** hands off with `SERIOUS_ISSUE`. In the console, choose **Take over case**, edit the human reply, then **Send reply & resolve**.
- **04 Frustrated, but solvable:** negative sentiment alone does not trigger a handoff.
- **05 Recognising limits:** hands off with `UNSUPPORTED_ACTION`.
- A sixth standard case is available in the case list. **Simulate new demo message** creates and processes an additional clear service case.

Presentation supports fixed **16:9**, **16:10** and **4:3** aspect ratios, scaled to the browser window. Pause replay, step backwards/forwards, scrub events or select playback speed. **Fullscreen** uses the browser fullscreen API where supported. Replay alone does not change data. The header and footer identify **Out of The Dark**.

## Integrate with other subsystems

`demo_backend/` is a replaceable integration mock. Its decisions are fixed examples, not text classification. New messages without a case ID use the clear-case scenario. The missing booking reference is satisfied only by the agreed `ABC123` demo reply. Files are stored and linked without OCR.

To connect System 1, create `frontend/.env.local` and restart Vite:

```dotenv
API_PROXY_TARGET=http://127.0.0.1:8001
VITE_DEMO_CONTROLS=false
```

The browser calls only `/api/*`; Vite proxies those requests to System 1. The mock reset control is hidden. The other backend must support the fixture IDs and fields below, or the API adapter/scenario selector must be adapted. API failures do not silently fall back to mock data.

| Endpoint | Response / required fields |
| --- | --- |
| `GET /api/cases` | Case array with `id`, `subject`, `status`, `owner.type`, `priority`, `nextAction` |
| `GET /api/cases/{id}` | Case with `caseVersion`, `queue`, `messages`, `attachments`, `facts`, `sourceReferences`, `runResults`, optional `handoff` |
| `POST /api/inbound/messages` | Case object; use `caseId` for replies and `messageId` for idempotency |
| `POST /api/cases/{id}/process` | `{case, runResult, appliedAction}`; request `{requestId, expectedCaseVersion}` |
| `POST /api/cases/{id}/takeover` | Case object; request `{actionId, expectedCaseVersion, operatorId: "demo-agent"}` |
| `POST /api/cases/{id}/actions` | `{case, executionResult}`; mock supports human `RESOLVE` with no financial positions |
| `GET /api/events?caseId=…&after=…` | `{events, cursor}` with shared sequence and step IDs |
| `POST /api/cases/{id}/attachments` | Multipart `file`, maximum 2 MB; returns `AttachmentRef` |
| `GET /api/cases/{id}/attachments/{attachmentId}` | Case-scoped download |
| `POST /api/demo/reset` | Mock-only extension, outside the shared contract |

Request and case models are in `demo_backend/app.py` and OpenAPI. Process, takeover, inbound and resolution commands are stored idempotently. Reusing a key with different input, stale versions and ownership conflicts return `409`. The mock serializes short transactions. Uploads do not yet have idempotency keys; reset is a repeatable mock administration action.

Financial actions, live models and general human information-request/handoff forms are not implemented. System 2 results are deterministic fixtures; the mock does not yet implement the shared `process_case(RunRequest, emit_progress)` adapter. The actual shared models and processor are now available in `backend/`; see System 2 integration below. System 1 owns that integration. The console never calls System 2 directly.

## Checks

From the project root:

```sh
.venv/bin/python -m unittest demo_backend.test_api
cd frontend
npm test
npm run build
```

Backend tests use a temporary SQLite database and cover core flows, idempotency, ownership/version conflicts, sentiment-independent resolution, event cursors and attachment scope. Frontend tests cover HTTP processing, human ownership and replay without mutations.

See the [verification record](docs/planning/demo-verification.md), [task checklist](docs/planning/service-operations-tdd-tasks.md) and [shared contracts](docs/architecture/subsystems-and-contracts.md).

## Shared backend and data work

The following components were merged from the other workstreams. The console setup above and the shared-backend setup below are separate until integration is completed.

## Start working

Use Python 3.11+ for the shared backend and pipeline. If `.venv` was created with an older Python for the console, use a separate environment for these checks.

```sh
python3 -m venv .venv
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

Shared Pydantic contracts are defined; System 2 has an offline processor; System 1 route wiring remains to be implemented. Deterministic System 2 snapshots and recorded outputs are included. Remaining integration work:

1. **Case service:** FastAPI routes, SQLite persistence, case state, validated actions and events.
2. **AI service:** connect the implemented processor to System 1 snapshots and event persistence.
3. **Demo console:** connect the existing React console and presentation to the shared System 1 contracts; its local mock is already runnable.

Integrate complete → resolve, missing evidence → clarify → resolve, and serious case → handover before expanding scope. Follow [the subsystem contracts](docs/architecture/subsystems-and-contracts.md) where older plans differ. The React console and its standalone FastAPI mock are available as documented above. Wiring the shared contracts and System 2 into System 1 remains separate integration work; the data explorer is a review tool.

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
changes case state or reads arbitrary attachment paths. The FastAPI routes in `demo_backend/` and React application in `frontend/` currently use a standalone mock contract. They are not yet wired to this shared processor.

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
