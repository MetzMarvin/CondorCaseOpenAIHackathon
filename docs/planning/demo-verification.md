# System 3 — Demo verification

Implemented 30 October 2026. The service under `demo_backend/` is a deterministic integration stand-in for Systems 1/2; the production subsystem integration has not been tested.

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
