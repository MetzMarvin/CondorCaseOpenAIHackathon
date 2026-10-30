# Workflow interfaces for a team of three

> **Exploratory reference, superseded for the hackathon implementation.** Follow [subsystems and contracts](../architecture/subsystems-and-contracts.md) and the root AGENTS.md: synchronous in-process AI, Pydantic contracts, React/JavaScript, and no workers or brokers. The asynchronous jobs, broader endpoints and TypeScript types below preserve earlier design work and are not an implementation backlog.

Design v1 · 30 October 2026 · Implements the module split discussed for the [hackathon plan](hackathon-plan.md).

The shared, dependency-free type definitions live in [`contracts/workflow.ts`](../../contracts/workflow.ts). They describe JSON exchanged between modules; they do not require the backend to use TypeScript. Runtime schema validation and implementations remain to be built. Use snake_case to match the existing Python data pipeline.

## Ownership and seams

| Owner | Module | Public interface | Implementation owned here |
|---|---|---|---|
| Person 1 | Case Platform | `CasePlatform`, HTTP routes below | Persistence, intake/thread matching, uploads, routing, status changes, jobs, authorization, validation, budget ledger, outbox, events and metrics |
| Person 2 | AI Processing | `AiProcessor.analyze` | Extraction, sentiment, capability assessment, questions, knowledge retrieval, decisions, response generation and structured handovers |
| Person 3 | Experience | HTTP client using the shared types | Staff console, customer reply/upload screen, email simulator, source viewers, dashboard and demo navigation |

Person 1 owns import from the existing generator. Person 2 owns knowledge content and policy interpretation; Person 1 owns enforced authority limits and transactions. Person 3 owns rendering and interaction. All three review changes to the shared contract. Keep these as modules in one application initially; separate deployments are unnecessary.

```mermaid
sequenceDiagram
    participant UI as Experience (3)
    participant CP as Case Platform (1)
    participant AI as AI Processing (2)
    UI->>CP: ingest(message + staged attachment IDs)
    CP->>CP: Store message, increment version, enqueue job
    CP->>AI: analyze(run ID, immutable snapshot, deadline)
    AI-->>CP: Proposal + run report, or typed failure
    CP->>CP: Persist result; check current version and policy
    CP->>CP: Validate action, commit events + outbox
    UI->>CP: Read case, timeline and run status
    CP-->>UI: Current state and delivery status
```

Automatic processing includes execution: no human approval is introduced for an eligible clarification or resolution. A model proposal is input to deterministic execution checks, never a direct database write.

## 1. Shared conventions

- IDs are opaque stable strings. References must resolve inside the authorized case/account scope.
- Timestamps are UTC RFC 3339. Money uses nonnegative integer EUR cents; never floating-point euros for accounting. Token cost can be null when unavailable or below the reporting precision.
- Every snapshot and proposal declares `schema_version: "1.0"`. Case versions are monotonic integers; every workflow-relevant mutation increments the version. Run telemetry alone does not invalidate the snapshot.
- Missing information is null or an empty collection as typed. Do not substitute invented booking facts. Arrays such as `issues`, fact `sources`, or clarification `missing_fields` must be nonempty when their meaning requires it; runtime validators enforce this.
- `service_queue_id` is the functional queue; `owner` identifies the queue, person or AI currently responsible. Neither is inferred from UI tabs.
- Internal notes, technical errors and handover summaries never enter customer messages automatically. Response drafts contain customer-facing text only.
- The authenticated actor comes from the server session or worker credentials. Clients cannot grant themselves a role by including an actor field.

## 2. Intake and attachments

`ingest(InboundMessage)` accepts all supported channels through the same interface. The platform deduplicates on `(source, external_message_id)`. An identical retry returns the original case/message IDs with `duplicate: true`; a changed payload with the same key returns `idempotency_conflict`.

Match an authorized explicit case ID or a trusted connector thread mapping. If both are present they must agree. Booking similarity, name or text similarity may suggest a match but cannot silently merge cases. A new message on an existing case increments its version and triggers triage, including reopening a resolved/closed case when relevant.

