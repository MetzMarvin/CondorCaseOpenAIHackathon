"""Deterministic routing of supplied evidence; no legal inference from free text."""
from dataclasses import dataclass

from backend.contracts import CaseSnapshot, Fact, FinancialPosition, MissingFact, SourceRef, TechnicalError
from backend.ai_service.questions import QUESTIONS, missing_fact

POLICY = SourceRef(source_id='demo-expense-policy', version='2')
SERIOUS_ISSUES = {'safety_incident', 'serious_injury', 'discrimination', 'accessibility_failure', 'credible_threat'}
# Collection is supported for these issues; financial/legal adjudication is not.
INTAKE_REQUIREMENTS = {
    'expense_reimbursement': ('receipt_amount_minor', 'receipt_currency', 'expense_purpose'),
    'flight_delay': ('booking_reference',),
    'flight_cancellation': ('booking_reference', 'remedy_choice'),
    'denied_boarding': ('booking_reference', 'claim_details'),
    'baggage_delay': ('booking_reference', 'baggage_reference', 'baggage_return_date'),
    'baggage_damage': ('booking_reference', 'baggage_reference', 'damage_details', 'damage_discovery_date', 'written_complaint_date'),
    'baggage_loss': ('booking_reference', 'baggage_reference', 'written_complaint_date'),
    'service_complaint': ('claim_details',),
}
INTERNAL_FACTS = {
    'actual_arrival', 'disruption_cause', 'notification_log', 'payment_history',
    'operating_carrier', 'flight_distance', 'legal_regime', 'expense_eligibility',
    'policy_version', 'reasonable_measures',
}
CONTROL_FACTS = {'legal_review_required', 'conflict_review_status', 'evidence_access_status', 'policy_status'}
TECHNICAL_STATES = {
    'timeout': ('EVIDENCE_UNAVAILABLE', 'Internal evidence is temporarily unavailable.', True),
    'parser_error': ('EVIDENCE_PARSE_FAILED', 'The evidence could not be processed.', True),
    'cross_case_reference': ('EVIDENCE_SCOPE_VIOLATION', 'The evidence reference is not valid for this case.', False),
}


@dataclass(frozen=True)
class Decision:
    missing: tuple[MissingFact, ...] = ()
    reason: str | None = None
    explanation: str = ''
    position: FinancialPosition | None = None
    error: TechnicalError | None = None
    serious: bool = False


def _index(facts: tuple[Fact, ...]) -> tuple[dict[str, Fact], set[str]]:
    values: dict[str, Fact] = {}
    conflicts: set[str] = set()
    for fact in facts:
        if not fact.sources:
            continue
        previous = values.get(fact.name)
        if previous and (type(previous.value) is not type(fact.value) or previous.value != fact.value):
            conflicts.add(fact.name)
        values[fact.name] = fact
    return values, conflicts


def _valid(name: str, fact: Fact | None) -> bool:
    if fact is None:
        return False
    value = fact.value
    if name == 'receipt_amount_minor':
        return type(value) is int and value >= 0
    if name == 'receipt_currency':
        return isinstance(value, str) and len(value) == 3 and value.isascii() and value.isalpha() and value.isupper()
    if name == 'receipt_readable':
        return value is True
    return isinstance(value, str) and bool(value.strip())


