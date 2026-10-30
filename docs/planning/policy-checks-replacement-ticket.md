# PC01 Replace general expert approval with explicit policy checks

Status: Open repository ticket, not published to an issue tracker.
Priority: P0 for evaluation; runtime replacement follows the acceptance gate.
Owner: System 2. System 1 owns execution checks and any new internal evidence adapters.

Replace the two general support reviews in `backend/ai_service/experts.py` with a versioned checklist derived from 20 existing policy rules. Use Python for exact constraints and evaluate OpenAI Decisions API for questions that require interpretation. Compare the replacement with the current experts on the same evidence before changing the default processor.

The selection below comes from `CONDOR-CS-EN` version `0.1.0` in [policy.json](../policies/customer-service/policy.json). That package is `draft_review_required`, not approved Condor policy. Implement and evaluate it only in an explicitly enabled synthetic demo mode. This ticket does not approve legal rules or enable real payments.

## Source documents

- [Policy package and integration instructions](../policies/customer-service/README.md)
- [Canonical rules](../policies/customer-service/policy.json), selected by stable `rule_id`
- [Decision tables](../policies/customer-service/decision-tables.json), for exact boundaries and calculations
- [Source register](../policies/customer-service/sources.json), for authority and source locators
- [Acceptance specifications](../policies/customer-service/acceptance-scenarios.json)
- [Subsystem agreement](../architecture/subsystems-and-contracts.md), authoritative for interfaces and ownership

## First 20 policy rules

Include all nine rules listed in the package's `mandatory_rule_ids`, then 11 issue and escalation rules. These are 20 parent rules, not 20 indivisible yes/no questions. Split each rule into observable checks where needed, retaining its parent ID. The check focus below is an implementation starting point; it does not replace the complete rule text, exceptions or dependencies.

“Hybrid” means the model assesses interpretation from supplied evidence and code enforces the resulting constraints. Model answers cannot override a failed deterministic check.

