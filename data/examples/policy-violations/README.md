# Policy violation demo cases

Twenty English synthetic handling-violation variants, POLICY-VIOLATION-001 through POLICY-VIOLATION-020, assessed against `CONDOR-CS-EN` version `0.1.0` (`draft_review_required`).

These are authored examples, not 20 discovered real incidents. Existing legal-check cases do not establish 20 distinct policy violations. Each variant reuses an existing synthetic complaint and adds an explicitly synthetic handling audit that contradicts a specific instruction in the repository policy. Original cases remain unchanged. Original booking and flight references are retained for provenance; each variant has a separate case ID.

## Files

- `runtime/cases.jsonl`: customer emails, source-case provenance and internal evidence, including the deliberately incorrect handling audit.
- `runtime/run_requests.jsonl`: validated shared Pydantic `RunRequest` snapshots. Evidence is inline in sourced facts; no external attachment adapter is required.
- `evaluation/findings.jsonl`: stored reviewer findings, exact policy instructions, evidence references and corrective handling. Keep this outside runtime retrieval.
- `manifest.json`: policy version/hash, dataset count and integration status.

The runtime inputs contain historical bad handling to inspect, not instructions to execute. The snapshots have no financial execution authority. Stored findings are authored expectations, not AI engine results or approved legal determinations. Dataset authoring made no model calls, payments or customer messages. The separate audit evaluation below made live model calls without executing any business actions.

## Integration

This is a System 2 demo/review dataset. It is not automatically loaded into the running case list. System 1 owns importing these snapshots through its case service and preserving the synthetic label and evidence provenance. The dataset does not change application seeding, authoritative records or shared contracts. For an offline demonstration, show each complaint beside its stored finding. A separate read-only System 2 Decisions audit has now been evaluated: 20/20 expected violation labels matched, with 17/20 meeting the 0.90 confidence gate. See [audit results and limitations](../../../backend/ai_service/evaluation/POLICY_AUDIT.md). This does not establish automatic case-processing coverage.

## Catalogue

| Case | Source fixture | Policy rule | Violation |
|---|---|---|---|
| POLICY-VIOLATION-001 | LEGAL-001 | CARE-001 | Weather used to deny overnight care |
| POLICY-VIOLATION-002 | LEGAL-003 | DEL-002 | Delay claim rejected using touchdown |
| POLICY-VIOLATION-003 | LEGAL-004 | INT-003 | Meal claim discarded with compensation claim |
| POLICY-VIOLATION-004 | LEGAL-006 | EU-002 | Connection claim assessed only on first leg |
| POLICY-VIOLATION-005 | LEGAL-007 | REF-001 | Accepted refund remains unpaid after deadline |
| POLICY-VIOLATION-006 | LEGAL-009 | REF-001 | Voucher imposed without agreement |
| POLICY-VIOLATION-007 | LEGAL-010 | DB-001 | Overbooking payment deliberately deferred |
| POLICY-VIOLATION-008 | LEGAL-011 | DB-001 | Volunteer agreement erased |
| POLICY-VIOLATION-009 | LEGAL-012 | DB-001 | Disputed document refusal automatically upheld |
| POLICY-VIOLATION-010 | LEGAL-014 | DOWN-001 | Downgrade calculated on entire itinerary |
| POLICY-VIOLATION-011 | LEGAL-018 | BAG-001 | Lost bag kept in indefinite tracing |
| POLICY-VIOLATION-012 | LEGAL-019 | PRM-001 | Late assistance notice used as sole refusal |
| POLICY-VIOLATION-013 | LEGAL-020 | SER-001 | Injury closed as a meal expense |
| POLICY-VIOLATION-014 | LEGAL-002 | EVID-001 | Missing receipt alone triggers handoff |
| POLICY-VIOLATION-015 | LEGAL-001 | ESC-001 | Anger alone triggers handoff |
| POLICY-VIOLATION-016 | LEGAL-003 | INT-003 | Receipt demanded for fixed compensation |
| POLICY-VIOLATION-017 | LEGAL-009 | INT-002 | Card security code collected in notes |
| POLICY-VIOLATION-018 | LEGAL-007 | FIN-001 | Pending refund reported as paid |
| POLICY-VIOLATION-019 | LEGAL-016 | OPS-002 | Case age reset during reassignment |
| POLICY-VIOLATION-020 | LEGAL-004 | OPS-003 | Stale AI proposal executed after takeover |

## Validation performed

All 20 serialized snapshots pass `RunRequest.model_validate_json`. Case IDs are unique. Every finding joins to a supplied evidence source and an exact instruction in the pinned repository policy. These checks establish dataset structure and citation consistency, not engine accuracy or legal approval.
