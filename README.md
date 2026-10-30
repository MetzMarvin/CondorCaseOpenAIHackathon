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
`python -m backend.ai_service` for five deterministic, simulated contract flows.
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

The processor supports the synthetic `expense_reimbursement` issue with sourced
`receipt_amount_minor` and `receipt_currency` facts, subject to supplied financial
limits. `safety_incident` and `serious_injury` require specialist handling; other
issues are unsupported. The policy is a demo fixture, not real entitlement advice.
The `missing` and `reply` snapshots represent successive versions of the same case;
reply intake and evidence extraction remain System 1 integration responsibilities.

System 1 must create the run, supply an AI-owned IN_PROGRESS snapshot, persist
progress/results, and validate/apply proposals atomically with ownership, version,
idempotency and authority checks. The processor never sends messages, pays money,
changes case state or reads arbitrary attachment paths. The FastAPI routes in `demo_backend/` and React application in `frontend/` currently use a standalone mock contract. They are not yet wired to this shared processor.