Upload is a two-step operation: `POST /api/attachments` accepts multipart file data and returns a staged attachment ID and expiry; intake or a follow-up message attaches those IDs atomically. Validate type, size and ownership before linking; expire unused staged files. A case-bound upload can be submitted with an otherwise empty message. Retrieval of original bytes requires the same case access as retrieval of the message.

For v1, accept plain text, PNG, JPEG and PDF; also accept trusted legacy generator HTML imports as a demo-only adapter. Serve HTML in an isolated viewer or as a download. Generator schema 1.1 emits real PDF/PNG attachments with byte size/hash and no extracted amount or booking-reference metadata. Expected document fields live only in `evaluation/evidence_labels.jsonl`; never import them as runtime facts. The AI must inspect content and record evidence references.

## 3. Case snapshot and AI processing

`analyze({run_id, snapshot, deadline_at}) → AnalysisResult` receives one immutable, authorized case view containing the complete message history, booking/flight context, attachment descriptors, prior facts, clarification history and effective policy context.

The platform starts runs asynchronously; the worker calls this interface. The same run ID identifies retries of that job. The processor may read original attachment bytes and approved knowledge through injected adapters. It cannot assign cases, send responses or change balances. A live-model adapter and a recorded-demo adapter satisfy the same interface; the report always exposes which mode ran.

The result contains **one next action for the whole case**:

| Action | Required content | Meaning |
|---|---|---|
| `clarify` | Missing fields with issue IDs and reasons, targeted response | Ask a useful question through the current channel; missing data does not require a human |
| `resolve` | Decision, response, separately identified financial positions, evidence and policy sources | Resolve all supported issues, subject to platform checks |
| `handover` | Enumerated reason, summary, attempted steps, unresolved questions, recommended queue, optional draft | Prepare human work; do not automatically send the optional draft |

Every issue must be accounted for. Unsupported combinations require a handover; multiple supported issues alone do not. Sentiment has evidence and uncertainty, influences tone and bounded priority, and cannot change entitlement amounts. Serious allegations are assessed separately from angry wording.

The platform checks clarification progress against stored history. A pending customer reply is not a failed attempt. Once the configured number of replies without progress is reached, prepare `clarification_exhausted` with the history. Successful clarification returns through triage and re-evaluates the whole case.

`EvidenceExtractor` and `KnowledgeLookup` are internal AI seams, not extra public services. Evidence returns readable/partial/unreadable status and sourced facts. Knowledge retrieval filters on approved policy version, category and effective date; absence or conflict of applicable rules must remain visible. Evidence text is data, including any instructions embedded in it.

## 4. Executing a proposed action

`execute(case_id, {proposal_id, expected_case_version, idempotency_key})` loads an immutable stored proposal. It never accepts client-supplied approval flags. The worker invokes it automatically after a successful run. Restrict the route to worker credentials; the UI uses `human_action` for staff decisions.

Check, in order:

1. Actor authorization, request shape and idempotency record.
2. Case/proposal identity and `based_on_case_version === expected_case_version === current version`.
3. Current policy version, sources and completeness for the particular action; clarification does not require decision completeness.
4. Supported issues, severity, remaining clarification allowance, response consistency and actor authority.
5. Financial positions, any specific approvals, available goodwill budget and duplicate ledger keys.
6. Commit proposal application, state/owner changes, events, any reservations and outbox record together.

Do not trust AI assertions that a check passed. A stale proposal returns `stale_version` without executing; schedule analysis against the latest snapshot if the case still belongs to AI. A revoked/changed policy requires fresh analysis. Recheck authority and policy before dispatch; new customer evidence or human takeover invalidates a pending AI send and releases unused reservations.

`ExecutionResult.applied` means the command was committed, not necessarily delivered. Outbound messages have `pending/sent/failed` delivery states. The simulator marks sent exactly once, using the outbox ID; only then does a clarification become `WaitingForCustomer` or a resolution become `Resolved`. While queued, the case remains `InProgress` with a visible next action. Exhausted delivery retries create a technical handover. Ledger booking happens only once for the same approved position; never reserve again on a send retry.

