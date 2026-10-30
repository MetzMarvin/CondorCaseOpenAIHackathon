"""System 2 integration contract exercised through System 1's unchanged demo API.

Run separately with backend extras installed. Authorized reader is a test double;
this does not claim the case service has implemented production evidence access.
"""
import os
import tempfile
import unittest
from datetime import datetime, timezone
from hashlib import sha256
from unittest.mock import patch

_TEMP = tempfile.TemporaryDirectory(prefix='condor-evidence-boundary-')
os.environ['DEMO_DB'] = os.path.join(_TEMP.name, 'cases.sqlite')
os.environ['AI_MODE'] = 'offline'

from fastapi.testclient import TestClient
from demo_backend.app import app
from backend.contracts import SourceRef
from backend.ai_service.evidence import (
    AttachmentResult, EvidenceScope, FakeAttachmentReader, create_evidence_adapters,
)
from backend.ai_service.service import create_processor


class CaseServiceEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.client.post('/api/demo/reset', json={'actionId': 'reset'})

    def test_uploaded_receipt_resolves_with_injected_scoped_reader(self):
        waiting = self.client.post('/api/cases/case-evidence/process', json={
            'requestId': 'before-receipt', 'expectedCaseVersion': 1}).json()
        self.assertEqual(waiting['case']['status'], 'WAITING_FOR_CUSTOMER')
        # The case already supplies sourced expense purpose. This upload fills
        # the missing amount/currency without introducing a differently worded purpose.
        content = b'Total: 42.00\nCurrency: EUR\nReceipt date: 2026-10-29\n'
        uploaded = self.client.post('/api/cases/case-evidence/attachments', files={
            'file': ('receipt.txt', content, 'text/plain')})
        self.assertEqual(uploaded.status_code, 200, uploaded.text)
        aid = uploaded.json()['attachmentId']
        reply = self.client.post('/api/inbound/messages', json={
            'messageId': 'receipt-reply', 'caseId': 'case-evidence',
            'sender': 'guest@example.com', 'channel': 'EMAIL',
            'body': 'Here is the requested receipt.', 'attachmentIds': [aid]}).json()
        calls = []

        def configured(request, emit):
            calls.append(request.case_id)
            self.assertEqual(request.case_id, 'case-evidence')
            self.assertEqual(request.case_version, reply['version'])
            ref = next(ref for ref in request.snapshot.attachments if ref.attachment_id == aid)
            reader = FakeAttachmentReader((AttachmentResult(
                scope=EvidenceScope(case_id=request.case_id, case_version=request.case_version),
                reference=ref, status='found', content=content,
                source=SourceRef(source_id=aid, version='1'),
                content_hash=sha256(content).hexdigest(), observed_at=datetime.now(timezone.utc)),))
            # Internal eligibility/payment history already arrive in System 1's snapshot.
            return create_processor(adapters=create_evidence_adapters(attachments=reader))(request, emit)

        with patch('demo_backend.app.process_case', side_effect=configured):
            response = self.client.post('/api/cases/case-evidence/process', json={
                'requestId': 'after-receipt', 'expectedCaseVersion': reply['version']})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(calls, ['case-evidence'])
        self.assertEqual(result['case']['status'], 'RESOLVED')
        action = result['appliedAction']
        self.assertEqual(action['payload']['financialPositions'][0]['amountMinor'], 4200)
        self.assertIn(aid, [s['sourceId'] for s in action['sources']])


if __name__ == '__main__':
    unittest.main()
