# Historical policy violation audit

System 2's `policy_audit.audit_handling(client, request)` checks supplied historical
handling through the OpenAI Decisions API. It returns all rule verdicts, confidence,
policy release hash, evidence hash, prompt hash and provider usage. It never changes
cases or proposes execution. The existing `process_case` next-action review and
offline flows retain their behavior.

The next-action checker deliberately projects a small set of facts. That projection
omits `handling_audit_record` and the narrative operational records in the 20-case
policy-violation dataset. The new historical audit retains supplied sourced facts,
collection provenance and customer messages, and assesses the recorded handling
rather than a hypothetical next action. Attachment references remain metadata.
It loads the complete hash-verified policy package and asks about every rule,
including related rules and tables; expected findings are never sent to the API.
The draft remains synthetic review material, not approved settlement authority.

Run from the repository root (uses the backend `.env` / `OPENAI_API_KEY`, incurs
API usage):

```sh
.venv/bin/python -m backend.ai_service.evaluation.policy_audit --output /tmp/policy-audit.json
.venv/bin/python -m backend.ai_service.evaluation.policy_audit --controls --output /tmp/policy-controls.json
```

A nonzero exit means at least one expected verdict failed the 0.90 confidence gate.
`matched` counts exact expected labels; `detected` additionally requires confidence
at least 0.90 (for controls this means a confirmed expected non-violation label).
Provider failures/refusals, malformed answers, missing/duplicate rule answers and
oversized context are errors, never successful detections. No evidence is truncated.

## Recorded live results — 2026-10-30

- `policy_audit_report.json`: 20/20 authored violation labels matched; 17/20 met
  the confidence gate; zero provider errors. Cases 003, 005 and 014 were uncertain
  at 0.79, 0.73 and 0.69 respectively. The confidence gate therefore did not pass.
- `policy_audit_controls_report.json`: 3/4 exact expected labels; 1/4 met the
  confidence gate; zero provider errors. No control was labelled VIOLATION.
  The supplied-receipt control returned NOT_APPLICABLE instead of SUPPORTED
  (0.28 confidence). The embedded-command control returned SUPPORTED at 0.23.
- The reports retain every returned rule verdict, not just expected matches.
  Expected findings label one rule per case; other detected violations are unscored.
  These are synthetic development examples, not a held-out accuracy estimate or
  evidence of legal correctness. Confidence values are not calibrated guarantees.

This adds an auditable dataset review path, not the broad replacement described in
PC01. No default workflow strategy, shared contracts, routes, persistence or UI were
changed. Exposing this audit in the case application remains System 1 integration
work; using it as an execution gate requires further evaluation and policy review.

API contract: [official Decisions guide](https://developers.openai.com/api/docs/guides/decisions).
