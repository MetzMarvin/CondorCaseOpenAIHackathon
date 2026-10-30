import json
import unittest
from unittest.mock import Mock

from backend.ai_service.evaluation.policy_audit import load_cases, evaluate, control_cases
from backend.ai_service.policy_audit import audit_context, audit_handling
from backend.ai_service.policy_decisions import load_package


class PolicyAuditTests(unittest.TestCase):
    def setUp(self):
        self.requests, self.findings = load_cases()

    def test_all_data_preserved_without_expected_findings(self):
        self.assertEqual(len(self.requests), 20)
        for request in self.requests:
            context = audit_context(request)
            audit = next(f for f in context['facts'] if f['name'] == 'handling_audit_record')
            self.assertEqual(audit['value'], self.findings[request.case_id]['evidence_quote'])
            self.assertNotIn('corrective_handling', json.dumps(context))
            self.assertNotIn('expected_rule', context)
            self.assertNotIn('proposed_action', context)

    def client(self, mutate=lambda a: None):
        client = Mock()
        def post(*args, **kwargs):
            body = kwargs['body']
            self.assertEqual(args[0], '/decisions')
            self.assertEqual(len(body['questions']), len(load_package()['policy.json']['rules']))
            answers = [dict(type='choice', name=q['name'], choice='INSUFFICIENT_EVIDENCE', confidence=.99)
                       for q in reversed(body['questions'])]
            mutate(answers)
            return dict(answers=answers, usage={'input_tokens': 10})
        client.post.side_effect = post
        return client

    def test_unknown_is_a_verdict_and_snapshot_is_unchanged(self):
        request = self.requests[0]
        before = request.model_dump_json()
        result = audit_handling(self.client(), request)
        self.assertTrue(all(v['choice'] == 'INSUFFICIENT_EVIDENCE' for v in result['report']['verdicts']))
        self.assertEqual(before, request.model_dump_json())
        self.assertEqual(result['mode'], 'historical_handling_audit')
        self.assertEqual(len(result['evidence_sha256']), 64)

    def test_refusal_duplicate_missing_unknown_and_invalid_confidence_are_errors(self):
        for mutate in (lambda a: a.pop(), lambda a: a.append(a[0]),
                       lambda a: a[0].update(name='invented'),
                       lambda a: a[0].update(type='refusal'),
                       lambda a: a[0].update(confidence=float('nan'))):
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                audit_handling(self.client(mutate), self.requests[0])

    def test_error_or_unknown_never_scores_as_detection(self):
        def failed(request):
            raise RuntimeError('private data')
        result = evaluate(failed, self.requests, self.findings)
        self.assertEqual(result['errors'], 20)
        self.assertEqual(result['detected'], 0)
        self.assertNotIn('private data', json.dumps(result))
        result = evaluate(lambda r: audit_handling(self.client(), r), self.requests, self.findings)
        self.assertEqual(result['errors'], 0)
        self.assertEqual(result['detected'], 0)

    def test_low_confidence_violation_not_scored_as_confirmed(self):
        def low(answers):
            for a in answers:
                a.update(choice='VIOLATION', confidence=.89)
        result = evaluate(lambda r: audit_handling(self.client(low), r), self.requests[:1], self.findings)
        self.assertEqual(result['detected'], 0)

    def test_oversized_evidence_rejected_before_api(self):
        request = self.requests[0].model_copy(deep=True)
        request = request.model_copy(update={'snapshot': request.snapshot.model_copy(update={
            'known_facts': (request.snapshot.known_facts[0].model_copy(update={'value': 'x' * 65000}),)})})
        client = self.client()
        with self.assertRaises(ValueError):
            audit_handling(client, request)
        client.post.assert_not_called()

    def test_always_violation_fails_independent_controls(self):
        requests, findings = control_cases()
        def violation(answers):
            for answer in answers:
                answer.update(choice='VIOLATION')
        result = evaluate(lambda r: audit_handling(self.client(violation), r), requests, findings)
        self.assertEqual(result['total'], 4)
        self.assertEqual(result['matched'], 0)
