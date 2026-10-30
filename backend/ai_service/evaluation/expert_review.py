"""Opt-in live review benchmark with synthetic positive and counterfactual proposals.

Gold verdicts never enter the model input. This evaluates the approved demo policy,
not legal correctness of the separate unreviewed research corpus.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from openai import OpenAI

from ..context import ProcessingBundle, expert_context
from ..experts import Citation, ExpertReview, INSTRUCTIONS, REVIEW_TASKS
from ..fixtures import demo_request
from ..settings import Settings
from ..workflow import run_workflow


def cases():
    rows = []
    for scenario in ('clear', 'missing', 'partial_reply', 'reply', 'serious',
                     'unsupported', 'legal_review', 'authority_limit', 'conflict'):
        request = demo_request(scenario)
        bundle = ProcessingBundle(request)
        result = run_workflow(request, lambda _: None, bundle=bundle)
        if result.status != 'SUCCEEDED':
            raise ValueError('Benchmark fixture preparation failed')
        rows.append(dict(id=scenario, expected_supported=True,
                         context=expert_context(bundle, result)))
    clear = rows[0]['context']

    def negative(name, mutate):
        context = deepcopy(clear)
        mutate(context)
        rows.append(dict(id=name, expected_supported=False, context=context))

    negative('wrong_amount', lambda c: c['proposed_action']['financial_positions'][0].update(amount_minor=8400))
    negative('wrong_currency', lambda c: c['proposed_action']['financial_positions'][0].update(currency='USD'))
    negative('extra_compensation', lambda c: c['proposed_action']['financial_positions'].append(
        dict(type='COMPENSATION', amount_minor=25000, currency='EUR')))
    negative('exceeded_authority', lambda c: c['financial_limits'][0].update(maximum_minor=1000))
    negative('forbidden_resolution', lambda c: c.update(permitted_actions=['REQUEST_INFORMATION', 'HANDOFF']))
    negative('already_paid', lambda c: next(f for f in c['facts'] if f['name'] == 'payment_history').update(value='prior_reimbursement'))
    negative('ineligible_expense', lambda c: next(f for f in c['facts'] if f['name'] == 'expense_eligibility').update(value='ineligible'))
    negative('unjustified_handoff', lambda c: c.update(proposed_action=dict(type='HANDOFF', reason_code='SERIOUS_ISSUE')))
    return rows


def evaluate(review, catalog=None):
    """review(role, context) -> ExpertReview; exceptions are errors, never rejections."""
    rows = []
    for case in cases() if catalog is None else catalog:
        reviews = []
        for role in REVIEW_TASKS:
            try:
                result = review(role, deepcopy(case['context']))
                expected = {Citation(**c) for c in case['context']['required_citations']}
                citations_valid = (set(result.citations) == expected and len(result.citations) == len(expected)
                    and set(result.source_ids) == set(case['context']['required_source_ids']))
                reviews.append(dict(role=role, supported=result.supported, citations_valid=citations_valid))
            except Exception as exc:
                # Provider exception messages can include sensitive request data.
                reviews.append(dict(role=role, error=type(exc).__name__))
        errored = any('error' in r for r in reviews)
        supported = None if errored else all(r['supported'] for r in reviews)
        # Semantic rejection is required for negative cases. Bad citations/API errors
        # cannot accidentally earn a correct-rejection score.
        passed = (not errored and supported == case['expected_supported']
                  and (not supported or all(r['citations_valid'] for r in reviews)))
        rows.append(dict(id=case['id'], expected_supported=case['expected_supported'],
            supported=supported, passed=passed, reviews=reviews,
            context_sha256=hashlib.sha256(json.dumps(case['context'], sort_keys=True).encode()).hexdigest()))
    positives = [r for r in rows if r['expected_supported']]
    negatives = [r for r in rows if not r['expected_supported']]
    return dict(schema_version=1, mode='expert-review-benchmark', cases=rows,
        total=len(rows), passed=sum(r['passed'] for r in rows),
        valid_acceptance=dict(passed=sum(r['passed'] for r in positives), total=len(positives)),
        invalid_rejection=dict(passed=sum(r['passed'] for r in negatives), total=len(negatives)),
        errors=sum(r['supported'] is None for r in rows))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    settings = Settings.from_env()
    if not settings.api_key:
        parser.error('OPENAI_API_KEY is required; this command makes live model calls')
    with OpenAI(api_key=settings.api_key, base_url='https://api.openai.com/v1',
                timeout=settings.timeout, max_retries=0) as client:
        def review(role, context):
            response = client.responses.parse(model=settings.model, store=False,
                input=[dict(role='system', content=INSTRUCTIONS + '\n' + REVIEW_TASKS[role]
                    + '\nCite every required source and every exact selected passage, including prerequisites and exceptions.'),
                       dict(role='user', content=json.dumps(context, ensure_ascii=False))], text_format=ExpertReview)
            if response.status != 'completed' or response.output_parsed is None:
                raise ValueError('Incomplete review')
            return ExpertReview.model_validate(response.output_parsed.model_dump())
        report = evaluate(review)
    report['model'] = settings.model
    report['prompt_sha256'] = hashlib.sha256((INSTRUCTIONS + json.dumps(REVIEW_TASKS, sort_keys=True)).encode()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'cases'}))
    return 0 if report['passed'] == report['total'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
