"""Versioned local knowledge, independent of customer evidence and shared contracts."""
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)


class Applicability(Record):
    fact_name: str = Field(min_length=1)
    allowed_values: tuple[str, ...] = Field(min_length=1)


class Passage(Record):
    passage_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    role: Literal['RULE', 'PREREQUISITE', 'EXCEPTION']
    rule_key: str | None = Field(default=None, min_length=1)
    decision: str | None = Field(default=None, min_length=1)

    @model_validator(mode='after')
    def validate_decision(self):
        if (self.rule_key is None) != (self.decision is None):
            raise ValueError('Rule key and decision must be paired.')
        if self.rule_key is not None and self.role != 'RULE':
            raise ValueError('Only rule passages carry decisions.')
        return self


class Dependency(Record):
    source_id: str
    version: str
    passage_id: str


class KnowledgeCard(Record):
    source_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_location: str = Field(min_length=1)
    source_kind: Literal['demo_assumption', 'company_policy', 'legal_rule']
    issue_tags: tuple[str, ...] = Field(min_length=1)
    applicability: tuple[Applicability, ...] = ()
    effective_from: date | None = None
    effective_until: date | None = None
    retrieved_on: date
    universal: bool = False
    approval_state: Literal['DEMO_APPROVED', 'APPROVED', 'DRAFT', 'WITHDRAWN']
    content_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    text: str = Field(min_length=1)
    passages: tuple[Passage, ...] = Field(min_length=1)
    dependencies: tuple[Dependency, ...] = ()

    @model_validator(mode='after')
    def validate_integrity(self):
        passage_ids = [passage.passage_id for passage in self.passages]
        if len(passage_ids) != len(set(passage_ids)):
            raise ValueError('Duplicate passage ID.')
        synthetic = self.source_kind == 'demo_assumption'
        if (synthetic and self.approval_state == 'APPROVED') or (not synthetic and self.approval_state == 'DEMO_APPROVED'):
            raise ValueError('Synthetic and production approval are distinct.')
        if self.universal and (not synthetic or self.effective_from or self.effective_until or self.applicability):
            raise ValueError('Only undated unrestricted synthetic assumptions can be universal.')
        if self.effective_from and self.effective_until and self.effective_from >= self.effective_until:
            raise ValueError('Effective interval must have positive duration.')
        if self.content_hash != card_content_hash(self):
            raise ValueError('Knowledge card content hash mismatch.')
        return self

    def approved_for_event(self, event_date: date | None) -> bool:
        """Approval and interval gate only; callers must also check applicability."""
        approved = 'DEMO_APPROVED' if self.source_kind == 'demo_assumption' else 'APPROVED'
        if self.approval_state != approved:
            return False
        if event_date is None:
            return self.universal
        return ((self.effective_from is None or event_date >= self.effective_from)
                and (self.effective_until is None or event_date < self.effective_until))


class KnowledgeRegistry(Record):
    schema_version: Literal[1]
    cards: tuple[KnowledgeCard, ...]

    @model_validator(mode='after')
    def validate_registry(self):
        keys = [(card.source_id, card.version) for card in self.cards]
        if len(keys) != len(set(keys)):
            raise ValueError('Duplicate knowledge source version.')
        passage_keys = {(card.source_id, card.version, passage.passage_id)
                        for card in self.cards for passage in card.passages}
        for card in self.cards:
            for dependency in card.dependencies:
                if (dependency.source_id, dependency.version, dependency.passage_id) not in passage_keys:
                    raise ValueError('Required knowledge dependency is missing.')
        return self

    @classmethod
    def load(cls, path: str | Path) -> 'KnowledgeRegistry':
        return cls.model_validate_json(Path(path).read_text(encoding='utf-8'))

    def get(self, source_id: str, version: str) -> KnowledgeCard:
        for card in self.cards:
            if (card.source_id, card.version) == (source_id, version):
                return card
        raise KeyError((source_id, version))


def card_content_hash(card: KnowledgeCard | dict) -> str:
    """SHA-256 of normalized JSON excluding only the content_hash field."""
    if isinstance(card, KnowledgeCard):
        card = card.model_dump(mode='json')
    payload = {key: value for key, value in card.items() if key != 'content_hash'}
    return sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()


def bundled_registry() -> KnowledgeRegistry:
    return KnowledgeRegistry.load(Path(__file__).with_name('knowledge_data') / 'demo.json')
