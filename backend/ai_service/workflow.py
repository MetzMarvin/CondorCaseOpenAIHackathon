"""Synchronous, offline demo assessment. Never executes proposed actions."""
from typing import Callable
from datetime import date
from functools import partial
from uuid import NAMESPACE_URL, uuid5

from backend.contracts import (
    Fact, SourceRef, Assessment, Handoff, HandoffPayload, InformationPayload, ProgressUpdate,
    RequestInformation, ResolutionPayload, Resolve, RunRequest, RunResult, TechnicalError,
)
from backend.ai_service.assessment import CONTROL_FACTS, INTERNAL_FACTS, Decision, assess
from backend.ai_service.evidence import AttachmentRequest, EvidenceScope, create_evidence_adapters
from backend.ai_service.extraction import DocumentExtractor
from backend.ai_service.reconciliation import prepare_evidence
from backend.ai_service.retrieval import RetrievalQuery, retrieve
from backend.ai_service.questions import QUESTIONS, missing_fact
from backend.ai_service.questions import information_message

ProgressCallback = Callable[[ProgressUpdate], None]


def create_processor(*, adapters=None, extractor=None, retriever=None, context_callback=None):
    """Bind backend-owned dependencies while preserving the two-argument contract."""
    return partial(_process_case, adapters=adapters, extractor=extractor, retriever=retriever, context_callback=context_callback)


def process_case(request: RunRequest, emit_progress: ProgressCallback) -> RunResult:
    return _process_case(request, emit_progress)


