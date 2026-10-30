"""Deterministic approved-knowledge retrieval; never ingests customer documents."""
from collections.abc import Callable
from datetime import date
import re
from typing import Literal

from pydantic import Field

from .knowledge import KnowledgeRegistry, Record, bundled_registry


class RetrievalQuery(Record):
    issue_tags: tuple[str, ...]
    text: str = ''
    event_date: date | None = None
    applicability_facts: dict[str, str] = Field(default_factory=dict)
    max_rules: int = Field(default=8, ge=1)
    max_characters: int = Field(default=16000, ge=1)


class SelectedPassage(Record):
    source_id: str
    version: str
    passage_id: str
    text: str
    role: Literal['RULE', 'PREREQUISITE', 'EXCEPTION']
    rule_key: str | None
    decision: str | None
    content_hash: str
    source_kind: str
    rationale: str


class RetrievalResult(Record):
    status: Literal['SUPPORTED', 'APPLICABILITY_GAP', 'UNSUPPORTED', 'UNCLEAR_RULE', 'FAILED']
    passages: tuple[SelectedPassage, ...] = ()
    gaps: tuple[str, ...] = ()
    reason: str
    error_code: str | None = None


def retrieve(query: RetrievalQuery, registry_loader: Callable[[], KnowledgeRegistry] = bundled_registry) -> RetrievalResult:
    try:
        registry = registry_loader()
    except Exception:
        return RetrievalResult(status='FAILED', error_code='KNOWLEDGE_UNAVAILABLE', reason='Approved knowledge could not be loaded or validated.')
    selected = {}
    eligible = []
    gaps = set()
    for c in registry.cards:
        relevant, missing = _applicability(c, query)
        if relevant:
            gaps.update(missing)
            if not missing:
                eligible.append(c)
    if gaps:
        return RetrievalResult(status='APPLICABILITY_GAP', gaps=tuple(sorted(gaps)), reason='Establish applicability facts before selecting knowledge.')
    rules = [(c, p) for c in eligible for p in c.passages if p.role == 'RULE']
    decisions = {}
    for _, passage in rules:
        if passage.rule_key:
            decisions.setdefault(passage.rule_key, set()).add(passage.decision)
    conflicts = sorted(key for key, values in decisions.items() if len(values) > 1)
    if conflicts:
        return RetrievalResult(status='UNCLEAR_RULE', reason='Conflicting applicable decisions: ' + ', '.join(conflicts))
    terms = set(re.findall(r'\w+', query.text.casefold()))
    def rank(pair):
        card, passage = pair
        score = len(terms.intersection(re.findall(r'\w+', passage.text.casefold())))
        return (-score, card.source_id, card.version, passage.passage_id)
    rules = sorted(rules, key=rank)[:query.max_rules]
    if not rules:
        return RetrievalResult(status='UNSUPPORTED', reason='No approved applicable rule supports these issues.')
    pending = [(c, p, 'Approved issue/date/applicability match; lexical overlap ' + str(-rank((c, p))[0]) + '; stable source/version/passage tie-break.') for c, p in rules]
    while pending:
        card, item, rationale = pending.pop(0)
        key = (card.source_id, card.version, item.passage_id)
        if key in selected:
            continue
        relevant, missing = _applicability(card, query)
        if missing:
            return RetrievalResult(status='APPLICABILITY_GAP', gaps=tuple(sorted(missing)), reason='Required support has unknown applicability.')
        if not relevant:
            return RetrievalResult(status='UNCLEAR_RULE', reason='Required support is not approved and applicable: ' + '/'.join(key))
        selected[key] = SelectedPassage(source_id=card.source_id, version=card.version,
            content_hash=card.content_hash, source_kind=card.source_kind,
            rationale=rationale, **item.model_dump())
        pending.extend((card, p, 'Mandatory prerequisite or exception for ' + card.source_id)
                       for p in card.passages if p.role != 'RULE')
        for dependency in card.dependencies:
            support_card = registry.get(dependency.source_id, dependency.version)
            support = next(p for p in support_card.passages if p.passage_id == dependency.passage_id)
            pending.append((support_card, support, 'Mandatory dependency of ' + card.source_id + '/' + card.version))
    if sum(len(p.text) for p in selected.values()) > query.max_characters:
        return RetrievalResult(status='FAILED', error_code='KNOWLEDGE_BUDGET_EXCEEDED', reason='Required knowledge and support exceed the passage budget.')
    return RetrievalResult(status='SUPPORTED', passages=tuple(selected.values()), reason='Applicable supported knowledge selected.')


def _applicability(card, query):
    if not set(card.issue_tags).intersection(query.issue_tags):
        return False, set()
    if card.approval_state not in ('APPROVED', 'DEMO_APPROVED'):
        return False, set()
    missing = set()
    if query.event_date is None and not card.universal:
        missing.add('event_date')
    elif not card.approved_for_event(query.event_date):
        return False, set()
    for condition in card.applicability:
        value = query.applicability_facts.get(condition.fact_name)
        if value is None:
            missing.add(condition.fact_name)
        elif value not in condition.allowed_values:
            return False, set()
    return True, missing
