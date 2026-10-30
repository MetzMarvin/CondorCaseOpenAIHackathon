"""Synchronous, offline demo assessment. Never executes proposed actions."""
from typing import Callable
from uuid import NAMESPACE_URL, uuid5

from backend.contracts import (
    Assessment, Handoff, HandoffPayload, InformationPayload, ProgressUpdate,
    RequestInformation, ResolutionPayload, Resolve, RunRequest, RunResult, TechnicalError,
)
from backend.ai_service.assessment import POLICY, assess
from backend.ai_service.questions import information_message

ProgressCallback = Callable[[ProgressUpdate], None]


def process_case(request: RunRequest, emit_progress: ProgressCallback) -> RunResult:
    """Assess System 1's read-only snapshot and propose one action, or fail safely."""
    identity = dict(run_id=request.run_id, case_id=request.case_id,
                    based_on_case_version=request.case_version)
    step = 'extract_evidence'
    try:
        snapshot = request.snapshot
        if snapshot.owner.type != 'AI' or snapshot.status != 'IN_PROGRESS':
            return RunResult(**identity, status='FAILED', technical_error=TechnicalError(
                code='INVALID_AI_CONTEXT', message='Processing requires an active AI-owned case.', retryable=False))
        emit_progress(ProgressUpdate(step_id=step, type='step.started', summary='Checking supplied evidence.'))
        facts = snapshot.known_facts + snapshot.customer_context + snapshot.booking_context + snapshot.flight_context
        sources = tuple(dict.fromkeys((POLICY, *(source for fact in facts for source in fact.sources))))
        emit_progress(ProgressUpdate(step_id=step, type='step.completed', summary='Supplied evidence references collected.'))
        step = 'retrieve_policy'
        emit_progress(ProgressUpdate(step_id=step, type='step.completed', summary='Using synthetic demo policy v2.', source_ids=(POLICY.source_id,)))
        step = 'assess'
        emit_progress(ProgressUpdate(step_id=step, type='step.started', summary='Checking evidence gaps and specialist needs.'))
        decision = assess(snapshot, sources)
        if decision.error:
            emit_progress(ProgressUpdate(step_id=step, type='step.failed', summary=decision.error.message))
            return RunResult(**identity, status='FAILED', technical_error=decision.error)
        desired = 'HANDOFF' if decision.reason else 'REQUEST_INFORMATION' if decision.missing else 'RESOLVE'
        reason, explanation = decision.reason, decision.explanation
        if desired not in snapshot.permitted_actions:
            reason, explanation, desired = 'AUTHORITY_LIMIT', 'A colleague with the appropriate authority must perform the required action.', 'HANDOFF'
        if desired == 'HANDOFF' and 'HANDOFF' not in snapshot.permitted_actions:
            emit_progress(ProgressUpdate(step_id=step, type='step.failed', summary='No permitted action is available.'))
            return RunResult(**identity, status='FAILED', technical_error=TechnicalError(
                code='NO_PERMITTED_ACTION', message='System 1 must review the permitted actions.', retryable=False))
        assessment = Assessment(issues=snapshot.issues, missing_facts=decision.missing,
                                severity='serious' if decision.serious else 'ordinary', sentiment='not_assessed',
                                sources=sources, next_action_explanation=explanation)
        emit_progress(ProgressUpdate(step_id=step, type='step.completed', summary=explanation))
        envelope = dict(action_id=str(uuid5(NAMESPACE_URL, f'{request.case_id}/{request.run_id}/{request.case_version}/{desired}')),
                        case_id=request.case_id, run_id=request.run_id, expected_case_version=request.case_version, sources=sources)
        if desired == 'HANDOFF':
            action = Handoff(**envelope, type='HANDOFF', payload=HandoffPayload(
                reason_code=reason, suggested_queue='demo-specialists', summary=explanation,
                facts=facts, evidence=sources,
                unresolved_questions=tuple(item.reason for item in decision.missing) or (explanation,),
                prior_attempts=tuple(message.body for message in snapshot.messages if message.sender == snapshot.owner.id)))
        elif desired == 'REQUEST_INFORMATION':
            action = RequestInformation(**envelope, type=desired, payload=InformationPayload(
                missing_facts=decision.missing,
                question_de=information_message(decision.missing, is_reply=request.trigger == 'customer_reply')))
        else:
            position = decision.position
            amount = f'{position.amount_minor // 100}.{position.amount_minor % 100:02d} {position.currency}'
            action = Resolve(**envelope, type=desired, payload=ResolutionPayload(
                outcome='DEMO_REIMBURSEMENT', explanation=explanation, sources=sources,
                reply_de='Thank you for sharing the details and evidence. We are sorry for the inconvenience with your journey. '
                         f'Your expense reimbursement of {amount} has been approved under the demo policy. '
                         'This is a simulation; no real payment has been made.\n\nKind regards,\nYour Customer Care team',
                financial_positions=(position,)))
        step = 'validate_action'
        result = RunResult(**identity, status='SUCCEEDED', assessment=assessment, proposed_action=action)
        emit_progress(ProgressUpdate(step_id=step, type='step.completed', summary='Proposal validated; System 1 authorizes and applies it.'))
        return result
    except Exception:
        # Callback failures also invalidate the run; never expose internal error details.
        try:
            emit_progress(ProgressUpdate(step_id=step, type='step.failed', summary='Demo processing failed technically.'))
        except Exception:
            pass
        return RunResult(**identity, status='FAILED', technical_error=TechnicalError(
            code='AI_PROCESSING_FAILED', message='Demo processing failed technically.', retryable=True))
