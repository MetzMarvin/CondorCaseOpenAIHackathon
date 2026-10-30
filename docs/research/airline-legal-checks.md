# Airline complaint failure cases and legal checks

Research date: 2026-10-30. Scope: System 2 planning for a synthetic German-language demo.
This is a proposed scenario catalogue and source checklist, not an implemented legal engine or legal approval.
The [subsystem agreement](../architecture/subsystems-and-contracts.md) remains authoritative for interfaces.

## Current implementation versus proposed coverage

At inspection, `backend/ai_service/workflow.py` supports only `expense_reimbursement` under synthetic `demo-expense-policy` v1.
It checks supplied receipt amount/currency, evidence references, conflicts, serious injury/safety, supported issues and execution authority.
It does not establish EU261 entitlement, validate actual receipts, calculate flight distance, interpret Montreal claims or implement GDPR compliance.
The scenarios below are design proposals; their legal checks require approved, versioned knowledge and additional evidence before automation.
No new action, status, queue contract or handoff reason is introduced here.

## Decision rules for the proposed catalogue

- Resolve only supported, evidenced issues within the snapshot's permitted actions and financial authority.
- Request information when a specific relevant fact is missing and the customer can reasonably supply it.
- Obtain operational facts through System 1's snapshot/read-only adapter: disruption cause, carrier records, notification logs, actual arrival and prior payments.
- Missing operational data is not a reason to ask customers to prove airline internals. An unavailable adapter is a technical failure; genuinely unsupported investigation can justify `UNSUPPORTED_ACTION` with a concrete explanation.
- Missing evidence, anger, silence, multiple supported issues or retry count alone never justify handoff or rejection. Waiting is orchestration behavior, not a fourth business action.
- Hand off only a concrete serious issue, unsupported action, unresolved material conflict, unclear rule or authority limit.
- Technical errors return `FAILED` with no proposal. The agreement's `TECHNICAL_FAILURE` reason does not turn exceptions into invented business handoffs.
- System 1 alone applies actions, preserves human ownership, rejects stale versions and prevents duplicate payments/messages.

## Proposed customer follow-up scenarios

All rows assume the underlying issue is supported; otherwise identify the actual unsupported capability.

| # | Situation | Proposed behavior | Evidence needed / question focus |
|---|---|---|---|
| 1 | Booking cannot be uniquely matched | `REQUEST_INFORMATION` | Booking reference or flight/date; avoid unnecessary identity documents |
| 2 | Receipt missing | `REQUEST_INFORMATION` | Itemized receipt or relevant alternative evidence |
| 3 | Receipt photo illegible | `REQUEST_INFORMATION` | Clear image of the relevant amount/date; distinguish this from parser outage |
| 4 | Amount or currency ambiguous | `REQUEST_INFORMATION` | Original amount and currency; never guess conversion |
| 5 | Expense purpose unclear | `REQUEST_INFORMATION` | What was purchased and how it relates to disruption |
| 6 | Several passengers; claimant authority unclear | `REQUEST_INFORMATION` | Who is claiming and relevant representation evidence |
| 7 | Baggage damage/return timeline absent | `REQUEST_INFORMATION` | Receipt/return date, discovery date and written complaint evidence |
| 8 | Cancellation choice not stated | `REQUEST_INFORMATION` | Refund or rerouting preference, where legally relevant |
| 9 | Customer says expense already partly refunded | `REQUEST_INFORMATION` plus internal reconciliation | Relevant amount/provider; check System 1 payment records |
| 10 | Reply answers only one of two questions | `REQUEST_INFORMATION` | Ask only the remaining material question; retain supplied facts |

## Proposed specialist scenarios

| # | Situation | Existing reason code | Context to transfer |
|---|---|---|---|
| 11 | Serious injury or credible safety incident | `SERIOUS_ISSUE` | Event, urgency and evidence references; avoid routine settlement |
| 12 | Alleged discrimination or serious accessibility failure | `SERIOUS_ISSUE` | Specific alleged conduct and requested remedy |
| 13 | Credible threat requiring safety handling | `SERIOUS_ISSUE` | Concrete threat and context; ordinary angry language is insufficient |
| 14 | Court papers or represented dispute outside demo capability | `UNSUPPORTED_ACTION` | Document/deadline references and previous correspondence |
| 15 | Applicable legal regime genuinely unresolved | `UNCLEAR_RULE` | Route, operating carrier, event date and competing rules |
| 16 | Extraordinary-circumstance defense remains legally uncertain after evidence collection | `UNCLEAR_RULE` | Cause, causal link, reasonable measures and missing legal interpretation |
| 17 | Material evidence conflict persists after clarification | `UNRESOLVED_CONFLICT` | Both versions, provenance and attempted reconciliation |
| 18 | Required financial amount exceeds authority | `AUTHORITY_LIMIT` | Supported entitlement and exact authority gap; never reduce entitlement to fit budget |
| 19 | Rerouting/rebooking or package-travel remedy unsupported | `UNSUPPORTED_ACTION` | Requested remedy and itinerary; no invented booking confirmation |
| 20 | Privacy/access/deletion request outside complaint workflow | `UNSUPPORTED_ACTION` | Minimal request context to the appropriate human function |

