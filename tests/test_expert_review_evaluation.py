import unittest

from backend.ai_service.evaluation.expert_review import cases, evaluate
from backend.ai_service.experts import ExpertReview


class ExpertReviewEvaluationTests(unittest.TestCase):
    def test_context_contains_actual_decisions_without_raw_handoff_facts(self):
        catalog = {c['id']: c for c in cases()}
        self.assertEqual(catalog['clear']['context']['proposed_action']['financial_positions'],
                         [dict(type='REIMBURSEMENT', amount_minor=4200, currency='EUR')])
        self.assertEqual(catalog['serious']['context']['proposed_action'],
                         dict(type='HANDOFF', reason_code='SERIOUS_ISSUE'))
        self.assertEqual(catalog['partial_reply']['context']['proposed_action']['missing_fields'],
                         ['receipt_amount_minor'])
        self.assertEqual(catalog['clear']['context']['retrieval_status'], 'SUPPORTED')
        self.assertTrue(all('expected_supported' not in c['context'] for c in catalog.values()))

    def test_citation_echo_cannot_pass_negative_cases(self):
        def echo(role, context):
            return ExpertReview(supported=True, summary='Echo', source_ids=context['required_source_ids'],
                                citations=context['required_citations'])
        result = evaluate(echo)
        self.assertEqual(result['valid_acceptance'], dict(passed=9, total=9))
        self.assertEqual(result['invalid_rejection'], dict(passed=0, total=8))

    def test_always_reject_cannot_pass_positive_cases(self):
        result = evaluate(lambda *_: ExpertReview(supported=False, summary='Reject', source_ids=[]))
        self.assertEqual(result['valid_acceptance']['passed'], 0)
        self.assertEqual(result['invalid_rejection']['passed'], 8)

    def test_errors_and_broken_citations_are_not_correct_rejections(self):
        def error(*_):
            raise RuntimeError('private provider text')
        result = evaluate(error)
        self.assertEqual(result['errors'], result['total'])
        self.assertEqual(result['passed'], 0)
        self.assertNotIn('private provider text', str(result))
        invalid = evaluate(lambda *_: ExpertReview(supported=True, summary='Bad citations', source_ids=[]))
        self.assertEqual(invalid['passed'], 0)

    def test_reviewer_cannot_mutate_next_review_or_gold_context(self):
        catalog = cases()[:1]
        def review(role, context):
            self.assertEqual(context['proposed_action']['type'], 'RESOLVE')
            context['proposed_action']['type'] = 'HANDOFF'
            return ExpertReview(supported=True, summary='Review', source_ids=context['required_source_ids'],
                                citations=context['required_citations'])
        self.assertEqual(evaluate(review, catalog)['passed'], 1)
        self.assertEqual(catalog[0]['context']['proposed_action']['type'], 'RESOLVE')
