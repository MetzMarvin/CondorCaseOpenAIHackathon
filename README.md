# Condor Care Hub

Local, synthetic airline-claim demo: customer intake, preparation, a service console,
and validated simulated resolutions. No real email, payment or Salesforce action occurs.

System 1 now runs as **one application**, `backend.main:app`, with one case database.
`demo_backend.app:app` is a compatibility launcher for that same application; it does
not open the old `demo_backend/demo.sqlite` database or import its history.

## Setup and startup

Use Python 3.11+ and Node.js 22.12+. Work from the repository root. On Windows,
replace `.venv/bin/python` with `.venv/Scripts/python.exe` in the commands below.

```sh
python -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-lock.txt
.venv/bin/python -m backend.seed
```

On macOS/Linux, `./start.sh` starts both servers, installs missing dependencies,
initializes the unified database, and prints the demo URL. Its first-time environment
setup uses Python 3.13. Press Ctrl+C to stop both servers. Override occupied ports with
`BACKEND_PORT=8002 FRONTEND_PORT=5174 ./start.sh`.

The launcher defaults the decision stage to `AI_MODE=openai`; extraction follows
`CONDOR_PREPARATION_MODE` from your environment or project `.env`. For an entirely offline
rehearsal, use `AI_MODE=offline CONDOR_PREPARATION_MODE=offline ./start.sh`.
It performs no paid startup probe and never resets existing case progress. Missing
credentials, invalid model output and provider failures remain visible failed runs.

For a deterministic rehearsal, explicitly select both offline modes before starting:

```sh
AI_MODE=offline CONDOR_PREPARATION_MODE=offline .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

PowerShell equivalent:

```powershell
$env:AI_MODE = 'offline'
$env:CONDOR_PREPARATION_MODE = 'offline'
./.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```sh
cd frontend
npm ci
npm run dev -- --port 5173 --strictPort
```

