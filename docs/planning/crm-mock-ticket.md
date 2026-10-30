# CRM01 Implement the CRM mock and case enrichment

**Status:** Open repository ticket. **Priority:** P0. **Owner:** System 1. **Integration partner:** System 2.

Implement a local Salesforce-style CRM mock that checks whether a customer, booking and flight exist and belong together, then supplies sourced facts to the AI service. Use SQLite and SQLAlchemy in the existing backend, with deterministic synthetic data and no external credentials. This ticket elaborates KA02 and KA03 in the [knowledge access backlog](knowledge-access-tickets.md); track their CRM implementation here rather than duplicating work.

## Scope and ownership

System 1 owns records, matching, case access, snapshot construction and persistence. System 2 consumes the resulting `RunRequest` through the existing synchronous `process_case(request, emit_progress)` entry point. Follow the [subsystem agreement](../architecture/subsystems-and-contracts.md) and reuse [shared contracts](../../backend/contracts.py).

Inspect the System 1 package before selecting implementation paths. Do not put CRM storage in `backend/ai_service/`. This ticket does not require real Salesforce, MCP, a vector database, legal documents, OCR or a new frontend. Existing execution and financial-authority enforcement remain System 1 responsibilities.

## Records to implement

Use existing shared fixture IDs where available. The following are proposed internal storage fields, not new public API contracts.

| Record | Minimum information |
|---|---|
| Customer | Stable customer ID, synthetic name and contact information, record version |
| Booking | Stable booking ID/reference, passenger membership, itinerary flight IDs, record version |
| Flight instance | Stable flight ID, flight number, departure date, origin/destination, operating carrier, scheduled and actual timestamps when known, record version |
| Operational evidence | Flight association, disruption cause/notification evidence when available, observation time and source version; unknown stays unknown |
| Reimbursement history | Case/booking association, passenger and expense reference, amount in integer minor units, currency, payment status and source version |
| Case association | Existing case ID and authorized matched records, with the case version used for the association |

Fixture-only expense eligibility must be explicitly labelled as a synthetic demo policy assessment. Flight presence or a receipt alone must not generate an eligibility determination. Likewise, customer claims must not populate authoritative eligibility or payment controls.

## Implementation steps

1. Add or reuse SQLAlchemy records, foreign keys and deterministic seed data. Provide a repeatable seed command that does not erase existing case work; isolate any destructive reset to an explicit demo reset operation.
2. Implement a narrow read-only lookup service inside System 1. Inputs are case-authorized identifiers; outputs distinguish a unique match, no match, ambiguity and lookup failure. These are internal lookup outcomes, not new case statuses.
3. Match booking reference and passenger membership first when available. Resolve flight number with date and route context as needed. Never merge customers based only on matching names or email addresses, or choose the first ambiguous candidate.
4. Enrich `customer_context`, `booking_context` and `flight_context` with existing `Fact` and `SourceRef` models. Include stable source IDs/versions; retain observation times in the internal source registry. Preserve the workflow's agreed fact names and semantics.
5. Supply existing internal checks such as `expense_eligibility` and `payment_history` only from trusted mock records. Distinguish no prior reimbursement from unknown history, failed access and partial reimbursement. Coordinate how additional matching metadata is represented; do not silently change shared models.
6. Integrate enrichment before System 1 invokes the AI service. Record accepted evidence changes with the corresponding case-version update; do not mutate a snapshot already being assessed.
7. Expose results through existing case-detail and processing responses. Keep the full list of candidate customer records private to System 1. No general-purpose customer-search endpoint is required.
8. Document setup, seed data, failure simulation and the integration entry point. Supply representative snapshots to System 2.

## Expected behavior

| Situation | Required behavior |
|---|---|
| Unique customer, booking and flight match | Enrich the case with sourced facts; continue assessment |
| No match and a useful identifier is missing | Preserve the case and support a targeted customer question |
| Multiple possible matches | Request disambiguation without revealing other customers' records |
| Existing customer absent but claim otherwise plausible | Preserve the claim; no automatic denial or invented customer association |
| Identifiers disagree with authoritative records | Preserve both sources for clarification or concrete conflict handling |
| Required operational record is absent | Attempt internal enrichment; report a visible internal-data gap if unresolved, never ask the customer for airline-only records |
| Adapter/database unavailable | Technical failure with no business proposal or effects; never represent as no match |
| Previous or partial reimbursement | Supply history for reconciliation; do not propose a duplicate or infer the unpaid balance without support |
| Cross-case or unauthorized reference | Reject access before returning record data |

System 2 chooses questions or handoffs using the existing action types. A genuine unsupported investigation can be handed off with a reason; missing information or negative sentiment alone cannot cause handoff. Missing internal evidence follows the existing `INTERNAL_EVIDENCE_REQUIRED` behavior until enrichment succeeds.

## Acceptance criteria

- [ ] The mock runs offline with SQLite and no Salesforce/model credentials.
- [ ] Seed data supports the three existing demo flows within the 6–10-case demo scope; extra edge cases may be isolated unit fixtures.
- [ ] Customers, bookings and individual flight instances are matched consistently, with passenger membership checked.
- [ ] No match, ambiguous match and access failure are independently observable and tested.
- [ ] Facts supplied to System 2 include resolvable source IDs and versions; authoritative controls cannot come from inbound customer text.
- [ ] Payment history is scoped to the relevant claimant and expense and distinguishes paid, partially paid, unpaid and unknown states internally.
- [ ] Cross-case reads return no customer data; raw candidate lists do not reach the model or UI.
- [ ] A new relevant customer reply can resolve ambiguity and produce a new enriched snapshot without losing earlier evidence.
- [ ] Enrichment respects case version and human ownership; repeated reads have no side effects and repeated processing does not duplicate effects.
- [ ] Existing shared IDs, action types, statuses and progress step IDs remain compatible; any required contract addition is documented for both owners.

## Required verification

Add focused tests for a unique match, unknown booking, duplicate names/shared email, recurring flight number on different dates, incorrect passenger membership, conflicting identifiers, missing operational facts, partial reimbursement, adapter failure and cross-case access. Run the three core integration flows with System 2, including a simulated customer reply. Verify stale proposal rejection and duplicate-effect prevention through System 1's execution integration.

Deliver code, synthetic seeds, read-adapter tests, integration snapshots and setup instructions. Tests listed here are requirements for implementation; this ticket-writing task does not claim they have run.

## Documents and knowledge boundary

Customer attachments remain case-scoped evidence accessed through System 1 and extracted by System 2. Approved legal/company knowledge remains a separate versioned registry owned by System 2. CRM matching is a structured database lookup; it is not semantic retrieval. KA04–KA07 cover attachment access, extraction, registry and retrieval. They can start with generated documents and clearly labelled synthetic policies while real sources are obtained and reviewed.
