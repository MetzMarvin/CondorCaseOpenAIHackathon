import unittest

from backend.ai_service.customer_email import CustomerEmail, EmailQuestion
from backend.contracts import MissingFact


class CustomerEmailTests(unittest.TestCase):
    def draft(self, names):
        return CustomerEmail(action_type='REQUEST_INFORMATION', explanation='Evidence needed.',
            sentiment='neutral', opening='Thank you for your reply.',
            questions=[EmailQuestion(fact_name=name, question='Please confirm ' + name + '.') for name in names])

    def test_email_has_case_reference_and_reply_instructions(self):
        missing = (MissingFact(name='receipt_currency', reason='Currency is missing.'),)
        body = self.draft(['receipt_currency']).render('case-123', missing)
        self.assertIn('Subject: More information needed for your case case-123\n', body)
        self.assertIn('Please reply to this email', body)
        self.assertIn('Your Customer Care team', body)
        self.assertNotIn('receipt_amount', body)

    def test_missing_extra_and_duplicate_questions_are_rejected(self):
        missing = (MissingFact(name='receipt_currency', reason='Currency is missing.'),)
        for names in ([], ['receipt_amount'], ['receipt_currency', 'receipt_amount'],
                      ['receipt_currency', 'receipt_currency']):
            with self.subTest(names=names), self.assertRaises(ValueError):
                self.draft(names).render('case-123', missing)

    def test_case_reference_cannot_inject_headers(self):
        body = self.draft([]).render('case-123\nBcc: injected', ())
        self.assertNotIn('\nBcc:', body)
