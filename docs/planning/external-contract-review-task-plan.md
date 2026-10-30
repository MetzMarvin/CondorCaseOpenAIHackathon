# External contract review and integration task plan

Date: 30 October 2026 · Team: **Out of The Dark** · **OpenAI Codex Enterprise Hackathon**

## Verdict and scope

**No: the external contracts are not yet fully fulfilled or verified.** System 3 demonstrates the core flows against its own deterministic mock. That is a useful working example, but does not establish compatibility with the actual System 1 and System 2 implementations.

Reviewed the [shared contracts](../architecture/subsystems-and-contracts.md), [original simplified TDD plan](service-operations-tdd-tasks.md), current frontend, mock API, and their tests. The only backend implementation found in this checkout is `demo_backend/`. Findings below concern this checkout; they are not claims about code maintained elsewhere by the other teams. A second reviewer independently examined the mock's Contract 1 boundary and guarantees.

No implementation fixes were made during this review. All tasks below are pending. Priorities: **P0** before claiming integration compatibility; **P1** before the final demo rehearsal; **P2** after core integration works.

## Contract coverage

| Boundary / guarantee | Current evidence | Assessment |
| --- | --- | --- |
| System 3 → System 1 only | All business requests use `/api`; no direct AI or database access from React | Fulfilled structurally |
| List/detail, inbound, process, takeover, resolve, attachments | Routes and controls exist; happy paths pass local tests | Partially fulfilled; response shapes are local assumptions |
| Shared Pydantic source of truth | Request models exist, but nested records are mostly dictionaries; process/action/event response schemas are empty in OpenAPI | Incomplete |
| System 1 ↔ System 2 synchronous contract | No `process_case(RunRequest, emit_progress)` entry point or shared snapshot model | Not implemented in the stand-in; actual integration unverified |
| Three core business outcomes | Fixture resolution, information request/reply and reasoned handoff work | Verified against mock only |
| Versions and command idempotency | Process, inbound, takeover and human resolution use stored command IDs; stale requests rejected | Partial: upload not idempotent; pending-run takeover not tested |
| Failure visibility and recovery | UI has HTTP errors; mock only produces successful runs | Incomplete for typed failed runs and retry continuations |
| Shared event feed and replay | Backend emits ordered events; UI reads the feed and labels replay | Partial: no cursor consumption, deduplication or failure-aware graph |
| Integration with teammates' services | Proxy target is configurable | Not exercised; no actual external service/schema was available in this checkout |

## Findings with implementation evidence

### F1 — Shared models and AI adapter are missing (P0; Systems 1 and 2)

`demo_backend/app.py:37–84` defines local request models and a loosely typed `Case`. `process()` at line 165 makes and applies fixture decisions directly, then constructs a proposed action at line 187. There is no `RunRequest`, `CaseSnapshot`, callback or independent validation of an AI proposal. The returned assessment contains only `nextActionExplanation`, `missingFacts` and `sentiment`; required issues, severity and supporting references are absent.

This is an acknowledged stand-in limitation. Replacing it requires coordination with Systems 1/2, not business logic in React. Financial positions also remain untyped, and the mock rejects every nonempty human financial action; permitted financial execution is not demonstrated.

### F2 — Response shapes and fixture IDs are assumed rather than verified (P0; all teams)

`frontend/src/App.jsx:5,33,40–44` hard-codes scenario IDs, initially selects `case-clear`, and loads list/detail/events in one `Promise.all`. If a teammate's service has different IDs, or an empty list, the failed initial detail request prevents the list from being displayed. A failure in the event feed also blocks otherwise valid case detail. The UI assumes string facts, nested owner objects and specific response envelopes without agreed schema validation.

`demo_backend/app.py:143,164,200` lacks typed response models for events, process and actions. Runtime inspection confirmed their OpenAPI 200-response schemas are `{}`. Exact envelopes remain an agreement gap: the prose contract does not fully specify them, so differing shapes should not automatically be called backend bugs.

### F3 — Evidence and inbound metadata do not survive the full flow (P0; Systems 3 and 1)

`frontend/src/App.jsx:58–60` always submits `attachmentIds: []`. `upload()` at lines 68–70 ignores the returned `AttachmentRef`; uploaded evidence is never explicitly associated with the subsequent message. The original TDD task 4 required upload first, then submit the returned ID.

`demo_backend/app.py:100–101,150–162` validates supplied attachment IDs but discards those IDs, sender and channel when persisting the message. A runtime probe confirmed only body, direction, message ID, simulation flag and timestamp survive. The case retains uploaded files, but an external AI snapshot cannot recover which message supplied them from these records.

### F4 — Failed runs and retry continuations are incomplete (P0; Systems 1–3)

The mock always returns `SUCCEEDED` at `demo_backend/app.py:187`; exceptions in `mutate()` roll back without a retained failed run or `run.failed` event. System 3's `process()` at `frontend/src/App.jsx:57` consumes only `result.case`, ignoring `runResult.status` and technical errors.

