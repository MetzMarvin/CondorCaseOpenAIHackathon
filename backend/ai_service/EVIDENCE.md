# Read-only evidence integration

`evidence.py` is the public System 2 adapter seam; `requirements.py` is the
collection matrix. Existing shared Pydantic contracts and the two-argument
`process_case(request, emit_progress)` remain unchanged. No shared changes are
proposed. `service.create_processor(adapters=...)` now wires these contracts into
the synchronous workflow; see the [implementation status ledger](../../docs/development/workflow-implementation-status.md).

`create_evidence_adapters(crm=..., operational=..., attachments=...)` builds an
immutable dependency bundle for a configured processor. Omitted readers return
`unavailable` with a safe technical error. They never fabricate records or fall
back to reading a filesystem. Fake readers use explicit in-memory synthetic
results, without credentials or external I/O.

## System 1 implementation obligations

- CRM and operational readers implement `RecordReader.lookup(LookupRequest)`.
  The scope is the case ID and exact snapshot version. System 1 must authorize
  the snapshot and returned records; a scope label is not an authorization token.
  Match customer, booking and dated itinerary together before releasing facts.
- `found` requires nonempty facts with `SourceRef` IDs/versions and an aware
  observation time. Return `freshness=current` only after checking the requested
  snapshot version against authoritative records. `stale`/`unknown` are explicit
  and require refresh before using decision-critical internal facts. No arbitrary
  TTL is assumed. Consumers must reject mismatched scopes and stale results.
- `not_found` means the lookup completed without a match; `ambiguous` means more
  evidence is needed. Neither returns candidates or establishes ineligibility.
  `unavailable` requires `TechnicalError`; it is a failed run when required data
  cannot be acquired, never a customer question about airline internals.
- Attachment readers implement `AttachmentReader.read(AttachmentRequest)`.
  Resolve only the exact opaque `AttachmentRef` supplied for the scoped snapshot;
  check membership and current case version before reading bytes. Never accept
  paths, URLs, or substitute same-ID content from another version.
- Return bounded bytes and verified `reference.media_type`; reject unsupported
  formats, media mismatches, and over-limit files explicitly. A reader must
  configure its supported media types and byte limit (System 1 owns KA04).
  Outcomes are `found`, `not_found`, `scope_violation`, `unsupported`, `too_large`,
  and `unavailable`. Only `found` carries bytes, `SourceRef` version and SHA-256.
  A stable attachment ID/version must identify unchanged bytes. Changed content
  requires a changed version/hash. `observed_at` records the read observation.
- Do not return raw paths, unrelated passenger records, credentials, or storage
  exception strings in errors or diagnostics. These result objects are internal;
  attachment bytes and facts must not be copied wholesale into progress events.

## Source authority and gaps

`requirements_for_issue(issue)` identifies the intake facts already defined in
`INTAKE_REQUIREMENTS`, matched CRM context, relevant operational facts, policy
context and execution controls. `requirement_for_fact` covers all existing
`INTERNAL_FACTS` and `CONTROL_FACTS`. The source-origin check is based on the
trusted adapter/channel, never on labels supplied by a customer or document.
Customer claims cannot populate eligibility, payment or execution controls.

Customer absence or contradiction asks a focused clarification; preserve prior
valid evidence. Internal gaps refresh/enrich from System 1. Internal conflicts
require reconciliation before payment and a concrete unresolved-conflict handoff
only if that reconciliation fails substantively. Policy gaps retrieve approved
versions; policy conflicts require rule clarification. Adapter/infrastructure
failures remain technical failures. Missing information, anger or silence alone
never causes handoff. Serious allegations retain the existing specialist route.

The matrix describes collection, not added legal automation. Only the existing
synthetic expense policy supports resolution. Other supported intake categories
still require a concrete unsupported-adjudication handoff once intake is ready.
Actual CRM matching, operational freshness checks and attachment byte/media limits
remain System 1 dependencies (KA02–KA04). System 2 extraction and workflow
consumption are implemented and tested with synthetic scoped readers.

## Evidence preparation (KA08)

`reconciliation.prepare_evidence(request, adapters=None, *, customer_facts=())`
returns `PreparedEvidence`: a copied effective request and source references, or
an error with no effective request. The default supplied-fact path does no reads.
It preserves prior messages, missing requirements and every sourced value;
conflicting values remain available to the existing clarification/handoff logic.
KA05 callers may supply already provenance-validated customer facts; only known
customer question fields are accepted, never internal controls.

Explicit `customer_match`, `booking_match` or `flight_match` entries in
`missing_information` request CRM enrichment. Current scoped CRM results establish
these facts using the value `matched`. CRM may also supply booking reference,
flight number and flight date. Ambiguous/not-found outcomes retain the gap and
ask for a booking identifier without candidate records. They defer operational
lookup until the booking can be identified. CRM cannot provide payment controls.

Configured operational enrichment fills absent expense eligibility and payment
history for the supported expense-resolution path. Other intake-only issues and
serious allegations retain existing specialist routing. Readers must return the
exact case/version and `current` freshness; stale/unknown freshness, incomplete
required records, scope mismatches and unavailable readers produce technical
errors. Supplied snapshot facts are trusted as System 1's version-consistent
snapshot; the shared Fact model does not carry independent freshness metadata.
Reader exception text is never exposed. System 1 still owns actual adapters,
matching, freshness verification, and all business effects.

The active workflow now extracts supplied attachments, prepares evidence, retrieves
approved knowledge, and assesses the resulting snapshot copy. Configure System 1
readers with `backend.ai_service.create_processor(adapters=...)`; the returned
callable retains `(request, emit_progress)`. Optional `extractor` and `retriever`
arguments support backend configuration and deterministic testing. The default
entry point supports supplied-fact demos; attachments require an authorized reader
and otherwise fail technically. Live experts receive the prepared snapshot and
selected passages. No shared contracts or System 1 records are changed.

### Synthetic document and message extraction

The v2 extractor accepts the generator's uppercase labels, including `TOTAL EUR`,
`ITEM`, `BOOKING`, `FLIGHT`, `PIR REFERENCE` and `BAG TAG`, as well as the
legacy receipt labels. Essential toiletries are an extracted purpose, not an
eligibility decision. The generator populates `DATE` from `flight_date`, even
on receipts; this becomes a flight date. A purchase date still requires explicit
receipt evidence. The generator owner must supply a separate purchase date if
the demo needs complete expense evidence.

Snapshot message bodies support explicit booking/PIR/tag references and the
generator's flight-number/date sentence. Extraction does not turn prose about
spending into a receipt, or establish internal eligibility. Message provenance
uses the message ID, snapshot version, SHA-256 of the UTF-8 body and exact body
offsets. Known service senders are excluded by the workflow. The shared Message
contract has no direction field; authoritative inbound/outbound classification
remains a System 1 integration dependency.

Distinct values are preserved for clarification. In particular, the current
shared customer-fact vocabulary has one `baggage_reference` slot for both PIRs
and bag tags; different identifiers will conservatively remain a conflict until
the systems agree on separate identifier types or verified alias reconciliation.
Unrecognized prose remains unextracted. No shared contract or generator is changed.