| # | Rule ID and source title | Initial check focus | Method | Required regression example |
|---|---|---|---|---|
| 1 | GOV-001 Apply the correct authority | Preserve authority order; flag conflicting sources; never treat draft text as approved policy. | Hybrid | A company budget cannot erase a supported entitlement. |
| 2 | GOV-002 Select the policy by event date | Require event date and an applicable version; distinguish review date from effective date. | Python | A future profile cannot be applied early; historical baggage events need historical limits. |
| 3 | INT-002 Check identity and representative authority | Require action-specific identity and payee/representative authority from trusted records. | Python gates | A booking reference alone cannot authorize a financial change. |
| 4 | INT-003 Classify all issues | Identify separate claim items; preserve compensation, refund, expenses and goodwill; exclude sentiment from entitlement. | Hybrid | An angry mixed claim gets separate assessments, not automatic handoff. |
| 5 | EVID-001 Request only missing evidence | Consult internal records first; request only necessary customer-held gaps; retain the same case. | Hybrid | Do not request an already supplied receipt or ask the passenger for airline operational proof. |
| 6 | TIME-001 Preserve separate legal deadlines | Select the deadline basis and trigger; keep legal and service deadlines distinct. | Hybrid | A customer reply or service-target expiry does not restart or extinguish a legal deadline. |
| 7 | FIN-001 Control refunds and payments | Verify payee, amount/currency, authority, prior payments and voucher consent; preserve payment state. | Python; System 1 enforcement | A paid claim cannot be paid again; submitted is not settled; silence is not voucher consent. |
| 8 | AI-001 Control automated decisions | Permit only supported, tested demo actions on verified facts; preserve simulation labels and human-review paths. | Python gates | Missing facts or anger alone cannot force handoff; draft permission cannot authorize production. |
| 9 | RAG-001 Retrieve rules with authority and date filters | Pin release/version/language, load mandatory controls, expand dependencies and retain source locators. | Python | Low similarity must not drop a mandatory exception; reject mixed versions. |
| 10 | EU-001 Check EU261 scope | Establish route, carrier, reservation and applicable presentation requirements before adjudication. | Hybrid | Missing scope is unknown, not an automatic denial; cancellation must not require check-in. |
| 11 | EU-002 Check connections and carrier responsibility | Use operating carrier, ticket contracts and final destination; distinguish separate tickets. | Hybrid | Agency sale alone cannot invalidate a claim; do not sum connecting segment distances. |
| 12 | CAN-002 Check cancellation compensation exceptions | Check passenger receipt of notice and table boundaries; assess the extraordinary-circumstances defense separately. | Hybrid | Notice to an intermediary is not proof of passenger receipt; absent proof cannot establish an exception. |
| 13 | DEL-002 Assess arrival delay compensation | Use the specified arrival event at the final destination and exact delay thresholds. | Hybrid | Touchdown cannot substitute for door opening; test one second below and exactly at the threshold. |
| 14 | COMP-001 Calculate fixed compensation | Calculate per eligible passenger from structured tables; separate other payments; preserve the draft's full-base rule. | Python | Receipt totals cannot determine fixed compensation; no automatic discretionary reduction. |
| 15 | EXC-001 Check extraordinary circumstances with evidence | Assess actual event, causation and reasonable measures; keep unrelated rights independent. | Model interpretation plus gates | A generic WEATHER label cannot justify a final refusal. |
| 16 | CARE-001 Provide care during a covered disruption | Establish care duty, waiting needs and remedy choice; assess care independently of compensation defenses. | Hybrid | Proven extraordinary circumstances must not automatically remove care. |
| 17 | EXP-001 Reimburse necessary care expenses | Check each item's duty, amount, currency, date, purpose, reliable proof and prior provision/payment. | Hybrid | Separate supported and disputed expenses; missing advance approval alone cannot reject an expense. |
| 18 | BAG-001 Open a baggage incident and preserve deadlines | Distinguish delay, damage and loss; use availability/receipt and complaint-dispatch timestamps. | Hybrid | Do not start a delayed-baggage complaint clock at flight departure or substitute the damage deadline. |
| 19 | BAG-002 Assess baggage damages | Assess proven loss and applicable limits, exceptions, passenger count and dated conversion basis. | Hybrid | A liability ceiling is not a flat payment, not per bag, and not a permanent EUR amount. |
| 20 | ESC-001 Hand over for a specific reason | Require a supported reason and concrete specialist context, evidence, gaps and urgency. | Hybrid | A missing receipt alone cannot trigger handoff; a serious report can require specialist review. |

The selection prioritizes existing expense flows and disruption/baggage test data. Other issue rules remain outside the first evaluation cohort. Do not claim complete policy coverage from these 20 rules.

## Dependencies and applicability

Load all mandatory controls explicitly before semantic retrieval. Expand `related_rule_ids` transitively with cycle detection and deduplication, within one release. Preserve complete attached decision tables and cited source details. If required support exceeds the context budget, report incomplete support; do not silently truncate it.

The 20 selected parents have dependencies outside this list, such as CAN-001, REF-001, OPS-003, SER-001, RAG-002 and PRIV-001. The selection limits the initial scored cohort, not the evidence required to interpret it. Produce a dependency manifest distinguishing selected parents from supporting rules. A dependent rule without an implemented check must not silently count as passed; restrict the supported action scope or require specialist review where substantive interpretation remains unresolved.

Treat unknown facts as unknown. A rule can be NOT_APPLICABLE only when the evidence establishes that its trigger does not apply. Separate missing customer evidence, missing internal evidence, source ambiguity and technical retrieval failures.

## Implementation