## Proposed technical and orchestration scenarios

These are not customer blame or business denials; preserve state and allow controlled recovery.

| # | Situation | Expected behavior | Owner / distinction |
|---|---|---|---|
| 21 | Evidence adapter times out | `FAILED`, no proposal | System 2 reports technical error; System 1 manages retry |
| 22 | Attachment parser crashes | `FAILED`, no proposal | Different from genuinely unreadable customer evidence (#3) |
| 23 | Model unavailable or output invalid | Validated stored simulation if explicitly configured; otherwise `FAILED` | Never fabricate successful business assessment |
| 24 | Policy source missing or corrupt | `FAILED`, no proposal | Infrastructure/data availability; valid policy ambiguity is #15 |
| 25 | Progress callback raises | `FAILED`, no proposal | No simulated send/payment from a partial run |
| 26 | Cross-case attachment reference detected | Stop access; `FAILED`, no proposal | System 1 scoped access; no path expansion or other-case disclosure |
| 27 | Human takeover during run | Reject obsolete AI action | System 1 version/owner validation; human ownership wins |
| 28 | Same request/action arrives twice | Original result; no duplicate effects | System 1 idempotency; different payload with same key conflicts |
| 29 | Customer remains silent or sends another angry message | Preserve waiting or reassess relevant new evidence | No automatic denial/handoff based on silence, tone or count |
| 30 | Flight cause/arrival record missing internally | Request internal enrichment before entitlement assessment | Adapter failure → failed run; no customer question about airline internals |

## Legal source checklist

These are selected legal requirements and interpretation checks, not an exhaustive jurisdiction analysis.
Record event date and source version separately from retrieval date.

| Check | Selected rule / verification point | Primary official source |
|---|---|---|
| Effective date | Regulation 2026/2202 amends EU261 and 2027/97; Article 3 specifies application from **23 October 2027**. Do not apply its future rules to the October 2026 demo merely because adopted. | [Official Journal text and dates](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=OJ%3AL_202602202) |
| EU261 scope | Check departure/arrival, operating carrier, reservation and check-in conditions. EU departures and qualifying EU-carrier inbound flights have different scope tests. | [EU261 Articles 2–3](https://eur-lex.europa.eu/eli/reg/2004/261/oj/eng) |
| Cancellation | Check notice timing and offered rerouting before compensation; reimbursement/rerouting and care are separate rights. | [EU261 Articles 5, 8–9](https://eur-lex.europa.eu/eli/reg/2004/261/oj/eng) |
| Denied boarding | Distinguish involuntary operational refusal from volunteering and justified health/security/document refusal. | [EU261 Articles 2(j), 4](https://eur-lex.europa.eu/eli/reg/2004/261/oj/eng) |
| Compensation bands | €250 ≤1,500 km; €400 intra-EU >1,500 km or other 1,500–3,500 km; €600 otherwise. Check reduction conditions separately. | [EU261 Article 7](https://eur-lex.europa.eu/eli/reg/2004/261/oj/eng) |
| Departure delay | Care thresholds: 2/3/4 hours by distance category; at least five hours triggers Article 8(1)(a) options. Check overnight accommodation. | [EU261 Articles 6, 8–9](https://eur-lex.europa.eu/eli/reg/2004/261/oj/eng) |
| Arrival delay | Final-destination arrival delay of at least three hours can create compensation entitlement; check itinerary and exceptions. | [European Commission passenger guidance](https://europa.eu/youreurope/citizens/travel/passenger-rights/air/) |
| Extraordinary circumstances | Airline must substantiate the defense and reasonable measures; do not infer it from “weather” or “technical issue” alone. Care/reimbursement rights require separate assessment. | [Commission guidance: extraordinary circumstances and assistance](https://europa.eu/youreurope/citizens/travel/passenger-rights/air/) |
| Unprovided care | Assess necessary, reasonable and appropriate documented expenses; distinguish care costs, ticket refund, compensation and voluntary goodwill. | [Commission guidance: assistance](https://europa.eu/youreurope/citizens/travel/passenger-rights/air/) |
| Baggage complaints | Checked-baggage damage: written complaint promptly, within seven days after receipt. Delay: within 21 days after baggage is placed at passenger's disposal. Preserve dates and content. | [Montreal Convention Article 31](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A22001A0718%2801%29) |
| Baggage loss/action | Admission of loss or nonarrival after 21 days permits enforcement of baggage rights; litigation has a separate two-year period under Article 35. Do not confuse complaint and court deadlines. | [Montreal Articles 17(3), 35](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A22001A0718%2801%29) |
| Baggage cap | ICAO revised the ordinary baggage limit to **1,519 SDR per passenger from 28 December 2024**. This is not an automatic flat payout or fixed euro amount; assess loss, applicability and exceptions. | [ICAO revision announcement](https://www.icao.int/news/international-air-travel-liability-limits-set-increase-enhancing-customer-compensation-0), [Montreal Article 22](https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX%3A22001A0718%2801%29) |
| GDPR data use | Establish lawful basis; collect only necessary data; maintain accuracy, limited retention and security. Medical material needs separate Article 9 assessment. | [GDPR Articles 5, 6, 9](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32016R0679) |
| Automated decisions | Article 22 concerns solely automated decisions with legal/similarly significant effects. Its exceptions require specific justification; qualifying contract/consent cases require safeguards including human intervention and contestation. A payment cap is not an Article 22 exemption. | [GDPR Article 22](https://eur-lex.europa.eu/legal-content/EN/TXT/?qid=1594897545294&uri=CELEX%3A32016R0679) |

## Proposed demo policies, not statutory rules

- Use synthetic identities and attachments; label stored answers, simulated payments and event replay.
- Keep consequential real-world decisions out of this mockup; automatic demo resolution does not establish production Article 22 compliance.
- Ask targeted German questions; do not demand a passport, medical history or full bank statement by default.
- Retain source IDs/versions and concise decision reasons; avoid raw personal data in progress events.
- Do not make goodwill contingent on anger, language, nationality or willingness to waive statutory rights.
- No arbitrary “three questions then reject” policy; substantive unresolved conflicts can justify specialist handling, the number of attempts cannot.
- No invented mandatory human approval for clear supported demo cases; execution authority remains System 1's responsibility.

## Ten suggested fixtures

Names below are planning labels, not shared IDs or a claim that tests exist.

| Fixture | Inputs | Expected result |
|---|---|---|
| Clear expense | Supported expense, sourced amount/currency, permitted authority | `RESOLVE` with separate reimbursement position |
| Missing receipt then reply | Missing amount evidence, then sourced customer reply on same case | `REQUEST_INFORMATION` then `RESOLVE` |
| Angry supported claim | Clear expense plus negative tone | Same outcome as clear expense |
| Partial reply | Only currency supplied; amount still missing | Focused `REQUEST_INFORMATION`, no handoff |
| Serious injury | Injury and expense in same complaint | `HANDOFF` / `SERIOUS_ISSUE` with context |
| Unsupported rerouting | Customer requires a live rebooking | `HANDOFF` / `UNSUPPORTED_ACTION` |
| Authority gap | Supported reimbursement above permitted amount | `HANDOFF` / `AUTHORITY_LIMIT`, no reduced award |
| Conflicting evidence | Material inconsistent receipt values and attempted clarification | `HANDOFF` / `UNRESOLVED_CONFLICT` |
| Adapter/callback failure | Evidence lookup or progress persistence raises | `FAILED`, no proposal and no effects |
| Takeover plus replay | Human takeover before apply, then duplicate submission | System 1 rejects stale AI action and prevents duplicate effects |

## Verification limits and integration dependencies

Checked official search results and retrieved Commission guidance, EUR-Lex amendment metadata/text, and ICAO's revision notice on the research date.
Some direct EUR-Lex HTML opens returned anti-bot pages; indexed official passages supplied several article checks. This is a targeted review, not exhaustive case-law validation.
German limitation periods, venue, ADR notices, package-travel overlap, accessibility duties and claim-specific exceptions require separate approved knowledge before implementing those outcomes.
No production legal review, executable scenario test, source updater or factual entitlement calculator was performed/created in this research task.
System 1 owns operational evidence adapters, payment history, execution authority, persistence and recovery; System 3 owns display and human controls.
System 2 can later implement approved scenarios behind the existing synchronous interface; shared contract changes must be coordinated explicitly.
