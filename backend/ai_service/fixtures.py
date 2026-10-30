"""Deterministic System 2 snapshots; callers own persistence and reply intake."""
from backend.contracts import CaseSnapshot, Fact, FinancialLimit, Owner, RunRequest, SourceRef


def demo_request(scenario: str) -> RunRequest:
    if scenario not in {'clear', 'missing', 'reply', 'serious', 'unsupported'}:
        raise ValueError('Unknown demo scenario')
    evidence = (SourceRef(source_id='demo-receipt-01', version='1'),)
    facts = () if scenario == 'missing' else (
        Fact(name='receipt_amount_minor', value=4200, sources=evidence),
        Fact(name='receipt_currency', value='EUR', sources=evidence),
    )
    snapshot = CaseSnapshot(status='IN_PROGRESS', owner=Owner(type='AI', id='demo-ai'),
        language='de', messages=(), attachments=(), known_facts=facts,
        issues=('safety_incident',) if scenario == 'serious' else ('unsupported_request',) if scenario == 'unsupported' else ('expense_reimbursement',),
        missing_information=(), customer_context=(), booking_context=(), flight_context=(),
        permitted_actions=('REQUEST_INFORMATION', 'RESOLVE', 'HANDOFF'),
        financial_limits=(FinancialLimit(type='REIMBURSEMENT', maximum_minor=10000, currency='EUR'),))
    return RunRequest(run_id=f'demo-run-{scenario}', case_id='demo-case-evidence' if scenario in {'missing', 'reply'} else f'demo-case-{scenario}',
        case_version=2 if scenario == 'reply' else 1, trigger='customer_reply' if scenario == 'reply' else 'manual_process', snapshot=snapshot)