def assess(snapshot: CaseSnapshot, sources: tuple[SourceRef, ...]) -> Decision:
    issues = set(snapshot.issues)
    # Only System 1's internal context may carry execution/eligibility controls.
    internal, internal_conflicts = _index(snapshot.booking_context + snapshot.flight_context)
    all_facts = snapshot.known_facts + snapshot.customer_context + snapshot.booking_context + snapshot.flight_context
    facts, conflicts = _index(all_facts)
    value = lambda name: internal[name].value if name in internal else None

    if issues & SERIOUS_ISSUES:
        return Decision(reason='SERIOUS_ISSUE', serious=True,
                        explanation='A safety or specialist care colleague needs to review this serious report before any settlement. Reported issues: '
                        + ', '.join(sorted(issues & SERIOUS_ISSUES)) + '.')
    unsupported = issues - INTAKE_REQUIREMENTS.keys()
    if not issues or unsupported:
        return Decision(reason='UNSUPPORTED_ACTION', explanation='A customer care specialist is needed for an action outside this demo: '
                        + ', '.join(sorted(unsupported or {'unclassified_request'})) + '.')
    if internal_conflicts & (INTERNAL_FACTS | CONTROL_FACTS):
        return Decision(reason='UNRESOLVED_CONFLICT', explanation='Internal records disagree on a decision-critical check. A specialist must reconcile these records.')
    access = value('evidence_access_status')
    if access is not None and access != 'available':
        code, message, retryable = TECHNICAL_STATES.get(str(access), ('INVALID_INTERNAL_CONTEXT', 'The internal evidence status is invalid.', False))
        return Decision(error=TechnicalError(code=code, message=message, retryable=retryable))
    if value('policy_status') not in (None, 'available'):
        return Decision(error=TechnicalError(code='POLICY_UNAVAILABLE', message='Approved policy data is unavailable.', retryable=True))
    if value('legal_review_required') is True:
        return Decision(reason='UNCLEAR_RULE', explanation='A legal specialist must confirm the applicable rule or exception. No entitlement decision has been made.')
    if value('legal_review_required') is not None and value('legal_review_required') is not False:
        return Decision(error=TechnicalError(code='INVALID_INTERNAL_CONTEXT', message='The legal review flag must be a boolean.', retryable=False))

    missing: dict[str, MissingFact] = {}
    requested = dict.fromkeys(m.name for m in snapshot.missing_information)
    for issue in snapshot.issues:
        requested.update(dict.fromkeys(INTAKE_REQUIREMENTS[issue]))
    # Invalid supplied optional evidence must not be silently accepted.
    requested.update(dict.fromkeys(name for name in facts if name in QUESTIONS))
    for name in requested:
        if name in {'customer_match', 'booking_match', 'flight_match'}:
            if name in internal_conflicts:
                return Decision(reason='UNRESOLVED_CONFLICT', explanation='Matched internal records disagree. A specialist must reconcile the booking and passenger relationship.')
            if value(name) != 'matched':
                missing['booking_reference'] = missing_fact('booking_reference')
            continue
        if name in INTERNAL_FACTS:
            if name not in internal or internal[name].value in (None, ''):
                return Decision(error=TechnicalError(code='INTERNAL_EVIDENCE_REQUIRED',
                                message='Internal records must be enriched before assessment: ' + name + '.', retryable=False))
            continue
        if name not in QUESTIONS:
            return Decision(reason='UNSUPPORTED_ACTION', explanation='A specialist must clarify an unsupported evidence requirement: ' + name + '.')
        # A matching flight/date is an alternative to a booking reference.
        if name == 'booking_reference' and name not in conflicts and all(
                _valid(n, facts.get(n)) and n not in conflicts for n in ('flight_number', 'flight_date')):
            continue
        if name in conflicts or not _valid(name, facts.get(name)):
            missing[name] = missing_fact(name, conflicting=name in conflicts)

    customer_conflicts = conflicts & QUESTIONS.keys()
    if customer_conflicts and value('conflict_review_status') == 'unresolved':
        return Decision(missing=tuple(missing.values()), reason='UNRESOLVED_CONFLICT',
                        explanation='Material evidence still conflicts after clarification. A specialist must reconcile the original sources and prior attempts.')
    other_conflicts = conflicts - QUESTIONS.keys() - CONTROL_FACTS - INTERNAL_FACTS
    if other_conflicts:
        return Decision(reason='UNRESOLVED_CONFLICT', explanation='A specialist must reconcile conflicting evidence outside the supported clarification fields: '
                        + ', '.join(sorted(other_conflicts)) + '.')
    if missing:
        return Decision(missing=tuple(missing.values()), explanation='Specific customer evidence is needed to continue the review.')
    if issues != {'expense_reimbursement'}:
        return Decision(reason='UNSUPPORTED_ACTION', explanation='The available evidence is ready for a claims specialist. Legal adjudication of '
                        + ', '.join(sorted(issues - {'expense_reimbursement'})) + ' is outside the approved demo policy.')

    eligibility = value('expense_eligibility')
    if eligibility is None:
        return Decision(error=TechnicalError(code='INTERNAL_EVIDENCE_REQUIRED',
                        message='System 1 must supply a sourced expense eligibility check before reimbursement.', retryable=False))
    if eligibility != 'eligible':
        return Decision(reason='UNCLEAR_RULE', explanation='A claims specialist must review expense eligibility. A receipt alone does not establish entitlement; no payment or denial is proposed.')
    if value('payment_history') is None:
        return Decision(error=TechnicalError(code='INTERNAL_EVIDENCE_REQUIRED',
                        message='System 1 must supply a sourced reimbursement history check before payment.', retryable=False))
    if value('payment_history') != 'no_prior_reimbursement':
        return Decision(reason='UNRESOLVED_CONFLICT', explanation='A payment specialist must reconcile previous reimbursements and the remaining amount before a further payment is proposed.')
    amount, currency = facts['receipt_amount_minor'].value, facts['receipt_currency'].value
    limits = [limit for limit in snapshot.financial_limits if limit.type == 'REIMBURSEMENT' and limit.currency == currency]
    if not limits or any(limit.requires_approval or amount > limit.maximum_minor for limit in limits):
        return Decision(reason='AUTHORITY_LIMIT', explanation=f'A colleague with payment authority must review the proposed reimbursement of {amount // 100}.{amount % 100:02d} {currency}. '
                        'The amount is not reduced to fit the AI limit.')
    explanation = 'The supplied eligibility check and expense evidence satisfy the synthetic demo policy.'
    return Decision(explanation=explanation, position=FinancialPosition(type='REIMBURSEMENT', amount_minor=amount,
                    currency=currency, explanation=explanation, sources=sources))
