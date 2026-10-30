"""Read-only evidence preparation. Supplied snapshot facts remain the default path."""
from dataclasses import dataclass

from backend.ai_service.assessment import INTERNAL_FACTS, SERIOUS_ISSUES
from backend.ai_service.questions import QUESTIONS
from backend.contracts import Fact, RunRequest, SourceRef, TechnicalError
from backend.ai_service.evidence import EvidenceScope, LookupRequest, ReadOnlyEvidenceAdapters


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
            try:
                result = adapters.crm.lookup(LookupRequest(scope=scope, snapshot=snapshot, fact_names=matches))
            except Exception:
                return _failure('EVIDENCE_UNAVAILABLE', 'CRM evidence access failed.', True)
            if result.scope != scope:
                return _failure('EVIDENCE_SCOPE_VIOLATION', 'CRM evidence does not match the requested case version.')
            if result.status == 'unavailable':
                return _failure('EVIDENCE_UNAVAILABLE', 'CRM evidence is unavailable.', result.error.retryable)
            unmatched = result.status in {'not_found', 'ambiguous'}
            if result.status == 'found':
                if result.freshness != 'current':
                    return _failure('EVIDENCE_STALE', 'CRM evidence requires refresh at the current case version.', True)
                allowed = {'customer_match', 'booking_match', 'flight_match', 'booking_reference', 'flight_number', 'flight_date'}
                if any(fact.name not in allowed for fact in result.facts):
                    return _failure('INVALID_ADAPTER_EVIDENCE', 'CRM returned facts outside its evidence authority.')
                if not set(matches) <= {fact.name for fact in result.facts if fact.value == 'matched'}:
                    return _failure('INTERNAL_EVIDENCE_REQUIRED', 'CRM returned incomplete match evidence.')
                snapshot = snapshot.model_copy(update={'booking_context': snapshot.booking_context + result.facts})
    if adapters is not None and not unmatched and set(snapshot.issues) == {'expense_reimbursement'}:
        supplied = {fact.name for fact in snapshot.booking_context + snapshot.flight_context if fact.sources and fact.value not in (None, '')}
        needed = tuple(name for name in ('expense_eligibility', 'payment_history') if name not in supplied)
        if needed:
            scope = EvidenceScope(case_id=request.case_id, case_version=request.case_version)
            try:
                result = adapters.operational.lookup(LookupRequest(scope=scope, snapshot=snapshot, fact_names=needed))
            except Exception:
                return _failure('EVIDENCE_UNAVAILABLE', 'Internal evidence access failed.', True)
            if result.scope != scope:
                return _failure('EVIDENCE_SCOPE_VIOLATION', 'Evidence does not match the requested case version.')
            if result.status == 'unavailable':
                return _failure('EVIDENCE_UNAVAILABLE', 'Internal evidence is unavailable.', result.error.retryable)
            if result.status != 'found':
                return _failure('INTERNAL_EVIDENCE_REQUIRED', 'Required internal records could not be established.')
            if result.freshness != 'current':
                return _failure('EVIDENCE_STALE', 'Internal evidence requires refresh at the current case version.', True)
            if any(fact.name not in INTERNAL_FACTS - {'legal_regime', 'policy_version'} for fact in result.facts):
                return _failure('INVALID_ADAPTER_EVIDENCE', 'Operational reader returned facts outside its evidence authority.')
            found = {fact.name for fact in result.facts if fact.sources and fact.value not in (None, '')}
            if not set(needed) <= found:
                return _failure('INTERNAL_EVIDENCE_REQUIRED', 'Required internal records are incomplete.')
            snapshot = snapshot.model_copy(update={'flight_context': snapshot.flight_context + result.facts})
    sources = tuple(dict.fromkeys(source for fact in snapshot.known_facts + snapshot.customer_context + snapshot.booking_context + snapshot.flight_context for source in fact.sources))
    return PreparedEvidence(request.model_copy(update={'snapshot': snapshot}), sources=sources)


def _failure(code: str, message: str, retryable: bool = False) -> PreparedEvidence:
    return PreparedEvidence(None, TechnicalError(code=code, message=message, retryable=retryable))
