# Local knowledge registry

`knowledge.bundled_registry()` loads `knowledge_data/demo.json` through the same
validated `KnowledgeRegistry.load(path)` interface available to future local
source ingestion. `registry.cards` is immutable and `registry.get(source_id,
version)` addresses one exact version (unknown keys raise `KeyError`). No network,
vector store, customer evidence ingestion or shared action schema changes occur.

The sole bundled source is **synthetic demo assumption** `demo-expense-policy`,
version `2`, with `DEMO_APPROVED` status. It makes no claim of legal review or
production approval. `legal_rule` and `company_policy` sources instead require
`APPROVED`; neither production kinds nor demo approval can substitute for the
other. `DRAFT` and `WITHDRAWN` may be stored but are never eligible. Approval is
trusted ingestion metadata, not something a content hash proves.

`card.approved_for_event(event_date)` checks approval and dates only. Intervals
use inclusive `effective_from` and exclusive `effective_until`. `retrieved_on`
is acquisition metadata, never a substitute for the relevant case event date.
A missing event date makes every card ineligible except an explicitly universal,
undated synthetic assumption. Universal cards cannot carry applicability filters.
The bundled card is universal to support existing fixtures without inventing a
flight/event date. Future-effective rules are not eligible for earlier events.

Retrievers must additionally check `issue_tags` and each `applicability` entry's
`fact_name` against its `allowed_values`. Missing case facts are applicability
gaps, not permission to guess. `approved_for_event` does not perform this check.

Passages have stable IDs, text and `RULE`, `PREREQUISITE` or `EXCEPTION` roles.
Optional paired `rule_key`/`decision` metadata belongs only to rule passages:
different decisions for the same key indicate a conflict when both apply;
complementary prerequisite/exception passages are not contradictory decisions.
The bundled rule uses `expense_reimbursement` / `supported`. Dependencies point
to exact source IDs, versions and passage IDs (including same-card support).
Every dependency must exist at load time. Retrieval must retain dependencies,
check their approval and applicability, and follow cross-card support recursively
with a visited set; dependency presence does not imply permission to use it.

`content_hash` is lowercase SHA-256 of the complete normalized card JSON except
`content_hash` itself: UTF-8, sorted keys, compact separators, literal Unicode,
with all schema defaults included and dates serialized as ISO dates. Use
`card_content_hash` with a complete normalized dictionary to stamp approved
fixtures before validation. Hashes cover text, passages and decision metadata.
They detect accidental corruption, not malicious replacement or legal validity.
JSON/validation errors and filesystem errors propagate to the caller; orchestration
must convert these infrastructure failures into failed runs, never business
outcomes. Duplicate source/version or passage IDs and missing dependencies fail
validation. Loading does not resolve conflicts or silently select a latest version.

Validation: `python -m unittest tests.test_knowledge_registry` exercises the public
registry/model seam, including synthetic approval, interval boundaries, content
corruption, duplicates, dependencies and rule metadata. Workflow wiring and
applicability retrieval are follow-on work; this registry alone does not change
existing proposal generation.
