# Condor Care Hub · Out of The Dark

Hackathon demo with an English React/Vite service console and process replay. The customer view belongs to System 1; System 3 provides Dashboard & Service and Process view only. System 1 owns FastAPI/SQLite state and simulated effects; System 2 supplies structured decisions; System 3 displays the outcome and recorded workflow. All demo labels and messages use English. All data, messages and financial actions are synthetic.

System 1 now includes synchronous claim preparation; see **Claim preparation queue** below
for configuration, retry endpoints and the boundary with System 2.

Local airline-complaint mocks for the Condor AI Week hackathon.

## Current integration boundary

The operations console (`/`, `demo_backend.app:app`) and customer portal
(`/portal`, `backend.main:app`) currently require their respective backend.
Vite uses one `API_PROXY_TARGET` for all `/api` requests. Switching that target
switches the backend for the entire frontend; it does not connect the two stores.
The default launcher starts only the operations backend. Portal intake requires
the separate startup instructions under **Local intake application** below.
Do not point both backends at the same SQLite file: their table schemas differ.

## Start locally

From the **repository root** (`CondorCaseOpenAIHackathon/`), run:

```sh
./start.sh
```

The parent workspace also provides a `start.sh` wrapper for the same command.

This starts both servers, installs missing dependencies, initializes the database
on first use, and prints the demo URL. Requires Python 3.13 for initial environment
creation and Node.js 22.12+. Existing case progress is preserved. Press **Ctrl+C**
to stop both servers. To avoid occupied ports, use
`BACKEND_PORT=8002 FRONTEND_PORT=5174 ./start.sh`.

The launcher defaults to `AI_MODE=openai`; use `AI_MODE=offline ./start.sh` for
an explicit deterministic demo. Put `OPENAI_API_KEY` in the project `.env` or shell
environment. Missing credentials, invalid output and provider failures remain failed
runs without business proposals. The legacy `AI_FALLBACK_OFFLINE` flag is ignored.
The existing `OPENAI_TIMEOUT_SECONDS` setting applies to each live expert call.
The launcher makes no paid startup probe and does not reset demo data.

### Manual startup

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

The separate intake/preparation backend in `backend/main.py` is not connected to that operations demo. Its customer portal and stored evidence use a different database and inbound contract. Unifying those implementations remains integration work.

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

### Simulated email delivery

`backend.email_delivery` sends generated drafts to a persistent SQLite outbox.
Delivery is explicitly simulated; no SMTP connection or external email is sent.
It consumes `questionDe` for follow-ups and `replyDe` for resolutions, preserving
generated subjects and bodies. Plain offline messages get a case-reference subject.
Internal handoff summaries cannot be sent. Repeating an action ID returns the
original delivery, including its timestamp; changing its content or recipient is
rejected, including after a process restart.

System 1 calls this adapter **after** validating the action's current case version,
ownership, state, permitted actions and financial authority. Supply the recipient
from the trusted case contact. This adapter only records delivery; it does not
apply case transitions, execute payments or publish process events. Those steps
still belong to the case service, whose routes are not implemented in this checkout.

```python
from backend.email_delivery import SimulatedEmailSender

sender = SimulatedEmailSender('email-outbox.sqlite3')
# authorized_action is a validated RequestInformation or Resolve action.
delivery = sender.send_authorized(authorized_action, 'customer@example.test')
```

For a local preview, save a successful `RunResult` as a single JSON object and run:

```sh
.venv/bin/python -m backend.email_delivery --result /tmp/generated-result.json --to customer@example.test
```

The command prints the simulated delivery and stores it in `email-outbox.sqlite3`
(ignored by Git). Use `--database /tmp/demo-outbox.sqlite3` to choose another file.
The preview command does not authorize or apply the proposal to a live case.
Run delivery checks with
`.venv/bin/python -m unittest discover -s tests -p 'test_email_delivery.py' -v`.

### AI processor

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
failure returns a failed run. Select `AI_MODE=offline` explicitly when a deterministic
simulation is wanted; live failures are never converted into business outcomes.
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

## Optional legal and policy RAG

For the downloaded legal corpus, set your own `OPENAI_API_KEY` in `.env`, then run:

```sh
bash scripts/setup-legal-rag.sh
QDRANT_COLLECTION=legal_research .venv/bin/python -m backend.ai_service.rag search 'flight delay compensation'
```

