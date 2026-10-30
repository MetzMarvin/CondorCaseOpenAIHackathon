"""Knowledge registry public boundary behavior."""
import unittest

from backend.ai_service.knowledge import bundled_registry


class RegistryTests(unittest.TestCase):
    def test_bundled_policy_is_explicitly_synthetic_version_two(self):
        registry = bundled_registry()
        card = registry.get('demo-expense-policy', '2')
        self.assertEqual(card.source_kind, 'demo_assumption')
        self.assertEqual(card.approval_state, 'DEMO_APPROVED')
        self.assertTrue(card.approved_for_event(None))
        self.assertEqual({p.role for p in card.passages}, {'RULE', 'PREREQUISITE', 'EXCEPTION'})
        self.assertEqual(len(card.content_hash), 64)

    def test_corrupt_content_and_duplicate_versions_are_rejected(self):
        from backend.ai_service.knowledge import KnowledgeRegistry
        data = bundled_registry().model_dump(mode='json')
        data['cards'][0]['passages'][0]['text'] = 'Pay everyone.'
        with self.assertRaises(ValueError):
            KnowledgeRegistry.model_validate(data)
        data = bundled_registry().model_dump(mode='json')
        data['cards'].append(data['cards'][0])
        with self.assertRaises(ValueError):
            KnowledgeRegistry.model_validate(data)

    def card_with(self, **updates):
        from backend.ai_service.knowledge import KnowledgeCard, card_content_hash
        data = bundled_registry().cards[0].model_dump(mode='json')
        data.update(updates)
        data['content_hash'] = card_content_hash(data)
        return KnowledgeCard.model_validate(data)

    def test_dates_use_event_time_start_inclusive_end_exclusive(self):
        from datetime import date
        card = self.card_with(universal=False, effective_from='2025-01-01', effective_until='2026-01-01')
        self.assertFalse(card.approved_for_event(None))
        self.assertFalse(card.approved_for_event(date(2024, 12, 31)))
        self.assertTrue(card.approved_for_event(date(2025, 1, 1)))
        self.assertTrue(card.approved_for_event(date(2025, 12, 31)))
        self.assertFalse(card.approved_for_event(date(2026, 1, 1)))
        with self.assertRaises(ValueError):
            self.card_with(universal=False, effective_from='2026-01-01', effective_until='2026-01-01')

    def test_approval_cannot_turn_demo_assumptions_into_production_rules(self):
        for state in ('DRAFT', 'WITHDRAWN'):
            self.assertFalse(self.card_with(approval_state=state).approved_for_event(None))
        for updates in (dict(approval_state='APPROVED'), dict(source_kind='legal_rule'),
                        dict(universal=True, effective_from='2025-01-01'),
                        dict(source_kind='company_policy', approval_state='APPROVED')):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                self.card_with(**updates)
        from datetime import date
        legal = self.card_with(source_kind='legal_rule', approval_state='APPROVED', universal=False)
        self.assertFalse(legal.approved_for_event(None))
        self.assertTrue(legal.approved_for_event(date(2026, 1, 1)))

    def test_registry_rejects_missing_dependency_passages_and_duplicate_passage_ids(self):
        from backend.ai_service.knowledge import KnowledgeRegistry
        card = self.card_with(dependencies=[dict(source_id='missing', version='2', passage_id='exception')])
        with self.assertRaises(ValueError):
            KnowledgeRegistry(schema_version=1, cards=(card,))
        card = self.card_with(dependencies=[dict(source_id='demo-expense-policy', version='2', passage_id='missing')])
        with self.assertRaises(ValueError):
            KnowledgeRegistry(schema_version=1, cards=(card,))
        passages = bundled_registry().cards[0].model_dump(mode='json')['passages']
        with self.assertRaises(ValueError):
            self.card_with(passages=passages + [passages[0]])

    def test_rule_decisions_are_paired_and_not_attached_to_support_passages(self):
        passages = bundled_registry().cards[0].model_dump(mode='json')['passages']
        for updates in (dict(decision=None), dict(rule_key=None), dict(role='EXCEPTION'), dict(rule_key='')):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                self.card_with(passages=[{**passages[0], **updates}, *passages[1:]])

    def test_loader_rejects_corrupt_json_and_unknown_fields(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from backend.ai_service.knowledge import KnowledgeRegistry
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'broken.json'
            path.write_text('{broken')
            with self.assertRaises(ValueError):
                KnowledgeRegistry.load(path)
            with self.assertRaises(OSError):
                KnowledgeRegistry.load(Path(directory) / 'absent.json')
        with self.assertRaises(ValueError):
            self.card_with(unknown_field='not silently accepted')

    def test_different_versions_and_cross_card_dependencies_remain_addressable(self):
        from backend.ai_service.knowledge import KnowledgeRegistry
        first = bundled_registry().cards[0]
        second = self.card_with(version='3', approval_state='DRAFT')
        registry = KnowledgeRegistry(schema_version=1, cards=(first, second))
        self.assertEqual(registry.get('demo-expense-policy', '3').approval_state, 'DRAFT')
        self.assertEqual(registry.get('demo-expense-policy', '2').approval_state, 'DEMO_APPROVED')
        with self.assertRaises(KeyError):
            registry.get('demo-expense-policy', '4')