`command()` and `perform()` at lines 49–55 retain only the last failed HTTP call. If inbound submission succeeds but its response is lost, retrying that call can recover the case, but does not resume the intended `/process` continuation. The new-case control also loses its selection continuation in that situation. A successful command followed by a failed refresh has a different recovery requirement and must not be blindly repeated.

`frontend/src/api.js:5–9` parses JSON before checking HTTP status; a non-JSON error response loses its original status and message. These are inspection findings, not failure-injection tests performed in this review.

### F5 — Upload commands are not idempotent (P1; Systems 1 and 3)

`demo_backend/app.py:213–219` accepts no command key and creates a new file, attachment ID and version increment on every upload. The browser supplies no key either. The shared common behavior requires idempotency on mutations, while the upload table does not specify how to carry that key. Agree the header/form field first. Treat `/api/demo/reset` separately as a documented mock-only administration extension, not a requirement for the real Case Service.

### F6 — Takeover-during-processing guarantee is unverified (P0; Systems 1 and 2)

The lock at `demo_backend/app.py:122` covers the entire synchronous operation. The owner/version check happens before fixture execution at lines 167–169. The current test sends new processing requests only **after** takeover; it does not delay a run, accept takeover, then reject that run's stale proposal.

This is a coverage and integration-boundary limitation, not a demonstrated race failure in a teammate's implementation. The real integration needs validation when applying the proposal, after AI computation, without preventing a concurrent takeover from being accepted.

### F7 — Event replay does not implement all feed semantics (P1; System 3)

`frontend/src/App.jsx:40–44` ignores the returned cursor and replaces the event list with a fresh full response. There is no explicit ordering/deduplication, paging or cursor reset logic. Full-feed replay works with this small mock, but the original TDD task 6's cursor/dedup checks are missing.

`Flow()` at lines 23–28 treats any encountered step as visited regardless of started/completed/failed type. The fallback explanation at line 38 says an action was applied even for an unrecognised `run.failed` event with no step. That can misrepresent failure during replay. Live polling is optional because recorded replay is allowed; failure-aware rendering is not optional.

### F8 — Useful handoff and case information is not fully displayed (P1; System 3)

The detail renderer in `frontend/src/App.jsx:77` shows handoff reason, summary, questions and prior attempts, but not the handoff's own facts/evidence references or suggested queue. It separately shows case facts and attachments, which is not equivalent to identifying the evidence used by the handoff. `missingInformation` and run assessments/results are not rendered explicitly. Category and queue are also absent from the case-list summaries.

### F9 — Original plan and tests overstate neither integration nor coverage, but leave gaps (P1/P2)

The three frontend tests in `frontend/src/App.test.jsx` cover a clear case, human-owner button disabling and replay without mutation. They do not cover evidence upload/reply, handoff completion, missing IDs, failed reads, conflicts or transient retries. Seven backend tests cover mock happy paths and selected guards; they do not establish real System 2 compatibility or takeover during an active run.

The original TDD plan still contains German example labels despite the current English-only guidance. New tests/tasks must use current English UI labels. Advanced filters, extra human action forms and financial UI were intentionally deferred; do not promote them to P0 without a concrete agreed demo requirement.

## Ordered simplified TDD tasks

Each task: write one focused failing behavior/contract test, implement the smallest change, then run relevant existing checks. Do not build workers, authentication or another decision engine.

### T1 — Freeze the actual interchange schemas and fixtures

- [ ] **Priority/owners:** P0 · System 1 leads, Systems 2/3 review. Maps to original task 1. Suggested timebox: 20 minutes.
- [ ] Obtain System 1's actual Pydantic/OpenAPI definitions and System 2's function signature. Record which are implemented versus proposed.
- [ ] **Red:** validate three shared request/result/event fixtures against those models; reject incomplete assessments and invalid action payloads.
- [ ] **Green:** use shared typed models and explicit HTTP response envelopes; align case/operator/source IDs and field names. Define source versions and financial position types, even if demo positions are empty.
- [ ] **Done:** all teams use the same fixtures; OpenAPI describes process/action/event responses; no unresolved required fields.

### T2 — Connect the real synchronous AI boundary and action validator

- [ ] **Priority/owners:** P0 · Systems 1 and 2; System 3 consumes results. Depends on T1. Timebox: 30 minutes.
- [ ] **Red:** fake `process_case` receives a complete versioned snapshot and emits progress; its typed proposal is validated before mutation. A delayed proposal is rejected after takeover without sending a reply or financial action.
- [ ] **Green:** wire the actual adapter (or a contract-compatible fake), assemble snapshots, recheck owner/version/authority at application, and record results. Keep synchronous requests; allow reads/takeover while computation runs.
- [ ] **Done:** three actions pass through the same validator; stale results cannot apply. System 2 performs no direct case writes or customer sends.

### T3 — Make the console boot against System 1's cases

