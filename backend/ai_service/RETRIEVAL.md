# Filtered local knowledge retrieval

Public internal seam: `retrieve(RetrievalQuery(...), registry_loader=bundled_registry)`
returns `RetrievalResult`. This is System 2 only; shared action contracts and the
synchronous workflow entry point are unchanged. The callable registry reader can
be supplied by the configured processor; no customer documents are ingested.

The caller supplies `issue_tags`, optional lexical `text`, an established
`event_date`, and `applicability_facts` mapping fact names to established string
values. Do not use current time, receipt/reply timestamps or inferred jurisdictions
as substitutes for the relevant case event date. Conflicting facts must first be
reconciled by the caller. The default universal synthetic policy supports the
existing undated expense fixtures without establishing legal entitlement.

Approval, issue, event interval and established applicability filter candidates
before token-overlap ranking. Unknown potentially applicable facts produce sorted
`gaps`; they never silently authorize a rule. Conflicting decisions for one
`rule_key` are detected across every applicable rule before ranking. Stable
source/version/passage IDs break lexical ties. No latest-version heuristic applies.

`max_rules` limits primary ranked rule passages. All same-card prerequisite and
exception passages plus transitive exact-version dependencies are mandatory and
survive this limit. A visited passage set handles cyclic support references.
Dependencies must themselves pass every filter. `max_characters` is a hard sum
of passage text lengths, not a token or whole-prompt budget; the context assembler
must separately bound its full serialized context. Overflow returns no passages.

Outcomes are deliberately distinct:

- `SUPPORTED`: exact passages and source hashes, roles, decisions and selection
  rationales. This indicates retrieved support, not satisfied evidence prerequisites
  or execution authority; KA09 still checks the deterministic recommendation.
- `APPLICABILITY_GAP`: potentially applicable knowledge needs listed fact names.
  Preserve evidence/enrichment routing; missing facts alone do not mean handoff.
- `UNSUPPORTED`: no applicable approved rule; map to unsupported capability only
  when appropriate for the workflow's assessed action.
- `UNCLEAR_RULE`: conflicting applicable decisions or required support that is
  ineligible. Reason identifies the conflicting rule key or dependency reference.
- `FAILED`: `KNOWLEDGE_UNAVAILABLE` for registry loading/validation failure, or
  `KNOWLEDGE_BUDGET_EXCEEDED` for mandatory support overflow. No exception text,
  private paths or business proposal are returned.

Every non-supported outcome has no selected passages. Retrieval does not prove
that arbitrary prose is supported or that every requested issue is resolved;
proposal validation must verify the required rule keys and exact selected support.
Workflow integration and run diagnostics are KA09/KA11 work.

Validation performed: `python -m unittest tests.test_knowledge_retrieval
 tests.test_knowledge_registry` (15 tests), covering default no-date support,
approval/issue/date/regime gates, explicit gaps, deterministic rank and ties,
contradictions before limits, cyclic/transitive dependencies, withdrawn/expired/
wrong-regime support, corrupt/missing registry data and support budget overflow.
