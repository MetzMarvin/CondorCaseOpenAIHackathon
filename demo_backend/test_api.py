import os
import tempfile
import unittest
os.environ['DEMO_DB'] = tempfile.mktemp(suffix='.sqlite')
from fastapi.testclient import TestClient
from demo_backend.app import app

class DemoTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.client.post('/api/demo/reset', json={'actionId': 'reset'})

    def process(self, cid, version=1, key='run-1'):
        return self.client.post(f'/api/cases/{cid}/process', json={'requestId':key, 'expectedCaseVersion': version})

    def test_clear_and_duplicate(self):
        first = self.process('case-clear').json()
        self.assertEqual(first['case']['status'], 'RESOLVED')
        self.assertEqual(first, self.process('case-clear').json())
        self.assertEqual(len(first['case']['messages']), 2)
        self.assertEqual(self.process('case-clear', 2).status_code, 409)

    def test_evidence_same_case(self):
        waiting = self.process('case-evidence').json()['case']
        self.assertEqual(waiting['status'], 'WAITING_FOR_CUSTOMER')
        reply = self.client.post('/api/inbound/messages', json={'messageId':'reply-1', 'caseId':waiting['id'], 'sender':'guest@example.com', 'body':'Booking reference ABC123, flight DE1234.'}).json()
        final = self.process(reply['id'], reply['caseVersion'], 'run-2').json()['case']
        self.assertEqual(final['id'], waiting['id'])
        self.assertEqual(final['status'], 'RESOLVED')
        self.assertEqual(len(self.client.get('/api/cases').json()), 6)

    def test_handoff_takeover_and_stale_ai(self):
        case = self.process('case-serious').json()['case']
        self.assertEqual(case['handoff']['reasonCode'], 'SERIOUS_ISSUE')
        taken = self.client.post('/api/cases/case-serious/takeover', json={'actionId':'take-1','expectedCaseVersion':case['caseVersion'],'operatorId':'demo-agent'}).json()
        self.assertEqual(self.process(taken['id'], case['caseVersion'], 'old-run').status_code, 409)
        self.assertEqual(self.process(taken['id'], taken['caseVersion'], 'new-run').status_code, 409)
        resolved = self.client.post('/api/cases/case-serious/actions', json={'actionId':'human-1','caseId':taken['id'],'expectedCaseVersion':taken['caseVersion'],'type':'RESOLVE','payload':{'reply':'We have reviewed your request personally.','outcome':'MANUAL_REVIEW','explanation':'Demo assessment completed','sourceIds':['demo-policy-1'],'financialPositions':[]}})
        self.assertEqual(resolved.json()['case']['status'], 'RESOLVED')

    def test_angry_clear_is_not_handoff(self):
        self.assertEqual(self.process('case-angry').json()['case']['status'], 'RESOLVED')

    def test_events_cursor(self):
        before = self.client.get('/api/events?caseId=case-clear').json()
        self.process('case-clear')
        after = self.client.get(f"/api/events?caseId=case-clear&after={before['cursor']}").json()
        self.assertTrue(after['events'])
        self.assertTrue(all(e['sequence'] > before['cursor'] for e in after['events']))

    def test_upload_scope(self):
        ref = self.client.post('/api/cases/case-evidence/attachments', files={'file':('receipt.txt', b'Demo receipt', 'text/plain')}).json()
        self.assertEqual(self.client.get(f"/api/cases/case-evidence/attachments/{ref['attachmentId']}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/cases/case-clear/attachments/{ref['attachmentId']}").status_code, 404)

    def test_intake_deduplicates(self):
        body = {'messageId':'new-1','sender':'guest@example.com','body':'Please send a booking confirmation.'}
        first = self.client.post('/api/inbound/messages', json=body).json()
        self.assertEqual(first, self.client.post('/api/inbound/messages', json=body).json())
        self.assertEqual(len(self.client.get('/api/cases').json()), 7)
        self.assertEqual(self.process(first['id'], first['caseVersion']).json()['case']['status'], 'RESOLVED')

if __name__ == '__main__': unittest.main()
