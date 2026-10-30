"""Regression coverage for the active System 2 pipeline."""
import unittest
from unittest.mock import patch

from backend.ai_service.fixtures import demo_request
from backend.ai_service.retrieval import RetrievalResult
from backend.ai_service.workflow import process_case


class WorkflowPipelineTests(unittest.TestCase):
    def test_knowledge_failure_prevents_resolution(self):
        failure = RetrievalResult(status='FAILED', error_code='KNOWLEDGE_UNAVAILABLE', reason='Knowledge unavailable.')
        with patch('backend.ai_service.workflow.retrieve', return_value=failure):
            result = process_case(demo_request('clear'), lambda _: None)
        self.assertEqual(result.status, 'FAILED')
        self.assertIsNone(result.proposed_action)
        self.assertEqual(result.technical_error.code, 'KNOWLEDGE_UNAVAILABLE')

    def document_case(self, text):
        from datetime import datetime, timezone
        from hashlib import sha256
        from backend.ai_service.evidence import AttachmentResult, EvidenceScope
        from backend.contracts import AttachmentRef, SourceRef
        request = demo_request('clear')
        reference = AttachmentRef(attachment_id='new-receipt', filename='receipt.txt',
                                  media_type='text/plain', local_reference='system-1-token')
        request = request.model_copy(update={'snapshot': request.snapshot.model_copy(update={
            'attachments': (reference,), 'known_facts': (), 'flight_context': ()})})
        content = text.encode()
        result = AttachmentResult(scope=EvidenceScope(case_id=request.case_id, case_version=request.case_version),
            reference=reference, status='found', content=content,
            source=SourceRef(source_id=reference.attachment_id, version='7'),
            content_hash=sha256(content).hexdigest(), observed_at=datetime.now(timezone.utc))
        return request, result

    def processor(self, document, retriever=None):
        from datetime import datetime, timezone
        from backend.ai_service import create_processor
        from backend.ai_service.evidence import create_evidence_adapters, FakeAttachmentReader, FakeRecordReader, LookupResult
        record = LookupResult(scope=document.scope, status='found', freshness='current',
            observed_at=datetime.now(timezone.utc), facts=demo_request('clear').snapshot.flight_context)
        return create_processor(adapters=create_evidence_adapters(
            attachments=FakeAttachmentReader((document,)), operational=FakeRecordReader({document.scope: record})),
            retriever=retriever)

    def test_document_and_internal_readers_drive_real_service_without_mutating_snapshot(self):
        request, document = self.document_case('Total: 12.34\nCurrency: EUR\nDate: 2026-10-29\nPurpose: meals')
        before = request.model_dump_json()
        with patch.dict('os.environ', {'AI_MODE': 'offline'}):
            result = self.processor(document)(request, lambda _: None)
        self.assertEqual(result.status, 'SUCCEEDED')
        self.assertEqual(result.proposed_action.type, 'RESOLVE')
        position = result.proposed_action.payload.financial_positions[0]
        self.assertEqual(position.amount_minor, 1234)
        self.assertIn(document.source, position.sources)
        self.assertEqual(request.model_dump_json(), before)

    def test_partial_document_requests_only_missing_currency(self):
        request, document = self.document_case('Total: 12.34\nPurpose: meals')
        with patch.dict('os.environ', {'AI_MODE': 'offline'}):
            result = self.processor(document)(request, lambda _: None)
        self.assertEqual(result.proposed_action.type, 'REQUEST_INFORMATION')
        self.assertEqual([f.name for f in result.proposed_action.payload.missing_facts], ['receipt_currency'])

    def test_missing_attachment_adapter_fails_instead_of_ignoring_attachment(self):
        request, _ = self.document_case('Total: 12.34')
        result = process_case(request, lambda _: None)
        self.assertEqual(result.status, 'FAILED')
        self.assertEqual(result.technical_error.code, 'ATTACHMENT_ADAPTER_UNCONFIGURED')

    def test_retrieval_outcomes_gate_financial_proposal(self):
        from backend.ai_service.workflow import create_processor
        for status, expected in [('UNSUPPORTED', 'HANDOFF'), ('UNCLEAR_RULE', 'HANDOFF'),
                                 ('APPLICABILITY_GAP', 'REQUEST_INFORMATION')]:
            knowledge = RetrievalResult(status=status, gaps=('event_date',) if status == 'APPLICABILITY_GAP' else (),
                                        reason='Selected knowledge requires review.')
            with self.subTest(status=status):
                result = create_processor(retriever=lambda _: knowledge)(demo_request('clear'), lambda _: None)
                self.assertEqual(result.proposed_action.type, expected)
                self.assertNotIn('demo-expense-policy', [s.source_id for s in result.assessment.sources])

    def test_selected_policy_versions_reach_action_and_progress(self):
        from backend.ai_service.retrieval import retrieve, RetrievalQuery
        from backend.ai_service.workflow import create_processor
        selected = retrieve(RetrievalQuery(issue_tags=('expense_reimbursement',)))
        selected = selected.model_copy(update={'passages': tuple(p.model_copy(update={'version': '3'}) for p in selected.passages)})
        events = []
        result = create_processor(retriever=lambda _: selected)(demo_request('clear'), events.append)
        self.assertEqual(result.proposed_action.type, 'RESOLVE')
        self.assertEqual([s.version for s in result.proposed_action.sources if s.source_id == 'demo-expense-policy'], ['3'])
        self.assertIn('demo-expense-policy', next(e.source_ids for e in events if e.step_id == 'retrieve_policy' and e.type == 'step.completed'))

    def test_live_experts_receive_prepared_facts_and_selected_passages(self):
        request, document = self.document_case('Total: 12.34\nCurrency: EUR\nPurpose: meals')
        with patch.dict('os.environ', {'AI_MODE': 'openai', 'OPENAI_API_KEY': 'test-only'}), \
             patch('backend.ai_service.experts.run_experts', side_effect=lambda request, baseline, *args, **kwargs: baseline) as experts:
            result = self.processor(document)(request, lambda _: None)
        self.assertEqual(result.status, 'SUCCEEDED')
        prepared = experts.call_args.args[0]
        self.assertIn(1234, [f.value for f in prepared.snapshot.known_facts if f.name == 'receipt_amount_minor'])
        self.assertEqual({p.role for p in experts.call_args.kwargs['knowledge'].passages},
                         {'RULE', 'PREREQUISITE', 'EXCEPTION'})