This loads the manifest-selected sources into a separate research collection.
See the [team setup instructions](docs/development/knowledge-rag.md#team-quick-start-with-the-downloaded-legal-corpus)
for prerequisites and the required shared data files.

Start the persistent local Qdrant database and initialize its empty collection:

```sh
.venv/bin/python -m pip install -r requirements-rag.txt
docker compose -f compose.rag.yaml up -d
.venv/bin/python -m backend.ai_service.rag init
```

The [Qdrant dashboard](http://localhost:6335/dashboard) runs on port 6335.
Retrieval combines BM25 and OpenAI `text-embedding-3-small` with RRF fusion.
See [the RAG guide](docs/development/knowledge-rag.md) for later document imports,
search commands, configuration, and System 2 integration boundaries.

## Local intake application

The customer-only portal saves claims, customer updates and attachments through
one FastAPI intake service. Email simulation and staff response workflows belong to
the separate service, not this frontend. The UI, fixtures and errors are in English.
Intake **does not invoke System 2 or generate replies**. Existing AI work remains
available independently. Seeded service messages are explicitly labeled stored examples.

### Setup and startup

Run from the repository root, containing `AGENTS.md`, `backend` and `frontend`.
Requires Python 3.12+ and Node.js 22.12+. Tested with Python 3.14 and Node.js 24.11.
Internet is needed for dependency installation; the installed demo needs no model
access, API keys, real mailbox, payment provider or other external service.

Terminal 1 (Windows / PowerShell):

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r backend/requirements-lock.txt
./.venv/Scripts/python.exe -m backend.seed
./.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The lockfile includes tested runtime and test dependencies. Direct dependencies
are listed in `backend/requirements.txt` and `backend/requirements-dev.txt`.
On macOS/Linux, use `.venv/bin/python` in place of `./.venv/Scripts/python.exe`.

Terminal 2:

```powershell
cd frontend
npm ci
npm run dev
```

Open the [customer portal](http://127.0.0.1:5173/portal).
The former `/email` and `/demo/cases` screens are removed. Existing case links at
`/portal/cases/{caseId}` continue to show customer-visible correspondence.
Vite forwards `/api` to FastAPI on port 8000. Keep both processes running;
stop them with `Ctrl+C`. [OpenAPI schemas](http://127.0.0.1:8000/docs) describe the intake routes.

### Persistence and demo data

Startup creates the SQLite tables and adds missing fixtures. The seed command can
also initialize them without starting the server. Existing cases and replies are
never reset by startup or reseeding.

- SQLite: `data/care-hub.sqlite3`; local uploaded files: `data/attachments/`.
- Set `CONDOR_DATA_DIR` before backend startup to use a different local folder.
  For a fresh demo, choose a new empty directory, for example
  `$env:CONDOR_DATA_DIR = "$PWD/data-demo-2"`. Earlier German fixture copies are
  not overwritten; use a fresh directory for the English examples.
- Local runtime data, uploads, environments and frontend build outputs are ignored
  by Git. The existing pinned data-pipeline inputs remain tracked.
- Demo links have no authentication. Use synthetic data on localhost only.

| Case | Initial scenario |
|---|---|
| `case-clear` | Complete flight-delay claim, newly received |
| `case-evidence` | Hotel expenses, with a stored request for evidence |
| `case-serious` | Serious incident, prepared as a specialist-routing example |
| `case-incomplete` | Missing baggage with limited details; no intake-driven handoff |
| `case-human` | Human-owned case awaiting a customer reply |
| `case-resolved` | Resolved example that can reopen on a new message |

Stable intake fixtures are in `backend/fixtures.py`. Expected actions are fixture
metadata, not executed decisions. They are separate from System 2's sourced expense
snapshots; evidence extraction and snapshot assembly remain future integration work.

### Customer walkthrough

1. Submit a fictional email address, subject and message through the portal. Open
   the receipt link and verify the case is **Received**.
2. Keep the case link to view the customer-visible status and correspondence.
3. Add a customer update or upload `backend/demo-files/hotel-receipt.png` through
   that case page. The message and file stay on the same case.

For local fixture checks, open `/portal/cases/case-evidence` directly. There is no
global case picker or operator navigation in the customer portal. Staff responses
are displayed when supplied by the service, never composed here.

Design: [frontend guidelines](docs/architecture/frontend-design-guidelines.md).
The portal component and scoped styles are in `frontend/src/portal/` to keep them
separate from the team's operations-console frontend.

### Intake interfaces

`POST /api/inbound/messages` accepts JSON or multipart with one JSON text field
called `metadata` and repeated file fields called `files`.

```json
{
  "messageId": "msg-demo-unique-001",
  "channel": "PORTAL",
  "sender": "demo@example.com",
  "subject": "Hotel expenses",
  "body": "Here is the receipt for my overnight stay.",
  "caseId": "case-evidence"
}
```

New claims omit `caseId`. Email replies additionally require `inReplyTo`, such as
`msg-case-evidence-out`. No matching by subject, sender, name or booking takes place.
Original submitted text is preserved. Unknown fields, client filesystem paths and
arbitrary attachment IDs are rejected.

Receipts contain `messageId`, `caseId`, `caseVersion` and `customerCaseUrl`.
Identical retries return the original receipt; changed content, including file
contents, returns `409`. The mounted form retains text, files and the retry ID after
failure. Drafts do not persist across navigation or reloads.

| Implemented route | Purpose |
|---|---|
| `GET /api/health` | Local demo status |
| `POST /api/inbound/messages` | Shared intake, including atomic message uploads |
| `GET /api/cases?status=…&queue=…&owner=…` | Shared `CaseSummary` records, including `owner` object and `version` |
| `GET /api/portal/cases/{caseId}` | Customer-visible status, messages and attachments only |
| `GET /api/cases/{caseId}/attachments/{attachmentId}` | Download a customer-visible attachment belonging to that case |
| `GET /api/events?caseId=…&after=…` | Shared `EventPage`; up to 200 ordered records and a continuation cursor |

Intake request/receipt and portal projections live in `backend/intake_contracts.py`.
They inherit the shared `Contract` conventions (Python snake_case, JSON camelCase).
Case summaries, statuses and events reuse `backend/contracts.py` directly. The older
`InboundMessageRequest` is a planning-era shape; this implemented route uses the
stricter `InboundMessage` with subject, explicit reply references and message-scoped uploads.

Uploads accept five PDF/JPEG/PNG files, up to 10 MiB each (shown as 10 MB in the UI).
Content is parsed to reject damaged, encrypted or incorrectly labeled files.
Storage names are generated IDs; display filenames do not control filesystem paths.
There is no OCR or document extraction.

Database records and events commit together. On failure, the transaction rolls back
and newly written files are removed. SQLite serializes writes, including duplicate
checks. A hard process termination during file writing can leave an unreferenced
local file; crash recovery and production upload hardening are deferred.

Every valid, nonempty reply is treated as relevant in this slice. It reopens
`WAITING_FOR_CUSTOMER`, `RESOLVED` and `CLOSED` as `IN_PROGRESS`. Ownership and queue
are preserved; `WAITING_FOR_SPECIALIST` remains unchanged. No automatic action follows.

Not wired into intake: AI processing, `/process`, `/takeover`, `/actions`, the full
internal case-detail API, separate attachment uploads, Salesforce context and graph views.
See the [subsystem agreement](docs/architecture/subsystems-and-contracts.md).

### Checks

```powershell
./.venv/Scripts/python.exe -m pytest backend/tests tests -q
cd frontend
npm run build
```

Backend checks use temporary databases and exercise both channels, cross-channel
replies, ownership, customer visibility, content/size limits, concurrent duplicates,
failed writes, event cursors and restart persistence. The frontend build is written
to `frontend/dist`; `npm run preview` serves it on port 4173 with the backend running.


## Claim preparation queue (System 1)

Install `backend/requirements-lock.txt` and run the existing FastAPI server. Startup
adds the preparation tables without resetting existing data. Intake commits a pending
entry with the message, then prepares it synchronously. The intake receipt stays unchanged.
Ten seed cases now include Sophie, an unmatched customer, ambiguous journeys and conflicting IDs.
Seed cases start pending: use the explicit prepare endpoint to inspect them.

Configuration is shown in `.env.example`. The server loads root `.env` without overriding
process environment variables. Default `CONDOR_PREPARATION_MODE=offline` makes no model calls.
Set it to `live` and set `CONDOR_EXTRACTION_MODEL` to a vision/structured-output-capable
OpenAI model to enable extraction with `OPENAI_API_KEY`. Credentials never reach React.
Calls have a 30-second timeout and no SDK retries. A case with many scanned pages can
therefore take longer than 30 seconds; processing remains synchronous for this demo.

- `GET /api/preparation/queue`: inspect persisted preparation entries.
- `GET /api/cases/{caseId}/preparation`: inspect the current version.
- `POST /api/cases/{caseId}/prepare`: JSON `{"requestId":"retry-1","expectedCaseVersion":1}`.
  Repeating a completed request returns its original result. Use a new ID for a new attempt.
  Startup returns interrupted attempts to pending; retry explicitly. Run one backend process.

Queue states are PENDING, PREPARING, READY, READY_WITH_ERRORS and SUPERSEDED.
Replies supersede older versions. Preparation never changes ownership, business status,
financial authority, or case version. Failed extraction/enrichment preserves original
messages and recovered text in READY_WITH_ERRORS. Unmatched records are not missing-evidence
judgments. Progress uses the common event feed's extract_evidence step.

PDFs use embedded text first, then local rendering and vision transcription. Partial or
unreadable pages have explicit diagnostics. No raw PDFs or resolvable original attachment
references go to System 2; originals remain available through customer download routes.
Offline outputs are content-addressed and versioned, with no fabricated fallback for unknown
inputs. `backend/demo-files/preparation-receipt.png` has a stored transcription for offline demos.

`PreparationService.run_request` constructs the shared RunRequest only for a current,
AI-owned IN_PROGRESS case. Authority is supplied by trusted System 1 orchestration and
otherwise defaults to none. Issues/missing_information remain unassessed. System 2 must
add topic extraction before consuming these snapshots for real decisions; preparation does
not invoke it, send replies, or execute actions. Its present empty-topic handoff is not an
end-to-end integration. The Salesforce adapter uses only synthetic read-only fixtures.

Run `python -m pytest backend/tests -q` and `python -m unittest discover -s tests -q`.
Automated preparation tests use offline or mocked model responses, not live credentials.