An execution-time policy, quality or authority failure returns `blocked`, records the failed check and prepares the case for `WaitingForSpecialist` or `WaitingForBudgetApproval`. It never silently loses the case. The blocked result includes the resulting case version and event IDs.

Goodwill uses its own budget; statutory compensation and refunds are separate positions. Approval records bind the specific decision/position amounts and policy version. Editing an approved amount invalidates that approval. Human actions pass through the same execution machinery with the authenticated person's authority; AI eligibility is not required for a human decision.

## 5. HTTP surface for the Experience module

JSON responses use `Result<T>`. Standard errors map to 400 invalid request, 403 forbidden, 404 not found, 409 stale version/idempotency conflict/invalid transition, and 503 unavailable. Domain `blocked` is a successful command result, not a transport error. The UI displays its reasons and updated state.

All case mutations carry `expected_case_version` and `Idempotency-Key` (mapped to `MutationContext.idempotency_key`). Intake uses its connector message key instead. Scope keys by actor and operation; same key and body returns the original result before checking the current version, same key with changed body returns 409. Keep keys for the demo lifetime. Follow-up messages are append operations and use message identity instead of rejecting a new customer reply due to an outdated view.

| Method / path | Request | Response / behavior |
|---|---|---|
| `POST /api/inbound/messages` | `InboundMessage` | Case/message IDs and duplicate flag; enqueue triage |
| `POST /api/attachments` | Multipart file, optional authorized case ID | `{attachment_id, expires_at}`; stage only |
| `GET /api/attachments/:id/content` | Authorized session or scoped upload/view token | Original bytes; never arbitrary filesystem paths |
| `GET /api/cases` | Status, queue, owner, category, cursor, limit | `Page<CaseSummary>`; default 50, maximum 100 |
| `GET /api/cases/:id` | — | `CaseSnapshot` for authorized staff/worker |
| `GET /api/cases/:id/events` | Cursor | `Page<CaseEvent>` in `(at,id)` order |
| `POST /api/cases/:id/messages` | Inbound message fields; path fixes case ID | Same intake/deduplication rules |
| `POST /api/cases/:id/assign` | Version, owner, service queue, reason | Updated `CaseSummary`; takeover invalidates pending AI work |
| `POST /api/cases/:id/agent-runs` | Version | 202 `{run_id}`; deduplicate active work for same version |
| `GET /api/agent-runs/:id` | — | `{run_id, status, result}`; status queued/running/completed/failed, result null until finished, otherwise `AnalysisResult` |
| `POST /api/cases/:id/execute` | Version, stored proposal ID | Worker-only `ExecutionResult` |
| `POST /api/cases/:id/actions` | Version, `ProposedAction`, reason | Authorized staff action; `ExecutionResult` |
| `POST /api/cases/:id/approvals` | Version, decision ID, position IDs, approve/reject, reason | Immutable approval ID and new case version; binds stored amounts |
| `POST /api/cases/:id/close` | Version, reason | Updated case; only from `Resolved` |
| `GET /api/metrics` | From/to UTC, optional queue | Metric definitions below |

Use polling for v1: refresh selected case and run every two seconds while active; stop at completion or on leaving the page. A 409 prompts a reload and explicit reapplication of a staff edit; never silently overwrite a colleague.

Customer views use separate `GET /api/customer/cases` and `GET /api/customer/cases/:id` projections. Return only `{id, subject, status_label, next_action, updated_at}` plus public messages and customer-owned attachments in detail. Do not expose the staff snapshot, internal sources, financial deliberations or event payloads. Derive customer identity from the demo session; emailed upload links are scoped to one case and expire.

## 6. Events, metrics and failures

