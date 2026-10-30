# System 2 routing stage handoff

Date: 2026-10-30. Stage: core AI routing implemented; end-to-end integration outstanding at this checkpoint.

System 2 can propose customer clarification, specialist handoff or a supported demo reimbursement from a structured case snapshot. Technical failures return failed runs without business proposals. The next stage is to connect these decisions to intake, case persistence and the operations console, while retaining the synchronous demo scope.

The [subsystem agreement](../architecture/subsystems-and-contracts.md) remains authoritative. This handoff introduces no shared contract changes.

## Delivered in this stage

- Targeted English customer questions for missing or unreadable evidence; partial replies retain supplied answers and ask only for remaining facts.
- Clarification of conflicting customer evidence, followed by specialist escalation when a material conflict remains unresolved.
- Handoff reasons for serious issues, legal uncertainty, unsupported actions and insufficient authority, with facts, sources and prior attempts.
- Expense reimbursement proposals gated by sourced eligibility, reimbursement history and financial authority.
- Separate failed-run outcomes for technical and internal-evidence problems.
- Ten deterministic demo scenarios and stored outputs for use without model access.

The last completed validation run at this checkpoint passed 46 tests, including mocked-provider tests. This establishes module behavior, not end-to-end deployment or live-provider validation.

## Outstanding work for the integration stage

| Work | Owner | Completion check |
|---|---|---|
| Turn incoming messages and case-scoped attachments into structured issues, facts and missing-information entries | System 1 provides intake and read-only evidence access; System 2 owns evidence assessment | A simulated message/upload produces a valid snapshot with resolvable source references; no arbitrary file access or cross-case evidence |
| Supply internal eligibility and payment-history checks | System 1 supplies authoritative context; System 2 applies the demo decision rules | Sourced `expense_eligibility = "eligible"` and `payment_history = "no_prior_reimbursement"` are available for a clear expense case; missing internal evidence never becomes a customer question |
| Persist runs and progress, validate proposals and apply business actions | System 1 | A clarification records one simulated outbound message and waits for the customer; a resolution records its simulated reply/payment; a handoff updates ownership/queue |
| Correlate customer replies and reassess the same case | System 1, with System 2 processing the new snapshot | A partial reply asks only the remaining question; complete evidence resolves the same case with an increased version |
| Map specialist handoffs to operational teams | System 1 configures routing; System 3 displays it | Explicit mapping exists for legal review, safety, payment approval and other specialist handling; no external authority is contacted implicitly |
| Enforce ownership, version and idempotency at execution | System 1 | Duplicate requests do not duplicate messages/payments; takeover invalidates a pending AI proposal; human ownership is preserved |
| Connect the operations console | System 3 through System 1 APIs | Operators can inspect questions, reasons, evidence, run failures and history; simulate replies; take over and complete a case |
| Exercise the integrated demo | All three systems | Clear case resolves; missing evidence prompts a question then resolves after reply; serious/unsupported case reaches a human with context |

All current AI handoffs suggest `demo-specialists`. Distinct operational queues have not been introduced by this stage. A handoff summary is internal context, not a customer notification.

The fact vocabulary and setup are documented in the [System 2 integration guide](../../README.md#system-2-integration). System 1 must deliberately populate internal control facts; customer statements cannot grant eligibility, authority or a completed internal check.

## Deliberate limits for this stage

- Automatic resolution covers the synthetic expense-reimbursement policy. Flight disruption, denied boarding, baggage and general service claims can collect evidence, then hand off for adjudication.
- A complete EU261 or Montreal entitlement calculator is not implemented. Approved rules, applicable dates, evidence requirements and reviewed reference cases are prerequisites for expanding automatic legal decisions. See the [legal and failure-mode catalogue](../research/airline-legal-checks.md).
- The deterministic router does not classify raw message text or read attachment contents. It consumes structured snapshots; model-assisted review does not replace the missing evidence adapter.
- Reminder scheduling and automatic closure on silence are outside this stage. Missing evidence, anger, silence or message count alone must not cause rejection or handoff.
- Real customer messaging, payments, production authentication and additional channels remain outside the hackathon demo.

## Next-stage order

1. Agree the System 1 snapshot mapping, evidence references and specialist queue mapping.
2. Wire synchronous processing, result persistence and validated action execution.
3. Connect the console and demonstrate the three core flows, duplicate submission and human takeover.

Retain stored outputs as the offline demo path. Broader legal automation can follow after the integrated core flows work.
