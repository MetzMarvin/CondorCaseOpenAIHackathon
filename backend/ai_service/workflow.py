"""Synchronous, offline demo assessment. Never executes proposed actions."""
from typing import Callable
from datetime import date
from dataclasses import replace
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid5

from backend.contracts import (
    SourceRef, Fact, Assessment, Handoff, HandoffPayload, InformationPayload, ProgressUpdate,
    RequestInformation, ResolutionPayload, Resolve, RunRequest, RunResult, TechnicalError,
)
from backend.ai_service.assessment import assess, Decision, INTERNAL_FACTS
from backend.ai_service.questions import information_message, QUESTIONS, missing_fact
from backend.ai_service.retrieval import RetrievalQuery, RetrievalResult, retrieve
from backend.ai_service.reconciliation import prepare_evidence
from backend.ai_service.evidence import AttachmentRequest, AttachmentResult, EvidenceScope
from backend.ai_service.extraction import DocumentExtractor, ExtractionResult
from backend.ai_service.context import ProcessingBundle

ProgressCallback = Callable[[ProgressUpdate], None]

# This implementation adjudicates only this reviewed synthetic policy content.
# A new card/version requires a coordinated deterministic rule implementation.
EXPENSE_POLICY_HASH = '3bf29bc02f767a9772c7aac3ec6a5f214a217ba7d9de0fcbb0b3f1dd716022ed'
EXPENSE_SUPPORT = {'expense-rule', 'expense-prerequisites', 'expense-exceptions'}


def supports_implemented_expense_rule(passages):
    selected = {p.passage_id for p in passages if p.source_id == 'demo-expense-policy'
                and p.version == '2' and p.content_hash == EXPENSE_POLICY_HASH
                and p.source_kind == 'demo_assumption'}
    return EXPENSE_SUPPORT <= selected and any(p.passage_id == 'expense-rule'
        and p.source_id == 'demo-expense-policy' and p.version == '2'
        and p.rule_key == 'expense_reimbursement' and p.decision == 'supported' for p in passages)


def create_processor(*, adapters=None, extractor=None, retriever=None):
    """Bind offline dependencies without changing the synchronous call signature."""
    def processor(request, emit_progress):
        return run_workflow(request, emit_progress, bundle=ProcessingBundle(request),
                            adapters=adapters, extractor=extractor, retriever=retriever)
    return processor


def process_case(request: RunRequest, emit_progress: ProgressCallback) -> RunResult:
    return create_processor()(request, emit_progress)


