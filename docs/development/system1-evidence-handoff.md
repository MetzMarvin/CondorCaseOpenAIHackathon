# System 1 evidence integration handoff

Owner: System 1. System 2 exposes the configured processor and read-only contracts;
this document does not implement readers, persistence or action execution.

## Current demo behavior

The inspected `demo_backend/app.py` imports the unconfigured
`backend.ai_service.service.process_case`. It persists uploads and attachment
references, but does not supply attachment bytes to System 2. Its
`extract_receipt()` helper finds a decimal followed by `EUR` in customer email,
replaces existing receipt amount/currency facts, and clears all missing-information
entries. It does not verify a receipt or preserve differing receipt values.

That is a deliberately narrow demo shortcut. For example, “I spent 42.00 EUR”
can currently become `receipt_amount_minor=4200`, while “I did not spend 42.00 EUR”
matches the same pattern. Neither establishes document evidence. Replacing older
facts can hide contradictions, and clearing all missing entries can discard
unrelated outstanding requirements. Keep this shortcut confined to explicitly
labelled fixtures; do not use it for the attachment-backed flow.

Intake classification is also fixture-oriented: it selects serious/unsupported
keywords and otherwise creates an expense claim. The configured System 2 extractor
recognizes supported synthetic labels and selected email identifier patterns;
it is not a general complaint classifier or production OCR implementation.

## Bind the processor

Configure the following dependency bundle in System 1 after constructing its
authorized reader implementations. `crm_reader`, `operational_reader` and
`attachment_reader` below are System 1-owned objects, not classes supplied by
System 2:

```python
from backend.ai_service.evidence import create_evidence_adapters
from backend.ai_service.extraction import DocumentExtractor
from backend.ai_service.service import create_processor

process_case = create_processor(
    adapters=create_evidence_adapters(
        crm=crm_reader,
        operational=operational_reader,
        attachments=attachment_reader,
    ),
    extractor=DocumentExtractor(),
)

# Existing synchronous processing call and final execution checks stay in System 1.
result = process_case(request, emit_progress)
```

Install `requirements-extraction.txt` for text PDFs. Images/scans require an
explicit OCR adapter; `FakeOCR` returns supplied fixture text and performs no image
recognition. A missing parser/OCR configuration is a technical failure, not proof
that a customer's document is unreadable. The default approved knowledge remains
the synthetic expense policy. The unreviewed Qdrant research collection does not
authorize reimbursements.

## Reader and snapshot responsibilities

- Build a version-consistent snapshot with sourced internal facts, attachments,
  messages, issue classification and remaining requirements. Customer prose must
  not set eligibility, payment history or execution authority. Preserve claims and
  differing evidence rather than overwriting them with the latest regex match.
- CRM `lookup(LookupRequest)` returns only authorized case/version matches. Missing
  `customer_match`, `booking_match` and `flight_match` requirements request matching.
  Return `ambiguous` without exposing candidate passenger records.
- Operational `lookup(LookupRequest)` supplies sourced current eligibility and
  payment-history facts. Conflicting values trigger a refresh. A unique current
  result can supersede historical values in the effective assessment snapshot;
  unresolved conflicting results or ambiguity retain specialist context. Outages,
  wrong scope and stale results remain technical failures.
- Attachment `read(AttachmentRequest)` validates the exact case ID, version and
  attachment reference against authoritative membership before resolving its
  internal storage key. Do not fetch `local_reference` as an arbitrary URL or use
  a customer filename as a path. The existing `/api/.../attachments/...` reference
  is an opaque reference for this purpose.
- A found attachment returns bounded bytes, verified media type, an immutable
  source version, SHA-256 and observation time in `AttachmentResult`. Upload's
  client-provided content type alone is insufficient media verification. Existing
  upload size checks remain useful; read-time checks must also enforce limits.
- Preserve customer/agent message identity. The current processor skips the
  configured demo sender `condor-service@example.com`, AI/system markers and the
  owner ID. Coordinate any additional outbound sender before it can be mistaken
  for incoming customer evidence.
- Persist run diagnostics through the configured diagnostic sink using a safe
  projection. Do not serialize the private processing bundle or document bytes
  wholesale. System 1 remains responsible for ownership/version rechecks,
  idempotency, simulated outbound messages and financial effects.

Detailed contracts: [EVIDENCE.md](../../backend/ai_service/EVIDENCE.md) and
[PROCESSING.md](../../backend/ai_service/PROCESSING.md).

## Required integrated acceptance checks

1. A supported case with an actual generated receipt, sourced eligibility and no
   prior payment resolves using extracted document values and source versions.
2. Email text containing an amount, including a negated or requested amount, does
   not itself establish receipt evidence or override an existing receipt.
3. Missing evidence requests only the remaining material fields. Upload plus reply
   resolves the same case at its new version; a partial reply retains earlier
   evidence and still asks for the unresolved field.
4. A different receipt amount preserves both sources and requests clarification.
   Conflicting internal eligibility/payment facts refresh through the operational
   reader before a substantive unresolved-conflict handoff.
5. Wrong-case/version attachments, parser outage and stale internal lookup fail
   without an outbound customer question or payment. Unreadable evidence, as
   distinct from infrastructure failure, requests a readable replacement.
6. A serious allegation hands off with context. Negative sentiment or missing
   evidence alone does not.
7. Duplicate requests produce no duplicate effects. A human takeover during
   extraction/model processing prevents the stale proposal from executing.
8. The three core flows run with `AI_MODE=offline`; OCR simulation and financial
   effects remain explicitly labelled. No evaluation labels enter runtime input.

These are handoff acceptance requirements, not claims of end-to-end validation.
The existing demo API tests exercise its supplied-fact/regex receipt shortcut;
they must be extended to exercise the configured attachment reader path.
