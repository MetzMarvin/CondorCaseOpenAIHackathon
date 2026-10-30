"""Ensure the review harness detects regressions, not just successful execution."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from backend.ai_service.evaluation.__main__ import write_artifacts
from backend.ai_service.evaluation.runner import compare, evaluate
from backend.ai_service.evaluation.scenarios import scenarios
from backend.ai_service.workflow import process_case


class EvaluationTests(unittest.TestCase):
    def test_catalog_passes_and_is_repeatable(self):
        first = evaluate()
        self.assertTrue(all(s['passed'] for s in first['scenarios']))
        self.assertEqual(first, evaluate())

    def test_wrong_payment_is_detected_even_with_correct_routing(self):
        def wrong_amount(request, emit):
            result = process_case(request, emit)
            action = result.proposed_action
            position = action.payload.financial_positions[0].model_copy(update={'amount_minor': 10000})
            payload = action.payload.model_copy(update={'financial_positions': (position,)})
            return result.model_copy(update={'proposed_action': action.model_copy(update={'payload': payload})})
        clear = next(s for s in scenarios() if s.id == 'clear')
        row = evaluate(wrong_amount, (clear,))['scenarios'][0]
        self.assertFalse(row['passed'])
        self.assertTrue(any('exact reimbursement' in c['name'] and not c['passed'] for c in row['checks']))

    def test_exception_does_not_hide_later_scenarios(self):
        def broken(request, emit):
            raise RuntimeError('injected')
        report = evaluate(broken)
        self.assertEqual(len(report['scenarios']), len(scenarios()))
        self.assertTrue(all(not s['passed'] for s in report['scenarios']))

    def test_comparison_reports_changes_regressions_and_removed_coverage(self):
        old = evaluate()
        new = deepcopy(old)
        new['scenarios'][0]['passed'] = False
        new['scenarios'][1]['stages'][0]['result']['proposedAction']['payload']['replyDe'] = 'Changed wording'
        removed = new['scenarios'].pop()
        added = deepcopy(removed)
        added['id'] = 'new_case'
        new['scenarios'].append(added)
        states = {c['id']: c['state'] for c in compare(new, old)}
        self.assertEqual(states['evidence_loop'], 'regressed')
        self.assertEqual(states['clear'], 'changed')
        self.assertEqual(states[removed['id']], 'removed')
        self.assertEqual(states['new_case'], 'added')
        self.assertTrue(all(c['state'] == 'unchanged' for c in compare(old, old)))
        with self.assertRaises(ValueError):
            compare(old, {'schemaVersion': 99})

    def test_report_is_self_contained_and_escapes_script_content(self):
        report = evaluate()
        report['metadata'] = dict(label='</script><script>alert(1)</script>', revision='test', dirty=True, generatedAt='fixed')
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            write_artifacts(report, output)
            page = (output / 'index.html').read_text()
            self.assertNotIn(report['metadata']['label'], page)
            self.assertNotIn('__REPORT_DATA__', page)
            embedded = page.split('type="application/json">')[1].split('</script>')[0]
            self.assertEqual(json.loads(embedded), report)
            self.assertEqual(json.loads((output / 'results.json').read_text()), report)
            self.assertIn('19/19', (output / 'summary.md').read_text())
            import xml.etree.ElementTree as ET
            ET.parse(output / 'overview.svg')


if __name__ == '__main__':
    unittest.main()
