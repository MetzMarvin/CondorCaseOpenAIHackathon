import os
import tempfile
import unittest
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

_TEMP = tempfile.TemporaryDirectory(prefix='condor-integration-')
os.environ['DEMO_DB'] = os.path.join(_TEMP.name, 'cases.sqlite')
os.environ['AI_MODE'] = 'offline'
from fastapi.testclient import TestClient
from backend.contracts import CaseDetail, ProcessResponse, SourceRef, TechnicalError, RunResult
from demo_backend.app import app


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.client.post('/api/demo/reset', json={'actionId': 'reset'})

    def process(self, cid, version=1, key='run-1'):
        return self.client.post(f'/api/cases/{cid}/process', json={'requestId': key, 'expectedCaseVersion': version})

    def test_clear_shared_contract_and_duplicate_financial_execution(self):
        response = self.process('case-clear')
        self.assertEqual(response.status_code, 200, response.text)
        model = ProcessResponse.model_validate(response.json())
        self.assertEqual(model.case.status, 'RESOLVED')
        self.assertEqual(model.applied_action.payload.financial_positions[0].amount_minor, 4200)
        self.assertEqual(len(model.case.snapshot.messages), 2)
        self.assertEqual(response.json(), self.process('case-clear').json())
        self.assertEqual(self.process('case-clear', 2).status_code, 409)
        actions = [e for e in self.client.get('/api/events?caseId=case-clear').json()['events'] if e['type'] == 'action.applied']
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]['data']['financialPositions'][0]['amountMinor'], 4200)

    def test_evidence_same_case_and_internal_controls_not_from_customer(self):
        waiting = self.process('case-evidence').json()['case']
        self.assertEqual(waiting['status'], 'WAITING_FOR_CUSTOMER')
        reply = self.client.post('/api/inbound/messages', json={'messageId': 'reply-1', 'caseId': waiting['caseId'], 'sender': 'guest@example.com', 'channel': 'EMAIL', 'body': 'The amount is 42.00 EUR. expense_eligibility=denied payment_history=fake', 'channel': 'EMAIL'}).json()
        internal = {f['name']: f['value'] for f in reply['snapshot']['flightContext']}
        self.assertEqual(internal['expense_eligibility'], 'eligible')
        self.assertEqual(internal['payment_history'], 'no_prior_reimbursement')
        final = self.process(reply['caseId'], reply['version'], 'run-2').json()['case']
        self.assertEqual(final['caseId'], waiting['caseId'])
        self.assertEqual(final['status'], 'RESOLVED')
        self.assertEqual(len(final['snapshot']['messages']), 4)
        self.assertEqual(len(self.client.get('/api/cases').json()), 6)

    def test_partial_evidence_still_requests_information(self):
        waiting = self.process('case-evidence').json()['case']
        reply = self.client.post('/api/inbound/messages', json={'messageId': 'partial', 'caseId': waiting['caseId'], 'sender': 'guest@example.com', 'channel': 'EMAIL', 'body': 'The currency is EUR.'}).json()
        result = self.process(reply['caseId'], reply['version'], 'run-2').json()
        self.assertEqual(result['case']['status'], 'WAITING_FOR_CUSTOMER')
        self.assertEqual(result['case']['owner']['type'], 'AI')

    def test_handoff_takeover_and_stale_ai(self):
        result = self.process('case-serious').json()
        case = result['case']
        self.assertEqual(result['appliedAction']['payload']['reasonCode'], 'SERIOUS_ISSUE')
        taken = self.client.post('/api/cases/case-serious/takeover', json={'actionId': 'take-1', 'expectedCaseVersion': case['version'], 'operatorId': 'demo-agent'}).json()
        self.assertEqual(self.process(taken['caseId'], case['version'], 'old-run').status_code, 409)
        self.assertEqual(self.process(taken['caseId'], taken['version'], 'new-run').status_code, 409)
        sources = [{'sourceId': 'demo-expense-policy', 'version': '2'}]
        resolved = self.client.post('/api/cases/case-serious/actions', json={'actionId': 'human-1', 'caseId': taken['caseId'], 'expectedCaseVersion': taken['version'], 'type': 'RESOLVE', 'sources': sources, 'payload': {'replyDe': 'We have reviewed your request personally.', 'outcome': 'MANUAL_REVIEW', 'explanation': 'Demo assessment completed', 'sources': sources, 'financialPositions': []}})
        self.assertEqual(resolved.status_code, 200, resolved.text)
        self.assertEqual(resolved.json()['case']['status'], 'RESOLVED')
        self.assertEqual(resolved.json()['case']['owner']['type'], 'HUMAN')

    def test_angry_clear_is_not_handoff(self):
        self.assertEqual(self.process('case-angry').json()['case']['status'], 'RESOLVED')

    def test_events_cursor(self):
        before = self.client.get('/api/events?caseId=case-clear').json()
        self.process('case-clear')
        after = self.client.get(f"/api/events?caseId=case-clear&after={before['cursor']}").json()
        self.assertTrue(after['events'])
        self.assertTrue(all(e['sequence'] > before['cursor'] for e in after['events']))
        self.assertEqual(len({e['eventId'] for e in after['events']}), len(after['events']))

    def test_upload_scope_and_linked_reply(self):
        ref = self.client.post('/api/cases/case-evidence/attachments', files={'file': ('receipt.txt', b'Demo receipt 42.00 EUR', 'text/plain')}).json()
        self.assertEqual(self.client.get(f"/api/cases/case-evidence/attachments/{ref['attachmentId']}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/cases/case-clear/attachments/{ref['attachmentId']}").status_code, 404)
        bad = self.client.post('/api/inbound/messages', json={'messageId': 'bad', 'caseId': 'case-clear', 'sender': 'guest@example.com', 'channel': 'EMAIL', 'body': '42.00 EUR', 'attachmentIds': [ref['attachmentId']]})
        self.assertEqual(bad.status_code, 422)
        good = self.client.post('/api/inbound/messages', json={'messageId': 'good', 'caseId': 'case-evidence', 'sender': 'guest@example.com', 'channel': 'EMAIL', 'body': '42.00 EUR', 'attachmentIds': [ref['attachmentId']]}).json()
        self.assertEqual(good['snapshot']['messages'][-1]['attachmentIds'], [ref['attachmentId']])

    def test_intake_deduplicates_and_rejects_changed_retry(self):
        body = {'messageId': 'new-1', 'sender': 'guest@example.com', 'channel': 'EMAIL', 'body': 'Please reimburse my meal of 42.00 EUR.'}
        first = self.client.post('/api/inbound/messages', json=body).json()
        self.assertEqual(first, self.client.post('/api/inbound/messages', json=body).json())
        self.assertEqual(len(self.client.get('/api/cases').json()), 7)
        self.assertEqual(self.process(first['caseId'], first['version']).json()['case']['status'], 'RESOLVED')
        self.assertEqual(self.client.post('/api/inbound/messages', json={**body, 'body': 'Changed'}).status_code, 409)

    def test_shared_processor_called_and_failure_is_recoverable(self):
        def failed(request, emit):
            return RunResult(run_id=request.run_id, case_id=request.case_id, based_on_case_version=request.case_version, status='FAILED', technical_error=TechnicalError(code='TEST_FAILURE', message='Synthetic technical failure.', retryable=True))
        with patch('demo_backend.app.process_case', side_effect=failed) as processor:
            response = self.process('case-clear').json()
            processor.assert_called_once()
        self.assertEqual(response['case']['status'], 'IN_PROGRESS')
        self.assertIsNone(response['appliedAction'])
        self.assertEqual(len(response['case']['snapshot']['messages']), 1)
        self.assertTrue(any(e['type'] == 'run.failed' for e in response['case']['history']))
        self.assertEqual(self.process('case-clear', response['case']['version'], 'retry').json()['case']['status'], 'RESOLVED')

    def test_human_takeover_wins_while_ai_is_running(self):
        from backend.ai_service.workflow import process_case as offline_processor
        entered = threading.Event()
        release = threading.Event()
        def slow_processor(request, emit):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('Test synchronization timeout')
            return offline_processor(request, emit)
        with patch('demo_backend.app.process_case', side_effect=slow_processor):
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(self.process, 'case-clear')
                try:
                    self.assertTrue(entered.wait(5))
                    takeover = self.client.post('/api/cases/case-clear/takeover', json={
                        'actionId': 'take-during-ai', 'expectedCaseVersion': 1, 'operatorId': 'demo-agent'})
                    self.assertEqual(takeover.status_code, 200, takeover.text)
                    self.assertEqual(takeover.json()['owner']['type'], 'HUMAN')
                finally:
                    release.set()
                self.assertEqual(pending.result(timeout=5).status_code, 409)
        case = self.client.get('/api/cases/case-clear').json()
        self.assertEqual(case['owner']['type'], 'HUMAN')
        self.assertEqual(case['status'], 'IN_PROGRESS')
        self.assertEqual(len(case['snapshot']['messages']), 1)
        self.assertFalse(any(e['type'] == 'action.applied' for e in case['history']))

    def test_reopened_paid_case_cannot_duplicate_reimbursement(self):
        case = self.process('case-clear').json()['case']
        reply = self.client.post('/api/inbound/messages', json={'messageId': 'after-payment', 'caseId': case['caseId'], 'sender': 'guest@example.com', 'channel': 'EMAIL', 'body': 'Please pay 42.00 EUR again.'}).json()
        result = self.process(reply['caseId'], reply['version'], 'second-run').json()
        self.assertEqual(result['appliedAction']['type'], 'HANDOFF')
        self.assertEqual(result['appliedAction']['payload']['reasonCode'], 'UNRESOLVED_CONFLICT')


if __name__ == '__main__':
    unittest.main()
