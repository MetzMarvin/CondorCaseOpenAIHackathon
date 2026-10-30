# 07: Inspect reproducible decision sources in the console

**What to build:** Operators can inspect the evidence and knowledge versions behind a stored run, understand its question or handoff reason, and distinguish a technical failure from a business outcome. The view remains useful without model access and does not expose raw customer documents in progress events.

**Blocked by:** 04: Complete the three offline flows through authoritative execution.

**Status:** ready-for-agent

**Owners:** System 2 produces safe manifests; System 1 owns persistence and scoped read access; System 3 displays results exclusively through System 1 APIs.

**Source coverage:** KA11–12 for the supplied-fact path.

- [ ] A persisted manifest identifies input case version, evidence versions, selected knowledge versions, relevant configuration versions, simulation mode and concise decision reasons.
- [ ] Agreed event step IDs are reused, with references rather than raw document text or personal details. Storage location, access scope and retention behavior are explicit; internal manifests do not silently redefine public event contracts.
- [ ] Callback and persistence failures remain visible without fabricated success. Safe error categories and retryability information survive storage and retrieval.
- [ ] The console distinguishes customer claims, authoritative records and synthetic policy assumptions, and displays known/missing/conflicting evidence plus reasons for questions and handoffs.
- [ ] Permitted policy passages and source IDs/versions are available through scoped System 1 reads. Links expose neither arbitrary filesystem paths nor other passengers' information.
- [ ] Simulations and replay are labelled; proposed actions are visually distinct from executed effects. Human takeover and action authority stay with System 1.
- [ ] Manifest round-trip, sensitive-content exclusion and callback/persistence failure tests pass. UI fixtures exercise the three core flows, missing sources and technical failures without requiring document extraction or live drafting.
- [ ] Open any created/updated HTML visualization in the user's browser and provide its link; report clearly if opening is unavailable.
