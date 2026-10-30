# Integrated demo — verification

## Integrated update — 30 October 2026

The project `.venv` was replaced with Python **3.13.16** (minimum supported version
3.11). The previous Python 3.9 environment remains in ignored
`.venv-python39-backup/`. Both AGENTS.md files now require Python 3.11+;
`.python-version` selects 3.13.

System 1 now calls the actual shared System 2 processor. React consumes shared
CaseDetail/ProcessResponse/EventPage contracts and offers dashboard, service,
customer and recorded-process perspectives. All sends and payments remain local
simulations. The interface and demo messages now use English only, following the latest user instruction.

### Checks performed after integration

- `.venv/bin/python --version`: Python 3.13.16.
- `.venv/bin/python -m pip check`: no broken requirements.
- `.venv/bin/python -m unittest discover -s tests -v`: **51 passed**.
- `.venv/bin/python -m unittest demo_backend.test_api -v`: **11 passed**.
  Includes shared processor invocation, same-case evidence loop, payment
  idempotency, partial evidence, technical failure recovery, and a blocking fake
  processor test proving concurrent human takeover prevents stale AI effects.
- `npm test`: **10 passed** across App, CustomerView and API adapter tests.
- `npm run build`: production bundle built successfully.
- `git diff --check`: no whitespace errors.
- Browser rehearsal on isolated FastAPI port 8002 / Vite port 5174, with
  `AI_MODE=offline` and `/tmp/condor-integrated-python313.sqlite`:
  - clear case resolved automatically with System 2's expense reply;
  - evidence case requested receipt amount/currency; customer perspective showed
    the same `case-evidence`; synthetic receipt uploaded and `42.00 EUR` reply
    produced four messages, resolved status, attachment link and confirmed
    simulated reimbursement of 42 EUR; dashboard counts updated;
  - serious case produced `SERIOUS_ISSUE` context; human takeover disabled AI;
    personal reply resolved the case retaining HUMAN ownership;
  - after browser reload, the same evidence case retained all four messages,
    its attachment, resolved status and accepted 42 EUR reimbursement.

No live model/provider calls, real email, real payments, Salesforce, OCR or
production authentication were exercised. Existing old servers on ports 8000/5173
were left running; start/restart the documented backend with the new interpreter
before using those ports. Historical standalone checks below describe the prior
booking-confirmation mock, not the current integrated fixture story.

## Historical standalone implementation

## Performed checks

- Backend: `.venv/bin/python -m unittest demo_backend.test_api` — 7 tests passed.
- Frontend: `npm test` — 3 tests passed.
- Frontend: `npm run build` — production bundle built successfully.
- Dependency installation after updating Vitest reported 0 vulnerabilities.
- Browser: clear case → automatic resolution; UI displays `RESOLVED` and recorded events.
- Browser: evidence demo → question → simulated `ABC123` reply → resolution on `case-evidence`; console displays all four messages and six total seeded cases.
- Browser: serious case → `SERIOUS_ISSUE` handoff → human takeover → human response → resolved with human ownership.
- Presentation: visually inspected the default 16:9 stage with English explanation cards and replay controls.
- Browser sizing: checked 16:9 at 1280×720 and 1920×1080, and 4:3 at 1024×768. DOM measurements confirmed stage content height equals its fixed height and the footer remains inside the stage. The 16:10 option is implemented but was not separately browser-checked.

## Limits

No live AI, real email, financial actions, OCR, authentication or deployment was tested or implemented. The mock uses stored decisions; the three flows run without model credentials. Browser tests use the local mock, not teammates' services. Fullscreen availability depends on the embedding browser.

English-language update: translated UI, accessible labels, API messages, seeded cases and stored outputs; existing local records translated without resetting case progress. Presentation identifies the team as **Out of The Dark**.

## English-only update

Following the user's language correction, dashboard/service, customer and process
labels, error text, default human replies and currency formatting use English.
Both AGENTS.md files require English. The known previous German default human
reply in the isolated demo database and cached command response was translated
without resetting case progress. Frontend tests: 10 passed; backend integration
tests: 11 passed. Production build passed. Browser inspection confirmed English
dashboard and customer labels.
