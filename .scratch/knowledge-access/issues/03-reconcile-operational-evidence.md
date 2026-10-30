# 03: Reconcile operational evidence and previous reimbursements

**What to build:** A matched case is assessed against authoritative operational evidence and reimbursement history. Supported expenses can proceed, while unknown internal facts, previous payments and material conflicts prevent unsupported or duplicate reimbursement proposals.

**Blocked by:** 02: Match CRM records and clarify ambiguous identities.

**Status:** ready-for-agent

**Owners:** System 1 supplies authoritative operational/payment records and version-consistent snapshots; System 2 reconciles evidence and chooses proposals. Consolidate the operational work already described by CRM01.

**Source coverage:** Remaining KA03 and operational KA08 requirements.

- [ ] Operational facts include sourced flight timing, operating carrier, disruption/notification evidence and reasonable measures where available. Unknown values remain unknown; a cause label alone cannot establish a legal defense.
- [ ] Reimbursement history is scoped to claimant and expense and distinguishes unpaid, paid, partially paid, unknown and unavailable states. Amounts use integer minor units and explicit currency.
- [ ] Eligibility controls remain explicitly synthetic and authoritative. Customer text cannot override internal facts, financial authority or payment history.
- [ ] Source versions, observation times and freshness requirements are traceable. Evidence changes require a fresh case-version snapshot; assessment does not mutate snapshots.
- [ ] Missing internal facts trigger internal enrichment. Unobtainable required data remains a visible failed run under the existing internal-evidence behavior, never a customer question about airline records.
- [ ] Prior/partial payments require reconciliation before another reimbursement proposal; an unpaid balance is never inferred without support.
- [ ] Conflicting values and provenance survive assessment. Customer clarification asks only material unanswered questions; unresolved material conflicts carry a concrete handoff explanation and prior clarification context.
- [ ] Offline tests cover supplied, absent, stale, conflicting and unavailable operational records, prior/partial reimbursement and preservation of earlier evidence. Missing evidence, anger or silence alone never causes handoff.
