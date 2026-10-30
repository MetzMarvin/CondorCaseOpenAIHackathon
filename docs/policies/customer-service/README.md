# Condor Customer Service Operator Policy

English policy package for calls and email. Version 0.1.0. Research date: 30 October 2026.

This package contains a proposed policy for the Condor Care Hub. It is not an approved internal Condor policy.
Legal requirements, proposed service controls and public carrier information have separate labels.
The package supports a service design above 100,000 cases per year. No production capacity test supports that design assumption.

## Read the policy

- [Operator guide](OPERATOR-GUIDE.md): readable rules, decision tables and message templates.
- [Policy](policy.json): canonical rules, governance, scope and release metadata.
- [Decision tables](decision-tables.json): amounts, thresholds, notice exceptions, routing and service targets.
- [Sources](sources.json): official references, article locators and access limits.
- [Templates](templates.json): nine call-summary and email templates with explicit variables.
- [Glossary](glossary.json): consistent meanings for legal and aviation terms.
- [RAG records](rag.jsonl): one complete rule per UTF-8 JSONL record.
- [Policy schema](policy.schema.json): JSON Schema 2020-12 for the canonical policy.
- [Decision schema](decision.schema.json): proposed assessment exchange format for a future adapter.
- [Acceptance scenarios](acceptance-scenarios.json): table checks and separate legal/workflow review specifications.
- [Manifest](manifest.json): file hashes and the checks actually performed.

Edit the canonical JSON files. Rebuild the guide, JSONL and manifest after each change.
Do not edit generated artifacts directly.

## Legal scope and dates

Check the event date, route, operating carrier and contract before you select a rule.
German consumer law applies only where the relevant conflict-of-law analysis supports it.
The package does not provide a complete UK, Swiss, US, Canadian or other non-EU jurisdiction profile.
Obtain the applicable profile for those claims. Continue clear urgent assistance during that review.