def run_workflow(request, emit_progress, *, bundle, adapters=None, extractor=None, retriever=None):
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
        customer_facts = []
        unreadable_without_source = False
        scope = EvidenceScope(case_id=request.case_id, case_version=request.case_version)
        for message in snapshot.messages:
            if message.sender in {snapshot.owner.id, 'AI', 'SYSTEM', 'condor-service@example.com'}:
                continue
            extracted_message = DocumentExtractor().extract_message(message, scope)
            bundle.message_extractions.append(extracted_message)
            if extracted_message.error:
                return RunResult(**identity, status='FAILED', technical_error=extracted_message.error)
            for candidate in extracted_message.candidates:
                provenance = candidate.provenance
                if (provenance.source != SourceRef(source_id=message.message_id, version=str(scope.case_version))
                        or provenance.content_hash != sha256(message.body.encode('utf-8')).hexdigest()
                        or message.body[provenance.span_start:provenance.span_end] != provenance.original_value):
                    raise ValueError('Message extraction provenance mismatch')
                customer_facts.append(Fact(name=candidate.name, value=candidate.value,
                                           sources=(provenance.source,)))
        if adapters is not None:
            scope = EvidenceScope(case_id=request.case_id, case_version=request.case_version)
            for reference in snapshot.attachments:
                attachment = AttachmentResult.model_validate(adapters.attachments.read(AttachmentRequest(scope=scope, reference=reference)).model_dump())
                if attachment.scope != scope or attachment.reference != reference:
                    return RunResult(**identity, status='FAILED', technical_error=TechnicalError(
                        code='EVIDENCE_SCOPE_VIOLATION', message='Attachment access returned a different scope.', retryable=False))
                bundle.attachments.append(attachment)
                extracted = ExtractionResult.model_validate((extractor or DocumentExtractor()).extract(attachment).model_dump())
                if extracted.scope != scope:
                    raise ValueError('Extraction scope mismatch')
                bundle.extractions.append(extracted)
                if extracted.status == 'parser_failure':
                    return RunResult(**identity, status='FAILED', technical_error=extracted.error)
                if extracted.status == 'unreadable':
                    if attachment.source:
                        customer_facts.append(Fact(name='receipt_readable', value=False, sources=(attachment.source,)))
                    else:
                        unreadable_without_source = True
                for candidate in extracted.candidates:
                    provenance = candidate.provenance
                    if provenance.page < 1 or provenance.span_start < 0 or provenance.span_end <= provenance.span_start or provenance.span_end - provenance.span_start != len(provenance.original_value):
                        raise ValueError('Invalid extraction span')
                    if candidate.provenance.source != attachment.source or candidate.provenance.content_hash != attachment.content_hash:
                        raise ValueError('Extraction provenance mismatch')
                    customer_facts.append(Fact(name=candidate.name, value=candidate.value, sources=(candidate.provenance.source,)))
        prepared = prepare_evidence(request, adapters, customer_facts=tuple(customer_facts))
        if prepared.error:
            return RunResult(**identity, status='FAILED', technical_error=prepared.error)
        request = prepared.request
        bundle.effective_request = request
        snapshot = request.snapshot
        facts = snapshot.known_facts + snapshot.customer_context + snapshot.booking_context + snapshot.flight_context
        sources = tuple(dict.fromkeys(source for fact in facts for source in fact.sources))
        emit_progress(ProgressUpdate(step_id=step, type='step.completed', summary='Supplied evidence references collected.',
                                     source_ids=tuple(dict.fromkeys(source.source_id for source in sources))))
        step = 'assess'
        emit_progress(ProgressUpdate(step_id=step, type='step.started', summary='Checking evidence gaps and specialist needs.'))
        decision = assess(snapshot, sources)
        if decision.error:
            emit_progress(ProgressUpdate(step_id=step, type='step.failed', summary=decision.error.message))
            return RunResult(**identity, status='FAILED', technical_error=decision.error)
        if unreadable_without_source and not decision.reason:
            missing = {m.name: m for m in decision.missing}
            missing['receipt_readable'] = missing_fact('receipt_readable')
            decision = Decision(missing=tuple(missing.values()), explanation='Readable expense evidence is needed to continue the review.')
        step = 'retrieve_policy'
        values = {}
        conflicts = set()
        for fact in facts:
            if fact.sources and isinstance(fact.value, str):
                if fact.name in values and values[fact.name] != fact.value:
                    conflicts.add(fact.name)
                values[fact.name] = fact.value
        for name in conflicts:
            values.pop(name, None)
        # Internal applicability cannot be spoofed through customer evidence.
        for name in INTERNAL_FACTS:
            values.pop(name, None)
        for fact in snapshot.booking_context + snapshot.flight_context:
            if fact.sources and isinstance(fact.value, str) and fact.name not in conflicts:
                values[fact.name] = fact.value
        try:
            event_date = date.fromisoformat(values['flight_date']) if 'flight_date' in values else None
        except ValueError:
            event_date = None
        knowledge = RetrievalResult.model_validate((retriever or retrieve)(RetrievalQuery(issue_tags=snapshot.issues,
            event_date=event_date, applicability_facts=values)).model_dump())
        bundle.retrieval = knowledge
        if knowledge.status == 'FAILED':
            return RunResult(**identity, status='FAILED', technical_error=TechnicalError(
                code=knowledge.error_code or 'KNOWLEDGE_UNAVAILABLE', message='Approved knowledge retrieval failed.', retryable=True))
        if not decision.reason:
            if knowledge.status == 'APPLICABILITY_GAP':
                names = tuple('flight_date' if n == 'event_date' else n for n in knowledge.gaps)
                if not names or any(n not in QUESTIONS for n in names):
                    return RunResult(**identity, status='FAILED', technical_error=TechnicalError(
                        code='INTERNAL_APPLICABILITY_REQUIRED', message='Internal applicability facts are required.', retryable=False))
                decision = Decision(missing=tuple({m.name: m for m in (*(missing_fact(n) for n in names), *decision.missing)}.values()),
                                    explanation='Travel or customer evidence is needed to establish policy applicability.')
            elif not decision.missing and knowledge.status == 'UNCLEAR_RULE':
                decision = Decision(reason='UNCLEAR_RULE', explanation='Applicable approved rules require specialist reconciliation.')
            elif not decision.missing and (knowledge.status != 'SUPPORTED' or not supports_implemented_expense_rule(knowledge.passages)):
                decision = Decision(reason='UNSUPPORTED_ACTION', explanation='No approved applicable rule supports this expense proposal.')
        selected_sources = tuple(dict.fromkeys(SourceRef(source_id=p.source_id, version=p.version) for p in knowledge.passages))
        sources = tuple(dict.fromkeys((*selected_sources, *sources)))
        if decision.position:
            decision = replace(decision, position=decision.position.model_copy(update={'sources': sources}))
        emit_progress(ProgressUpdate(step_id=step, type='step.completed', summary='Approved knowledge applicability checked.',
                                     source_ids=tuple(s.source_id for s in selected_sources)))
        step = 'assess'
        if adapters is None and snapshot.attachments and decision.missing and not decision.reason:
            return RunResult(**identity, status='FAILED', technical_error=TechnicalError(
                code='ATTACHMENT_ADAPTER_UNCONFIGURED', message='Attached evidence requires a configured case-scoped reader.', retryable=False))
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
        emit_progress(ProgressUpdate(step_id=step, type='step.completed', summary='Deterministic assessment completed.'))
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
                         f'Your expense reimbursement of {amount} is proposed under the demo policy, subject to case-service validation. '
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
