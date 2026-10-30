"""Validate and run synthetic legal cases; does not assert legal correctness."""
import json
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.contracts import RunRequest, SourceRef
from backend.ai_service.evidence import (
    AttachmentResult, EvidenceScope, FakeAttachmentReader, FakeRecordReader,
    create_evidence_adapters,
)
from backend.ai_service.workflow import create_processor


def main():
    directory = ROOT / 'data/examples/legal-checks'
    runtime = directory / 'runtime'
    cases = [json.loads(line) for line in (runtime / 'complaints.jsonl').read_text().splitlines()]
    expectations = [json.loads(line) for line in (directory / 'evaluation/expectations.jsonl').read_text().splitlines()]
    requests = [RunRequest.model_validate_json(line)
        for line in (runtime / 'run_requests.jsonl').read_text().splitlines()]
    ids = {f'LEGAL-{number:03}' for number in range(1, 21)}
    if not (len(cases) == len(expectations) == len(requests) == 20
            and {row['id'] for row in cases} == ids
            and {row['case_id'] for row in expectations} == ids
            and {request.case_id for request in requests} == ids):
        raise ValueError('Expected exactly 20 distinct matching cases, snapshots and expectations')
    for row, expected, request in zip(cases, expectations, requests):
        if row['id'] != expected['case_id'] or row['id'] != request.case_id:
            raise ValueError('Catalogue order differs from snapshots or expectations')
        if (not row['synthetic'] or row['language'] != 'en'
                or request.snapshot.messages[0].body != row['customer_email']
                or tuple(row['issues']) != request.snapshot.issues):
            raise ValueError('Snapshot must preserve the authored synthetic English complaint')
        if 'simulated_followup' in row or 'expected_checks' in row:
            raise ValueError('Evaluation content must stay outside runtime complaints')
        if not expected['sources'] or not expected['expected_checks'] or not expected['failure_signals']:
            raise ValueError('Each case needs independent legal review criteria and sources')
    index = {
        (row['case_id'], row['local_reference']): row['path']
        for row in map(json.loads, (runtime / 'evidence_index.jsonl').read_text().splitlines())
    }
    results = []
    failed = False
    for request in requests:
        attachments = []
        for reference in request.snapshot.attachments:
            path = (runtime / index[request.case_id, reference.local_reference]).resolve()
            if not path.is_relative_to((runtime / 'evidence').resolve()):
                raise ValueError('Evidence path must remain inside the fixture directory')
            content = path.read_bytes()
            attachments.append(AttachmentResult(
                scope=EvidenceScope(case_id=request.case_id, case_version=request.case_version),
                reference=reference, status='found', content=content,
                source=SourceRef(source_id=reference.attachment_id, version='1'),
                content_hash=sha256(content).hexdigest(),
                observed_at=request.snapshot.messages[0].timestamp,
            ))
        adapters = create_evidence_adapters(
            crm=FakeRecordReader({}), operational=FakeRecordReader({}),
            attachments=FakeAttachmentReader(tuple(attachments)),
        )
        result = create_processor(adapters=adapters)(request, lambda _: None)
        failed |= result.status == 'FAILED'
        results.append(result.model_dump_json(by_alias=True))
        outcome = result.proposed_action.type if result.proposed_action else result.technical_error.code
        print(f'{request.case_id}: {result.status} / {outcome}')
    (directory / 'evaluation/offline_results.jsonl').write_text('\n'.join(results) + '\n')
    if failed:
        raise SystemExit('One or more offline runs failed; see evaluation/offline_results.jsonl')
    print('20 fixtures validated and executed. Legal acceptance criteria were not automatically scored.')


if __name__ == '__main__':
    main()
