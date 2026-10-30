"""Compatibility-launcher integration checks against the unified System 1 API."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.contracts import CaseDetail, ProcessResponse
from backend.database import Database, Event
from backend.main import create_app
from sqlalchemy import select


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='condor-unified-')
        self.addCleanup(self.folder.cleanup)
        self.env = patch.dict(os.environ, {'AI_MODE': 'offline', 'CONDOR_PREPARATION_MODE': 'offline'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.client = self.enterContext(TestClient(create_app(Path(self.folder.name))))

    def process(self, case_id='case-clear', request_id='run-1'):
        case = self.client.get('/api/cases/' + case_id).json()
        return self.client.post(f'/api/cases/{case_id}/process', json={
            'requestId': request_id, 'expectedCaseVersion': case['version']})

    def test_compatibility_launcher_uses_same_app(self):
        from backend.main import app
        from demo_backend.app import app as compatibility_app
        self.assertIs(app, compatibility_app)
        self.assertEqual(self.client.post('/api/demo/reset', json={'actionId': 'reset'}).status_code, 404)

    def test_result_and_idempotent_response_survive_restart(self):
        first = self.client.post('/api/cases/case-clear/process', json={
            'requestId': 'persisted', 'expectedCaseVersion': 1})
        self.assertEqual(first.status_code, 200, first.text)
        result = ProcessResponse.model_validate(first.json())
        self.assertEqual(result.case.status, 'RESOLVED')
        with TestClient(create_app(Path(self.folder.name))) as restarted:
            repeat = restarted.post('/api/cases/case-clear/process', json={
                'requestId': 'persisted', 'expectedCaseVersion': 1})
            self.assertEqual(repeat.json(), first.json())
            customer = restarted.get('/api/portal/cases/case-clear').json()
            self.assertEqual(customer['status'], 'RESOLVED')
            self.assertEqual(customer['messages'][-1]['direction'], 'OUTBOUND')
            self.assertNotIn('runResults', customer)
            self.assertNotIn('history', customer)

    def test_aggregate_financial_authority_rejects_without_effects(self):
        before = self.client.get('/api/cases/case-clear').json()
        takeover = self.client.post('/api/cases/case-clear/takeover', json={
            'actionId': 'take', 'expectedCaseVersion': before['version'], 'operatorId': 'demo-agent'})
        self.assertEqual(takeover.status_code, 200, takeover.text)
        case = takeover.json()
        sources = [{'sourceId': 'human-review', 'version': '1'}]
        position = dict(type='REIMBURSEMENT', amountMinor=6000, currency='EUR', explanation='Demo expense', sources=sources)
        action = dict(actionId='over-limit', caseId='case-clear', expectedCaseVersion=case['version'],
                      type='RESOLVE', sources=sources, payload=dict(outcome='MANUAL', explanation='Reviewed',
                      replyDe='Simulated reply', sources=sources, financialPositions=[position, position]))
        response = self.client.post('/api/cases/case-clear/actions', json=action)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()['error']['code'], 'AUTHORITY_LIMIT')
        after = self.client.get('/api/cases/case-clear').json()
        self.assertEqual(after['version'], case['version'])
        self.assertEqual(after['snapshot']['messages'], case['snapshot']['messages'])
        self.assertFalse(any(e['type'] == 'action.applied' for e in after['history']))

    def test_current_version_in_conflict_and_case_schema(self):
        case = CaseDetail.model_validate(self.client.get('/api/cases/case-clear').json())
        response = self.client.post('/api/cases/case-clear/takeover', json={
            'actionId': 'stale', 'expectedCaseVersion': case.version + 1, 'operatorId': 'demo-agent'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error']['currentCaseVersion'], case.version)

    def test_event_migration_preserves_rows_and_sequence(self):
        with tempfile.TemporaryDirectory(prefix='condor-old-events-') as folder:
            path = Path(folder)
            with sqlite3.connect(path / 'care-hub.sqlite3') as connection:
                connection.execute('CREATE TABLE events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, id VARCHAR UNIQUE, case_id VARCHAR, type VARCHAR, step_id VARCHAR, timestamp VARCHAR, summary VARCHAR, data JSON)')
                connection.execute("INSERT INTO events VALUES (42, 'old-event', 'old-case', 'case.updated', NULL, '2026-10-30T00:00:00Z', 'Preserved', '{}')")
            connection.close()
            database = Database(path)
            try:
                with database.session() as session:
                    event = session.scalar(select(Event))
                    self.assertEqual(event.sequence, 42)
                    self.assertEqual(event.id, 'old-event')
                    self.assertIsNone(event.run_id)
                with database.engine.connect() as connection:
                    self.assertEqual(connection.exec_driver_sql('SELECT version FROM schema_versions').scalar(), 1)
            finally:
                database.engine.dispose()


if __name__ == '__main__':
    unittest.main()
