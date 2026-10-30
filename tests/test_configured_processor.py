import unittest
from datetime import datetime, timezone
from hashlib import sha256
from backend.ai_service.fixtures import demo_request
from backend.ai_service.evidence import AttachmentResult, EvidenceScope, FakeAttachmentReader, create_evidence_adapters
from backend.ai_service.service import create_processor
from backend.ai_service.settings import Settings
from backend.contracts import AttachmentRef, SourceRef


class ConfiguredProcessorTests(unittest.TestCase):
    def test_authorized_receipt_bytes_complete_missing_case_without_mutating_snapshot(self):
        request = demo_request('missing')
        reference = AttachmentRef(attachment_id='receipt', filename='private.txt', media_type='text/plain', local_reference='case-token')
        request = request.model_copy(update={'snapshot': request.snapshot.model_copy(update={'known_facts': (), 'attachments': (reference,)})})
        content = b'Total: 42.00\nCurrency: EUR\nPurpose: meals\nDate: 2026-10-30'
        result = AttachmentResult(scope=EvidenceScope(case_id=request.case_id, case_version=request.case_version), reference=reference,
            status='found', content=content, source=SourceRef(source_id='receipt', version='7'), content_hash=sha256(content).hexdigest(), observed_at=datetime.now(timezone.utc))
        processor = create_processor(adapters=create_evidence_adapters(attachments=FakeAttachmentReader((result,))), settings=Settings('offline', ''))
        before = request.model_dump_json()
        outcome = processor(request, lambda _: None)
        self.assertEqual(outcome.status, 'SUCCEEDED')
        self.assertEqual(outcome.proposed_action.type, 'RESOLVE')
        self.assertEqual(outcome.proposed_action.payload.financial_positions[0].amount_minor, 4200)
        self.assertIn(SourceRef(source_id='receipt', version='7'), outcome.proposed_action.sources)
        self.assertEqual(request.model_dump_json(), before)

    def test_no_approved_policy_cannot_resolve_complete_receipt(self):
        from backend.ai_service.knowledge import KnowledgeRegistry
        from backend.ai_service.retrieval import retrieve
        processor = create_processor(settings=Settings('offline', ''), retriever=lambda query: retrieve(query,
            lambda: KnowledgeRegistry(schema_version=1, cards=())))
        outcome = processor(demo_request('clear'), lambda _: None)
        self.assertEqual(outcome.proposed_action.type, 'HANDOFF')
        self.assertEqual(outcome.proposed_action.payload.reason_code, 'UNSUPPORTED_ACTION')
        self.assertNotIn('demo-expense-policy', [s.source_id for s in outcome.proposed_action.sources])

    def test_unreadable_receipt_does_not_resolve_using_old_supplied_amount(self):
        request = demo_request('clear')
        reference = AttachmentRef(attachment_id='receipt', filename='private.txt', media_type='text/plain', local_reference='case-token')
        request = request.model_copy(update={'snapshot': request.snapshot.model_copy(update={'attachments': (reference,)})})
        content = b''
        read = AttachmentResult(scope=EvidenceScope(case_id=request.case_id, case_version=request.case_version), reference=reference,
            status='found', content=content, source=SourceRef(source_id='receipt', version='8'), content_hash=sha256(content).hexdigest(), observed_at=datetime.now(timezone.utc))
        processor = create_processor(settings=Settings('offline', ''), adapters=create_evidence_adapters(attachments=FakeAttachmentReader((read,))))
        outcome = processor(request, lambda _: None)
        self.assertEqual(outcome.proposed_action.type, 'REQUEST_INFORMATION')
        self.assertEqual([m.name for m in outcome.assessment.missing_facts], ['receipt_readable'])

    def test_attached_evidence_needing_extraction_requires_reader_configuration(self):
        request = demo_request('missing')
        reference = AttachmentRef(attachment_id='receipt', filename='receipt.txt', media_type='text/plain', local_reference='case-token')
        request = request.model_copy(update={'snapshot': request.snapshot.model_copy(update={'attachments': (reference,)})})
        result = create_processor(settings=Settings('offline', ''))(request, lambda _: None)
        self.assertEqual(result.status, 'FAILED')
        self.assertEqual(result.technical_error.code, 'ATTACHMENT_ADAPTER_UNCONFIGURED')

    def test_missing_internal_applicability_is_failed_even_with_customer_gaps(self):
        from backend.ai_service.retrieval import RetrievalResult
        processor = create_processor(settings=Settings('offline', ''), retriever=lambda query: RetrievalResult(
            status='APPLICABILITY_GAP', gaps=('legal_regime',), reason='Internal rule applicability unknown.'))
        result = processor(demo_request('missing'), lambda _: None)
        self.assertEqual(result.status, 'FAILED')
        self.assertEqual(result.technical_error.code, 'INTERNAL_APPLICABILITY_REQUIRED')

    def test_rule_metadata_does_not_authorize_unimplemented_policy(self):
        from backend.ai_service.knowledge import KnowledgeRegistry, bundled_registry, card_content_hash
        from backend.ai_service.retrieval import retrieve
        card = bundled_registry().cards[0].model_dump(mode='json')
        card['source_id'] = 'unimplemented-policy'
        for dependency in card['dependencies']:
            dependency['source_id'] = 'unimplemented-policy'
        card['content_hash'] = card_content_hash(card)
        registry = KnowledgeRegistry(schema_version=1, cards=(card,))
        processor = create_processor(settings=Settings('offline', ''), retriever=lambda query: retrieve(query, lambda: registry))
        outcome = processor(demo_request('clear'), lambda _: None)
        self.assertEqual(outcome.proposed_action.type, 'HANDOFF')
        self.assertEqual(outcome.proposed_action.payload.reason_code, 'UNSUPPORTED_ACTION')
