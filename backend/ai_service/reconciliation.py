"""Read-only evidence preparation. Supplied snapshot facts remain the default path."""
from dataclasses import dataclass

from backend.ai_service.assessment import INTERNAL_FACTS, SERIOUS_ISSUES
from backend.ai_service.questions import QUESTIONS
from backend.contracts import Fact, RunRequest, SourceRef, TechnicalError
from backend.ai_service.evidence import EvidenceScope, LookupRequest, LookupResult, ReadOnlyEvidenceAdapters, RecordReader


@dataclass(frozen=True)
class PreparedEvidence:
    request: RunRequest | None
    error: TechnicalError | None = None
    sources: tuple[SourceRef, ...] = ()


def prepare_evidence(request: RunRequest, adapters: ReadOnlyEvidenceAdapters | None = None,
                     *, customer_facts: tuple[Fact, ...] = ()) -> PreparedEvidence:
    # Candidates have already passed the extractor's provenance checks. Their
    # origin is customer evidence; they can never become internal authority.
    if any(fact.name not in QUESTIONS or not fact.sources for fact in customer_facts):
        return _failure('INVALID_CUSTOMER_EVIDENCE', 'Extracted customer evidence contains unsupported facts.')
    snapshot = request.snapshot.model_copy(deep=True)
    snapshot = snapshot.model_copy(update={'known_facts': snapshot.known_facts + customer_facts})
    unmatched = False
    if adapters is not None and not set(snapshot.issues) & SERIOUS_ISSUES:
        matches = tuple(dict.fromkeys(item.name for item in snapshot.missing_information
            if item.name in {'customer_match', 'booking_match', 'flight_match'}))
        supplied_matches = {fact.name for fact in snapshot.booking_context + snapshot.flight_context
                            if fact.sources and fact.value == 'matched'}
        matches = tuple(name for name in matches if name not in supplied_matches)
        if matches:
            scope = EvidenceScope(case_id=request.case_id, case_version=request.case_version)
            allowed = {'customer_match', 'booking_match', 'flight_match', 'booking_reference', 'flight_number', 'flight_date'}
            result, error = _validated_lookup(adapters.crm,
                LookupRequest(scope=scope, snapshot=snapshot, fact_names=matches), allowed, crm=True)
            if error:
                return PreparedEvidence(None, error)
            unmatched = result.status in {'not_found', 'ambiguous'}
            if result.status == 'found':
                if not set(matches) <= {fact.name for fact in result.facts if fact.value == 'matched'}:
                    return _failure('INTERNAL_EVIDENCE_REQUIRED', 'CRM returned incomplete match evidence.')
                snapshot = snapshot.model_copy(update={'booking_context': snapshot.booking_context + result.facts})
    if adapters is not None and not unmatched and set(snapshot.issues) == {'expense_reimbursement'}:
        supplied = {fact.name for fact in snapshot.booking_context + snapshot.flight_context if fact.sources and fact.value not in (None, '')}
        needed = tuple(name for name in ('expense_eligibility', 'payment_history') if name not in supplied)
        if needed:
            scope = EvidenceScope(case_id=request.case_id, case_version=request.case_version)
            result, error = _validated_lookup(adapters.operational,
                LookupRequest(scope=scope, snapshot=snapshot, fact_names=needed),
                INTERNAL_FACTS - {'legal_regime', 'policy_version'})
            if error:
                return PreparedEvidence(None, error)
            if result.status != 'found':
                return _failure('INTERNAL_EVIDENCE_REQUIRED', 'Required internal records could not be established.')
            found = {fact.name for fact in result.facts if fact.sources and fact.value not in (None, '')}
            if not set(needed) <= found:
                return _failure('INTERNAL_EVIDENCE_REQUIRED', 'Required internal records are incomplete.')
            snapshot = snapshot.model_copy(update={'flight_context': snapshot.flight_context + result.facts})
    sources = tuple(dict.fromkeys(source for fact in snapshot.known_facts + snapshot.customer_context + snapshot.booking_context + snapshot.flight_context for source in fact.sources))
    return PreparedEvidence(request.model_copy(update={'snapshot': snapshot}), sources=sources)


def _failure(code: str, message: str, retryable: bool = False) -> PreparedEvidence:
    return PreparedEvidence(None, TechnicalError(code=code, message=message, retryable=retryable))


def _validated_lookup(reader: RecordReader, request: LookupRequest,
                      allowed: set[str], *, crm: bool = False) -> tuple[LookupResult | None, TechnicalError | None]:
    label = 'CRM' if crm else 'Internal'
    try:
        result = reader.lookup(request)
    except Exception:
        return None, TechnicalError(code='EVIDENCE_UNAVAILABLE', message=f'{label} evidence access failed.', retryable=True)
    try:
        # Model instances can bypass validation through model_copy/model_construct.
        result = LookupResult.model_validate(result.model_dump())
    except Exception:
        return None, TechnicalError(code='INVALID_ADAPTER_EVIDENCE', message=f'{label} reader returned invalid evidence.', retryable=False)
    if result.scope != request.scope:
        message = 'CRM evidence' if crm else 'Evidence'
        return None, TechnicalError(code='EVIDENCE_SCOPE_VIOLATION', message=f'{message} does not match the requested case version.', retryable=False)
    if result.status == 'unavailable':
        return None, TechnicalError(code='EVIDENCE_UNAVAILABLE', message=f'{label} evidence is unavailable.', retryable=result.error.retryable)
    if result.status == 'found':
        if result.freshness != 'current':
            return None, TechnicalError(code='EVIDENCE_STALE', message=f'{label} evidence requires refresh at the current case version.', retryable=True)
        if any(fact.name not in allowed for fact in result.facts):
            message = 'CRM' if crm else 'Operational reader'
            return None, TechnicalError(code='INVALID_ADAPTER_EVIDENCE', message=f'{message} returned facts outside its evidence authority.', retryable=False)
    return result, None
