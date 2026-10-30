# Read-only evidence integration

`evidence.py` is the public System 2 adapter seam; `requirements.py` is the
collection matrix. Existing shared Pydantic contracts and the two-argument
`process_case(request, emit_progress)` remain unchanged. No shared changes are
proposed. These contracts alone do not wire enrichment into the workflow.

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
remain System 1 dependencies (KA02–KA04); extraction and workflow consumption are
subsequent System 2 tickets.
