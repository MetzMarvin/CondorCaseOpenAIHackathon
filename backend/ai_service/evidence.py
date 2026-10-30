"""System 2 read contracts. System 1 owns authorization and real reader implementations.

Readers receive only an already-authorized snapshot at its exact case version.
They must never resolve caller-supplied paths, URLs, or unscoped record IDs.
"""
from typing import Literal, Mapping, Protocol
from hashlib import sha256
from dataclasses import dataclass

from pydantic import AwareDatetime, Field, model_validator

from backend.contracts import AttachmentRef, CaseSnapshot, Contract, Fact, Id, SourceRef, TechnicalError, Version


class EvidenceScope(Contract):
    case_id: Id
    case_version: Version


class LookupRequest(Contract):
    scope: EvidenceScope
    snapshot: CaseSnapshot
    fact_names: tuple[Id, ...]


class LookupResult(Contract):
    scope: EvidenceScope
    status: Literal['found', 'not_found', 'ambiguous', 'unavailable']
    facts: tuple[Fact, ...] = ()
    observed_at: AwareDatetime | None = None
    freshness: Literal['current', 'stale', 'unknown'] = 'unknown'
    error: TechnicalError | None = None

    @model_validator(mode='after')
    def consistent_result(self):
        if self.status == 'found':
            if not self.facts or any(not fact.sources for fact in self.facts) or self.observed_at is None:
                raise ValueError('Found facts require sources with versions and an observation time')
        elif self.facts:
            raise ValueError('Non-found results cannot disclose candidate facts')
        if (self.status == 'unavailable') != (self.error is not None):
            raise ValueError('Only unavailable results require a technical error')
        return self


class RecordReader(Protocol):
    def lookup(self, request: LookupRequest) -> LookupResult:
        """Read CRM or operational facts; never expose ambiguous candidate records."""
        ...


class FakeRecordReader:
    """Explicit synthetic, case/version-keyed results; performs no external access."""
    def __init__(self, results: Mapping[EvidenceScope, LookupResult]):
        if any(scope != result.scope for scope, result in results.items()):
            raise ValueError('Result scope must match its configured scope')
        self._results = {scope: result.model_copy(deep=True) for scope, result in results.items()}

    def lookup(self, request: LookupRequest) -> LookupResult:
        return self._results.get(request.scope, LookupResult(scope=request.scope, status='not_found')).model_copy(deep=True)


class AttachmentRequest(Contract):
    scope: EvidenceScope
    reference: AttachmentRef


class AttachmentResult(Contract):
    scope: EvidenceScope
    reference: AttachmentRef
    status: Literal['found', 'not_found', 'scope_violation', 'unsupported', 'too_large', 'unavailable']
    content: bytes | None = Field(default=None, repr=False)
    source: SourceRef | None = None
    content_hash: str | None = None  # SHA-256 hex; exact returned bytes.
    observed_at: AwareDatetime | None = None
    error: TechnicalError | None = None

    @model_validator(mode='after')
    def consistent_attachment(self):
        if self.status == 'found':
            if self.content is None or self.source is None or self.observed_at is None:
                raise ValueError('Found attachment requires bytes, version and observation time')
            if self.source.source_id != self.reference.attachment_id:
                raise ValueError('Attachment source must identify the requested attachment')
            if self.content_hash != sha256(self.content).hexdigest():
                raise ValueError('Attachment content hash mismatch')
        elif any(value is not None for value in (self.content, self.source, self.content_hash)):
            raise ValueError('Failed attachment reads cannot return content')
        if (self.status == 'unavailable') != (self.error is not None):
            raise ValueError('Only unavailable results require a technical error')
        return self


class AttachmentReader(Protocol):
    def read(self, request: AttachmentRequest) -> AttachmentResult:
        """Resolve a System 1 token, authorize case/version, bound bytes and verify media type."""
        ...


class FakeAttachmentReader:
    """Synthetic in-memory reader: exact scope and reference matching, no file access."""
    def __init__(self, results: tuple[AttachmentResult, ...] = ()):
        self._results = {}
        for result in results:
            key = (result.scope, result.reference)
            if key in self._results:
                raise ValueError('Duplicate attachment fixture')
            self._results[key] = result

    def read(self, request: AttachmentRequest) -> AttachmentResult:
        result = self._results.get((request.scope, request.reference))
        if result is not None:
            return result.model_copy(deep=True)
        return AttachmentResult(scope=request.scope, reference=request.reference, status='scope_violation')


class UnavailableRecordReader:
    def lookup(self, request: LookupRequest) -> LookupResult:
        return LookupResult(scope=request.scope, status='unavailable', error=TechnicalError(
            code='EVIDENCE_ADAPTER_UNCONFIGURED', message='A required internal reader is not configured.', retryable=False))


class UnavailableAttachmentReader:
    def read(self, request: AttachmentRequest) -> AttachmentResult:
        return AttachmentResult(scope=request.scope, reference=request.reference, status='unavailable', error=TechnicalError(
            code='ATTACHMENT_ADAPTER_UNCONFIGURED', message='The attachment reader is not configured.', retryable=False))


@dataclass(frozen=True)
class ReadOnlyEvidenceAdapters:
    crm: RecordReader
    operational: RecordReader
    attachments: AttachmentReader


def create_evidence_adapters(*, crm: RecordReader | None = None,
                             operational: RecordReader | None = None,
                             attachments: AttachmentReader | None = None) -> ReadOnlyEvidenceAdapters:
    """Explicit backend injection; omitted integrations are unavailable, never invented data.

    The service factory can own this bundle without changing process_case's signature.
    No global registry, environment credentials, database, network or file reads.
    """
    return ReadOnlyEvidenceAdapters(
        crm if crm is not None else UnavailableRecordReader(),
        operational if operational is not None else UnavailableRecordReader(),
        attachments if attachments is not None else UnavailableAttachmentReader())
