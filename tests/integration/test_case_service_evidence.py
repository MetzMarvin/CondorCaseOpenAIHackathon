"""System 2 consumes case-scoped extracted evidence through unified System 1.

Original attachments remain in System 1. Downstream processing receives text and
provenance, never a raw file or a resolvable original attachment reference.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.main import create_app
from backend.ai_service.evidence import create_evidence_adapters
from backend.ai_service.service import create_processor


class CaseServiceEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict('os.environ', {
            'AI_MODE': 'offline', 'CONDOR_PREPARATION_MODE': 'offline',
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.directory = tempfile.TemporaryDirectory(prefix='condor-evidence-boundary-')
        self.addCleanup(self.directory.cleanup)
        self.client = TestClient(create_app(Path(self.directory.name)))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def test_uploaded_receipt_resolves_with_scoped_extracted_text(self):
        waiting = self.client.post('/api/cases/case-evidence/process', json={
            'requestId': 'before-receipt', 'expectedCaseVersion': 1})
        self.assertEqual(waiting.status_code, 200, waiting.text)
        self.assertEqual(waiting.json()['case']['status'], 'WAITING_FOR_CUSTOMER')
        content = (Path(__file__).resolve().parents[2] /
                   'backend/demo-files/preparation-receipt.png').read_bytes()
        response = self.client.post('/api/inbound/messages', data={
            'metadata': json.dumps({
                'messageId': 'receipt-reply', 'caseId': 'case-evidence',
                'sender': 'guest@example.com', 'channel': 'PORTAL',
                'subject': 'Requested receipt', 'body': 'Evidence attached.',
            })}, files=[('files', ('receipt.png', content, 'image/png'))])
        self.assertEqual(response.status_code, 200, response.text)
        reply = response.json()
        portal = self.client.get(reply['customerCaseUrl'].replace('/portal/', '/api/portal/')).json()
        uploaded = next(m for m in portal['messages'] if m['messageId'] == 'receipt-reply')['attachments'][0]
        aid = uploaded['attachmentId']
        self.assertEqual(self.client.get(uploaded['url']).content, content)
        self.assertEqual(self.client.get('/api/cases/case-clear/attachments/' + aid).status_code, 404)
        calls = []
        raw_reads = []

        class RejectRawAttachmentReader:
            def read(self, request):
                raw_reads.append(request)
                raise AssertionError('Original attachment must not reach System 2')

        def configured(request, emit):
            calls.append(request.case_id)
            self.assertEqual(request.case_id, 'case-evidence')
            self.assertEqual(request.case_version, reply['caseVersion'])
            self.assertEqual(request.snapshot.attachments, ())
            self.assertTrue(all(not m.attachment_ids for m in request.snapshot.messages))
            doc = next(d for d in request.snapshot.extracted_documents if d.attachment_id == aid)
            self.assertEqual(doc.text, 'SYNTHETIC RECEIPT - EUR 42.00')
            self.assertEqual(doc.page, 1)
            source_id = aid + ':page:1'
            amount = next(f for f in request.snapshot.known_facts if f.name == 'receipt_amount_minor')
            self.assertEqual(amount.value, 4200)
            self.assertIn(source_id, [s.source_id for s in amount.sources])
            return create_processor(adapters=create_evidence_adapters(
                attachments=RejectRawAttachmentReader()))(request, emit)

        with patch('backend.operations.process_case', side_effect=configured):
            response = self.client.post('/api/cases/case-evidence/process', json={
                'requestId': 'after-receipt', 'expectedCaseVersion': reply['caseVersion']})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(calls, ['case-evidence'])
        self.assertEqual(raw_reads, [])
        self.assertEqual(result['case']['status'], 'RESOLVED', result)
        action = result['appliedAction']
        self.assertEqual(action['payload']['financialPositions'][0]['amountMinor'], 4200)
        self.assertIn(aid + ':page:1', [s['sourceId'] for s in action['sources']])


if __name__ == '__main__':
    unittest.main()
