# Run manifests and the storage boundary

System 2 produces `RunManifest` through the synchronous configured processor:

```python
from backend.ai_service.service import create_processor

processor = create_processor(diagnostic_sink=system1_store_manifest)
result = processor(request, emit_progress)
```

The injected function accepts one `RunManifest`, returns `None` only after its
storage operation succeeds, and raises on failure. It receives no snapshot,
private processing bundle, model prompt, response text, bytes or secrets.
`RunManifest.model_dump_json()` and `RunManifest.model_validate_json(...)` are the
strict version-1 serialization boundary. Unknown fields are rejected.
This is an internal integration contract, not a change to shared public events
or the shared `RunResult` model.

The manifest records the case/run IDs and input case version; source IDs/versions
from the original and successfully prepared snapshots; each attachment reference's
read status, actual returned source version and SHA-256 bytes hash when available;
extraction result status, configuration version and simulation flag; selected
knowledge source/version/passage IDs with both the source-card hash and a separate
SHA-256 passage-text hash; configured model/mode; outcome, fixed decision reason,
allowlisted missing keys, safe error category/code and retryability. Attachment
references that were not read have `not_read` status and no invented version/hash.
A failed model call still emits the evidence and selected knowledge manifest.
Unknown adapter error codes become `TECHNICAL_FAILURE`; error text is never copied.
Opaque case/run/source/attachment IDs and source versions must already be safe
identifiers under System 1's contract; no new personal-data fields are accepted.

The built-in retriever is identified as `lexical-approved-v1`. A custom retriever
should supply `retrieval_configuration_version='your-reviewed-config-v1'` to the
factory. Omission produces `unversioned-custom`, explicitly insufficient to claim
reproducibility of that custom retrieval setup. Extraction configuration comes
from each `ExtractionResult.configuration_version`; adapters must version their
actual parser/OCR configuration as well as their extraction rules when supplying
custom extractors. The bundled label extractor reports `synthetic-labelled-fields-v1`.
Exact source versions identify supplied facts without retaining their values.
Reproduction still requires System 1 to retain the corresponding authorized
snapshots/source versions and the identified backend configurations.

Sink failure returns `FAILED` with `DIAGNOSTIC_PERSISTENCE_FAILED`, retryable true,
and no proposed action. The processor does not retry the failing sink or apply
business effects. A sink that writes and then raises may already have a manifest
for an unexecuted proposal: System 1 must atomically reconcile storage with the
returned failed result and deduplicate retries by run ID. A manifest describing a
proposal is never evidence that a message, payment or case mutation was executed.
Progress callback failures also produce a failed result and safe failure manifest.

## System 1 integration dependencies

No durable diagnostic store is implemented here. Without `diagnostic_sink`, no
manifest is persisted or retained. List/in-memory sinks in tests last only as long
as their owning process; they are not persistence. Existing stored simulation
outputs remain usable offline, but they are not a run-diagnostics database.

System 1 must implement and document all of the following before claiming KA11
persistence is complete:

- Actual storage location/table and transaction semantics alongside run results.
- Case-scoped access authorization and who may read/export a manifest.
- Retention duration, deletion policy and matching source/snapshot retention.
- Idempotent writes and recovery when storage fails after a partial write.

System 2 writes no files or database records for diagnostics, changes no case
status/ownership and performs no customer sends or financial effects. System 1
continues to authorize version, owner, action and financial limits independently.
