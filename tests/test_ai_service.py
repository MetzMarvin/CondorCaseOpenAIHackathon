import unittest
from backend.ai_service.workflow import process_case
from backend.ai_service.fixtures import demo_request
from backend.contracts import Owner, RunRequest, RunResult


class AIIntegrationTests(unittest.TestCase):
    def test_demo_flows_roundtrip_and_preserve_snapshots(self):
        for scenario, expected in [('clear', 'RESOLVE'), ('missing', 'REQUEST_INFORMATION'), ('reply', 'RESOLVE'), ('serious', 'HANDOFF'), ('unsupported', 'HANDOFF')]:
            with self.subTest(scenario=scenario):
                request = demo_request(scenario)
                before = request.model_dump_json()
                events = []
                result = process_case(RunRequest.model_validate_json(request.model_dump_json(by_alias=True)), events.append)
                self.assertEqual(result.status, 'SUCCEEDED')
                self.assertEqual(result.proposed_action.type, expected)
                self.assertEqual(result, RunResult.model_validate_json(result.model_dump_json(by_alias=True)))
                self.assertEqual(request.model_dump_json(), before)
                self.assertEqual(events[-1].step_id, 'validate_action')
                self.assertTrue(all(e.simulation for e in events))
                self.assertEqual(result.proposed_action.action_id, process_case(request, lambda _: None).proposed_action.action_id)
        self.assertEqual(demo_request('missing').case_id, demo_request('reply').case_id)
        self.assertGreater(demo_request('reply').case_version, demo_request('missing').case_version)

    def test_callback_failure_is_technical_failure(self):
        def broken(_):
            raise RuntimeError('private details')
        result = process_case(demo_request('clear'), broken)
        self.assertEqual(result.status, 'FAILED')
        self.assertIsNone(result.proposed_action)
        self.assertNotIn('private details', result.model_dump_json())

    def test_takeover_context_cannot_produce_ai_action(self):
        request = demo_request('clear')
        request = request.model_copy(update={'snapshot': request.snapshot.model_copy(update={'owner': Owner(type='HUMAN', id='operator')})})
        result = process_case(request, lambda _: None)
        self.assertEqual(result.status, 'FAILED')
        self.assertIsNone(result.proposed_action)

    def test_financial_authority_handoff(self):
        request = demo_request('clear')
        request = request.model_copy(update={'snapshot': request.snapshot.model_copy(update={'financial_limits': ()})})
        result = process_case(request, lambda _: None)
        self.assertEqual(result.proposed_action.payload.reason_code, 'AUTHORITY_LIMIT')

    def test_no_permissions_is_failed_run(self):
        request = demo_request('clear')
        request = request.model_copy(update={'snapshot': request.snapshot.model_copy(update={'permitted_actions': ()})})
        self.assertEqual(process_case(request, lambda _: None).status, 'FAILED')
