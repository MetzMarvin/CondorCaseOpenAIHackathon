import unittest

from backend.ai_service.fixtures import demo_request
from backend.ai_service.service import create_processor
from backend.ai_service.settings import Settings


class DiagnosticsTests(unittest.TestCase):
    def test_public_sink_receives_roundtrippable_versioned_manifest(self):
        from backend.ai_service.diagnostics import RunManifest
        manifests = []
        result = create_processor(settings=Settings('offline', ''), diagnostic_sink=manifests.append)(
            demo_request('clear'), lambda _: None)
        self.assertEqual(result.status, 'SUCCEEDED')
        manifest = manifests[0]
        self.assertIsInstance(manifest, RunManifest)
        self.assertEqual(RunManifest.model_validate_json(manifest.model_dump_json()), manifest)
        self.assertEqual((manifest.case_id, manifest.run_id, manifest.case_version),
                         ('demo-case-clear', 'demo-run-clear', 1))
        self.assertEqual(manifest.decision, 'RESOLVE')
        self.assertEqual(manifest.mode, 'offline')
        self.assertTrue(manifest.simulation)
        self.assertIsNone(manifest.model)
        self.assertEqual({(s.source_id, s.version) for s in manifest.evidence_sources}, {
            ('demo-receipt-01', '1'), ('demo-eligibility-check', '1'), ('demo-payment-history', '1')})
        self.assertEqual({(p.source_id, p.version) for p in manifest.knowledge}, {('demo-expense-policy', '2')})
        self.assertTrue(all(len(p.passage_hash) == 64 and len(p.source_hash) == 64 for p in manifest.knowledge))

    def test_attachment_bytes_and_extractor_configuration_are_traceable_without_content(self):
        from datetime import datetime, timezone
        from backend.ai_service.evidence import AttachmentResult, EvidenceScope, FakeAttachmentReader, create_evidence_adapters
        from backend.contracts import AttachmentRef, SourceRef
        request = demo_request('missing')
        reference = AttachmentRef(attachment_id='receipt', filename='private-customer.txt',
                                  media_type='text/plain', local_reference='/private/case/token')
        request = request.model_copy(update={'snapshot': request.snapshot.model_copy(update={'attachments': (reference,)})})
        # Known independent SHA-256 test vector, deliberately unreadable as a receipt.
        read = AttachmentResult(scope=EvidenceScope(case_id=request.case_id, case_version=request.case_version),
            reference=reference, status='found', content=b'abc', source=SourceRef(source_id='receipt', version='7'),
            content_hash='ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
            observed_at=datetime(2026, 10, 30, tzinfo=timezone.utc))
        manifests = []
        result = create_processor(settings=Settings('offline', ''), diagnostic_sink=manifests.append,
            adapters=create_evidence_adapters(attachments=FakeAttachmentReader((read,))))(request, lambda _: None)
        self.assertEqual(result.proposed_action.type, 'REQUEST_INFORMATION')
        manifest = manifests[0]
        attachment = manifest.attachments[0]
        self.assertEqual((attachment.attachment_id, attachment.source_version, attachment.content_hash),
            ('receipt', '7', 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'))
        self.assertEqual(attachment.extraction_status, 'partial')
        self.assertEqual(attachment.extraction_configuration_version, 'synthetic-labelled-fields-v1')
        self.assertEqual(manifest.retrieval_configuration_version, 'lexical-approved-v1')
        self.assertIn(SourceRef(source_id='receipt', version='7'), manifest.evidence_sources)
        self.assertNotIn('private', manifest.model_dump_json())
        self.assertNotIn('"abc"', manifest.model_dump_json())

    def test_model_failure_still_delivers_safe_manifest_with_retryability(self):
        from unittest.mock import patch
        manifests = []
        with patch('backend.ai_service.experts.OpenAI') as client:
            client.return_value.__enter__.return_value.responses.parse.side_effect = RuntimeError('private-provider-secret')
            result = create_processor(settings=Settings('openai', 'private-api-key', 'test-model-v1'),
                diagnostic_sink=manifests.append)(demo_request('clear'), lambda _: None)
        self.assertEqual(result.status, 'FAILED')
        manifest = manifests[0]
        self.assertEqual(manifest.status, 'FAILED')
        self.assertIsNone(manifest.decision)
        self.assertEqual(manifest.reason, 'TECHNICAL_FAILURE')
        self.assertEqual(manifest.error.code, 'AI_PROCESSING_FAILED')
        self.assertEqual(manifest.error.category, 'model')
        self.assertTrue(manifest.error.retryable)
        self.assertFalse(manifest.simulation)
        self.assertEqual(manifest.model, 'test-model-v1')
        self.assertTrue(manifest.knowledge)
        self.assertNotIn('private', manifest.model_dump_json())

    def test_input_reader_and_retrieval_failures_keep_safe_categories(self):
        from backend.ai_service.evidence import create_evidence_adapters
        from backend.ai_service.retrieval import RetrievalResult
        from backend.contracts import AttachmentRef, Owner
        request = demo_request('clear')
        invalid = request.model_copy(update={'snapshot': request.snapshot.model_copy(update={'owner': Owner(type='HUMAN', id='operator')})})
        attached = request.model_copy(update={'snapshot': request.snapshot.model_copy(update={'attachments': (
            AttachmentRef(attachment_id='receipt', filename='secret.txt', media_type='text/plain', local_reference='private-token'),)})})
        for given, options, category, code, retryable in (
            (invalid, {}, 'input', 'INVALID_AI_CONTEXT', False),
            (attached, {'adapters': create_evidence_adapters()}, 'evidence', 'ATTACHMENT_ADAPTER_UNCONFIGURED', False),
            (request, {'retriever': lambda _: RetrievalResult(status='FAILED', reason='secret customer text',
                error_code='customer@example.org/private')}, 'retrieval', 'TECHNICAL_FAILURE', True),
        ):
            with self.subTest(category=category):
                manifests = []
                result = create_processor(settings=Settings('offline', ''), diagnostic_sink=manifests.append,
                    **options)(given, lambda _: None)
                self.assertEqual(result.status, 'FAILED')
                manifest = manifests[0]
                self.assertEqual((manifest.error.category, manifest.error.code, manifest.error.retryable),
                                 (category, code, retryable))
                self.assertIsNone(manifest.decision)
                self.assertNotIn('private', manifest.model_dump_json())
                self.assertNotIn('secret', manifest.model_dump_json())

    def test_missing_keys_are_allowlisted_and_manifest_rejects_unstructured_payloads(self):
        import json
        from pydantic import ValidationError
        from backend.ai_service.diagnostics import RunManifest
        manifests = []
        create_processor(settings=Settings('offline', ''), diagnostic_sink=manifests.append)(
            demo_request('missing'), lambda _: None)
        manifest = manifests[0]
        self.assertEqual(set(manifest.missing_keys), {'receipt_amount_minor', 'receipt_currency'})
        self.assertEqual(manifest.reason, 'MISSING_EVIDENCE')
        for changes in ({'raw_text': 'customer@example.org'}, {'missing_keys': ['customer@example.org']},
                        {'case_version': '1'}, {'reason': 'private explanation'}, {'model': '/private/path'},
                        {'status': 'FAILED'}, {'retrieval_configuration_version': '/private/path'}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                RunManifest.model_validate_json(json.dumps({**manifest.model_dump(mode='json'), **changes}))

    def test_sink_failure_invalidates_proposal_and_preserves_snapshot(self):
        request = demo_request('clear')
        before = request.model_dump_json()
        observed = []
        def unavailable(manifest):
            observed.append(manifest)
            raise OSError('private database path')
        result = create_processor(settings=Settings('offline', ''), diagnostic_sink=unavailable)(request, lambda _: None)
        self.assertEqual(observed[0].decision, 'RESOLVE')
        self.assertEqual(result.status, 'FAILED')
        self.assertIsNone(result.proposed_action)
        self.assertEqual(result.technical_error.code, 'DIAGNOSTIC_PERSISTENCE_FAILED')
        self.assertTrue(result.technical_error.retryable)
        self.assertNotIn('private', result.model_dump_json())
        self.assertEqual(request.model_dump_json(), before)

    def test_progress_callback_failure_is_recorded_without_exception_text(self):
        manifests = []
        def broken_progress(_):
            raise OSError('customer@example.org')
        result = create_processor(settings=Settings('offline', ''), diagnostic_sink=manifests.append)(
            demo_request('clear'), broken_progress)
        self.assertEqual(result.status, 'FAILED')
        self.assertIsNone(manifests[0].decision)
        self.assertEqual(manifests[0].error.category, 'processing')
        self.assertNotIn('customer@example.org', manifests[0].model_dump_json())

    def test_custom_retrieval_version_is_explicit_or_marked_unversioned(self):
        from backend.ai_service.retrieval import retrieve
        for supplied, expected in ((None, 'unversioned-custom'), ('fixture-index-v3', 'fixture-index-v3')):
            with self.subTest(supplied=supplied):
                manifests = []
                result = create_processor(settings=Settings('offline', ''), diagnostic_sink=manifests.append,
                    retriever=retrieve, retrieval_configuration_version=supplied)(demo_request('clear'), lambda _: None)
                self.assertEqual(result.status, 'SUCCEEDED')
                self.assertEqual(manifests[0].retrieval_configuration_version, expected)

    def test_parser_failure_keeps_read_version_hash_and_extraction_configuration(self):
        from datetime import datetime, timezone
        from backend.ai_service.evidence import AttachmentResult, EvidenceScope, FakeAttachmentReader, create_evidence_adapters
        from backend.ai_service.extraction import DocumentExtractor
        from backend.contracts import AttachmentRef, SourceRef
        class FailedParser:
            def pages(self, _):
                raise OSError('private document contents')
        request = demo_request('missing')
        reference = AttachmentRef(attachment_id='receipt', filename='secret.pdf', media_type='application/pdf', local_reference='private-token')
        request = request.model_copy(update={'snapshot': request.snapshot.model_copy(update={'attachments': (reference,)})})
        read = AttachmentResult(scope=EvidenceScope(case_id=request.case_id, case_version=request.case_version),
            reference=reference, status='found', content=b'abc', source=SourceRef(source_id='receipt', version='9'),
            content_hash='ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
            observed_at=datetime(2026, 10, 30, tzinfo=timezone.utc))
        manifests = []
        result = create_processor(settings=Settings('offline', ''), diagnostic_sink=manifests.append,
            extractor=DocumentExtractor(pdf_parser=FailedParser()),
            adapters=create_evidence_adapters(attachments=FakeAttachmentReader((read,))))(request, lambda _: None)
        self.assertEqual(result.status, 'FAILED')
        self.assertEqual(manifests[0].error.category, 'extraction')
        self.assertEqual(manifests[0].error.code, 'EXTRACTION_PARSER_FAILURE')
        self.assertTrue(manifests[0].error.retryable)
        self.assertEqual(manifests[0].attachments[0].source_version, '9')
        self.assertEqual(manifests[0].attachments[0].extraction_configuration_version, 'synthetic-labelled-fields-v1')
        self.assertNotIn('private', manifests[0].model_dump_json())
