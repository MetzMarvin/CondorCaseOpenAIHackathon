# 02: Match CRM records and clarify ambiguous identities

**What to build:** A case receives sourced customer, booking and flight context after a unique authorized match. Missing or ambiguous identifiers lead to a focused customer question; a simulated reply enables a fresh assessment without exposing candidate passengers or losing earlier evidence.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

**Owners:** System 1 owns synthetic records, read adapters and snapshot assembly; System 2 owns assessment and questions. This ticket consolidates the matching work described by CRM01 rather than creating a duplicate implementation.

**Source coverage:** KA02, matching portions of KA01/03/08 and CRM01.

- [ ] A repeatable, non-destructive synthetic seed supplies stable customer, booking and individual flight IDs and versions using the agreed persistence stack. No real CRM credentials are required.
- [ ] Narrow case-authorized read adapters distinguish found, not found, ambiguous and unavailable. Shared models are reused; any minimal additions are coordinated by both owners.
- [ ] Matching verifies passenger membership and flight date/route context. Names or email alone cannot merge identities, and an ambiguous result never selects the first candidate.
- [ ] Only authorized matched records reach snapshots. Cross-case access is rejected and candidate records remain private to System 1.
- [ ] Source IDs/versions and observation times remain traceable. Customer-supplied identifiers cannot populate eligibility, financial authority or payment controls.
- [ ] Missing or ambiguous identifiers produce the minimum useful English question. A reply creates a fresh case-version snapshot and retains earlier valid evidence; no match alone causes denial or handoff.
- [ ] Adapter outages produce a visible technical failure without a business proposal, distinct from successful lookup with no records.
- [ ] Focused offline tests cover unique and unknown bookings, duplicate names/shared email, recurring flight numbers, incorrect passenger membership, conflicting identifiers, ambiguity resolved by reply, unavailable adapters and cross-case rejection.
