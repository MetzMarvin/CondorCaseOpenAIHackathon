"""Build offline snapshots/evidence from the authored legal complaint catalogue."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.contracts import (
    AttachmentRef, CaseSnapshot, Fact, FinancialLimit, Message, Owner,
    RunRequest, SourceRef,
)


def main():
    runtime = ROOT / 'data/examples/legal-checks/runtime'
    cases = [json.loads(line) for line in (runtime / 'complaints.jsonl').read_text().splitlines()]
    requests, index = [], []
    evidence_directory = runtime / 'evidence'
    evidence_directory.mkdir(exist_ok=True)
    for row in cases:
        cid = row['id']
        references, contexts = [], {}
        for key, value in row['internal_evidence'].items():
            eid = f'{cid}-{key}'
            filename = f'{eid}.txt'
            (evidence_directory / filename).write_text(
                f'SYNTHETIC DEMO RECORD — NOT A REAL DOCUMENT\nCase: {cid}\nRecord: {key}\n\n{value}\n'
            )
            reference = AttachmentRef(attachment_id=eid, filename=filename,
                media_type='text/plain', local_reference=f'{cid}:evidence:{key}')
            references.append(reference)
            contexts[key] = Fact(name=f'{key}_record', value=value,
                sources=(SourceRef(source_id=eid, version='1'),))
            index.append({'case_id': cid, 'local_reference': reference.local_reference,
                'path': f'evidence/{filename}'})
        (runtime / f'{cid}-email.txt').write_text(
            f'Subject: {row["subject"]}\n\n{row["customer_email"]}\n'
        )
        facts = tuple(Fact(name=name, value=value,
            sources=(SourceRef(source_id=f'{cid}-snapshot_facts', version='1'),))
            for name, value in row['snapshot_facts'].items())
        snapshot = CaseSnapshot(status='IN_PROGRESS', owner=Owner(type='AI', id='demo-ai'),
            language='en', messages=(Message(message_id=f'{cid}-message-1', channel='email',
                sender=f'{cid.lower()}@example.com', body=row['customer_email'],
                timestamp=row['received_at']),), attachments=tuple(references), known_facts=facts,
            issues=tuple(row['issues']), missing_information=(),
            customer_context=(Fact(name='synthetic', value=True,
                sources=(SourceRef(source_id=f'{cid}-booking', version='1'),)),),
            booking_context=(contexts['booking'],),
            flight_context=tuple(v for k, v in contexts.items() if k not in {'booking', 'snapshot_facts'}),
            permitted_actions=('REQUEST_INFORMATION', 'RESOLVE', 'HANDOFF'),
            financial_limits=(FinancialLimit(type='REIMBURSEMENT', maximum_minor=20000, currency='EUR'),))
        requests.append(RunRequest(run_id=f'{cid}-run-1', case_id=cid, case_version=1,
            trigger='manual_process', snapshot=snapshot))
    (runtime / 'run_requests.jsonl').write_text(
        ''.join(request.model_dump_json(by_alias=True) + '\n' for request in requests))
    (runtime / 'evidence_index.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in index))
    print(f'Built {len(requests)} legal case snapshots and {len(index)} evidence records.')


if __name__ == '__main__':
    main()
