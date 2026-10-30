"""Live research retrieval benchmark; gold passages are not legal outcome labels."""
import argparse
import json
import re
from pathlib import Path

from ..legal_search import search_issues
from ..rag import KnowledgeRag
from ..settings import ROOT


def normalize(text):
    return re.sub(r'\s+', ' ', text).casefold()


def evaluate(rag, cases, limit=20):
    rows = []
    for case in cases:
        results = {'baseline': rag.search(case['query'], limit=limit, kind='legal'),
                   'expanded': search_issues(rag, case['query'], limit=limit)}
        row = {'id': case['id'], 'checks': [], 'passages': {}}
        for mode, hits in results.items():
            row['passages'][mode] = [dict(source_id=h.chunk.source_id,
                version=h.chunk.version, chunk_id=h.chunk.chunk_id) for h in hits]
        for check in case['checks']:
            record = dict(check)
            for mode, hits in results.items():
                record[mode] = any(h.chunk.source_id == check['source_id'] and
                    normalize(check['anchor']) in normalize(h.chunk.text) for h in hits)
            row['checks'].append(record)
        rows.append(row)
    checks = [c for r in rows for c in r['checks']]
    return {'mode': 'live-research-retrieval', 'collection': rag.collection,
            'passage_budget': limit, 'total_checks': len(checks),
            'coverage': {mode: sum(c[mode] for c in checks) / len(checks)
                         for mode in ('baseline', 'expanded')}, 'cases': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, default=ROOT / 'data/examples/legal-checks/evaluation/retrieval.jsonl')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=20)
    args = parser.parse_args()
    cases = [json.loads(line) for line in args.cases.read_text().splitlines() if line.strip()]
    rag = KnowledgeRag(collection='legal_research')
    try:
        result = evaluate(rag, cases, args.limit)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({k: v for k, v in result.items() if k != 'cases'}))
    finally:
        rag.client.close()


if __name__ == '__main__':
    main()
