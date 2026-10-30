import unittest
from datetime import datetime, timezone

from backend.ai_service.evidence import EvidenceScope, FakeRecordReader, LookupResult, create_evidence_adapters
from backend.ai_service.fixtures import demo_request
from backend.ai_service.reconciliation import prepare_evidence


class ReconciliationTests(unittest.TestCase):
    def conflicted_request(self, name):
        from backend.contracts import Fact, SourceRef
        request = demo_request('clear')
        value = 'ineligible' if name == 'expense_eligibility' else 'prior_reimbursement_exists'
        conflicting = Fact(name=name, value=value, sources=(SourceRef(source_id='conflicting-record', version='1'),))
        return request.model_copy(update={'snapshot': request.snapshot.model_copy(update={
            'booking_context': (conflicting,)})})

    def test_authoritative_refresh_resolves_each_internal_conflict_and_retains_history(self):
        from backend.ai_service.assessment import assess
        for name in ('expense_eligibility', 'payment_history'):
            with self.subTest(name=name):
                request = self.conflicted_request(name)
                before = request.model_dump_json()
                calls = []
                resolved = next(f for f in request.snapshot.flight_context if f.name == name)
                class Reader:
                    def lookup(self, lookup):
                        calls.append(lookup)
                        return LookupResult(scope=lookup.scope, status='found', facts=(resolved,),
                            observed_at=datetime.now(timezone.utc), freshness='current')
                prepared = prepare_evidence(request, create_evidence_adapters(operational=Reader()))
                self.assertIsNone(prepared.error)
                self.assertEqual(calls[0].fact_names, (name,))
                self.assertEqual(calls[0].snapshot, request.snapshot)
                self.assertIsNotNone(assess(prepared.request.snapshot, prepared.sources).position)
                self.assertEqual(len(prepared.superseded_facts), 2)
                self.assertIn('conflicting-record', {s.source_id for s in prepared.sources})
                self.assertEqual(request.model_dump_json(), before)

    def test_unresolved_refreshed_conflict_hands_off_with_original_context(self):
        from backend.ai_service.assessment import assess
        request = self.conflicted_request('expense_eligibility')
        scope = EvidenceScope(case_id=request.case_id, case_version=request.case_version)
        for status in ('found', 'ambiguous'):
            with self.subTest(status=status):
                facts = tuple(f for f in request.snapshot.booking_context + request.snapshot.flight_context
                              if f.name == 'expense_eligibility') if status == 'found' else ()
                reader = FakeRecordReader({scope: LookupResult(scope=scope, status=status, facts=facts,
                    observed_at=datetime.now(timezone.utc), freshness='current')})
                prepared = prepare_evidence(request, create_evidence_adapters(operational=reader))
                self.assertIsNone(prepared.error)
                self.assertEqual(assess(prepared.request.snapshot, prepared.sources).reason, 'UNRESOLVED_CONFLICT')
                self.assertEqual(prepared.superseded_facts, ())
                self.assertIn(request.snapshot.booking_context[0], prepared.request.snapshot.booking_context)

    def test_conflict_refresh_outage_or_stale_result_is_technical_failure(self):
        request = self.conflicted_request('payment_history')
        prepared = prepare_evidence(request, create_evidence_adapters())
        self.assertIsNone(prepared.request)
        self.assertEqual(prepared.error.code, 'EVIDENCE_UNAVAILABLE')
        scope = EvidenceScope(case_id=request.case_id, case_version=request.case_version)
        reader = FakeRecordReader({scope: LookupResult(scope=scope, status='found',
            facts=request.snapshot.flight_context, observed_at=datetime.now(timezone.utc), freshness='stale')})
        prepared = prepare_evidence(request, create_evidence_adapters(operational=reader))
        self.assertIsNone(prepared.request)
        self.assertEqual(prepared.error.code, 'EVIDENCE_STALE')

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

    def test_malformed_reader_results_fail_closed_at_preparation_boundary(self):
        original = demo_request('clear')
        request = original.model_copy(update={'snapshot': original.snapshot.model_copy(update={'flight_context': ()})})
        scope = EvidenceScope(case_id=request.case_id, case_version=request.case_version)
        valid = LookupResult(scope=scope, status='found', facts=original.snapshot.flight_context,
            observed_at=datetime.now(timezone.utc), freshness='current')
        for change in ({'observed_at': None}, {'observed_at': datetime(2026, 10, 30)},
                       {'facts': tuple(f.model_copy(update={'sources': ()}) for f in valid.facts)},
                       {'status': 'invented'}):
            with self.subTest(change=change):
                reader = FakeRecordReader({scope: valid.model_copy(update=change)})
                prepared = prepare_evidence(request, create_evidence_adapters(operational=reader))
                self.assertIsNone(prepared.request)
                self.assertEqual(prepared.error.code, 'INVALID_ADAPTER_EVIDENCE')
