import unittest
from datetime import datetime, timezone

from backend.ai_service.evidence import EvidenceScope, FakeRecordReader, LookupResult, create_evidence_adapters
from backend.ai_service.fixtures import demo_request
from backend.ai_service.reconciliation import prepare_evidence


class ReconciliationTests(unittest.TestCase):
    def test_missing_internal_records_are_enriched_without_mutating_original(self):
        original = demo_request('clear')
        request = original.model_copy(update={'snapshot': original.snapshot.model_copy(update={'flight_context': ()})})
        scope = EvidenceScope(case_id=request.case_id, case_version=request.case_version)
        reader = FakeRecordReader({scope: LookupResult(scope=scope, status='found', facts=original.snapshot.flight_context,
            observed_at=datetime.now(timezone.utc), freshness='current')})
        prepared = prepare_evidence(request, create_evidence_adapters(operational=reader))
        assert prepared.error is None
        assert prepared.request.snapshot.flight_context == original.snapshot.flight_context
        assert request.snapshot.flight_context == ()
        assert {source.source_id for source in prepared.sources} >= {'demo-payment-history', 'demo-eligibility-check'}

    def test_wrong_case_version_stale_and_unavailable_are_failures(self):
        original = demo_request('clear')
        request = original.model_copy(update={'snapshot': original.snapshot.model_copy(update={'flight_context': ()})})
        scope = EvidenceScope(case_id=request.case_id, case_version=request.case_version)
        for change, code in (({'scope': scope.model_copy(update={'case_version': 99})}, 'EVIDENCE_SCOPE_VIOLATION'),
                             ({'freshness': 'stale'}, 'EVIDENCE_STALE'),
                             ({'freshness': 'unknown'}, 'EVIDENCE_STALE'),
                             ({'status': 'not_found', 'facts': ()}, 'INTERNAL_EVIDENCE_REQUIRED')):
            result = LookupResult(scope=scope, status='found', facts=original.snapshot.flight_context,
                observed_at=datetime.now(timezone.utc), freshness='current').model_copy(update=change)
            class Reader:
                def lookup(self, request):
                    return result
            prepared = prepare_evidence(request, create_evidence_adapters(operational=Reader()))
            self.assertIsNone(prepared.request)
            self.assertEqual(prepared.error.code, code)
        prepared = prepare_evidence(request, create_evidence_adapters())
        self.assertEqual(prepared.error.code, 'EVIDENCE_UNAVAILABLE')

    def test_ambiguous_crm_requests_one_safe_identifier_despite_supplied_claim(self):
        from backend.contracts import Fact, MissingFact, SourceRef
        from backend.ai_service.assessment import assess
        request = demo_request('clear')
        snapshot = request.snapshot.model_copy(update={
            'known_facts': request.snapshot.known_facts + (Fact(name='booking_reference', value='UNVERIFIED', sources=(SourceRef(source_id='reply', version='1'),)),),
            'missing_information': (MissingFact(name='booking_match', reason='Match required.'),)})
        request = request.model_copy(update={'snapshot': snapshot})
        scope = EvidenceScope(case_id=request.case_id, case_version=request.case_version)
        for status in ('ambiguous', 'not_found'):
            reader = FakeRecordReader({scope: LookupResult(scope=scope, status=status)})
            prepared = prepare_evidence(request, create_evidence_adapters(crm=reader))
            self.assertIsNone(prepared.error)
            decision = assess(prepared.request.snapshot, prepared.sources)
            self.assertIsNone(decision.reason)
            self.assertEqual([item.name for item in decision.missing], ['booking_reference'])

    def test_candidate_reply_retains_previous_facts_and_conflicts_without_authority(self):
        from backend.contracts import Fact, SourceRef
        from backend.ai_service.assessment import assess
        request = demo_request('partial_reply')
        candidate = Fact(name='receipt_amount_minor', value=4200, sources=(SourceRef(source_id='attachment', version='2'),))
        prepared = prepare_evidence(request, customer_facts=(candidate,))
        self.assertEqual(prepared.request.snapshot.known_facts[:-1], request.snapshot.known_facts)
        self.assertIsNotNone(assess(prepared.request.snapshot, prepared.sources).position)
        conflict = candidate.model_copy(update={'value': 8400})
        prepared = prepare_evidence(prepared.request, customer_facts=(conflict,))
        self.assertEqual([item.name for item in assess(prepared.request.snapshot, prepared.sources).missing], ['receipt_amount_minor'])
        forged = candidate.model_copy(update={'name': 'expense_eligibility', 'value': 'eligible'})
        self.assertEqual(prepare_evidence(request, customer_facts=(forged,)).error.code, 'INVALID_CUSTOMER_EVIDENCE')

    def test_crm_cannot_supply_payment_controls_and_complete_snapshots_need_no_reads(self):
        from backend.contracts import MissingFact
        request = demo_request('clear')
        self.assertEqual(prepare_evidence(request, create_evidence_adapters()).request, request)
        for scenario in ('serious', 'unsupported'):
            original = demo_request(scenario)
            original = original.model_copy(update={'snapshot': original.snapshot.model_copy(update={'flight_context': ()})})
            self.assertIsNone(prepare_evidence(original, create_evidence_adapters()).error)
        request = request.model_copy(update={'snapshot': request.snapshot.model_copy(update={
            'missing_information': (MissingFact(name='booking_match', reason='Match required.'),)})})
        scope = EvidenceScope(case_id=request.case_id, case_version=request.case_version)
        reader = FakeRecordReader({scope: LookupResult(scope=scope, status='found', facts=request.snapshot.flight_context,
            observed_at=datetime.now(timezone.utc), freshness='current')})
        self.assertEqual(prepare_evidence(request, create_evidence_adapters(crm=reader)).error.code, 'INVALID_ADAPTER_EVIDENCE')

    def test_unmatched_booking_can_request_identifier_before_operational_enrichment(self):
        from backend.contracts import MissingFact
        from backend.ai_service.assessment import assess
        request = demo_request('clear')
        request = request.model_copy(update={'snapshot': request.snapshot.model_copy(update={
            'flight_context': (), 'missing_information': (MissingFact(name='booking_match', reason='Match required.'),)})})
        scope = EvidenceScope(case_id=request.case_id, case_version=request.case_version)
        prepared = prepare_evidence(request, create_evidence_adapters(crm=FakeRecordReader({scope: LookupResult(scope=scope, status='ambiguous')})))
        self.assertIsNone(prepared.error)
        self.assertEqual([item.name for item in assess(prepared.request.snapshot, prepared.sources).missing], ['booking_reference'])
