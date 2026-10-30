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
`diagnostic_sink(bundle, result)` is invoked on successful and failed configured
runs. It contains sensitive internal data and must never be serialized wholesale.
The sink must project a safe manifest. A sink exception invalidates the run.
System 1 owns any actual persistence, access controls and retention, plus final
case-version, ownership, authority and idempotency enforcement.

Stored simulations can be regenerated without model access:

```sh
AI_MODE=offline python -m backend.ai_service > backend/ai_service/stored_outputs.jsonl
```
