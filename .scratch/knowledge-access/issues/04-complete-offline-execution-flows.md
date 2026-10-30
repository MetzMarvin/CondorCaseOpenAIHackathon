# 04: Complete the three offline flows through authoritative execution

**What to build:** Operators can demonstrate the three core flows through the existing console and synchronous case service: a clear case resolves, missing evidence prompts a question then resolves after a reply, and a serious or unsupported case reaches a specialist with context. System 1 applies accepted proposals exactly once.

**Blocked by:** 01: Resolve a supported expense using versioned synthetic knowledge; 03: Reconcile operational evidence and previous reimbursements.

**Status:** ready-for-agent

**Owners:** System 1 owns execution and reply correlation; System 2 supplies deterministic proposals and fixtures; System 3 connects existing demo controls. System 1/3 implementation belongs to those owners.

**Source coverage:** KA10 and core KA13.

- [ ] The three flows work synchronously through the agreed APIs and existing console controls with network access disabled and no model credentials. All simulated replies/payments and stored outputs are labelled in English.
- [ ] System 1 records runs and agreed progress events, validates proposals, persists effects and returns updated case details. System 2 never writes cases, sends messages or makes payments.
- [ ] Execution checks current version, ownership, permitted action, transition and financial authority. Human takeover invalidates pending AI proposals and cannot be overwritten by AI processing.
- [ ] Identical idempotency keys/payloads return the original result without repeated sends/payments; conflicting payload reuse is rejected. Intake and explicit processing cannot trigger duplicate runs.
- [ ] A customer reply updates the same case and produces a fresh snapshot; partial replies retain evidence and ask only remaining material questions.
- [ ] Failed runs preserve the case without business effects and follow System 1 recovery rules. Missing evidence or negative sentiment alone never causes handoff.
- [ ] Integration tests assert action, reason, questions, source versions and authoritative effects for all three flows, plus stale proposals, duplicate submissions, authority limits and failure recovery.
- [ ] Expected outcomes and future simulated replies remain outside runtime retrieval/model inputs. Record actual checks and unresolved owner dependencies; synthetic correctness is not legal validation.