Open the [operations console](http://127.0.0.1:5173/),
[customer portal](http://127.0.0.1:5173/portal), and
[API schema](http://127.0.0.1:8000/docs). Vite proxies `/api` to port 8000;
`API_PROXY_TARGET` can override that destination. Restart the backend after configuration changes.

## Database, migration and fresh demos

The default directory is `data/`: SQLite lives at `data/care-hub.sqlite3` and uploads
at `data/attachments/`. Set `CONDOR_DATA_DIR` to an alternative directory.
Startup creates missing tables and applies the additive schema migration, including
run IDs on events and durable operations records. Existing intake cases, messages,
attachments and progress are retained. Seed initialization adds missing cases only.

The ten-case fixture set includes `case-clear`, `case-evidence`, `case-serious`,
`case-incomplete`, `case-human`, `case-resolved`, `case-sophie`, `case-unmatched`,
`case-ambiguous`, and `case-conflicting`. Fresh core fixtures start at `NEW`.
Existing copies retain their prior state; use a new data directory for a clean rehearsal.

The destructive reset endpoint/control is disabled. For a fresh PowerShell demo:

```powershell
$env:CONDOR_DATA_DIR = "$PWD/data-rehearsal-1"
./.venv/Scripts/python.exe -m backend.seed
./.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Do not delete existing data to reset a demo. Legacy operations history remains in its
original database, untouched and unimported. Run one backend process; workers and brokers
are outside this hackathon implementation.

## Three core flows

1. **Clear claim:** process `case-clear`. A sourced 42.00 EUR hotel-expense fixture
   resolves with a simulated reply and one reimbursement ledger entry.
2. **Evidence loop:** process `case-evidence`; the AI asks for evidence and retains
   ownership. Submit the prepared portal reply `42.00 EUR` on the same case, then
   explicitly process its new version. It resolves without creating a second case.
3. **Serious claim:** process `case-serious`; inspect its reasoned specialist handoff,
   take over as `demo-agent`, then send a human resolution. Human ownership survives replies.

The customer portal displays only customer correspondence and status. Internal assessments,
run diagnostics and operational history remain in the console. Recorded graph animation is
replay, not live model streaming. Both views use the same System 1 cases and attachments.

## API and responsibility boundaries

| Endpoint | Behavior |
|---|---|
| `POST /api/inbound/messages` | JSON or multipart intake; returns `IntakeReceipt` |
| `GET /api/cases` | Shared summaries with owner, version and next action |
| `GET /api/cases/{caseId}` | Internal detail, snapshot, sources, runs and history |
| `GET /api/portal/cases/{caseId}` | Customer-visible case projection |
| `GET /api/cases/{caseId}/attachments/{attachmentId}` | Case-scoped customer-visible file |
| `GET /api/preparation/queue` | Persisted preparation entries |
| `GET /api/cases/{caseId}/preparation` | Current-version preparation |
| `POST /api/cases/{caseId}/prepare` | Explicit preparation retry |
| `POST /api/cases/{caseId}/process` | Synchronous System 2 call and validated effects |
| `POST /api/cases/{caseId}/takeover` | Versioned human ownership change |
| `POST /api/cases/{caseId}/actions` | Validated human action |
| `GET /api/events?caseId=...&after=...` | Ordered, run-linked event feed |

Intake fields are `messageId`, `channel` (`PORTAL` or `EMAIL`), `sender`, `subject`,
`body`, optional `caseId` and `inReplyTo`. EMAIL replies require a parent message.
Multipart uses one JSON `metadata` field and repeated `files` fields. Files are PDF,
JPEG or PNG, at most five files and 10 MiB each. Standalone upload is deferred:
attachments are committed with their message. Original text is preserved.

Intake returns `messageId`, `caseId`, `caseVersion`, and `customerCaseUrl`.
The console fetches case detail after the receipt and explicitly calls `/process`;
intake itself starts preparation but never a decision run. Repeated message IDs with
identical content return the original receipt; changed content conflicts.

Preparation extracts identifiers and factual text, enriches through the read-only
Salesforce mock, and does not assess completeness or entitlement. It uses embedded PDF
text first, then vision transcription. Unreadable pages and lookup failures retain
recovered text with diagnostics. Raw PDF bytes and original file-access references are
excluded from decision snapshots; originals remain downloadable through System 1.

System 2 owns topic interpretation, evidence normalization and assessment. System 1 owns
case mutations, authority checks and delivery/payment simulation. Internal case details
may contain staff attachment links; the processing projection contains extracted text.

Processing uses `requestId` and `expectedCaseVersion`; takeover uses `actionId`,
`expectedCaseVersion` and `operatorId: "demo-agent"`. Human actions use the shared
`ProposedAction` envelope without a run ID. Completed command retries return their
original response. A changed payload, stale version or invalid owner returns `409`.
Errors use `{error: {code, message, currentCaseVersion}}` where applicable.

Case versions increase on business changes. Progress does not increment them.
System 2 runs outside the database write transaction; takeover or a reply can invalidate
its result. Results remain auditable even when stale effects are rejected. Outbound
messages, ledger entries, action records and case changes commit together.
The demo permits up to 10,000 EUR minor units of reimbursement per case; compensation
and goodwill have no configured authority. A previous reimbursement blocks another
payment pending human reconciliation. No authentication or production approval flow is included.

Interrupted processing runs become recoverable failures on restart. Use a new request ID
for a deliberate new assessment; completed failed requests retain their original result.
Reassignment from human ownership back to AI is deferred.

## Model configuration

Root `.env` is backend-only and ignored by Git. Shell variables override saved values.
Preparation and decisions are independently configured:

- `CONDOR_PREPARATION_MODE=offline|live` and `CONDOR_EXTRACTION_MODEL` control extraction.
- `AI_MODE=offline|openai` and `OPENAI_MODEL` control the decision service.
- `OPENAI_API_KEY` supplies live credentials. The preparation configuration selected for
  this workspace is GPT-6.1 Terra; copy settings intentionally when using another worktree.

Use both offline modes for reproducible rehearsals. Stored interpretations cover the core
fixture texts and prepared replies; unfamiliar offline text produces an explicit technical
limitation rather than invented evidence or a financial decision. The offline image fixture
`backend/demo-files/preparation-receipt.png` has a content-addressed transcription.
Live calls require network access and appropriate model access. Simulated business effects
remain local in either mode. Never commit credentials or print them in test output.

## Checks and related material

```sh
.venv/bin/python -m pytest backend/tests demo_backend/test_api.py -q
.venv/bin/python -m unittest discover -s tests -v
cd frontend
npm test
npm run build
```

Pytest forces both model stages offline regardless of developer `.env`; integration tests
use temporary directories. These are check commands, not a claim that all have been run.
Report actual results for each delivery. Preserve 30 minutes for rehearsal and fixes.

See [subsystem contracts](docs/architecture/subsystems-and-contracts.md),
[executable contract guide](docs/architecture/module-contracts.md),
[data generation](data/README.md), and [planning context](docs/planning/hackathon-plan.md).
The [customer-service policy draft](docs/policies/customer-service/README.md) is a separate
review artifact, not automatically loaded demo policy or production legal guidance.


## Optional research and evidence integration

The [System 1 evidence handoff guide](docs/development/system1-evidence-handoff.md)
describes case-scoped evidence expectations for System 2. The
[policy research guide](docs/development/policy-research.md) describes optional legal
research tooling and its boundary from approved demo decisions.

The downloaded legal corpus can be loaded into a separate research collection using
`scripts/setup-legal-rag.sh`. See the [RAG setup guide](docs/development/knowledge-rag.md)
for required shared files, optional `requirements-rag.txt` dependencies, Docker/Qdrant
startup and search commands. Research infrastructure is optional and is not started by
`start.sh`; the three offline demo flows do not require it. These sources are not a grant
of financial authority and do not replace validated System 1 execution.
