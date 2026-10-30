"""Public scoped read-only adapter contract checks."""
import unittest
from datetime import datetime, timezone

from backend.ai_service.evidence import EvidenceScope, LookupRequest, LookupResult, FakeRecordReader
from backend.ai_service.fixtures import demo_request
from backend.contracts import Fact, SourceRef

NOW = datetime(2026, 10, 30, tzinfo=timezone.utc)

class AdapterTests(unittest.TestCase):
    def test_scoped_success_returns_versioned_facts_without_mutating_snapshot(self):
        snapshot = demo_request('clear').snapshot
        before = snapshot.model_dump_json()
        scope = EvidenceScope(case_id='case-a', case_version=3)
        result = LookupResult(scope=scope, status='found', facts=(Fact(name='actual_arrival', value='2026-10-30T11:00:00Z', sources=(SourceRef(source_id='flight-1', version='2'),)),), observed_at=NOW, freshness='current')
        reader = FakeRecordReader({scope: result})
        self.assertEqual(reader.lookup(LookupRequest(scope=scope, snapshot=snapshot, fact_names=('actual_arrival',))), result)
        self.assertEqual(snapshot.model_dump_json(), before)
        other = reader.lookup(LookupRequest(scope=EvidenceScope(case_id='case-b', case_version=3), snapshot=snapshot, fact_names=('actual_arrival',)))
        self.assertEqual(other.status, 'not_found')
        self.assertEqual(other.facts, ())

    def test_ambiguous_and_unavailable_do_not_disclose_records_or_look_like_absence(self):
        from pydantic import ValidationError
        from backend.contracts import TechnicalError
        scope = EvidenceScope(case_id='case-a', case_version=3)
        for status in ('not_found', 'ambiguous', 'unavailable'):
            error = TechnicalError(code='CRM_UNAVAILABLE', message='CRM is unavailable.', retryable=True) if status == 'unavailable' else None
            result = LookupResult(scope=scope, status=status, error=error)
            reader = FakeRecordReader({scope: result})
            self.assertEqual(reader.lookup(LookupRequest(scope=scope, snapshot=demo_request('clear').snapshot, fact_names=())).status, status)
            with self.assertRaises(ValidationError):
                LookupResult(scope=scope, status=status, error=error, facts=(Fact(name='customer_name', value='Other passenger', sources=(SourceRef(source_id='crm', version='1'),)),))
        with self.assertRaises(ValidationError):
            LookupResult(scope=scope, status='found', facts=(Fact(name='actual_arrival', value='now', sources=()),))
        with self.assertRaises(ValueError):
            FakeRecordReader({EvidenceScope(case_id='wrong-case', case_version=3): result})

    def test_attachment_bytes_require_case_version_reference_and_verified_hash(self):
        from hashlib import sha256
        from pydantic import ValidationError
        from backend.ai_service.evidence import AttachmentRequest, AttachmentResult, FakeAttachmentReader
        from backend.contracts import AttachmentRef
        scope = EvidenceScope(case_id='case-a', case_version=3)
        reference = AttachmentRef(attachment_id='a1', filename='receipt.txt', media_type='text/plain', local_reference='opaque-token')
        request = AttachmentRequest(scope=scope, reference=reference)
        result = AttachmentResult(scope=scope, reference=reference, status='found', content=b'hello', source=SourceRef(source_id='a1', version='2'), content_hash=sha256(b'hello').hexdigest(), observed_at=NOW)
        reader = FakeAttachmentReader((result,))
        self.assertEqual(reader.read(request).content, b'hello')
        for other in (EvidenceScope(case_id='case-b', case_version=3), EvidenceScope(case_id='case-a', case_version=4)):
            denied = reader.read(AttachmentRequest(scope=other, reference=reference))
            self.assertEqual(denied.status, 'scope_violation')
            self.assertIsNone(denied.content)
        with self.assertRaises(ValidationError):
            AttachmentResult(**{**result.model_dump(), 'content_hash': '0' * 64})
        forged = reference.model_copy(update={'local_reference': '../../etc/passwd'})
        self.assertEqual(reader.read(AttachmentRequest(scope=scope, reference=forged)).status, 'scope_violation')

    def test_factory_defaults_fail_closed_and_accepts_explicit_synthetic_readers(self):
        from backend.ai_service.evidence import create_evidence_adapters, AttachmentRequest
        from backend.contracts import AttachmentRef
        adapters = create_evidence_adapters()
        scope = EvidenceScope(case_id='case-a', case_version=1)
        lookup = LookupRequest(scope=scope, snapshot=demo_request('clear').snapshot, fact_names=('payment_history',))
        self.assertEqual(adapters.crm.lookup(lookup).status, 'unavailable')
        self.assertEqual(adapters.operational.lookup(lookup).status, 'unavailable')
        attachment = AttachmentRequest(scope=scope, reference=AttachmentRef(attachment_id='a', filename='a.txt', media_type='text/plain', local_reference='token'))
        self.assertEqual(adapters.attachments.read(attachment).status, 'unavailable')
        fake = FakeRecordReader({scope: LookupResult(scope=scope, status='ambiguous')})
        self.assertEqual(create_evidence_adapters(crm=fake).crm.lookup(lookup).status, 'ambiguous')

    def test_requirements_keep_customer_claims_out_of_internal_controls(self):
        from backend.ai_service.requirements import requirements_for_issue
        expense = {item.name: item for item in requirements_for_issue('expense_reimbursement')}
        self.assertEqual(expense['receipt_currency'].authority, 'customer')
        self.assertEqual(expense['receipt_currency'].when_absent, 'ask_customer')
        self.assertEqual(expense['expense_eligibility'].authority, 'operational')
        self.assertEqual(expense['payment_history'].when_absent, 'enrich_internal')
        self.assertEqual(expense['payment_history'].when_conflicting, 'reconcile_internal')
        self.assertEqual(expense['permitted_actions'].authority, 'control')
        self.assertFalse(expense['expense_eligibility'].accepts_origin('customer'))
        self.assertFalse(expense['permitted_actions'].accepts_origin('customer'))
        self.assertEqual({item.name for item in requirements_for_issue('baggage_damage') if item.authority == 'customer'},
                         {'booking_reference', 'baggage_reference', 'damage_details', 'damage_discovery_date', 'written_complaint_date'})
        with self.assertRaises(ValueError):
            requirements_for_issue('unsupported_law')
