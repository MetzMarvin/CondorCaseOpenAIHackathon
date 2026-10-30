import unittest
from types import SimpleNamespace

from backend.ai_service.legal_search import issue_queries, search_issues
from backend.ai_service.evaluation.legal_retrieval import evaluate


def hit(source, identity, text='text'):
    return SimpleNamespace(chunk=SimpleNamespace(source_id=source, version='v1', chunk_id=identity, text=text))


class LegalSearchTests(unittest.TestCase):
    def test_mixed_complaint_expands_independent_issues(self):
        queries = issue_queries('Flight cancelled and my wheelchair was damaged with my checked bag.')
        self.assertTrue(any('Article 5' in q for q in queries))
        self.assertTrue(any('Article 31' in q for q in queries))
        self.assertTrue(any('1107/2006' in q for q in queries))
        self.assertEqual(len(queries), len(set(queries)))

    def test_bounded_unique_results_and_primary_source_queries(self):
        calls = []
        class Rag:
            def search(self, query, **kwargs):
                calls.append(kwargs)
                return [hit('eu261', 'same'), hit('eu261', 'other')]
        results = search_issues(Rag(), 'Cancelled flight', limit=1)
        self.assertEqual(len(results), 1)
        self.assertTrue(any(c.get('source_ids') == ('eu261',) for c in calls))
        self.assertTrue(all(c['kind'] == 'legal' for c in calls))
        self.assertEqual(len(search_issues(Rag(), 'Cancelled flight', limit=20)), 2)

    def test_unknown_topic_uses_original_and_errors_propagate(self):
        self.assertEqual(issue_queries('A question about my invoice'), ['A question about my invoice'])
        class Broken:
            def search(self, *args, **kwargs):
                raise RuntimeError('unavailable')
        with self.assertRaisesRegex(RuntimeError, 'unavailable'):
            search_issues(Broken(), 'bag delayed')
        for text in ('', ' ' * 5, 'a' * 6001):
            with self.assertRaises(ValueError):
                issue_queries(text)

    def test_benchmark_requires_source_and_passage_not_just_document(self):
        class Rag:
            collection = 'test'
            def search(self, *args, **kwargs):
                return [hit('wrong', '1', 'target phrase'), hit('right', '2', 'different')]
        result = evaluate(Rag(), [dict(id='x', query='invoice', checks=[dict(
            issue='x', source_id='right', anchor='target phrase')])])
        self.assertEqual(result['coverage'], dict(baseline=0, expanded=0))