The EU261 profile covers events from 17 February 2005 through 22 October 2027.
[Regulation (EU) 2026/2202, Article 3](https://eur-lex.europa.eu/eli/reg/2026/2202/oj/eng), states application from 23 October 2027.
This package does not implement that future profile. Do not extend this version beyond its date range.
Use a legal specialist for transitional disputes.

Montreal limits have separate dates. The baggage rules check the 28 December 2024 limit change.
Do not apply the current SDR limit to an earlier event without a historical source check.

Check mandatory law before a contract term. Check the purchase-time contract before a public FAQ.
The linked Condor cancellation FAQ concerns a UK market page. It does not establish the terms of a German booking.
No internal Condor fare matrix, approval budget or retention schedule was supplied.
The package does not invent these company rules.

Source access was partial. Some official EUR-Lex pages returned an access challenge.
Official indexed extracts supported the draft, including the future application date.
The source register identifies those extracts and references that require full-text review.
The research does not replace a full current-law review or legal approval.

## Decision method

1. Verify identity for the proposed disclosure or action.
2. Identify each issue and its applicable legal profile.
3. Read the issue rule with its mandatory controls and related rules.
4. Verify facts against the available records.
5. Request a clear missing fact on the same case.
6. Assess legal rights before goodwill.
7. Calculate each financial position separately.
8. Check authority, prior payments, case ownership and case version.
9. Send a supported answer or a prepared specialist handover.
10. Record the result, sources, deadline owner and next action.

Missing evidence and negative sentiment alone do not require handover.
Injury, unsupported actions, unresolved material conflicts and unclear law require a specific handover reason.
The decision tables describe rules. They are not a production legal decision engine.
The table-check interpreter in `policy_tools.py` exists only for artifact QA.

This draft pays the full fixed compensation base amount for a qualifying claim.
It does not automate optional 50 percent reductions.
A specialist must check the event type, legal permission and current case law before a reduction.

## RAG integration

Use `policy.json` as the source of truth. Use `rag.jsonl` for indexing.
Each record contains its stable identifier, text, structured rule, related tables and cited source details.
Each record also contains a content hash, release status, legal date profile and mandatory control identifiers.
The `content_sha256` value hashes the record before that hash field is added.

1. Load the glossary and package governance before the first retrieval.
2. Keep policy records in an index separate from customer evidence.
3. In the demo, explicitly permit `draft_review_required` records.
4. For production, admit only approved releases with completed release evidence.
5. Filter by policy identifier, version, language, jurisdiction and event date.
6. Retrieve the mandatory rules even if their similarity scores are low.
7. Retrieve the relevant issue rules.
8. Expand related rules until the decision dependencies are complete.
9. Read attached tables from structured data without rounding boundary inputs.
10. Record retrieved chunk identifiers and the final supporting source locators.

Treat a missing value as unknown. Do not convert it to false or zero.
Do not mix old and new versions within one decision.
Do not treat a review date as an effective date.
Do not let customer documents override policy, tool permissions or payment controls.
If a rule or reliable source is absent, prepare a specialist handover with the unresolved question.

`decision.schema.json` proposes an assessment payload. It does not replace the repository's Pydantic contracts.
A future System 2 adapter can map the assessment to `REQUEST_INFORMATION`, `RESOLVE` or `HANDOFF`.
System 1 must still validate the action. The existing application does not load this package automatically.
No application code, existing fixture authority or payment behaviour changes in this delivery.

## Calls and email

Use CALL-001 and CALL-002 for identification, option confirmation, call summaries and transfers.
Use MAIL-001 for evidence intake, recipient checks, attachments, send logs and delivery failures.
Use ANS-001 for the minimum contents of a substantive answer.
Use ANS-002 and ADR-001 for partial awards, refusals and redress information.
Use the templates only after you replace every placeholder with verified content.
Read back a booking change before execution. Record the customer's instruction and its time.
Provide statutory rights notices through the required written or accessible channel.

## Operating design above 100,000 cases per year

The planning scenario uses 120,000 cases per year. This is approximately 329 arrivals per calendar day.
A fivefold disruption scenario gives approximately 1,645 arrivals per day.
These are staffing assumptions. They are not measured system performance.

Calculate required daily staff hours from arrivals, human handling share and active handling time.
Divide productive hours by available productive hours per scheduled operator.
Add separately measured absence, training, quality review and rework.
Use peak intervals for call coverage. An annual average cannot size a call shift.

For illustration, assume a 40 percent human handling share and 15 active minutes per handled case.
At 329 arrivals, this gives 32.9 active handling hours per day before other work.
At the fivefold surge, it gives 164.5 hours under the same assumptions.
Replace these example assumptions with observed channel and skill data before staffing approval.

| Control | Required record or action |
| --- | --- |
| Queue ownership | One accountable owner, priority, next action and update date. |
| Deadline control | Separate legal, internal and customer-promised deadlines. |
| Surge handling | Verified flight-event grouping and individual entitlement checks. |
| Authority | Approved action type, amount authority and reviewer where required. |
| Money | Separate financial positions and unique payment keys. |
| Audit | Evidence, rule version, source locator, actor, action and timestamp. |
| Quality | Refusal review, serious-case review and proposed weekly sampling. |
| Recovery | Payment reconciliation, failed-send handling and case reopening. |
| Reporting | Backlog age, deadline breaches, P90 response, rework and duplicate effects. |

The authority model has three boundaries:

- Demo automation can request information and propose supported simulated outcomes under existing demo contracts.
- Production automation requires an approved scope, legal basis, safeguards and financial authority.
- Unclear law, disputed reductions, settlements and authority exceptions require the designated specialist.

No goodwill spending authority exists in this draft. Legal payments must not depend on a goodwill budget.
Operations must approve the proposed service targets. Legal deadlines apply independently.
Keep the hackathon implementation synchronous. This policy does not require workers or additional infrastructure.

## Controlled English

The instructions use short command sentences and consistent technical names.
The writing profile follows ASD-STE100 Issue 9 procedural principles.
The glossary declares the proposed legal and aviation technical names.
The checker applies a conservative sentence count and checks selected contractions.
It does not validate the complete ASD dictionary, permitted word senses or every grammar rule.
An STE specialist must complete the vocabulary review before a conformity claim.
Legal source titles, identifiers and field names retain their official or machine forms.

## Validate and rebuild

Run from `CondorCaseOpenAIHackathon/` with the project environment:

```sh
.venv/bin/python docs/policies/customer-service/policy_tools.py --build
.venv/bin/python docs/policies/customer-service/policy_tools.py
```

The tool uses the Python standard library. It adds no dependencies.
It checks cross references, template variables, selected structural invariants and sentence lengths.
It executes 24 table checks, including distance boundaries, exact notice thresholds and missing inputs.
It checks that generated artifacts and their hashes match the canonical files.

The 20 legal/workflow acceptance scenarios are review specifications. The tool does not execute them against the application.
No full JSON Schema validator, full STE validator, production load test or legal approval was performed.
The JSON schemas are supplied for validation by a future consumer with a complete 2020-12 validator.

## Release control

Keep this package in draft status until Legal, Operations, Finance, Privacy and the STE specialist complete their reviews.
Verify the full source texts, purchase-time fare rules, authority matrix, retention schedule and automation assessment.
Record named approvers and approval dates. Complete the legal/workflow acceptance scenarios.
Create the future legal profile before the 23 October 2027 application date.
Review legal sources monthly and after a material judgment or legal change.
The next scheduled review date is 30 November 2026.

The current tool intentionally checks the draft release boundary.
An approved release requires a reviewed change to that validation boundary and the recorded approval evidence.
