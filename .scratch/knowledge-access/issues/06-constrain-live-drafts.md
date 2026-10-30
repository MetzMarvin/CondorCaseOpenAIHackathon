# 06: Constrain live drafts to supported evidence and policy

**What to build:** Optional live expert drafting produces customer text grounded in authorized case facts and selected approved passages while preserving the deterministic recommendation. Unsupported or invalid model output fails visibly instead of becoming an automatic resolution or a silent simulated fallback.

**Blocked by:** 01: Resolve a supported expense using versioned synthetic knowledge; 03: Reconcile operational evidence and previous reimbursements.

**Status:** ready-for-agent

**Owner:** System 2; coordinate only necessary shared interface additions with System 1.

**Source coverage:** Remaining KA09 and fake-model acceptance cases from KA13.

- [ ] Bounded context contains necessary sourced facts, unresolved gaps, applicable policy passages/exceptions, permitted actions and the validated deterministic recommendation. It excludes unrelated personal data, secrets, arbitrary attachment paths and other cases' evidence.
- [ ] Required evidence and exceptions cannot silently disappear to satisfy context limits; insufficient context support prevents resolution.
- [ ] Output conforms to shared run/proposal models and preserves case/run/action identity, expected version, action type, amounts/currency, material questions and authority limits.
- [ ] Citation validation checks passage existence and substantive support for the relevant fact or rule, not source-ID membership alone. Unresolved support prevents automatic resolution.
- [ ] Drafts cannot invent entitlement/denial or claim that a message/payment was executed before System 1 accepts the action.
- [ ] Malformed output, refusal, unsupported claims and provider failures produce technical failures without a business proposal. Credentials/model calls stay on the backend; offline simulation remains explicit and usable independently.
- [ ] Fake-model tests cover invented citations, irrelevant supporting passages, altered amounts/actions, omitted questions, unsupported legal claims, premature execution claims, context overflow, malformed responses, refusal and provider failure. Tests need no live provider credentials.
