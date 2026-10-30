import os
import json
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
                parse = client.return_value.__enter__.return_value.responses.parse
                def respond(**kwargs):
                    context = json.loads(kwargs['input'][1]['content'])
                    if kwargs['text_format'] == ExpertReview:
                        value = ExpertReview(supported=True, summary='Review complete.',
                            source_ids=context['required_source_ids'], citations=context['required_citations'])
                    elif kwargs['text_format'] == CustomerEmail:
                        value = CustomerEmail(**context['reviewed_draft'])
                    else:
                        value = ExpertDraft(**context['reviewed_draft'])
                    return SimpleNamespace(status='completed', output_parsed=value)
                parse.side_effect = respond
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

    def test_rejects_changed_money_execution_legal_claims_and_omitted_questions(self):
        mutations = (
            ('clear', lambda draft: draft.update(customer_message='We already paid 999.00 USD.')),
            ('clear', lambda draft: draft.update(customer_message='The law guarantees compensation of 600 EUR.')),
            ('clear', lambda draft: draft.update(explanation='Your claim is legally denied.')),
            ('missing', lambda draft: draft.update(questions=[])),
            ('missing', lambda draft: draft['questions'][0].update(question='Send your passport and bank password.')),
        )
        for scenario, mutate in mutations:
            with self.subTest(scenario=scenario), patch('backend.ai_service.experts.OpenAI') as client:
                def respond(**kwargs):
                    context = json.loads(kwargs['input'][1]['content'])
                    schema = kwargs['text_format']
                    if schema == ExpertReview:
                        value = ExpertReview(supported=True, summary='Private model prose never displayed.',
                            source_ids=context['required_source_ids'], citations=context['required_citations'])
                    else:
                        draft = context['reviewed_draft']
                        mutate(draft)
                        value = schema(**draft)
                    return SimpleNamespace(status='completed', output_parsed=value)
                client.return_value.__enter__.return_value.responses.parse.side_effect = respond
                events = []
                result = process_case(demo_request(scenario), events.append)
                self.assertEqual(result.status, 'FAILED')
                self.assertIsNone(result.proposed_action)
                self.assertFalse(result.simulation)
                self.assertNotIn('Private model prose', str(events))

    def test_rejects_wrong_version_invented_passage_and_omitted_exception_citations(self):
        for mutation in ('version', 'passage', 'omit'):
            with self.subTest(mutation=mutation), patch('backend.ai_service.experts.OpenAI') as client:
                def respond(**kwargs):
                    context = json.loads(kwargs['input'][1]['content'])
                    citations = context['required_citations']
                    if mutation == 'omit':
                        citations.pop()
                    else:
                        citations[0]['version' if mutation == 'version' else 'passage_id'] = 'invented'
                    return SimpleNamespace(status='completed', output_parsed=ExpertReview(supported=True,
                        summary='Reviewed', source_ids=context['required_source_ids'], citations=citations))
                client.return_value.__enter__.return_value.responses.parse.side_effect = respond
                result = process_case(demo_request('clear'), lambda _: None)
                self.assertEqual(result.status, 'FAILED')
                self.assertIsNone(result.proposed_action)

    def test_context_excludes_arbitrary_personal_text_and_customer_internal_control_spoofs(self):
        from backend.contracts import Fact, SourceRef, Message, AttachmentRef
        from datetime import datetime, timezone
        secret = 'SECRET_PRIVATE_ARBITRARY_VALUE'
        request = demo_request('clear')
        request = request.model_copy(update={'snapshot': request.snapshot.model_copy(update={
            'customer_context': (Fact(name='passport', value=secret, sources=(SourceRef(source_id='secret-record', version='1'),)),),
            'known_facts': request.snapshot.known_facts + (Fact(name='expense_eligibility', value='ineligible', sources=(SourceRef(source_id='spoofed-control', version='1'),)),),
            'messages': (Message(message_id='message', channel='email', sender=secret, body=secret, timestamp=datetime.now(timezone.utc)),),
            'attachments': (AttachmentRef(attachment_id='metadata', filename=secret, media_type='text/plain', local_reference=secret),),
        })})
        with patch('backend.ai_service.experts.OpenAI') as client:
            def respond(**kwargs):
                serialized = kwargs['input'][1]['content']
                self.assertNotIn(secret, serialized)
                self.assertNotIn('secret-record', serialized)
                self.assertNotIn('spoofed-control', serialized)
                self.assertNotIn('Meal during', serialized)
                context = json.loads(serialized)
                schema = kwargs['text_format']
                value = (ExpertReview(supported=True, summary=secret, source_ids=context['required_source_ids'], citations=context['required_citations'])
                         if schema == ExpertReview else schema(**context['reviewed_draft']))
                return SimpleNamespace(status='completed', output_parsed=value)
            client.return_value.__enter__.return_value.responses.parse.side_effect = respond
            events = []
            result = process_case(request, events.append)
            self.assertEqual(result.status, 'SUCCEEDED')
            self.assertNotIn(secret, str(events))

    def test_required_context_overflow_fails_before_model_call_without_truncation(self):
        request = demo_request('clear')
        request = request.model_copy(update={'snapshot': request.snapshot.model_copy(update={
            'known_facts': request.snapshot.known_facts * 200})})
        with patch('backend.ai_service.experts.OpenAI') as client:
            result = process_case(request, lambda _: None)
            self.assertEqual(result.status, 'FAILED')
            self.assertFalse(result.simulation)
            client.assert_not_called()