- [ ] **Priority/owner:** P0 · System 3. Depends on T1. Maps to original tasks 1–2. Timebox: 15 minutes.
- [ ] **Red:** a list with an ID other than `case-clear` loads; an empty list has an empty state; event-feed failure does not hide readable case detail.
- [ ] **Green:** load the case list first, choose a valid case, configure scenario mappings from agreed fixtures, and isolate optional activity loading. Normalize schema differences only in the API adapter.
- [ ] **Done:** switching `API_PROXY_TARGET` is sufficient for the agreed backend; no hidden dependency on mock-only reset or invented IDs.

### T4 — Link uploaded evidence to the correct inbound message

- [ ] **Priority/owners:** P0 for message linkage; P1 for upload retry · Systems 3 and 1. Depends on T1/T3. Maps to original task 4. Timebox: 20 minutes.
- [ ] **Red:** upload → reply includes the returned attachment ID; persisted message retains sender, channel and attachment references; subsequent snapshot contains the same evidence.
- [ ] **Green:** retain pending upload refs per case, submit them with the reply and clear only after successful acceptance. Preserve metadata in System 1. An upload failure stops the dependent submission.
- [ ] Add the agreed upload idempotency key; retrying an identical upload creates one attachment/version change. Reject cross-case references.
- [ ] **Done:** a genuine synthetic file, not only the `ABC123` text shortcut, travels through the agreed integration path on the same case.

### T5 — Preserve failed runs and recover interrupted commands

- [ ] **Priority/owners:** P0 · System 1 records failures; System 3 presents/recovers; System 2 supplies typed errors. Depends on T1–T3. Maps to original tasks 3, 5 and 7. Timebox: 25 minutes.
- [ ] **Red:** failed AI run stays unresolved with a visible technical error and manual takeover available. A lost inbound response can be retried with the same key, then continues processing exactly once.
- [ ] **Green:** persist failed results/events, render failure status, and retain the logical workflow continuation with the original command payload/key. Handle refresh-only failures separately. Preserve HTTP status even for non-JSON errors.
- [ ] **Done:** no false success, duplicate inbound message or automatic blind retry after `409`; fresh state is loaded after conflicts. Human ownership prevents automatic continuation.

### T6 — Make history and presentation faithfully reflect events

- [ ] **Priority/owner:** P1 · System 3; System 1 supplies agreed event fixtures. Depends on T1/T5. Maps to original task 6. Timebox: 15 minutes.
- [ ] **Red:** overlapping pages render each event once in sequence order; switching cases resets cursor/history; failed events do not display completion or an applied-action explanation.
- [ ] **Green:** consume cursor, deduplicate by event ID, order by sequence, clamp playback position after refresh, and distinguish started/completed/failed events.
- [ ] **Done:** replay remains explicitly labelled, uses only recorded activity and never modifies authoritative case state. Live polling remains optional.

### T7 — Complete the minimal operator context and align documentation

- [ ] **Priority/owner:** P1 · System 3. Depends on T1. Maps to original tasks 2 and 5. Timebox: 15 minutes.
- [ ] **Red:** a handoff fixture shows reason, destination, facts, linked evidence, questions and prior attempts; missing facts and failed-run context are visible.
- [ ] **Green:** render the existing contract fields without adding business decisions. Show category/queue in list summaries. Replace remaining German examples in the original task plan with current English labels.
- [ ] **Done:** a colleague can understand and handle the case without reading raw JSON. Extra action forms and advanced filters remain P2 unless agreed otherwise.

### T8 — Run the shared end-to-end acceptance gate

- [ ] **Priority/owners:** P0 release gate · all three owners. Depends on T1–T7. Maps to original task 8. Reserve the final 30 minutes exclusively for rehearsal and fixes.
- [ ] Run React against the actual System 1 service connected to System 2 stored outputs; keep model credentials absent.
- [ ] Exercise clear → automatic reply/resolution; missing evidence → upload/reply → same-case resolution; serious/unsupported → contextual handoff → takeover → human resolution.
- [ ] Verify duplicate commands, interrupted retries, failed run/manual recovery, and delayed AI result after accepted takeover. Check persistence after reload and case counts from the agreed seed.
- [ ] Record exact commands, service revisions, click paths and outcomes. A mock-only pass must be labelled as such. Carry unresolved blockers explicitly rather than marking the contracts complete.

Timeboxes total approximately 170 minutes including rehearsal and assume the three owners can work in parallel where dependencies permit. If less time remains, prioritize T1–T5 and the T8 gate; defer presentation polish and nonessential operator display enhancements, while keeping failures and handoff reasons visible.

## Review verification actually performed

- Read shared contract, original task plan, implementation and tests; independent read-only backend review by a subagent.
- `.venv/bin/python -m unittest demo_backend.test_api`: **7 passed**.
- `npm test` in `frontend/`: **3 passed**.
- Isolated temporary-database probes confirmed persisted inbound message field loss, incomplete assessment fields, and empty OpenAPI schemas for event/process/action responses.
- No requests were sent to teammates' services. No concurrency/failure injection or new browser rehearsal was performed during this review. Existing passing tests do not resolve the findings above.
