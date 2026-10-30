# Configured synchronous processing

`service.create_processor(adapters=..., extractor=..., retriever=..., settings=...)`
returns the existing `process_case(request, emit_progress)` interface. Both offline
and live modes execute the same preparation, extraction, assessment and retrieval
pipeline. `workflow.process_case` is explicitly offline. `service.process_case`
retains backend environment configuration (`AI_MODE=offline` disables model use).

System 1 injects authorized read-only adapters; System 2 never resolves paths from
attachment metadata. Attachment responses are revalidated, matched against exact
case/version/reference and extracted provenance. Candidates enter only customer
facts on a copied snapshot. Unreadable evidence asks for readable evidence; partial
extraction leaves remaining material gaps. Reader/parser failures fail the run.
Without adapters, supplied sourced facts remain supported. If attachments need
reading to fill outstanding evidence, configuration failure is explicit.

A retriever accepts `RetrievalQuery` and returns `RetrievalResult`. For custom
registries, bind `lambda query: retrieve(query, registry_loader)`. Only the exact
reviewed synthetic expense policy v2 content fingerprint and its rule,
prerequisite and exception passages authorize the implemented expense resolution.
Loading another approved card does not implement new legal adjudication. Unknown
customer applicability asks reviewed questions; unknown internal applicability
fails. Missing evidence never becomes a policy-absence handoff.

Live model context contains allowlisted sourced facts, with arbitrary string
values represented as presence only; internal controls require internal origin.
It excludes messages, sender/customer identity, filenames, paths and raw attachment
text. Whole selected passages and their restrictions are retained. The entire
serialized context must fit 32,000 UTF-8 bytes or the run fails before a model call.
This is a conservative size bound, not token accounting.

Reviews must cite every selected passage by exact source, version and passage ID.
This identity check is combined with deterministic rule support; it does not claim
to prove free-text semantic entailment. Model drafts must match the supplied
reviewed template exactly except for sentiment. The model cannot author new
substantive statements, change questions, change money or claim execution. Free-text
review summaries are discarded and never forwarded into another model or events.
Provider errors, refusals and invalid drafts fail without offline fallback.

The internal `ProcessingBundle` retains per-run observations for diagnostics;
`create_processor(diagnostic_sink=...)` invokes the sink with a strict safe
`RunManifest` on successful and failed configured runs. The private bundle contains
sensitive data and is never passed to that sink. A sink exception invalidates the
run. See [diagnostics and storage responsibilities](DIAGNOSTICS.md).
System 1 owns any actual persistence, access controls and retention, plus final
case-version, ownership, authority and idempotency enforcement.

Stored simulations can be regenerated without model access:

```sh
AI_MODE=offline python -m backend.ai_service > backend/ai_service/stored_outputs.jsonl
```

## Exhaustive Decisions policy review

Set backend configuration to:

```dotenv
AI_MODE=openai
AI_POLICY_STRATEGY=decisions
OPENAI_API_KEY=your-backend-key
```

`decisions` is the default policy strategy. Set `AI_POLICY_STRATEGY=experts`
to retain the previous Responses reviewer. The default replaces the Responses policy reviewer with one synchronous `POST /v1/decisions`
request using `gpt-6-luna`. The evidence and communication reviewers still use
`OPENAI_MODEL`. The installed SDK's generic POST method supports the endpoint
without changing shared dependencies. See the [official Decisions API guide](https://developers.openai.com/api/docs/guides/decisions).

Every rule in `docs/policies/customer-service/policy.json` is checked, including
mandatory governance rules and rules whose applicability is uncertain. No top-k
retrieval filter can omit a generated rule. The complete policy, decision tables,
and source metadata accompany the allowlisted case context. Each selected approved
demo passage receives an additional mandatory check. Related rules, exceptions,
prohibitions and table preconditions are part of the review. Manifest hashes are
verified before calling the provider; partial policy regeneration fails the run.
Subsequent runs pick up a newly generated, internally consistent package.

Each named check returns `SUPPORTED`, `NOT_APPLICABLE`, `VIOLATION`, or
`INSUFFICIENT_EVIDENCE`. All answers must be present exactly once and have confidence
at least 0.90 (an application threshold, not a calibrated guarantee). Mandatory
rules and approved passages require `SUPPORTED`. Other rules may be demonstrably
inapplicable. Refusals, invalid answers, provider errors and failed checks produce
failed runs without a proposed action or an offline fallback. Missing evidence
never becomes an automatic handoff through this reviewer.

The generated package is currently `draft_review_required`: it supplies additional
constraints, not approved settlement authority. It is not added to the approved
knowledge registry. Existing deterministic proposals and financial limits remain
unchanged. The reviewer cannot invent missing facts: the current minimal evidence
projection can therefore produce `INSUFFICIENT_EVIDENCE` for richer policy rules.
Additional verified facts must come from System 1's snapshot/read adapters.

When a diagnostic sink is supplied, the additive `policy_report` manifest field
records package ID/version/status/hash, model and per-rule verdicts, including
completed but rejected reviews. Provider failures leave an empty verdict list;
malformed responses are not stored. System 1 owns persistence of these manifests
and action execution. Shared RunRequest/RunResult and progress step IDs are unchanged.
`AI_MODE=offline` continues to run the stored deterministic demo without any model
call, including when this strategy is selected. Mocked tests cover API transport,
rule coverage, failed reviews and the three demo flows; they do not establish live
model accuracy or legal approval.