def _process_case(request: RunRequest, emit_progress: ProgressCallback, *,
                  adapters=None, extractor=None, retriever=None, context_callback=None) -> RunResult:
    """Assess System 1's read-only snapshot and propose one action, or fail safely."""
    identity = dict(run_id=request.run_id, case_id=request.case_id,
                    based_on_case_version=request.case_version)
    step = 'extract_evidence'
    try:
        snapshot = request.snapshot
        if snapshot.owner.type != 'AI' or snapshot.status != 'IN_PROGRESS':
            return RunResult(**identity, status='FAILED', technical_error=TechnicalError(
                code='INVALID_AI_CONTEXT', message='Processing requires an active AI-owned case.', retryable=False))
        emit_progress(ProgressUpdate(step_id=step, type='step.started', summary='Preparing case-scoped evidence.'))
        customer_facts = []
        scope = EvidenceScope(case_id=request.case_id, case_version=request.case_version)
        reader = (adapters or create_evidence_adapters()).attachments
        extractor = extractor or DocumentExtractor()
        for message in snapshot.messages:
            if message.sender in {snapshot.owner.id, 'AI', 'SYSTEM'}:
                continue
            extracted_message = DocumentExtractor().extract_message(message, scope)
            if extracted_message.error:
                emit_progress(ProgressUpdate(step_id=step, type='step.failed',
                                             summary=extracted_message.error.message))
                return RunResult(**identity, status='FAILED', technical_error=extracted_message.error)
            customer_facts.extend(Fact(name=c.name, value=c.value, sources=(c.provenance.source,))
                                  for c in extracted_message.candidates)
        for reference in snapshot.attachments:
            attachment = reader.read(AttachmentRequest(scope=scope, reference=reference))
            if attachment.scope != scope or attachment.reference != reference:
                raise ValueError('Attachment scope mismatch')
            extracted = extractor.extract(attachment)
            if extracted.scope != scope:
                raise ValueError('Extraction scope mismatch')
            if extracted.error:
                emit_progress(ProgressUpdate(step_id=step, type='step.failed', summary=extracted.error.message))
                return RunResult(**identity, status='FAILED', technical_error=extracted.error)
            customer_facts.extend(Fact(name=c.name, value=c.value, sources=(c.provenance.source,))
                                  for c in extracted.candidates)
            if extracted.status == 'unreadable':
                customer_facts.append(Fact(name='receipt_readable', value=False,
                    sources=(attachment.source or SourceRef(source_id=reference.attachment_id, version=str(request.case_version)),)))
        prepared = prepare_evidence(request, adapters, customer_facts=tuple(customer_facts))
        if prepared.error:
            emit_progress(ProgressUpdate(step_id=step, type='step.failed', summary=prepared.error.message))
            return RunResult(**identity, status='FAILED', technical_error=prepared.error)
        snapshot = prepared.request.snapshot
        facts = snapshot.known_facts + snapshot.customer_context + snapshot.booking_context + snapshot.flight_context
        emit_progress(ProgressUpdate(step_id=step, type='step.completed', summary='Case evidence prepared.',
                                     source_ids=tuple(s.source_id for s in prepared.sources)))
        step = 'retrieve_policy'
        emit_progress(ProgressUpdate(step_id=step, type='step.started', summary='Retrieving approved applicable knowledge.'))
        # Conflicting or unsourced applicability values cannot select a rule.
        values = {}
        applicability_evidence = tuple(fact for fact in snapshot.known_facts + snapshot.customer_context
            if fact.name not in INTERNAL_FACTS | CONTROL_FACTS) + snapshot.booking_context + snapshot.flight_context
        for fact in applicability_evidence:
            if fact.sources:
                values.setdefault(fact.name, set()).add(str(fact.value))
        applicability = {name: next(iter(items)) for name, items in values.items() if len(items) == 1}
        event_date = None
        try:
            event_date = date.fromisoformat(applicability.get('event_date', applicability.get('flight_date', '')))
        except ValueError:
            pass
        knowledge = (retriever or retrieve)(RetrievalQuery(issue_tags=snapshot.issues,
            event_date=event_date, applicability_facts=applicability))
        if knowledge.status == 'FAILED':
            emit_progress(ProgressUpdate(step_id=step, type='step.failed', summary=knowledge.reason))
            return RunResult(**identity, status='FAILED', technical_error=TechnicalError(
                code=knowledge.error_code or 'KNOWLEDGE_UNAVAILABLE', message=knowledge.reason, retryable=True))
        policy_sources = tuple(dict.fromkeys(SourceRef(source_id=p.source_id, version=p.version) for p in knowledge.passages))
        sources = tuple(dict.fromkeys((*policy_sources, *prepared.sources)))
        emit_progress(ProgressUpdate(step_id=step, type='step.completed', summary=knowledge.reason,
                                     source_ids=tuple(s.source_id for s in policy_sources)))
        if context_callback is not None:
            context_callback(prepared.request, knowledge)
        step = 'assess'
        emit_progress(ProgressUpdate(step_id=step, type='step.started', summary='Checking evidence gaps and specialist needs.'))
        decision = assess(snapshot, sources)
        # Evidence collection and serious-case routing remain possible without a
        # resolution rule. A financial proposal always requires positive support.
        if not decision.error and not decision.reason:
            if knowledge.status == 'UNCLEAR_RULE':
                decision = Decision(reason='UNCLEAR_RULE', explanation=knowledge.reason)
            elif knowledge.status == 'APPLICABILITY_GAP':
                gaps = tuple('flight_date' if gap == 'event_date' else gap for gap in knowledge.gaps)
                if any(gap not in QUESTIONS for gap in gaps):
                    decision = Decision(error=TechnicalError(code='INTERNAL_EVIDENCE_REQUIRED',
                        message='Internal knowledge applicability facts are required.', retryable=False))
                else:
                    missing = {item.name: item for item in decision.missing}
                    missing.update((gap, missing_fact(gap)) for gap in gaps)
                    decision = Decision(missing=tuple(missing.values()), explanation=knowledge.reason)
            elif not decision.missing and (knowledge.status != 'SUPPORTED' or not any(
                    p.role == 'RULE' and p.rule_key == 'expense_reimbursement' and p.decision == 'supported'
                    for p in knowledge.passages)):
                decision = Decision(reason='UNSUPPORTED_ACTION', explanation='No approved rule supports automatic reimbursement.')
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
