import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
from openai import OpenAI

from backend.ai_service.context import ProcessingBundle, expert_context
from backend.ai_service.experts import ExpertReview
from backend.ai_service.fixtures import demo_request
from backend.ai_service.policy_decisions import check_policies, load_package, POLICY_ROOT
from backend.ai_service.service import create_processor
from backend.ai_service.settings import Settings
from backend.ai_service.workflow import run_workflow


class PolicyDecisionsTests(unittest.TestCase):
    def test_decisions_is_default_and_experts_is_explicit_opt_out(self):
        self.assertEqual(Settings('offline', '').policy_strategy, 'decisions')
        with patch.dict(os.environ, {}, clear=True), patch(
                'backend.ai_service.settings.dotenv_values', return_value={}):
            self.assertEqual(Settings.from_env().policy_strategy, 'decisions')
            with patch.dict(os.environ, {'AI_POLICY_STRATEGY': 'experts'}):
                self.assertEqual(Settings.from_env().policy_strategy, 'experts')

    def context(self, scenario='clear'):
        request = demo_request(scenario)
        bundle = ProcessingBundle(request)
        baseline = run_workflow(request, lambda _: None, bundle=bundle)
        return bundle, expert_context(bundle, baseline)

    @staticmethod
    def response(body):
        return {'answers': [dict(type='choice', name=q['name'], choice='SUPPORTED', confidence=0.98)
                            for q in reversed(body['questions'])]}

    def test_real_sdk_http_request_covers_every_rule_and_approved_passage(self):
        bundle, context = self.context()
        package = load_package()
        def handler(request):
            self.assertEqual(request.url.path, '/v1/decisions')
            body = json.loads(request.content)
            self.assertEqual(body['model'], 'gpt-6-luna')
            names = {q['name'] for q in body['questions']}
            self.assertTrue({r['rule_id'] for r in package['policy.json']['rules']} <= names)
            self.assertEqual(len(names), len(package['policy.json']['rules']) + len(context['approved_passages']))
            sent = json.loads(body['input'][1]['content'])
            self.assertEqual(sent['policy_package'], package)
            return httpx.Response(200, json=self.response(body))
        with OpenAI(api_key='test', base_url='https://api.openai.com/v1',
                    http_client=httpx.Client(transport=httpx.MockTransport(handler))) as client:
            report = check_policies(client, context, bundle)
        self.assertEqual(report.status, 'draft_review_required')
        self.assertIs(bundle.policy_report, report)

    def test_invalid_or_incomplete_reviews_fail_closed(self):
        mutations = [
            lambda a: a.pop(),
            lambda a: a.append(a[0]),
            lambda a: a[0].update(name='invented'),
            lambda a: a[0].update(type='refusal'),
            lambda a: a[0].update(choice='VIOLATION'),
            lambda a: a[0].update(choice='INSUFFICIENT_EVIDENCE'),
            lambda a: a[0].update(confidence=0.89),
            lambda a: a[0].update(confidence=float('nan')),
            lambda a: next(x for x in a if x['name'] == 'GOV-001').update(choice='NOT_APPLICABLE'),
        ]
        for mutate in mutations:
            bundle, context = self.context()
            client = Mock()
            def respond(*args, **kwargs):
                response = self.response(kwargs['body'])
                mutate(response['answers'])
                return response
            client.post.side_effect = respond
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                check_policies(client, context, bundle)

    def test_partial_regeneration_is_rejected_before_request(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('manifest.json', 'policy.json', 'sources.json', 'decision-tables.json'):
                (root / name).write_bytes((POLICY_ROOT / name).read_bytes())
            (root / 'policy.json').write_text('{}')
            bundle, context = self.context()
            client = Mock()
            with self.assertRaises(ValueError):
                check_policies(client, context, bundle, root=root)
            client.post.assert_not_called()

    def test_live_flows_and_diagnostics_preserve_proposals(self):
        for scenario in ('clear', 'missing', 'reply', 'serious', 'unsupported'):
            with self.subTest(scenario=scenario), patch('backend.ai_service.experts.OpenAI') as factory:
                client = factory.return_value.__enter__.return_value
                client.post.side_effect = lambda *a, **kw: self.response(kw['body'])
                def parse(**kw):
                    context = json.loads(kw['input'][1]['content'])
                    schema = kw['text_format']
                    value = (ExpertReview(supported=True, summary='Checked',
                        source_ids=context['required_source_ids'], citations=context['required_citations'])
                        if schema == ExpertReview else schema(**context['reviewed_draft']))
                    return SimpleNamespace(status='completed', output_parsed=value)
                client.responses.parse.side_effect = parse
                manifests = []
                settings = Settings('openai', 'test', policy_strategy='decisions')
                request = demo_request(scenario)
                before = request.model_dump_json()
                baseline = run_workflow(request, lambda _: None, bundle=ProcessingBundle(request))
                result = create_processor(settings=settings, diagnostic_sink=manifests.append)(request, lambda _: None)
                self.assertEqual(result.status, 'SUCCEEDED')
                self.assertEqual(result.proposed_action.type, baseline.proposed_action.type)
                self.assertEqual(result.proposed_action.action_id, baseline.proposed_action.action_id)
                self.assertEqual(request.model_dump_json(), before)
                self.assertEqual(client.post.call_count, 1)
                self.assertEqual(client.responses.parse.call_count, 2)
                self.assertTrue(manifests[0].policy_report.verdicts)

    def test_provider_failure_is_failed_run_without_business_action(self):
        with patch('backend.ai_service.experts.OpenAI') as factory:
            client = factory.return_value.__enter__.return_value
            def parse(**kw):
                context = json.loads(kw['input'][1]['content'])
                return SimpleNamespace(status='completed', output_parsed=ExpertReview(supported=True,
                    summary='Checked', source_ids=context['required_source_ids'], citations=context['required_citations']))
            client.responses.parse.side_effect = parse
            client.post.side_effect = RuntimeError('private-provider-error')
            manifests = []
            result = create_processor(settings=Settings('openai', 'test', policy_strategy='decisions'),
                diagnostic_sink=manifests.append)(demo_request('clear'), lambda _: None)
            self.assertEqual(result.status, 'FAILED')
            self.assertIsNone(result.proposed_action)
            self.assertNotIn('private-provider-error', result.model_dump_json())
            self.assertEqual(manifests[0].policy_report.verdicts, [])

    def test_offline_never_calls_decisions(self):
        with patch('backend.ai_service.experts.OpenAI') as factory:
            result = create_processor(settings=Settings('offline', '', policy_strategy='decisions'))(
                demo_request('clear'), lambda _: None)
            self.assertTrue(result.simulation)
            factory.assert_not_called()
