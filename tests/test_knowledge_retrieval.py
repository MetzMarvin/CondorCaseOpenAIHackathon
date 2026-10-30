import unittest
from backend.ai_service.knowledge import KnowledgeCard, KnowledgeRegistry, bundled_registry, card_content_hash
from backend.ai_service.retrieval import RetrievalQuery, retrieve


def card(**updates):
    data = bundled_registry().cards[0].model_dump(mode='json')
    data.update(updates)
    data['passages'] = [dict(rule_key=None, decision=None, **{k: v for k, v in p.items() if k not in ('rule_key', 'decision')}) | {k: v for k, v in p.items() if k in ('rule_key', 'decision')} for p in data['passages']]
    data['content_hash'] = card_content_hash(data)
    return KnowledgeCard.model_validate(data)


def registry(*cards):
    return lambda: KnowledgeRegistry(schema_version=1, cards=cards)


class RetrievalTests(unittest.TestCase):
    def test_default_undated_policy_keeps_mandatory_support_despite_rank_budget(self):
        result = retrieve(RetrievalQuery(issue_tags=('expense_reimbursement',), max_rules=1))
        self.assertEqual(result.status, 'SUPPORTED')
        self.assertEqual({p.passage_id for p in result.passages}, {'expense-rule', 'expense-prerequisites', 'expense-exceptions'})
        self.assertTrue(all(p.version == '2' and p.rationale for p in result.passages))

    def test_filter_approval_issue_date_regime_before_ranking_and_report_unknowns(self):
        from datetime import date
        query = RetrievalQuery(issue_tags=('expense_reimbursement',), event_date=date(2026, 6, 1), applicability_facts={'regime': 'EU'})
        variants = [dict(approval_state='DRAFT'), dict(issue_tags=['other']),
                    dict(universal=False, effective_until='2026-01-01'),
                    dict(universal=False, effective_from='2027-01-01'),
                    dict(universal=False, applicability=[dict(fact_name='regime', allowed_values=['US'])])]
        for updates in variants:
            with self.subTest(updates=updates):
                result = retrieve(query, registry(card(**updates)))
                self.assertEqual(result.status, 'UNSUPPORTED')
                self.assertEqual(result.passages, ())
        restricted = card(universal=False, applicability=[dict(fact_name='regime', allowed_values=['EU'])])
        result = retrieve(RetrievalQuery(issue_tags=query.issue_tags), registry(restricted))
        self.assertEqual(result.status, 'APPLICABILITY_GAP')
        self.assertEqual(result.gaps, ('event_date', 'regime'))
        self.assertEqual(result.passages, ())

    def test_contradiction_cannot_be_hidden_by_rank_limit(self):
        passages = bundled_registry().cards[0].model_dump(mode='json')['passages']
        passages[0]['decision'] = 'unsupported'
        conflicting = card(source_id='opposing', passages=passages, dependencies=[])
        result = retrieve(RetrievalQuery(issue_tags=('expense_reimbursement',), max_rules=1), registry(card(), conflicting))
        self.assertEqual(result.status, 'UNCLEAR_RULE')
        self.assertIn('expense_reimbursement', result.reason)
        self.assertEqual(result.passages, ())

    def test_cross_card_support_is_transitive_and_ineligible_exception_blocks_resolution(self):
        prerequisite = card(source_id='prerequisite', passages=[dict(passage_id='needed', text='Required supporting condition.', role='PREREQUISITE')], dependencies=[dict(source_id='exception', version='2', passage_id='stop')])
        exception = card(source_id='exception', passages=[dict(passage_id='stop', text='Do not pay twice.', role='EXCEPTION')], dependencies=[dict(source_id='prerequisite', version='2', passage_id='needed')])
        root = card(dependencies=[dict(source_id='prerequisite', version='2', passage_id='needed')])
        query = RetrievalQuery(issue_tags=('expense_reimbursement',), max_rules=1)
        result = retrieve(query, registry(root, prerequisite, exception))
        self.assertEqual(result.status, 'SUPPORTED')
        self.assertTrue({'needed', 'stop'}.issubset({p.passage_id for p in result.passages}))
        blocked = card(**{**exception.model_dump(mode='json'), 'approval_state': 'WITHDRAWN'})
        result = retrieve(query, registry(root, prerequisite, blocked))
        self.assertEqual(result.status, 'UNCLEAR_RULE')
        self.assertEqual(result.passages, ())

    def test_lexical_rank_and_ties_are_deterministic_across_registry_order(self):
        one = card(source_id='a', dependencies=[], passages=[dict(passage_id='rule', text='Hotel accommodation expenses.', role='RULE')])
        two = card(source_id='b', dependencies=[], passages=[dict(passage_id='rule', text='Meal food expenses.', role='RULE')])
        for cards in ((one, two), (two, one)):
            result = retrieve(RetrievalQuery(issue_tags=('expense_reimbursement',), text='meal', max_rules=1), registry(*cards))
            self.assertEqual([p.source_id for p in result.passages], ['b'])
            result = retrieve(RetrievalQuery(issue_tags=('expense_reimbursement',), max_rules=1), registry(*cards))
            self.assertEqual([p.source_id for p in result.passages], ['a'])

    def test_infrastructure_errors_and_required_support_overflow_fail_without_passages(self):
        def unavailable():
            raise OSError('secret private storage path')
        query = RetrievalQuery(issue_tags=('expense_reimbursement',))
        result = retrieve(query, unavailable)
        self.assertEqual((result.status, result.error_code), ('FAILED', 'KNOWLEDGE_UNAVAILABLE'))
        self.assertNotIn('secret', result.model_dump_json())
        result = retrieve(query.model_copy(update={'max_characters': 10}))
        self.assertEqual((result.status, result.error_code), ('FAILED', 'KNOWLEDGE_BUDGET_EXCEEDED'))
        self.assertEqual(result.passages, ())
        corrupt = card(dependencies=[dict(source_id='absent', version='2', passage_id='missing')])
        result = retrieve(query, registry(corrupt))
        self.assertEqual((result.status, result.error_code), ('FAILED', 'KNOWLEDGE_UNAVAILABLE'))

    def test_expired_and_wrong_regime_dependencies_never_reach_context(self):
        from datetime import date
        root = card(dependencies=[dict(source_id='exception', version='2', passage_id='stop')])
        query = RetrievalQuery(issue_tags=('expense_reimbursement',), event_date=date(2026, 6, 1), applicability_facts={'regime': 'EU'})
        for updates in (dict(universal=False, effective_until='2026-01-01'),
                        dict(universal=False, applicability=[dict(fact_name='regime', allowed_values=['US'])])):
            exception = card(source_id='exception', passages=[dict(passage_id='stop', text='Mandatory exception.', role='EXCEPTION')], dependencies=[], **updates)
            result = retrieve(query, registry(root, exception))
            self.assertEqual(result.status, 'UNCLEAR_RULE')
            self.assertEqual(result.passages, ())
