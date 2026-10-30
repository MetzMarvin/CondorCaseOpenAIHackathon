"""Reproducible integration audit. Run only against disposable local demo servers.

Creates synthetic cases; never resets a server. Outputs expected versus observed
behavior, including known gaps. A nonzero exit means unmet expectations.
"""
import argparse
import json
from pathlib import Path
from uuid import uuid4

import httpx


def audit(operations_url, intake_url):
    results = []
    operations = httpx.Client(base_url=operations_url, timeout=30)
    intake = httpx.Client(base_url=intake_url, timeout=30)

    def record(name, expected, observed):
        results.append(dict(check=name, passed=observed == expected,
                            expected=expected, observed=observed))

    def submit(body, case_id=None, **extra):
        payload = dict(messageId=uuid4().hex, channel='EMAIL', sender='audit@example.com', body=body)
        if case_id:
            payload['caseId'] = case_id
        return operations.post('/api/inbound/messages', json={**payload, **extra})

    def process(case):
        response = operations.post(f"/api/cases/{case['caseId']}/process", json={
            'requestId': uuid4().hex, 'expectedCaseVersion': case['version']})
        response.raise_for_status()
        return response.json()

    # Both sides of the current integration boundary.
    portal_payload = dict(messageId=uuid4().hex, channel='PORTAL', sender='audit@example.com',
                          subject='Audit portal claim', body='Please review my delayed baggage.')
    record('portal payload accepted by operations API', 200,
           operations.post('/api/inbound/messages', json=portal_payload).status_code)
    receipt = intake.post('/api/inbound/messages', json=portal_payload)
    record('portal payload accepted by intake API', 200, receipt.status_code)
    cid = receipt.json()['caseId']
    record('portal case visible in operations store', 200, operations.get(f'/api/cases/{cid}').status_code)
    record('operations backend customer projection', 200,
           operations.get('/api/portal/cases/case-evidence').status_code)
    record('intake backend internal detail', 200, intake.get(f'/api/cases/{cid}').status_code)
    record('intake backend processing endpoint', 200, intake.post(f'/api/cases/{cid}/process',
           json={'requestId': uuid4().hex, 'expectedCaseVersion': 1}).status_code)
    record('operations reply payload accepted by intake', 200, intake.post('/api/inbound/messages',
           json=dict(messageId=uuid4().hex, caseId=cid, channel='EMAIL', sender='audit@example.com',
                     body='Here is my update.', attachmentIds=[])).status_code)
    projection = intake.get(f'/api/portal/cases/{cid}').json()
    record('portal projection excludes operational internals', [],
           sorted(set(projection) & {'owner', 'queue', 'history', 'assessment', 'runResults'}))
    record('intake preparation available', 200, intake.get(f'/api/cases/{cid}/preparation').status_code)
    record('identical portal submission returns same receipt', receipt.json(),
           intake.post('/api/inbound/messages', json=portal_payload).json())
    record('changed portal retry conflicts', 409, intake.post('/api/inbound/messages',
           json={**portal_payload, 'body': 'Changed message'}).status_code)

    # These new claims exercise the real parser instead of preclassified snapshots.
    case = submit('Please reimburse my meal expense of 42.00 EUR.').json()
    outcome = process(case)
    record('new supported expense resolves', 'RESOLVED', outcome['case']['status'])
    case = submit('I am angry. Please reimburse my meal expense of 42.00 EUR.').json()
    record('negative sentiment alone does not hand off', 'RESOLVE', process(case)['appliedAction']['type'])
    case = submit('There was an injury on board.').json()
    outcome = process(case)
    record('explicit new injury hands off', 'SERIOUS_ISSUE', outcome['appliedAction']['payload']['reasonCode'])
    reply = submit('Here is an additional detail.', case['caseId']).json()
    record('specialist reply preserves waiting status', 'WAITING_FOR_SPECIALIST', reply['status'])

    case = submit('Please reimburse my meal.').json()
    waiting = process(case)
    record('missing evidence automatically requested', 'REQUEST_INFORMATION', waiting['appliedAction']['type'])
    record('missing evidence keeps AI ownership', 'AI', waiting['case']['owner']['type'])
    reply = submit('I suffered a serious injury on board. The meal was 42.00 EUR.', case['caseId']).json()
    record('new serious allegation in reply prevents resolution', 'HANDOFF', process(reply)['appliedAction']['type'])

    case = submit('My suitcase was destroyed. Replacement cost was 42.00 EUR.').json()
    record('baggage complaint is not paid as a meal', True, process(case)['appliedAction']['type'] != 'RESOLVE')
    case = submit('I was seriously injured on board. My expenses were 42.00 EUR.').json()
    record('injured wording triggers serious review', 'HANDOFF', process(case)['appliedAction']['type'])
    case = submit('Please reimburse my meal. The receipt adjustment is -42.00 EUR.').json()
    record('negative amount is not converted into a positive payment', True,
           process(case)['appliedAction']['type'] != 'RESOLVE')

    case = submit('Please reimburse my meal.').json()
    waiting = process(case)
    reply = submit('The currency is EUR.', case['caseId']).json()
    partial = process(reply)
    record('provided currency is no longer requested', False,
           'receipt_currency' in [f['name'] for f in partial['appliedAction']['payload']['missingFacts']])
    reply = submit('The receipt is 150.00 EUR.', case['caseId']).json()
    handoff = process(reply)
    record('authority limit hands off', 'AUTHORITY_LIMIT', handoff['appliedAction']['payload']['reasonCode'])
    record('handoff includes previous clarification attempts', True,
           bool(handoff['appliedAction']['payload']['priorAttempts']))

    case = submit('Please reimburse my meal.', channel='PORTAL').json()
    record('operations preserves inbound channel', 'PORTAL', case['snapshot']['messages'][0]['channel'])
    record('operations rejects invalid sender', 422, submit('Please reimburse my meal.', sender='bad-address').status_code)
    record('operations rejects blank body', 422, submit('   ').status_code)

    # Upload contract has no command key and accepts any declared file type.
    files = {'file': ('audit.html', b'<html>synthetic audit attachment</html>', 'text/html')}
    upload = operations.post(f"/api/cases/{case['caseId']}/attachments", files=files)
    record('operations rejects unsupported attachment type', 422, upload.status_code)
    second = operations.post(f"/api/cases/{case['caseId']}/attachments", files=files)
    if upload.status_code == second.status_code == 200:
        record('identical upload retry is idempotent', upload.json()['attachmentId'], second.json()['attachmentId'])
    operations.close()
    intake.close()
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operations', required=True)
    parser.add_argument('--intake', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    results = audit(args.operations, args.intake)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    for row in results:
        print(('PASS' if row['passed'] else 'GAP') + ': ' + row['check'])
    passed = sum(row['passed'] for row in results)
    print(f'{passed}/{len(results)} expectations met; {len(results)-passed} gaps reproduced.')
    raise SystemExit(int(passed != len(results)))
