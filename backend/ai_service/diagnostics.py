"""Safe System 2 manifest boundary; System 1 supplies storage and access policy."""
from hashlib import sha256
from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.ai_service.questions import QUESTIONS

from backend.contracts import ActionType, HandoffReason, Id, SourceRef, Version

Digest = Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')]
ConfigurationId = Annotated[str, Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$')]
MISSING_KEYS = frozenset(QUESTIONS) | {'event_date', 'legal_regime', 'policy_version'}


class ManifestRecord(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)


class KnowledgeVersion(ManifestRecord):
    source_id: Id
    version: Id
    passage_id: Id
    source_hash: Digest
    passage_hash: Digest


class AttachmentVersion(ManifestRecord):
    attachment_id: Id
    read_status: Literal['found', 'not_found', 'scope_violation', 'unsupported', 'too_large', 'unavailable', 'not_read']
    source_version: Id | None
    content_hash: Digest | None
    extraction_status: Literal['readable', 'partial', 'unreadable', 'parser_failure'] | None
    extraction_configuration_version: ConfigurationId | None
    extraction_simulation: bool | None


ERROR_CATEGORIES = {
    **dict.fromkeys(('INVALID_AI_CONTEXT', 'INVALID_INTERNAL_CONTEXT', 'NO_PERMITTED_ACTION'), 'input'),
    **dict.fromkeys(('ATTACHMENT_ADAPTER_UNCONFIGURED', 'EVIDENCE_ADAPTER_UNCONFIGURED',
        'ATTACHMENT_SCOPE_VIOLATION', 'EVIDENCE_SCOPE_VIOLATION', 'EVIDENCE_STALE',
        'EVIDENCE_UNAVAILABLE', 'INTERNAL_EVIDENCE_REQUIRED', 'INVALID_ADAPTER_EVIDENCE',
        'INVALID_CUSTOMER_EVIDENCE'), 'evidence'),
    **dict.fromkeys(('EXTRACTION_OUTPUT_LIMIT', 'EXTRACTION_PARSER_FAILURE', 'EVIDENCE_PARSE_FAILED',
        'OCR_ADAPTER_UNCONFIGURED', 'PDF_ADAPTER_UNCONFIGURED'), 'extraction'),
    **dict.fromkeys(('KNOWLEDGE_UNAVAILABLE', 'KNOWLEDGE_BUDGET_EXCEEDED',
        'INTERNAL_APPLICABILITY_REQUIRED', 'POLICY_UNAVAILABLE'), 'retrieval'),
    'AI_PROCESSING_FAILED': 'processing', 'TECHNICAL_FAILURE': 'processing',
}


class ManifestError(ManifestRecord):
    code: Id
    category: Literal['input', 'evidence', 'extraction', 'retrieval', 'model', 'processing']
    retryable: bool

    @field_validator('code')
    @classmethod
    def safe_code(cls, value):
        if value not in ERROR_CATEGORIES:
            raise ValueError('Unknown diagnostic error code')
        return value


class RunManifest(ManifestRecord):
    schema_version: Literal[1] = 1
    case_id: Id
    run_id: Id
    case_version: Version
    status: Literal['SUCCEEDED', 'FAILED']
    decision: ActionType | None
    reason: HandoffReason | Literal['SUPPORTED_EXPENSE', 'MISSING_EVIDENCE']
    error: ManifestError | None
    missing_keys: tuple[str, ...]
    evidence_sources: tuple[SourceRef, ...]
    knowledge: tuple[KnowledgeVersion, ...]
    attachments: tuple[AttachmentVersion, ...]
    retrieval_configuration_version: ConfigurationId
    mode: Literal['offline', 'openai', 'unknown']
    model: ConfigurationId | None
    simulation: bool

    @field_validator('missing_keys')
    @classmethod
    def safe_missing_keys(cls, keys):
        if any(key not in MISSING_KEYS for key in keys):
            raise ValueError('Unknown diagnostic missing key')
        return keys

    @model_validator(mode='after')
    def consistent_outcome(self):
        if self.status == 'FAILED':
            if self.error is None or self.decision is not None or self.reason != 'TECHNICAL_FAILURE':
                raise ValueError('Failed manifest requires safe error and no decision')
        elif self.error is not None or self.decision is None:
            raise ValueError('Successful manifest requires decision and no error')
        if self.mode == 'offline' and (self.model is not None or not self.simulation):
            raise ValueError('Offline processing is simulated and has no model')
        return self


class DiagnosticSink(Protocol):
    def __call__(self, manifest: RunManifest) -> None:
        """Synchronously store the safe manifest or raise; no case mutation."""
        ...


def build_manifest(bundle, result) -> RunManifest:
    """Project metadata explicitly. Never serialize the private processing bundle."""
    snapshots = [bundle.request.snapshot]
    if bundle.effective_request is not None:
        snapshots.append(bundle.effective_request.snapshot)
    sources = {(s.source_id, s.version): s for snapshot in snapshots
               for fact in snapshot.known_facts + snapshot.customer_context + snapshot.booking_context + snapshot.flight_context
               for s in fact.sources}
    for attachment in bundle.attachments:
        if attachment.source is not None:
            sources[(attachment.source.source_id, attachment.source.version)] = attachment.source
    reads = {a.reference.attachment_id: (i, a) for i, a in enumerate(bundle.attachments)}
    attachments = []
    for reference in bundle.request.snapshot.attachments:
        entry = reads.get(reference.attachment_id)
        read = entry[1] if entry else None
        extraction = bundle.extractions[entry[0]] if entry and entry[0] < len(bundle.extractions) else None
        attachments.append(AttachmentVersion(attachment_id=reference.attachment_id,
            read_status=read.status if read else 'not_read',
            source_version=read.source.version if read and read.source else None,
            content_hash=read.content_hash if read else None,
            extraction_status=extraction.status if extraction else None,
            extraction_configuration_version=extraction.configuration_version if extraction else None,
            extraction_simulation=extraction.simulation if extraction else None))
    action = result.proposed_action
    reason = ('TECHNICAL_FAILURE' if result.status == 'FAILED' else
              action.payload.reason_code if action.type == 'HANDOFF' else
              'MISSING_EVIDENCE' if action.type == 'REQUEST_INFORMATION' else 'SUPPORTED_EXPENSE')
    error = None
    if result.technical_error:
        code = result.technical_error.code if result.technical_error.code in ERROR_CATEGORIES else 'TECHNICAL_FAILURE'
        category = ERROR_CATEGORIES[code]
        if bundle.retrieval and bundle.retrieval.status == 'FAILED':
            category = 'retrieval'
        elif bundle.model_started and code == 'AI_PROCESSING_FAILED':
            category = 'model'
        error = ManifestError(code=code, category=category, retryable=result.technical_error.retryable)
    return RunManifest(case_id=bundle.request.case_id, run_id=bundle.request.run_id,
        case_version=bundle.request.case_version, status=result.status,
        decision=action.type if action else None, reason=reason, error=error,
        missing_keys=tuple(sorted(
                ({m.name for m in result.assessment.missing_facts} if result.assessment else set())
                .union(bundle.retrieval.gaps if bundle.retrieval else ()).intersection(MISSING_KEYS))),
        evidence_sources=tuple(sources[key] for key in sorted(sources)),
        knowledge=tuple(KnowledgeVersion(source_id=p.source_id, version=p.version, passage_id=p.passage_id,
            source_hash=p.content_hash, passage_hash=sha256(p.text.encode('utf-8')).hexdigest())
            for p in (bundle.retrieval.passages if bundle.retrieval else ())),
        attachments=tuple(attachments), retrieval_configuration_version=bundle.retrieval_configuration_version,
        mode=bundle.mode, model=bundle.model, simulation=result.simulation)
