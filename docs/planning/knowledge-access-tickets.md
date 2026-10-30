# Knowledge and evidence implementation tickets

Build case-scoped CRM access, attachment extraction and approved knowledge retrieval for the synchronous Condor Care Hub demo. All tickets below can be implemented with synthetic records and generated test documents before real legal, policy or customer documents are available. These are repository tickets, not published tracker issues.

The [subsystem agreement](../architecture/subsystems-and-contracts.md) governs implementation. System 2 owns AI orchestration; System 1 owns CRM records, evidence access and execution; System 3 owns display. Tickets assigned to Systems 1 and 3 describe integration work for their owners, not authorization for System 2 to edit those modules. Shared interface changes require coordination. English demo content follows root AGENTS.md; preserve existing contract field names pending a coordinated migration.

## Implementation approach

Use deterministic record lookup for customers, bookings and flights. Use extraction for customer attachments. Use retrieval of approved passages to supply knowledge to model calls. Do not put private customer records into a shared policy index.

Start with local Python adapters and a small JSON knowledge collection. Metadata filtering and lexical search are sufficient for the initial synthetic corpus; introduce embeddings only if evaluation demonstrates a retrieval gap. MCP can later expose the same adapters to other clients. MCP defines context exchange and tool access, while the application remains responsible for how context is used ([official architecture](https://modelcontextprotocol.io/docs/learn/architecture)). A separate MCP server is unnecessary for the current in-process demo.

```mermaid
flowchart LR
    Intake[System 1 intake] --> Match[Customer booking and flight lookup]
    Match --> Snapshot[Read only case snapshot]
    Snapshot --> Evidence[System 2 evidence extraction]
    Evidence --> Gaps[Completeness and conflict checks]
    Gaps --> Knowledge[Approved policy retrieval]
    Knowledge --> Context[Bounded model context]
    Context --> Proposal[Validated typed proposal]
    Proposal --> Execute[System 1 authority and execution]
    Execute --> Console[System 3 case and activity display]
```

Current code already provides shared Pydantic contracts, deterministic routing, questions, offline outputs and optional live expert drafting. `assessment.py` uses synthetic expense policy v2. `experts.py` supplies attachment metadata but does not read attachment contents. Extend these modules rather than creating a second workflow. The legal scenario catalogue is a design input, not approved executable legal knowledge.

## Ticket order

P0 is the core path; P1 adds document handling and broader diagnostics. Every ticket is initially open. Dependencies below are implementation dependencies, not dependencies on obtaining real documents.

| Ticket | Priority | Owner | Depends on | Deliverable |
|---|---|---|---|---|
| KA01 | P0 | System 2 with System 1 | None | Evidence requirements and adapter contracts |
| KA02 | P0 | System 1 | KA01 | CRM matching and synthetic records |
| KA03 | P0 | System 1 | KA02 | Operational evidence and snapshot enrichment |
| KA04 | P1 | System 1 | KA01 | Scoped attachment reader |
| KA05 | P1 | System 2 | KA04 | Document extraction with provenance |
| KA06 | P0 | System 2 | KA01 | Versioned knowledge registry |
| KA07 | P0 | System 2 | KA06 | Filtered knowledge retrieval |
| KA08 | P0 | System 2 | KA01, KA03 | Evidence reconciliation and follow-up |
| KA09 | P0 | System 2 | KA07, KA08 | Context assembly and proposal validation |
| KA10 | P0 | System 1 with System 2 | KA09 | Execution and reply integration |
| KA11 | P1 | System 1 with System 2 | KA09 | Persisted run diagnostics |
| KA12 | P1 | System 3 | KA11 | Evidence and source display |
| KA13 | P0 | System 2 with Systems 1 and 3 | KA10 | Offline acceptance suite |

KA05 joins KA08 and KA09 after the initial supplied-fact path works. KA13 expands to document and diagnostics cases as KA05, KA11 and KA12 land; these are not prerequisites for its first three-flow test.

## KA01 Define evidence requirements and read interfaces

**Problem:** The workflow needs to know which facts come from customers, CRM, operational records and policies before it can choose a useful lookup or question.

**Work:** Build a requirement matrix from `INTAKE_REQUIREMENTS`, `INTERNAL_FACTS` and the [failure catalogue](../research/airline-legal-checks.md). Describe narrow read-only adapter inputs and results. Reuse `Fact`, `SourceRef`, `AttachmentRef` and `CaseSnapshot`; keep extraction and retrieval metadata internal to System 2 unless a shared addition is necessary. Resolve service dependencies through configuration or a factory while preserving `process_case(request, emit_progress)`.

**Acceptance criteria:**

- Every supported issue identifies required facts, their authoritative source, and what to do when absent or conflicting.
- Lookup results distinguish found, not found, ambiguous and unavailable; these are adapter results, not new business actions or case statuses.
- A customer claim cannot populate internal eligibility, authority or payment controls.
- Fake adapters exercise success, ambiguity and technical failure without credentials or network access.
- Document scope, source version, freshness requirements and dependency ownership are explicit; proposed shared changes are listed for both owners.

**Validation:** Contract tests for adapter results and compatibility with existing shared models.

## KA02 Match customer booking and flight records

**Problem:** Supplied identifiers do not prove that the passenger, booking and flight belong together.

**Work:** Implement System 1 read-only matching over synthetic CRM records. Prefer stable customer/booking IDs and correlate passenger membership and itinerary segments. A flight number requires its date and relevant route context; email alone is not sufficient to merge identities. Keep candidate records inside System 1 until a match is authorized for the case.

**Acceptance criteria:**

- A unique valid match supplies stable record IDs and source versions to the snapshot.
- Unknown customers, duplicate names, shared email addresses, multiple bookings and recurring flight numbers have deterministic fixtures.
- No match requests an appropriate identifier or routes an unsupported investigation with a concrete reason; it never establishes ineligibility.
- Ambiguous matches do not choose the first record or disclose other passengers' details.
- Failed CRM access is distinguishable from a successful lookup returning no records.

**Validation:** Matching tests for unique, missing, ambiguous and inconsistent passenger/booking/flight relationships.

## KA03 Enrich snapshots with operational evidence

**Problem:** Entitlement assessment cannot rely on customer text for airline operational facts.

**Work:** Assemble sourced flight context, booking context and reimbursement history through System 1 adapters. Synthetic fixtures cover arrival time, operating carrier, disruption cause, notification history, reasonable measures where available, payment history and the existing demo eligibility check. Preserve unknown values explicitly; do not infer a legal defense from a cause label.

**Acceptance criteria:**

- Source record IDs, versions and observation times are traceable for decision-critical facts.
- Missing internal data triggers internal enrichment or a visible failed run when required data cannot be obtained; customers are not asked for airline records.
- Partial or previous payments require reconciliation before another reimbursement proposal.
- Customer-supplied fields cannot override internal controls.
- A snapshot is consistent with its case version; later evidence changes require a fresh assessment.

**Validation:** Supplied, absent, stale, conflicting and unavailable operational-record fixtures.

## KA04 Provide case scoped attachment access

**Problem:** Attachment metadata does not establish access to the document or its contents.

**Work:** System 1 resolves opaque attachment references to bounded bytes and verified media metadata. Define supported file types and size limits. Use generated synthetic files; real documents are unnecessary.

**Acceptance criteria:**

- Case membership is checked before bytes are returned; arbitrary paths, URLs and cross-case references are rejected.
- Missing files, unsupported formats, over-limit files and storage failures have explicit outcomes.
- System 2 has no direct database or unrestricted filesystem access.
- The same attachment ID/version resolves reproducibly; changed content receives a distinct version or hash.

**Validation:** Same-case success, cross-case rejection, path traversal, mismatched media type and unavailable storage tests.

## KA05 Extract document facts with provenance

**Problem:** Receipts and complaint documents must become sourced facts without inventing unreadable values.

**Work:** Add an extraction adapter under `backend/ai_service/`. Start with text and text-based PDFs; provide a fake OCR adapter for images/scanned PDFs so OCR integration is replaceable. Generate synthetic receipt and complaint fixtures. Return extraction status, page/span references, original values and normalized candidates.

**Acceptance criteria:**

- Amount, currency, date and expense purpose are independently represented; missing currency is never guessed and arithmetic uses integer minor units after validated conversion.
- Readable, partial, unreadable and parser-failure outcomes remain distinct.
- Missing or illegible customer evidence produces a focused question; a parser outage produces `FAILED` with no proposal.
- Every accepted fact resolves to an attachment version and supporting text/page.
- Instructions embedded in a document remain untrusted content and cannot change policy or trigger tools.
- OCR is labelled simulated until a real adapter is configured; attachment metadata alone never counts as extracted evidence.

**Validation:** Synthetic clear receipt, partial receipt, conflicting totals, unreadable image, parser exception and malicious instruction fixtures.

## KA06 Build a versioned knowledge registry

**Problem:** A hardcoded policy source reference cannot describe approval, applicability or the content used in a decision.

**Work:** Create System 2 internal models and a local JSON loader for knowledge cards. Include source ID/version, title, source location, source kind, issue tags, applicability metadata, effective interval, retrieval date, approval state, content hash, text and dependencies on related exceptions. Distinguish synthetic demo approval from production legal approval. Seed only clearly labelled synthetic policy cards.

**Acceptance criteria:**

- Invalid, duplicate or corrupt cards fail validation; draft, withdrawn and future-effective cards cannot be used as applicable approved knowledge.
- Event date and retrieval date are separate, with explicit date boundary semantics.
- The current synthetic expense policy has reproducible content and version references.
- Legal rules, company policy and demo assumptions are distinguishable.
- Future real-source ingestion uses the same schema without requiring a vector database or altering shared action contracts.

**Validation:** Registry loading, duplicate versions, invalid date intervals, approval states and content-integrity tests.

## KA07 Retrieve applicable knowledge with supporting exceptions

**Problem:** Text similarity alone can retrieve a convincing passage from the wrong policy version or jurisdiction.

**Work:** Filter the registry by approval, issue, relevant case date and established applicability facts before lexical ranking. Retrieve short source passages with related prerequisites and exceptions. Keep an internal retrieval interface that can later accommodate embeddings.

**Acceptance criteria:**

- Known irrelevant, expired and unapproved cards cannot reach the model context.
- Unknown applicability facts are recorded as gaps, not assigned a guessed jurisdiction.
- Results include source version, passage ID and selection rationale; order is deterministic for fixtures.
- No applicable supported rule, conflicting applicable rules and registry infrastructure failure have distinct outcomes: unsupported capability, concrete `UNCLEAR_RULE`, or `FAILED` as appropriate.
- Mandatory exception passages survive retrieval limits; if required support cannot fit, no unsupported resolution is produced.
- Customer attachments never enter the global knowledge collection.

**Validation:** Synthetic wrong-date, wrong-regime, contradictory-rule, missing-exception and unavailable-registry retrieval fixtures.

## KA08 Reconcile evidence and ask only material questions

**Problem:** New evidence must update the assessment without losing provenance or repeatedly asking answered questions.

**Work:** Extend existing `assessment.py` and `questions.py` to consume matched CRM facts and extraction candidates. Maintain source precedence and material conflicts explicitly. Separate customer gaps, internal enrichment needs and unsupported decisions. Integrate KA05 when available.

**Acceptance criteria:**

- A partial reply retains earlier valid evidence and asks only remaining material questions.
- Ambiguous CRM matching requests the minimum useful identifier without revealing candidate records.
- Internal-data gaps do not generate customer questions about airline internals.
- Conflicting values are preserved; an unresolved material conflict has a concrete handoff explanation and prior clarification context.
- Missing information, anger or silence alone never triggers denial or handoff.
- Serious allegations continue to trigger the existing specialist path.

**Validation:** Extend current routing tests for partial replies, conflicting evidence, internal gaps and negative sentiment.

## KA09 Assemble model context and validate proposals

**Problem:** The live experts currently receive a broad snapshot and hardcoded policy context; source-ID membership alone does not prove a claim is supported.

**Work:** Build a bounded context from necessary sourced facts, unresolved gaps, approved passages, permitted actions and the validated deterministic recommendation. Extend existing expert drafting and post-validation. Preserve offline operation and backend-only credentials. Use synthetic knowledge and a fake model for tests.

**Acceptance criteria:**

- Every call receives only case-authorized evidence and the selected knowledge versions; unrelated personal data is excluded.
- No secret, arbitrary attachment path or other case's content enters the prompt or diagnostics.
- Required evidence and exceptions cannot be silently truncated to fit the context budget.
- Output conforms to shared `RunResult` and proposal models; IDs, amounts, currency, action type, missing questions and authority constraints remain consistent with deterministic assessment.
- Citation checks verify the referenced passage exists and supports the relevant rule/fact; unresolved substantive support prevents automatic resolution.
- Customer-facing drafts cannot claim a payment or message was executed before System 1 accepts it, or invent an entitlement or denial.
- Invalid output, refusal or provider failure produces a technical failure; offline simulation is explicit and never silently substituted for a live result.

**Validation:** Fake-model tests for invented citations, changed amounts, omitted questions, unsupported legal claims, execution claims and malformed output.

## KA10 Integrate execution and the customer reply loop

**Problem:** A validated proposal must still be checked against current authoritative state before simulated effects occur.

**Work:** System 1 wires the existing synchronous entry point, applies accepted actions and feeds new customer replies into a new snapshot. System 2 supplies deterministic integration fixtures. Reuse existing endpoint and action contracts.

**Acceptance criteria:**

- Complete supported expense resolves, missing receipt requests information then resolves after a reply, and serious/unsupported cases hand off with context.
- Version, owner, permitted action and financial authority are checked at execution time.
- Human takeover invalidates a pending AI proposal; the AI cannot overwrite human ownership.
- Identical idempotency keys and payloads do not repeat sends/payments; conflicting payload reuse is rejected.
- Failed runs preserve the case with no business effects and can be retried under System 1's recovery rules.
- Intake and explicit processing do not trigger duplicate runs.

**Validation:** End-to-end synthetic flows, takeover race and duplicate-action tests owned by System 1 with System 2 fixtures.

## KA11 Persist run diagnostics and source manifests

**Problem:** A decision must be reproducible without putting raw customer documents into progress events.

**Work:** System 2 emits existing agreed progress steps and a diagnostic manifest identifying input case version, evidence versions, selected knowledge versions, simulation mode and concise decision reasons. System 1 owns storage and access. Coordinate any needed internal storage contract separately from public event fields.

**Acceptance criteria:**

- A run can be traced to the exact evidence and knowledge versions used, including extraction/retrieval configuration versions.
- Events use existing step IDs and contain references rather than document text or personal details.
- Callback or persistence failures remain visible; no successful business outcome is fabricated.
- Stored simulations remain usable without model access and are clearly labelled; storage location, access scope and retention behavior are explicit.
- Retrieval, extraction and model failures retain safe error categories and useful retryability information.

**Validation:** Manifest round trips, callback failure and sensitive-content exclusion tests.

## KA12 Show evidence and knowledge sources in the console

**Problem:** Operators need to understand which facts are known, missing, conflicting or only claimed.

**Work:** System 3 displays CRM match outcome, evidence status, source IDs/versions, selected policy passages where permitted, and reasons for questions/handoffs. Fetch all data through System 1. Coordinate a minimal read-response extension only if existing case detail cannot carry the needed information.

**Acceptance criteria:**

- Operators can distinguish customer claims, internal records and synthetic policy assumptions.
- Unreadable attachments and technical failures are visually distinct.
- Source links are case-scoped and do not expose filesystem paths or other passengers.
- Simulated outputs and replay are labelled; proposals and executed effects are distinguishable.
- Existing human takeover and action controls remain under System 1 authority.

**Validation:** UI fixtures for all three core flows plus missing source and technical failure; open any updated HTML visualization in the user's browser.

## KA13 Expand the offline acceptance suite

**Problem:** Retrieval and adapter changes can regress the three core flows or accidentally rely on live providers.

**Work:** Extend existing tests and `backend/ai_service/evaluation/` with a compact synthetic suite. Keep expected outcomes and future simulated replies outside runtime retrieval and model inputs. Reuse existing fixtures where possible.

**Acceptance criteria:**

- The core demo passes with network access disabled and no model credentials.
- Cover unique/no/ambiguous CRM match; internal adapter failure; missing evidence then reply; serious allegation; authority limit; prior reimbursement; invalid model output; expired policy; and conflicting sources.
- Add extraction, cross-case reference and prompt-injection checks when KA04/KA05 land.
- Integration checks verify stale proposal rejection and no duplicate effects in System 1.
- Assertions check action, reason, missing fields, cited versions and effects, not merely answer wording.
- Results distinguish synthetic workflow correctness from legal validation; generated expected answers never become approved policy.

**Validation:** Run focused tests per ticket and the integrated three-flow suite after wiring; record only checks actually performed.

## Deferred work requiring additional inputs

- Loading real legal/company policies and enabling additional entitlement decisions requires source material, applicability rules and an identified reviewer. No present ticket claims legal approval.
- Connecting a real CRM requires the product, sandbox endpoint, authentication method, supported record schema and case-access rules. The mock adapters above establish the integration seam first.
- A production OCR service needs a provider decision and representative documents; the extraction contract and synthetic tests can be built now.
- A remote MCP wrapper is optional future integration work if another client needs these tools. It must preserve the same authorization and read-only boundaries.
- Vector retrieval should follow a measured recall problem on a larger approved corpus, with relevance and applicability tests retained.

## Completion of this ticket drafting task

This backlog specifies implementation and validation work. It does not implement CRM access, document extraction or retrieval, and no application tests were run as part of drafting these tickets.
