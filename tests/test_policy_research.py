import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from backend.ai_service.fixtures import demo_request
from backend.ai_service.policy_research import prepare_policy, research_case, research_queries
from backend.ai_service.rag import KnowledgeChunk, SearchHit
from backend.contracts import Fact, SourceRef


def record(rule_id='RULE-1', mandatory=None):
    value = dict(policy_id='DEMO-POLICY', policy_version='0.1', rule_id=rule_id,
                 chunk_id='DEMO-POLICY:0.1:' + rule_id, status='draft_review_required',
                 language='en', record_type='rule', rule={'title': 'Synthetic rule'},
                 text='Synthetic policy for test research.',
                 mandatory_rule_ids=mandatory or [], related_rule_ids=[],
                 legal_profile={'event_date_from': '2026-01-01'},
                 jurisdiction_scope=['demo only'])
    value['content_sha256'] = hashlib.sha256(json.dumps(value, sort_keys=True,
        ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    return value


class PolicyResearchTests(unittest.TestCase):
    def prepare(self, records, **kwargs):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'rag.jsonl'
            path.write_text('\n'.join(json.dumps(r) for r in records), encoding='utf-8')
            return prepare_policy(path, **kwargs)

    def test_explicit_draft_opt_in_and_complete_metadata_roundtrip(self):
        row = record()
        with self.assertRaisesRegex(ValueError, 'explicit'):
            self.prepare([row])
        chunks = self.prepare([row], allow_draft=True)
        chunk = KnowledgeChunk.model_validate_json(chunks[0].model_dump_json())
        self.assertEqual(chunk.policy_provenance.source_record, row)
        self.assertFalse(chunk.policy_provenance.runtime_enabled)
        self.assertEqual(chunk.version, '0.1')

    def test_rejects_changed_content_and_incomplete_dependencies(self):
        row = record()
        row['text'] = 'Changed text'
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.prepare([row], allow_draft=True)
        with self.assertRaisesRegex(ValueError, 'missing mandatory'):
            self.prepare([record(mandatory=['MISSING'])], allow_draft=True)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.prepare([record(), record()], allow_draft=True)

    def test_case_queries_do_not_include_customer_values_and_results_are_research(self):
        snapshot = demo_request('clear').snapshot
        private = Fact(name='expense_purpose', value='PRIVATE-CUSTOMER-IDENTITY',
                       sources=(SourceRef(source_id='private-reference', version='1'),))
        snapshot = snapshot.model_copy(update={'known_facts': (private,),
            'issues': ('expense_reimbursement', 'PRIVATE-UNKNOWN-ISSUE')})
        queries = research_queries(snapshot)
        self.assertEqual(len(queries), 1)
        self.assertNotIn('PRIVATE', str(queries))
        chunk = self.prepare([record()], allow_draft=True)[0]
        class FakeRag:
            def search(self, query, limit):
                assert 'PRIVATE' not in query
                return [SearchHit(score=0.5, chunk=chunk)]
        before = snapshot.model_dump_json()
        result = research_case(snapshot, FakeRag())
        self.assertFalse(result['runtime_enabled'])
        self.assertFalse(result['applicability_checked'])
        self.assertFalse(result['mandatory_support_expanded'])
        self.assertEqual(result['results'][0]['hits'][0]['chunk']['version'], '0.1')
        self.assertEqual(snapshot.model_dump_json(), before)


if __name__ == '__main__':
    unittest.main()
