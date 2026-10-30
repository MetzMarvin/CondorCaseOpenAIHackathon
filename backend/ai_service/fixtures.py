"""Deterministic System 2 snapshots; callers own persistence and reply intake."""
from backend.contracts import CaseSnapshot, Fact, FinancialLimit, MissingFact, Owner, RunRequest, SourceRef

SCENARIOS = ('clear', 'missing', 'reply', 'serious', 'unsupported', 'unreadable', 'partial_reply', 'legal_review', 'authority_limit', 'conflict')


def demo_request(scenario: str) -> RunRequest:
    if scenario not in SCENARIOS:
        raise ValueError('Unknown demo scenario')
    evidence = (SourceRef(source_id='demo-receipt-01', version='1'),)
    facts = (Fact(name='expense_purpose', value='Meal during the documented disruption.', sources=evidence),)
    facts += () if scenario in {'missing', 'partial_reply'} else (
        Fact(name='receipt_amount_minor', value=4200, sources=evidence),
        Fact(name='receipt_currency', value='EUR', sources=evidence),
    )
    if scenario == 'partial_reply':
        facts += (Fact(name='receipt_currency', value='EUR', sources=evidence),)
    if scenario == 'unreadable':
        facts += (Fact(name='receipt_readable', value=False, sources=evidence),)
    internal = (
        Fact(name='expense_eligibility', value='eligible', sources=(SourceRef(source_id='demo-eligibility-check', version='1'),)),
        Fact(name='payment_history', value='no_prior_reimbursement', sources=(SourceRef(source_id='demo-payment-history', version='1'),)),
    )
    if scenario == 'legal_review':
        internal += (Fact(name='legal_review_required', value=True, sources=evidence),)
    if scenario == 'conflict':
        facts += (Fact(name='receipt_amount_minor', value=8400, sources=(SourceRef(source_id='demo-receipt-02', version='1'),)),)
        internal += (Fact(name='conflict_review_status', value='unresolved', sources=evidence),)
    snapshot = CaseSnapshot(status='IN_PROGRESS', owner=Owner(type='AI', id='demo-ai'),
        language='en', messages=(), attachments=(), known_facts=facts,
        issues=('safety_incident',) if scenario == 'serious' else ('unsupported_request',) if scenario == 'unsupported' else ('expense_reimbursement',),
        missing_information=(MissingFact(name='receipt_currency', reason='Stale missing item; already supplied in the reply.'),) if scenario == 'partial_reply' else (),
        customer_context=(), booking_context=(), flight_context=internal,
        permitted_actions=('REQUEST_INFORMATION', 'RESOLVE', 'HANDOFF'),
        financial_limits=(FinancialLimit(type='REIMBURSEMENT', maximum_minor=1000 if scenario == 'authority_limit' else 10000, currency='EUR'),))
    return RunRequest(run_id=f'demo-run-{scenario}', case_id='demo-case-evidence' if scenario in {'missing', 'reply', 'partial_reply'} else f'demo-case-{scenario}',
        case_version=3 if scenario == 'reply' else 2 if scenario == 'partial_reply' else 1,
        trigger='customer_reply' if scenario in {'reply', 'partial_reply'} else 'manual_process', snapshot=snapshot)