1. Create a System 2 policy-check registry. For each atomic check record parent rule ID/version, check ID, trigger, required facts and their trusted origin, dependencies, method, permitted answers, blocking effect and test IDs. Hash the policy release and check configuration.
2. Implement Python checks for dates, amounts, currency, table boundaries, version consistency, trusted authority inputs and action permissions. Use policy tables directly; do not ask a model to calculate these values.
3. Add a backend-only Decisions API adapter for interpretive checks. Supply the applicable complete rule bundle and scoped evidence. Use explicit choices: SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE, NOT_APPLICABLE. Ask independent questions together; evaluate dependent questions in later stages. Handle refusals and provider errors separately from policy verdicts. Follow the [official Decisions API guide](https://developers.openai.com/api/docs/guides/decisions).
4. Retain a trace per check: rule/check/version, result, evidence references, source locators, evaluator version and blocking reason. Bind decisions to the evidence bundle supplied. If a rationale or evidence selection is produced by a separate model call, label and validate it separately; do not imply the Decisions API supplies a verified explanation.
5. Aggregate checks in code. Mandatory failures cannot be overridden by a majority, average score or confident model answer. Missing customer facts produce a clear information request. Missing internal data uses a narrow internal adapter or an explicit failed-run result where no adapter is available. Genuine ambiguity or unsupported actions produce the agreed reasoned handoff. Technical errors remain failed runs.
6. Map to existing shared RunResult and proposed action models through the synchronous `process_case(request, emit_progress)` boundary. Preserve the offline workflow and stored demo outputs. Replace only the general expert approval stage after the evaluation gate; communication drafting remains separate.

System 2 never executes payments, sends messages or changes case state. System 1 must independently enforce current ownership/version, permissions, financial authority and idempotency at execution. Any new evidence field, persisted trace or adapter requires a coordinated System 1 change; this ticket does not silently extend shared contracts. System 3 UI work is outside scope.

## Evaluation and replacement gate

Use existing policy acceptance specifications, the LEGAL test cases in `data/examples/legal-checks/`, and the three deterministic demo flows. Inspect their actual facts and expected behavior before adapting them. The policy specifications and legal expectations are synthetic and unreviewed; keep them labeled and separate from approved payout authority.

- For every atomic check add applicable supported, contradicted, missing-evidence and not-applicable examples where meaningful. Cover exact boundaries, contradictory evidence, missing dependencies and customer instructions attempting to override policy.
- Make claim-level expected checks, outcomes, amounts and routing independent of the processor. Never derive gold answers from the candidate model or feed evaluation labels/future replies into its context.
- Map existing scenarios including FLOW_CLEAR, FLOW_EVIDENCE, FLOW_SERIOUS, ANGER_ONLY, GENERIC_WEATHER, WEATHER_WITH_CARE, ARRIVAL_EXACT_3H, ARRIVAL_BELOW_3H, AGENCY, VOUCHER_SILENCE, DUPLICATE_PAYMENT, BAGGAGE_LIMIT, BAGGAGE_OLD_DATE, FUTURE_LAW and PAYMENT_PENDING. Add explicit coverage for selected rules without adequate existing examples.
- Freeze a development set and a separate holdout set before tuning. Run both the current experts and the replacement on identical snapshots, proposals and retrieved support. Include bad proposals with correct-looking citations so citation copying cannot pass the benchmark.
- Report per-check and per-parent results, false acceptance, false rejection, missing-evidence handling, unsupported conclusions, citation validity, final action/financial correctness, provider errors, latency and cost. Report denominators and missing coverage. API errors and malformed outputs never count as correct rejection.
- All deterministic checks and three offline demo flows must pass. Require zero false acceptance on the frozen critical-control fixtures (identity, duplicate payment, authority, version and unsupported financial award). The replacement must not regress supported-case acceptance or information-request/handoff correctness on the shared holdout, and must improve at least one predeclared failing metric. Report finite-sample results without implying a general guarantee.
- Keep the current default if the gate fails or no live comparison exists. Use an explicit configuration switch for the candidate and preserve rollback. Human policy review and release evidence remain necessary before production approval.

## Deliverables and definition of done

- Versioned registry covering exactly these 20 parent rules, their atomic checks and complete dependency manifest.
- Deterministic evaluators, Decisions API adapter and code-based aggregation with focused tests.
- Reviewed mappings from available test data to expected check and action outcomes.
- Reproducible baseline/candidate report with policy, prompt, model and dataset versions, coverage and measured replacement-gate results.
- Offline stored outputs supporting the clear, evidence/reply and serious-case flows without model access.
- Documented configuration, failure behavior, rollback and separately assigned System 1 integration dependencies.

Creating this ticket does not implement or approve the replacement. The existing expert-review benchmark is useful baseline scaffolding, but its demo-only counterfactual cases do not by themselves establish coverage of these 20 draft-policy rules.
