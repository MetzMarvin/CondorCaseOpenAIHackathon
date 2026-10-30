# 01: Resolve a supported expense using versioned synthetic knowledge

**What to build:** A supported synthetic expense case receives a typed resolution proposal backed by approved, applicable policy passages and their exceptions. Extend the existing synchronous assessment rather than introducing a second workflow. Knowledge remains separate from private case evidence.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

**Owner:** System 2. Coordinate any necessary shared contract additions with System 1.

**Source coverage:** KA06–07 and knowledge-related KA01/09 requirements.

- [ ] A local knowledge registry records source ID/version, kind, title/location, applicability, effective interval, retrieval date, approval state, content hash, passages and required exceptions. Synthetic demo approval is clearly distinguished from production legal approval.
- [ ] Invalid or duplicate versions, corrupt content and invalid date intervals fail validation. Draft, withdrawn, future-effective and irrelevant cards never become applicable knowledge.
- [ ] Retrieval filters on established applicability facts and the relevant event date before deterministic lexical ranking. Unknown applicability remains a gap; event date and retrieval date have explicit, separate semantics.
- [ ] Selected passages carry versioned references and selection reasons. Required prerequisites and exceptions cannot be dropped to fit a limit; insufficient support prevents automatic resolution.
- [ ] The current synthetic expense policy drives the existing assessment and proposal with resolvable support. No applicable rule, contradictory rules and registry failure produce distinct unsupported, UNCLEAR_RULE and FAILED outcomes as appropriate.
- [ ] Evidence requirements, source precedence, freshness and adapter outcome semantics are documented for this slice; customer claims cannot supply internal eligibility or payment controls.
- [ ] The existing process_case(request, emit_progress) interface, shared IDs/action types and progress steps remain compatible. System 2 proposes actions and never executes effects.
- [ ] Focused offline tests verify a supported resolution, date boundaries, approval filtering, unknown applicability, conflicting rules, missing exceptions and registry failure. Fixtures and customer text use English and label simulations.
