"""Offline acceptance checks and stable, complete behavioral comparisons."""
import difflib
import json

from backend.ai_service.workflow import process_case
from backend.ai_service.evaluation.scenarios import scenarios
from backend.contracts import RunRequest, RunResult


def dump(value):
    return value.model_dump(mode='json', by_alias=True)


def evaluate(processor=process_case, catalog=None):
    rows = []
    for scenario in scenarios() if catalog is None else catalog:
        stages, checks = [], []

        def check(name, passed):
            checks.append({'name': name, 'passed': bool(passed)})

        for index, original in enumerate(scenario.requests):
            # Fresh validated objects isolate runs, including nested JSON fact values.
            request = RunRequest.model_validate_json(original.model_dump_json())
            before = dump(request)
            progress = []

            def emit(event):
                if scenario.broken_callback:
                    raise RuntimeError('Injected evaluation callback failure')
                progress.append(dump(event))

            stage = {'request': before, 'expected': scenario.outcomes[index],
                     'expectedCode': scenario.codes[index], 'progress': progress}
            prefix = f'Stage {index + 1}: '
            try:
                result = processor(request, emit)
                stage['result'] = dump(result)
                action = result.proposed_action
                actual = action.type if action else result.status
                code = result.technical_error.code if result.technical_error else getattr(action.payload, 'reason_code', None)
                stage.update(actual=actual, code=code)
                check(prefix + 'expected outcome', actual == scenario.outcomes[index])
                check(prefix + 'expected reason / error', code == scenario.codes[index])
                check(prefix + 'snapshot unchanged', before == dump(request))
                check(prefix + 'shared contract valid', RunResult.model_validate(stage['result']) == result)
                check(prefix + 'identity and version preserved',
                      (result.run_id, result.case_id, result.based_on_case_version) == (request.run_id, request.case_id, request.case_version))
                check(prefix + 'simulation labeled', result.simulation and all(e['simulation'] for e in progress))
                replay_events = []
                def replay_emit(event):
                    if scenario.broken_callback:
                        raise RuntimeError('Injected evaluation callback failure')
                    replay_events.append(dump(event))
                replay = processor(RunRequest.model_validate(before), replay_emit)
                check(prefix + 'repeat gives identical result and progress', dump(replay) == stage['result'] and replay_events == progress)
                if scenario.missing:
                    check(prefix + 'exact remaining evidence gaps', result.assessment is not None and
                          sorted(m.name for m in result.assessment.missing_facts) == sorted(scenario.missing[index]))
                if action:
                    check(prefix + 'proposal carries sources', bool(action.sources))
                    check(prefix + 'validation progress recorded', bool(progress) and progress[-1]['stepId'] == 'validate_action' and progress[-1]['type'] == 'step.completed')
                    if action.type == 'RESOLVE':
                        check(prefix + 'exact reimbursement, no extra positions',
                              [(p.type, p.amount_minor, p.currency) for p in action.payload.financial_positions] == [('REIMBURSEMENT', 4200, 'EUR')])
                    if action.type == 'HANDOFF':
                        check(prefix + 'concrete specialist context', bool(action.payload.summary and action.payload.evidence and action.payload.unresolved_questions))
                else:
                    check(prefix + 'technical failure has no action', result.status == 'FAILED' and result.technical_error is not None)
            except Exception as exc:
                stage.update(actual='EXCEPTION', exception=f'{type(exc).__name__}: {exc}')
                check(prefix + 'processor completes without uncaught exception', False)
            stages.append(stage)
        if len(stages) > 1:
            check('Reply snapshots retain the case and advance its version',
                  len({r.case_id for r in scenario.requests}) == 1 and
                  all(a.case_version < b.case_version for a, b in zip(scenario.requests, scenario.requests[1:])))
        rows.append({'id': scenario.id, 'purpose': scenario.purpose, 'stages': stages,
                     'checks': checks, 'passed': all(c['passed'] for c in checks)})
    return {'schemaVersion': 1, 'mode': 'offline-simulation', 'scenarios': rows}


def compare(current, baseline):
    if baseline.get('schemaVersion') != 1 or baseline.get('mode') != current['mode']:
        raise ValueError('Baseline must be a version 1 offline evaluation report')
    old = {r['id']: r for r in baseline['scenarios']}
    new = {r['id']: r for r in current['scenarios']}
    changes = []
    for key in sorted(old.keys() | new.keys()):
        a, b = old.get(key), new.get(key)
        state = 'added' if a is None else 'removed' if b is None else 'regressed' if a['passed'] and not b['passed'] else 'fixed' if not a['passed'] and b['passed'] else 'changed' if a != b else 'unchanged'
        diff = '\n'.join(difflib.unified_diff(
            json.dumps(a, indent=2, sort_keys=True).splitlines(),
            json.dumps(b, indent=2, sort_keys=True).splitlines(), fromfile='baseline', tofile='current', lineterm='')) if a != b else ''
        changes.append({'id': key, 'state': state, 'diff': diff})
    return changes
