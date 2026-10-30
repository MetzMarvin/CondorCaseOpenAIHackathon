# System 3: Service Operations & Live Demo Console — TDD subtasks

Implementation checklist for the owner of **System 3**, based on [subsystems and contracts](../architecture/subsystems-and-contracts.md). This was written before implementation. The shared-contract integration, dashboard and customer perspective now exist; see the [startup and integration guide](../../README.md) and [performed checks](demo-verification.md). The original checklist below remains available for reviewing remaining integration work; unchecked items are not a claim that every feature is absent.

## Target and working assumptions

Build one React/JavaScript/Vite screen with a case list and selected case detail. Use English UI text and a persistent “Demo – AI, email and payments simulated” label. System 1 owns business state and validation; the console only submits commands and displays responses.

**First working milestone:** select a fixture case, inspect its messages, trigger processing, and see the returned resolution and simulated reply. Then extend the same screen for missing evidence and human handover.

Assume a three-hour implementation window: 150 minutes of implementation/integration, followed by 30 minutes of demo checks and fixes. Timeboxes are targets, not estimates of guaranteed completion. Start against recorded JSON fixtures; connect to System 1 as soon as its endpoints are available. Fixture mode is a development aid; the integrated demo must use System 1 with stored AI outputs and no model credentials.

## Simplified TDD loop

For each behavior: write one failing user-facing test, implement the smallest change that passes, then remove obvious duplication. Test visible outcomes and submitted HTTP commands, not component internals, CSS, or snapshots. Keep tests from earlier tasks passing.

Use Vitest, React Testing Library and jsdom for the small frontend suite. Stub `fetch` with deterministic JSON responses at the HTTP boundary; avoid building a second business engine in the browser. Use the same API client in fixture tests and integration. Only add test dependencies when starting implementation.

Suggested structure: `frontend/src/api.js`, `frontend/src/App.jsx`, `frontend/src/App.test.jsx` and `frontend/src/test/fixtures/`. Split components only when helpful. Shared Pydantic schemas remain the source of truth.

## Ordered subtasks

### 1. Agree fixtures and establish a passing test harness — 15 min

- [ ] Coordinate with System 1 on exact response envelopes, field names, demo operator ID, allowed human actions and the existing-case reference used for replies. The contract document does not yet define all JSON shapes.
- [ ] Reuse three agreed deterministic cases: clear, missing evidence, and serious/unsupported. Record before/after responses, versions, sources and events using shared IDs. Mark any temporary local fixture shapes as provisional until checked against Pydantic/OpenAPI.
- [ ] **Red:** render the app against a stubbed `GET /api/cases` and expect the English heading and one returned subject.
- [ ] **Green:** create the Vite app, a thin API client and the smallest list rendering.
- [ ] **Done:** the frontend starts and one behavior test passes. Document the actual start/test commands as they become available.

Dependency: agreement with System 1; temporary fixtures allow progress while its implementation is pending. The three fixtures are the test subset of the eventual 6–10 seeded demo cases.

### 2. Read a case from the list — 25 min

- [ ] **Red:** clicking a case fetches its detail and shows its subject, English status, owner and messages. Selecting another case replaces those details.
- [ ] **Green:** implement list/detail on one screen, showing summary category, queue, priority and next action where supplied. Detail shows facts, missing information, source references and attachment links from System 1.
- [ ] Add a small test for loading and failed reads: “Loading …” and a useful error with “Reload”. An empty list shows “No cases available”.
- [ ] **Done:** select cases reliably; a failed load never displays a different case's details as the selected case. Attachment links use the case-scoped API route.

Dependency: task 1. Basic display first; advanced filtering can wait.

### 3. Complete the clear-case flow — 25 min

- [ ] **Red:** “Start AI processing” sends exactly one `POST /api/cases/{caseId}/process` with `requestId` and the latest `expectedCaseVersion`; its response changes the visible status to “Resolved” and shows the simulated outgoing reply.
- [ ] **Green:** disable processing while pending, consume the returned case and refresh the list/detail as needed. Do not infer successful resolution from a click or a progress event.
- [ ] Use a clear but angry fixture to verify that the UI still displays the returned automatic resolution. The console must not derive a handoff from sentiment.
- [ ] **Done — first working milestone:** list → detail → process → resolved case and reply, without a human approval step. Start trying this against System 1 now if available.

Dependency: task 2. Backend decides and executes the outcome; the frontend test proves correct display and request sequencing.

### 4. Add minimal intake and the missing-evidence loop — 30 min

