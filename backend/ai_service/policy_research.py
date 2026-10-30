"""Opt-in draft policy preparation and case-topic research; no decision authority."""
import argparse
import hashlib
import json
from pathlib import Path

from backend.contracts import CaseSnapshot
from .rag import KnowledgeChunk, KnowledgeRag, PolicyProvenance
from .settings import ROOT


ISSUE_QUERIES = {
    'expense_reimbursement': 'reasonable expense reimbursement receipts meals hotel transport right to care',
    'flight_delay': 'flight arrival delay compensation right to care extraordinary circumstances',
    'flight_cancellation': 'flight cancellation reimbursement rerouting compensation notice exceptions',
    'denied_boarding': 'involuntary denied boarding compensation assistance exceptions',
    'baggage_delay': 'delayed baggage essential purchases receipts written complaint deadlines',
    'baggage_damage': 'damaged baggage written complaint deadlines evidence repair',
    'baggage_loss': 'lost baggage proof of loss liability limits written complaint',
    'accessibility_failure': 'reduced mobility accessibility assistance obligations',
    'service_complaint': 'service complaint evidence customer response escalation',
    'safety_incident': 'safety incident specialist escalation urgent assistance',
    'serious_injury': 'passenger injury specialist escalation urgent assistance',
    'discrimination': 'discrimination complaint specialist escalation',
}


def prepare_policy(path: Path, *, allow_draft: bool = False) -> list[KnowledgeChunk]:
    """Validate record hashes and preserve complete rule records without approving them."""
    records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    chunks, seen, releases = [], set(), set()
    for record in records:
        payload = {key: value for key, value in record.items() if key != 'content_sha256'}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                           separators=(',', ':')).encode()).hexdigest()
        if digest != record.get('content_sha256'):
            raise ValueError('Policy record content hash mismatch')
        if record.get('status') != 'draft_review_required' or not allow_draft:
            raise ValueError('This research importer requires draft_review_required records and explicit --allow-draft')
        if record.get('language') != 'en' or record.get('record_type') != 'rule':
            raise ValueError('Only English rule records are supported')
        identity = (record['policy_id'], record['policy_version'], record['rule_id'])
        if identity in seen:
            raise ValueError('Duplicate policy rule')
        seen.add(identity)
        releases.add(identity[:2])
        chunks.append(KnowledgeChunk(
            source_id=record['policy_id'], version=record['policy_version'],
            chunk_id=record['chunk_id'], title=record['rule']['title'], kind='policy',
            source_uri=f"policy:{record['policy_id']}/{record['policy_version']}#{record['rule_id']}",
            text=record['text'], policy_provenance=PolicyProvenance(source_record=record),
        ))
    if len(releases) != 1:
        raise ValueError('Import exactly one complete policy release at a time')
    for record in records:
        dependencies = record['mandatory_rule_ids'] + record['related_rule_ids']
        if any((record['policy_id'], record['policy_version'], rule) not in seen for rule in dependencies):
            raise ValueError('Policy release has missing mandatory or related rules')
    return chunks


def research_queries(snapshot: CaseSnapshot) -> tuple[str, ...]:
    """Use allowlisted issue topics only; no identities, raw prose or assumed applicability."""
    return tuple(dict.fromkeys(ISSUE_QUERIES[issue] for issue in snapshot.issues if issue in ISSUE_QUERIES))


def research_case(snapshot: CaseSnapshot, rag: KnowledgeRag, *, limit: int = 5):
    """Return cited research candidates; never a proposed action or entitlement decision."""
    queries = research_queries(snapshot)
    results = [{'query': query, 'hits': [hit.model_dump() for hit in rag.search(query, limit=limit)]}
               for query in queries]
    return {'purpose': 'research_only', 'runtime_enabled': False,
            'applicability_checked': False, 'mandatory_support_expanded': False,
            'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'docs/policies/customer-service/rag.jsonl')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/processed/policy-research.jsonl')
    parser.add_argument('--allow-draft', action='store_true', help='Explicitly prepare draft research records')
    args = parser.parse_args()
    chunks = prepare_policy(args.source, allow_draft=args.allow_draft)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(''.join(chunk.model_dump_json() + '\n' for chunk in chunks), encoding='utf-8')
    print(json.dumps({'output': str(args.output), 'chunks': len(chunks), 'runtime_enabled': False}))


if __name__ == '__main__':
    main()