Events are append-only and emitted by the platform in the mutation transaction. Minimum event types: `case_received`, `message_received`, `triage_started`, `facts_updated`, `assignment_changed`, `proposal_created`, `action_blocked`, `response_queued`, `response_sent`, `response_failed`, `clarification_answered`, `handover_created`, `approval_recorded`, `budget_reserved`, `budget_released`, `payment_simulated`, `case_resolved`, `case_reopened`, `case_closed`, `work_started`, `work_stopped`.

State/assignment events include before/after values. Decision events include proposal/decision ID, policy version and source references. Response events include message ID and action kind. Budget events include position/reservation IDs and money. All events include actor, reason, timestamp, correlation ID and resulting case version; multiple events from one transaction may share that version.

`GET /api/metrics` returns `{from, to, basis, counts, durations}`. `basis` is `measured` or `synthetic`; never mix those populations. Counts include received, open, resolved, automatically resolved, handovers and overdue. Each duration entry is `{name, unit: "seconds", sample_size, median, p90}` with null percentiles for empty samples. Names: `first_meaningful_response`, `queue_wait`, `customer_wait`, `resolution_time`, `human_active_time`. Active work uses explicit start/stop sessions, not tab-open time. In v1, omit human time when session tracking is unavailable rather than inventing it.

Person 1 owns orchestration retries, with a configurable default of two additional attempts for transient provider failures. Person 2 reports failure type and retryability; malformed output/unreadable evidence does not become automatic success. Exhausted technical retries leave the original messages intact and create a prepared human handover. Worker crash recovery uses persisted jobs and outbox records. The manual workspace remains usable.

## 7. Existing pipeline adapter

Read only the exported `runtime/` directory. Evaluation labels, future simulator replies and provenance remain outside runtime inputs and retrieval. The import adapter validates IDs and relationships and imports idempotently by dataset manifest plus record ID.

| Existing export | Application mapping |
|---|---|
| Case IDs, subject, language, channel, timestamps | Preserve; add version 1, category `unknown`, triage queue owner, normal priority, uncertain severity and null sentiment |
| Contact, booking and flight references | Resolve into the snapshot; use null when genuinely absent, reject dangling supplied IDs |
| Inbound messages | Inherit case channel; preserve thread and timestamp; delivery `received`, sent timestamp null |
| Attachment relative paths | Copy/serve via controlled content storage; calculate byte size/hash/version; retain synthetic marker |
| Legacy attachment amount/booking metadata | Keep as fixture provenance only; schema 1.1 omits these extraction answers from runtime metadata |
| Initial `case_received` events | Preserve IDs/time, enrich with import actor, reason, correlation ID and version 1 |
| Generator `policy.json` | Map supported categories/version; missing limits require explicit demo configuration before executing monetary actions |

The current generator supplies actual PDF baggage reports and PNG baggage tags/receipts, including held-back customer uploads and unreadable scans. Use `data/examples/baggage/` for the focused demonstration. Future reply messages and file bytes remain under `evaluation/` until the test harness stages an upload and ingests the reply; extract the new content and reassess the same case. The explorer's walkthrough previews these fixtures without running an agent. Importing 3,000 records does not require 3,000 live model calls.

## 8. First integration acceptance checks

1. Complete fixture → intake → live or visibly recorded analysis → automatic simulated send → resolved case, with policy/source references visible.
2. Missing receipt → one targeted automatic question → customer upload on the same case → fresh analysis → automatic resolution. No human approval.
3. Serious incident → handover with reason, facts and open questions → human takeover and response.
4. Angry complete case remains eligible; calm serious case reaches a specialist.
5. New message or human takeover during analysis makes the old proposal stale; no old response or duplicate ledger entry occurs.
6. Replay intake, execution and delivery requests → one message/action each; replay with a changed payload → conflict.
7. Model/delivery failure → visible failure and bounded retries → usable manual case.
8. Customer projection omits internal data; runtime snapshot omits hidden evaluation and future replies.

Start with these fixtures and the typed seams. Add full account navigation, disruption administration and richer dashboard controls after the three core journeys work. These remain planned extensions, not prerequisites for the first integration.
