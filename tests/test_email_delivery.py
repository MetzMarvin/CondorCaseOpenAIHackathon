import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

from backend.ai_service.customer_email import CustomerEmail, EmailQuestion
from backend.ai_service.fixtures import demo_request
from backend.ai_service.service import process_case
from backend.email_delivery import SimulatedEmailSender


class EmailDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / 'outbox.sqlite3'
        self.sender = SimulatedEmailSender(self.database)

    def action(self, scenario='missing'):
        from unittest.mock import patch
        with patch.dict('os.environ', {'AI_MODE': 'offline'}):
            result = process_case(demo_request(scenario), lambda progress: None)
        self.assertEqual(result.status, 'SUCCEEDED')
        return result.proposed_action

    def test_generated_template_is_delivered_without_rewriting(self):
        action = self.action()
        email = CustomerEmail(action_type='REQUEST_INFORMATION', explanation='Missing evidence',
                              sentiment='neutral', opening='Thank you for your reply.',
                              questions=[EmailQuestion(fact_name=f.name, question='Please confirm ' + f.name)
                                         for f in action.payload.missing_facts])
        draft = email.render(action.case_id, action.payload.missing_facts)
        action = action.model_copy(update={'payload': action.payload.model_copy(update={'question_de': draft})})
        delivery = self.sender.send_authorized(action, 'customer@example.test')
        self.assertEqual('Subject: ' + delivery.subject + '\n\n' + delivery.body, draft)
        self.assertEqual(delivery.case_id, action.case_id)
        self.assertTrue(delivery.simulation)

    def test_retry_after_restart_returns_original_delivery(self):
        action = self.action()
        original = self.sender.send_authorized(action, 'customer@example.test')
        repeated = SimulatedEmailSender(self.database).send_authorized(action, 'customer@example.test')
        self.assertEqual(original, repeated)
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM email_outbox').fetchone()[0], 1)
        with self.assertRaises(ValueError):
            self.sender.send_authorized(action, 'different@example.test')
        changed = action.model_copy(update={'payload': action.payload.model_copy(update={'question_de': 'Changed'})})
        with self.assertRaises(ValueError):
            self.sender.send_authorized(changed, 'customer@example.test')

    def test_offline_question_and_resolution_receive_case_subject(self):
        for scenario in ('missing', 'clear'):
            action = self.action(scenario)
            delivery = self.sender.send_authorized(action, 'customer@example.test')
            self.assertIn(action.case_id, delivery.subject)
            self.assertEqual(delivery.body, action.payload.question_de if scenario == 'missing' else action.payload.reply_de)

    def test_internal_handoff_is_not_sent(self):
        with self.assertRaises(ValueError):
            self.sender.send_authorized(self.action('serious'), 'customer@example.test')

    def test_invalid_recipient_and_malformed_drafts_are_not_recorded(self):
        action = self.action()
        for recipient in ('', 'not-an-email', 'a@b\nBcc: other@example.test'):
            with self.subTest(recipient=recipient), self.assertRaises(ValueError):
                self.sender.send_authorized(action, recipient)
        for draft in (' ', 'Subject: hello\nBcc: other@example.test\n\nBody', 'Subject: hello\n\n'):
            bad = action.model_copy(update={'payload': action.payload.model_copy(update={'question_de': draft})})
            with self.subTest(draft=draft), self.assertRaises(ValueError):
                self.sender.send_authorized(bad, 'customer@example.test')
        with closing(sqlite3.connect(self.database)) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM email_outbox').fetchone()[0], 0)
