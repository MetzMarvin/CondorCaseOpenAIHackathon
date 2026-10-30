"""Synchronous, offline demo assessment. Never executes proposed actions."""
from typing import Callable
from uuid import NAMESPACE_URL, uuid5

from backend.contracts import (
    Assessment, FinancialPosition, Handoff, HandoffPayload, InformationPayload,
    MissingFact, ProgressUpdate, RequestInformation, ResolutionPayload, Resolve,
    RunRequest, RunResult, SourceRef, TechnicalError,
)

ProgressCallback = Callable[[ProgressUpdate], None]
POLICY = SourceRef(source_id='demo-expense-policy', version='1')
# Approved synthetic demo policy, not a statement of real airline entitlement.
SUPPORTED_ISSUES = {'expense_reimbursement'}
SERIOUS_ISSUES = {'safety_incident', 'serious_injury'}
REQUIRED_FACTS = {
    'receipt_amount_minor': 'Bitte senden Sie einen Beleg mit dem erstattungsfähigen Betrag in Cent.',
    'receipt_currency': 'Bitte nennen Sie die Währung des Belegs.',
}


def process_case(request: RunRequest, emit_progress: ProgressCallback) -> RunResult:
    """Consume System 1's snapshot and callback; return a typed simulated result."""
    identity = dict(run_id=request.run_id, case_id=request.case_id,
                    based_on_case_version=request.case_version)
    step = 'extract_evidence'
    try:
        snapshot = request.snapshot
        if snapshot.owner.type != 'AI' or snapshot.status != 'IN_PROGRESS':
            return RunResult(**identity, status='FAILED', technical_error=TechnicalError(
                code='INVALID_AI_CONTEXT', message='KI-Verarbeitung benötigt einen aktiven KI-Fall.', retryable=False))
        emit_progress(ProgressUpdate(step_id=step, type='step.started', summary='Demo-Evidenz wird geprüft.'))
        facts = {}
        conflict = False
        for fact in snapshot.known_facts:
            if fact.name in facts and facts[fact.name].value != fact.value:
                conflict = True
            facts[fact.name] = fact
        sources = tuple(dict.fromkeys((POLICY, *(s for f in snapshot.known_facts for s in f.sources))))
        emit_progress(ProgressUpdate(step_id=step, type='step.completed', summary='Bereitgestellte Fakten geprüft.'))
        step = 'assess'
        emit_progress(ProgressUpdate(step_id=step, type='step.started', summary='Demo-Fall wird bewertet.'))
        missing = list(snapshot.missing_information)
        reason = None
        explanation = 'Belegte Kosten entsprechen der synthetischen Demo-Regel.'
        serious = bool(set(snapshot.issues) & SERIOUS_ISSUES)
        if serious:
            reason, explanation = 'SERIOUS_ISSUE', 'Sicherheitsvorfall oder schwere Verletzung benötigt Fachbearbeitung.'
        elif not snapshot.issues or set(snapshot.issues) - SUPPORTED_ISSUES:
            reason, explanation = 'UNSUPPORTED_ACTION', 'Mindestens ein Anliegen liegt außerhalb der unterstützten Demo-Regel.'
        elif conflict:
            reason, explanation = 'UNRESOLVED_CONFLICT', 'Widersprüchliche Fakten erfordern eine fachliche Prüfung.'
        else:
            for name, question in REQUIRED_FACTS.items():
                if (name not in facts or not facts[name].sources) and not any(m.name == name for m in missing):
                    missing.append(MissingFact(name=name, reason=question))
        position = None
        if not reason and not missing:
            amount = facts['receipt_amount_minor'].value
            currency = facts['receipt_currency'].value
            if type(amount) is not int or amount < 0 or not isinstance(currency, str) or len(currency) != 3 or not currency.isascii() or not currency.isupper() or not currency.isalpha():
                missing.append(MissingFact(name='receipt_details', reason='Bitte bestätigen Sie Betrag und dreistellige Währung des Belegs.'))
            else:
                limits = [limit for limit in snapshot.financial_limits if limit.type == 'REIMBURSEMENT' and limit.currency == currency]
                if not limits or any(limit.requires_approval or amount > limit.maximum_minor for limit in limits):
                    reason, explanation = 'AUTHORITY_LIMIT', 'Die Erstattung überschreitet die bereitgestellte KI-Befugnis oder benötigt Freigabe.'
                else:
                    position = FinancialPosition(type='REIMBURSEMENT', amount_minor=amount, currency=currency,
                                                 explanation=explanation, sources=sources)
        desired = 'HANDOFF' if reason else 'REQUEST_INFORMATION' if missing else 'RESOLVE'
        if desired not in snapshot.permitted_actions:
            reason, explanation, desired = 'AUTHORITY_LIMIT', 'Die erforderliche Aktion ist für die KI nicht freigegeben.', 'HANDOFF'
        if desired == 'HANDOFF' and 'HANDOFF' not in snapshot.permitted_actions:
            raise ValueError('No authorized proposal available')
        if desired == 'REQUEST_INFORMATION':
            explanation = 'Für die Demo-Entscheidung fehlen belegte Angaben.'
        assessment = Assessment(issues=snapshot.issues, missing_facts=tuple(missing),
                                severity='serious' if serious else 'ordinary', sentiment='not_assessed',
                                sources=sources, next_action_explanation=explanation)
        emit_progress(ProgressUpdate(step_id=step, type='step.completed', summary=explanation))
        step = 'retrieve_policy'
        emit_progress(ProgressUpdate(step_id=step, type='step.completed', summary='Synthetische Demo-Regel v1 verwendet.', source_ids=(POLICY.source_id,)))
        envelope = dict(action_id=str(uuid5(NAMESPACE_URL, f'{request.case_id}/{request.run_id}/{request.case_version}/{desired}')),
                        case_id=request.case_id, run_id=request.run_id, expected_case_version=request.case_version, sources=sources)
        if desired == 'HANDOFF':
            action = Handoff(**envelope, type='HANDOFF', payload=HandoffPayload(
                reason_code=reason, suggested_queue='demo-specialists', summary=explanation,
                facts=snapshot.known_facts, evidence=sources,
                unresolved_questions=tuple(m.reason for m in missing),
                prior_attempts=tuple(m.body for m in snapshot.messages if m.sender == 'demo-ai')))
        elif desired == 'REQUEST_INFORMATION':
            action = RequestInformation(**envelope, type=desired, payload=InformationPayload(
                missing_facts=tuple(missing), question_de=' '.join(m.reason for m in missing)))
        else:
            action = Resolve(**envelope, type=desired, payload=ResolutionPayload(
                outcome='DEMO_REIMBURSEMENT', explanation=explanation, sources=sources,
                reply_de=f'Wir erstatten Ihnen im Demo-Modus {position.amount_minor / 100:.2f} {position.currency}.',
                financial_positions=(position,)))
        step = 'validate_action'
        result = RunResult(**identity, status='SUCCEEDED', assessment=assessment, proposed_action=action)
        emit_progress(ProgressUpdate(step_id=step, type='step.completed', summary='Vorschlag geprüft; Ausführung erfolgt durch den Fallservice.'))
        return result
    except Exception:
        # Callback failures also invalidate the run; never expose internal error details.
        try:
            emit_progress(ProgressUpdate(step_id=step, type='step.failed', summary='Technischer Fehler bei der Demo-Verarbeitung.'))
        except Exception:
            pass
        return RunResult(**identity, status='FAILED', technical_error=TechnicalError(
            code='AI_PROCESSING_FAILED', message='Demo-Verarbeitung technisch fehlgeschlagen.', retryable=True))
