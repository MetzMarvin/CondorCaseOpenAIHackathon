"""Boundary validation, independent of model access or persistence."""
import unittest
from pydantic import TypeAdapter, ValidationError
from backend.contracts import FinancialPosition, ProcessEvent, ProposedAction, RunResult


class ContractTests(unittest.TestCase):
    def action(self, kind='RESOLVE'):
        source = {'sourceId': 'policy-01', 'version': '1'}
        payloads = {
            'RESOLVE': dict(outcome='supported', explanation='Demo-Regel', sources=[source], replyDe='Wir erstatten Ihre Kosten.'),
            'REQUEST_INFORMATION': dict(missingFacts=[dict(name='receipt', reason='Kosten belegen')], questionDe='Bitte senden Sie den Beleg.'),
            'HANDOFF': dict(reasonCode='SERIOUS_ISSUE', suggestedQueue='specialist', summary='Sicherheitsvorfall', facts=[], evidence=[source], unresolvedQuestions=[], priorAttempts=[]),
        }
        return dict(actionId='a1', caseId='c1', runId='r1', expectedCaseVersion=2, sources=[source], type=kind, payload=payloads[kind])

    def result(self):
        return dict(runId='r1', caseId='c1', basedOnCaseVersion=2, status='SUCCEEDED', assessment=dict(issues=['expense'], missingFacts=[], severity='ordinary', sentiment='negative', sources=[], nextActionExplanation='Belegt'), proposedAction=self.action())

    def test_three_action_types_roundtrip_and_schema(self):
        adapter = TypeAdapter(ProposedAction)
        for kind in ('RESOLVE', 'REQUEST_INFORMATION', 'HANDOFF'):
            action = adapter.validate_python(self.action(kind))
            self.assertEqual(adapter.validate_json(action.model_dump_json(by_alias=True)), action)
        self.assertEqual(adapter.json_schema()['discriminator']['propertyName'], 'type')
        self.assertIn('runId', RunResult.model_json_schema()['properties'])

    def test_action_payload_mismatch_rejected(self):
        action = self.action()
        action['type'] = 'HANDOFF'
        with self.assertRaises(ValidationError):
            TypeAdapter(ProposedAction).validate_python(action)

    def test_ai_identity_and_version_must_match(self):
        for key, value in [('runId', None), ('runId', 'other'), ('caseId', 'other'), ('expectedCaseVersion', 3)]:
            result = self.result()
            result['proposedAction'][key] = value
            with self.assertRaises(ValidationError):
                RunResult.model_validate(result)
        RunResult.model_validate(self.result())

    def test_failed_run_cannot_invent_business_action(self):
        failed = dict(runId='r1', caseId='c1', basedOnCaseVersion=2, status='FAILED', technicalError=dict(code='MODEL_ERROR', message='Unavailable', retryable=True))
        RunResult.model_validate(failed)
        with self.assertRaises(ValidationError):
            RunResult.model_validate(dict(failed, proposedAction=self.action()))
        with self.assertRaises(ValidationError):
            RunResult.model_validate(dict(failed, technicalError=None))

    def test_money_requires_nonnegative_integer_minor_units(self):
        for amount in (-1, 1.5, True, '100'):
            with self.assertRaises(ValidationError):
                FinancialPosition(type='GOODWILL', amount_minor=amount, currency='EUR', explanation='Demo', sources=[])

    def test_step_events_require_known_step_and_aware_timestamp(self):
        event = dict(eventId='e1', caseId='c1', sequence=1, type='step.completed', stepId='assess', timestamp='2026-10-30T12:00:00Z', summary='Geprüft')
        ProcessEvent.model_validate(event)
        for patch in (dict(stepId=None), dict(stepId='invented'), dict(timestamp='2026-10-30T12:00:00')):
            with self.assertRaises(ValidationError):
                ProcessEvent.model_validate(event | patch)
