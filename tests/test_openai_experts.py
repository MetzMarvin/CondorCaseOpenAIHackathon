import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.ai_service import process_case
from backend.ai_service.experts import ExpertDraft, ExpertReview
from backend.ai_service.customer_email import CustomerEmail, EmailQuestion
from backend.ai_service.fixtures import demo_request
from backend.ai_service.settings import Settings
from backend.ai_service.workflow import process_case as offline


class OpenAIExpertTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'AI_MODE': 'openai', 'OPENAI_API_KEY': 'test-secret'}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_all_live_flows_use_all_experts_and_preserve_authority(self):
        for scenario in ('clear', 'missing', 'partial_reply', 'reply', 'serious', 'unsupported'):
            with self.subTest(scenario=scenario), patch('backend.ai_service.experts.OpenAI') as client:
                request = demo_request(scenario)
                before = request.model_dump_json()
                baseline = offline(request, lambda _: None)
                review = ExpertReview(supported=True, summary='Evidence and policy reviewed.',
                                      source_ids=[s.source_id for s in baseline.assessment.sources])
                draft = ExpertDraft(action_type=baseline.proposed_action.type,
                    explanation='The reviewed evidence supports this demo proposal.',
                    sentiment='negative', customer_message='Customer care draft.')
                if baseline.proposed_action.type == 'REQUEST_INFORMATION':
                    draft = CustomerEmail(action_type='REQUEST_INFORMATION', explanation='Missing evidence.',
                        sentiment='negative', opening='Thank you for contacting us.', questions=[
                            EmailQuestion(fact_name=f.name, question='Please provide ' + f.name + '.')
                            for f in baseline.proposed_action.payload.missing_facts])
                parse = client.return_value.__enter__.return_value.responses.parse
                parse.side_effect = [SimpleNamespace(status='completed', output_parsed=value)
                                     for value in (review, review, draft)]
                events = []
                result = process_case(request, events.append)
                self.assertEqual(result.status, 'SUCCEEDED')
                self.assertFalse(result.simulation)
                self.assertTrue(all(not event.simulation for event in events))
                self.assertEqual(parse.call_count, 3)
                self.assertTrue(all(call.kwargs['store'] is False for call in parse.call_args_list))
                self.assertNotIn('test-secret', str(parse.call_args_list))
                self.assertEqual(request.model_dump_json(), before)
                self.assertEqual(result.proposed_action.action_id, baseline.proposed_action.action_id)
                self.assertEqual(result.proposed_action.type, baseline.proposed_action.type)
                if result.proposed_action.type == 'REQUEST_INFORMATION':
                    self.assertIn('Subject: More information needed', result.proposed_action.payload.question_de)
                    self.assertIn('request_information', [event.step_id for event in events])
                    if scenario == 'partial_reply':
                        self.assertNotIn('receipt_currency', result.proposed_action.payload.question_de)
                else:
                    self.assertNotIn('request_information', [event.step_id for event in events])
                if result.proposed_action.type == 'RESOLVE':
                    self.assertEqual(result.proposed_action.payload.financial_positions,
                                     baseline.proposed_action.payload.financial_positions)

    def test_resolution_text_cannot_override_validated_financial_decision(self):
        unsafe_texts = (
            'Your reimbursement of 999.99 USD is approved.',
            'Your reimbursement of nine hundred euros is approved.',
            'We have transferred the reimbursement to your bank account.',
            'Your payment has been processed successfully.',
            'We cannot reimburse your expenses.',
        )
        request = demo_request('clear')
        baseline = offline(request, lambda _: None)
        for text in unsafe_texts:
            with self.subTest(text=text), patch('backend.ai_service.experts.OpenAI') as client:
                review = ExpertReview(supported=True, summary='Supported.', source_ids=[])
                draft = ExpertDraft(action_type='RESOLVE', explanation=text,
                                    sentiment='neutral', customer_message=text)
                client.return_value.__enter__.return_value.responses.parse.side_effect = [
                    SimpleNamespace(status='completed', output_parsed=value)
                    for value in (review, review, draft)]
                events = []
                result = process_case(request, events.append)
                self.assertEqual(result.status, 'SUCCEEDED')
                self.assertEqual(result.proposed_action.payload, baseline.proposed_action.payload)
                self.assertEqual(result.assessment.next_action_explanation,
                                 baseline.assessment.next_action_explanation)
                self.assertNotIn(text, result.model_dump_json())
                self.assertTrue(all(text not in event.summary for event in events))

    def test_api_error_refusal_and_unknown_sources_fail_without_fallback(self):
        invalid = ExpertReview(supported=True, summary='Review', source_ids=['invented-source'])
        disagreement = ExpertReview(supported=False, summary='Insufficient evidence', source_ids=[])
        for response in (RuntimeError('test-secret'), None, invalid, disagreement):
            with self.subTest(response=type(response)), patch('backend.ai_service.experts.OpenAI') as client:
                parse = client.return_value.__enter__.return_value.responses.parse
                if isinstance(response, Exception):
                    parse.side_effect = response
                else:
                    parse.return_value = SimpleNamespace(status='completed', output_parsed=response)
                result = process_case(demo_request('clear'), lambda _: None)
                self.assertEqual(result.status, 'FAILED')
                self.assertFalse(result.simulation)
                self.assertIsNone(result.proposed_action)
                self.assertNotIn('test-secret', result.model_dump_json())

    def test_offline_does_not_create_client(self):
        with patch.dict(os.environ, {'AI_MODE': 'offline'}), patch('backend.ai_service.experts.OpenAI') as client:
            result = process_case(demo_request('clear'), lambda _: None)
            self.assertEqual(result.status, 'SUCCEEDED')
            self.assertTrue(result.simulation)
            client.assert_not_called()

    def test_incomplete_email_fails_the_run_instead_of_proposing_it(self):
        with patch('backend.ai_service.experts.OpenAI') as client:
            review = ExpertReview(supported=True, summary='Supported next action.', source_ids=[])
            draft = CustomerEmail(action_type='REQUEST_INFORMATION', explanation='Evidence missing.',
                sentiment='neutral', opening='Thank you for contacting us.', questions=[])
            client.return_value.__enter__.return_value.responses.parse.side_effect = [
                SimpleNamespace(status='completed', output_parsed=value) for value in (review, review, draft)]
            result = process_case(demo_request('missing'), lambda _: None)
            self.assertEqual(result.status, 'FAILED')
            self.assertIsNone(result.proposed_action)

    def test_missing_key_is_failed_run(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': ''}):
            self.assertEqual(process_case(demo_request('clear'), lambda _: None).status, 'FAILED')

    def test_configuration_loads_dotenv_and_shell_takes_precedence(self):
        with patch.dict(os.environ, {}, clear=True), patch('backend.ai_service.settings.dotenv_values',
                return_value={'OPENAI_API_KEY': 'file-secret', 'AI_MODE': 'auto', 'OPENAI_MODEL': 'file-model'}):
            settings = Settings.from_env()
            self.assertEqual(settings.mode, 'openai')
            self.assertEqual(settings.api_key, 'file-secret')
            self.assertNotIn('file-secret', repr(settings))
            with patch.dict(os.environ, {'OPENAI_MODEL': 'shell-model'}):
                self.assertEqual(Settings.from_env().model, 'shell-model')

    def test_human_owned_snapshot_never_calls_openai(self):
        from backend.contracts import Owner
        request = demo_request('clear')
        request = request.model_copy(update={'snapshot': request.snapshot.model_copy(
            update={'owner': Owner(type='HUMAN', id='operator')})})
        with patch('backend.ai_service.experts.OpenAI') as client:
            self.assertEqual(process_case(request, lambda _: None).status, 'FAILED')
            client.assert_not_called()