- [ ] **Red:** submitting a new simulated message calls `POST /api/inbound/messages`, selects the returned case, then calls `/process` exactly once with the returned version.
- [ ] **Green:** add a small prefilled demo-message control. Keep sender/channel fixed to agreed fixtures; allow editing the body.
- [ ] **Red:** the missing-evidence case shows “Waiting for customer” and the outgoing question. “Simulate customer reply” sends a new `messageId` with the existing case/thread reference, then processes that same case once with its updated version. The final response shows “Resolved”, both customer messages and the reply.
- [ ] **Green:** add a prefilled reply control and synthetic evidence upload to the existing case. Upload first through `POST /api/cases/{caseId}/attachments`, then include the returned attachment ID in the inbound message. Use a shared tiny local demo file; do not send filesystem paths.
- [ ] **Done:** evidence remains attached to the same case; no duplicate case or implicit second processing run. Missing evidence alone never causes a UI-created handoff. A failed upload preserves the draft and stops the subsequent submission.

Dependency: task 3 plus agreed inbound/upload responses. For a human-owned case, submit the reply but do not automatically call `/process`.

### 5. Show a handoff and complete human handling — 25 min

- [ ] **Red:** a serious/unsupported case displays “With specialists”, the returned reason, queue, summary, facts, evidence, unresolved questions and prior attempts.
- [ ] **Green:** render the handoff context directly from the case/run response.
- [ ] **Red:** “Take over case” sends `actionId`, current `expectedCaseVersion` and the fixed demo operator ID to `/takeover`; the returned owner is human. An edited English reply submitted via `/actions` with a new action ID and current version displays the returned human resolution.
- [ ] **Green:** add takeover and one minimal human `RESOLVE` form using an agreed permitted outcome and the shared action envelope. Include required explanation/source/financial fields from the contract; never invent authority or financial limits in the UI.
- [ ] **Done:** handoff → takeover → human reply/resolution works. Automatic processing controls are disabled for human-owned cases; only returned authoritative state updates ownership and status.

Dependency: task 3 and System 1's supported demo role/action payload. General reassignment and extra human action forms can follow later.

### 6. Display trustworthy activity history — 15 min

- [ ] **Red:** the selected case's `GET /api/events?caseId=…` response renders ordered event summaries once; a repeated page creates no duplicate entries. Switching cases clears the previous case's history and cursor.
- [ ] **Green:** add a plain timeline, ordered by `sequence` and deduplicated by `eventId`; pass the returned cursor as `after` on subsequent reads. Fetch on selection and after actions, including failed runs.
- [ ] **Done:** action history, handover and run failures are visible. Events do not independently overwrite case status or ownership. Post-run history is sufficient for this milestone; any later animation of stored events must say “Replay”.

Dependency: tasks 3–5 and System 1 event fixtures. Live polling during a synchronous request and a process graph are optional extensions.

### 7. Protect the demo from duplicate clicks and stale state — 15 min

- [ ] **Red:** double-clicking an action while pending sends one command; retrying a temporary failure reuses the original idempotency key and identical payload. A new logical submission gets a new key.
- [ ] **Red:** a `409` displays the safe conflict message and reloads current case state; it does not blindly replay the rejected mutation. After a takeover conflict, the UI shows the returned human owner and disables automated processing.
- [ ] **Green:** centralize pending/error handling and keep failed command payloads for deliberate retries. Distinguish retryable transport/server failures from conflicts and invalid input. Show useful `422`/`404` messages and retain editable drafts.
- [ ] **Done:** a failed run or rejected action never looks like a successful resolution. Manual takeover remains available when permitted by the refreshed state.

Dependency: existing mutation controls. System 1 owns server-side deduplication and rejection of stale AI actions; frontend tests do not prove those backend guarantees.

### 8. Integrate, rehearse and document — final 30 min

- [ ] Switch from test fixtures to System 1 HTTP endpoints; fix contract mismatches rather than adding business rules to the frontend.
- [ ] Run the focused frontend suite and production build. Record actual commands and outcomes, including any failures or blocked checks.
- [ ] Rehearse all three flows against the integrated FastAPI app with stored AI outputs and no model access: automatic resolution; evidence request/upload/reply on the same case; reasoned handoff/takeover/human resolution.
- [ ] Check duplicate submission and stale AI result after takeover together with the System 1 owner; verify one simulated send/payment and the authoritative human owner. Check technical failure leaves the case visible and manually recoverable.
- [ ] Confirm the list shows the agreed 6–10 seeded cases, English labels and simulation indicators. Reload the page to confirm persisted state comes back from System 1.
- [ ] Update the project README with actual frontend setup/start/test/build commands, API connection configuration and the three demo click paths. Coordinate backend setup, database initialization, seed/reset instructions and stored-output mode with System 1; do not invent a reset endpoint.
- [ ] **Done:** demo rehearsed from a documented initial database state, actual check results recorded, remaining limitations explicit.

## Scope cuts if time runs short

Keep all three core flows, basic loading/errors, human takeover and visible history. Defer process graphs, animated replay, metrics, advanced filters, a document previewer (attachment links suffice), polished styling and extra human action forms. Freeze new features at minute 150 and use the remaining time for integration and fixes.

## Verification record

The original planning change did not execute application tests. Subsequent implementation results are recorded separately in the [demo verification record](demo-verification.md).
