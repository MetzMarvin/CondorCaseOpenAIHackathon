import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.database import Operation,Case
from sqlalchemy import select
from backend.ai_service.interpretation import CLEAR

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path)) as c:yield c

def process(c,cid,key='p'):
    case=c.get('/api/cases/'+cid).json()
    return c.post('/api/cases/'+cid+'/process',json={'requestId':key,'expectedCaseVersion':case['version']})

def test_three_flows(client):
    c=client
    r=process(c,'case-clear');assert r.status_code==200,r.text
    assert r.json()['case']['status']=='RESOLVED',r.text
    assert c.get('/api/portal/cases/case-clear').json()['messages'][-1]['direction']=='OUTBOUND'
    assert process(c,'case-evidence','missing').json()['case']['status']=='WAITING_FOR_CUSTOMER'
    r=c.post('/api/inbound/messages',json=dict(messageId='reply',caseId='case-evidence',channel='PORTAL',sender='test@example.com',subject='Receipt',body='42.00 EUR'));assert r.status_code==200,r.text
    assert process(c,'case-evidence','reply-run').json()['case']['status']=='RESOLVED'
    assert process(c,'case-serious','serious').json()['case']['status']=='WAITING_FOR_SPECIALIST'
    case=c.get('/api/cases/case-serious').json()
    r=c.post('/api/cases/case-serious/takeover',json=dict(actionId='take',operatorId='demo-agent',expectedCaseVersion=case['version']));assert r.status_code==200,r.text
    version=r.json()['version'];src=[dict(sourceId='human-review',version='1')]
    r=c.post('/api/cases/case-serious/actions',json=dict(actionId='human',caseId='case-serious',expectedCaseVersion=version,sources=src,type='RESOLVE',payload=dict(outcome='MANUAL',explanation='Reviewed',replyDe='Reviewed personally. Simulation.',sources=src,financialPositions=[])))
    assert r.status_code==200,r.text
    assert r.json()['case']['status']=='RESOLVED'

def test_idempotency_and_event_runs(client):
    payload={'requestId':'same','expectedCaseVersion':1}
    r=client.post('/api/cases/case-clear/process',json=payload);assert r.status_code==200,r.text
    assert client.post('/api/cases/case-clear/process',json=payload).json()==r.json()
    assert client.post('/api/cases/case-evidence/process',json=payload).status_code==409
    events=client.get('/api/events?caseId=case-clear').json()['events']
    assert any(e['runId'] for e in events)
    with client.app.state.db.session() as s:
        assert len(list(s.scalars(select(Operation).where(Operation.kind=='financial'))))==1

def test_takeover_during_run(client,monkeypatch):
    import backend.operations as ops
    original=ops.process_case
    def interrupted(request,emit):
        case=client.get('/api/cases/case-clear').json()
        r=client.post('/api/cases/case-clear/takeover',json=dict(actionId='race',operatorId='demo-agent',expectedCaseVersion=case['version']))
        assert r.status_code==200
        return original(request,emit)
    monkeypatch.setattr(ops,'process_case',interrupted)
    assert process(client,'case-clear').status_code==409
    case=client.get('/api/cases/case-clear').json()
    assert case['owner']['type']=='HUMAN' and case['runResults']
    assert not any(m['direction']=='OUTBOUND' for m in case['snapshot']['messages'])

def test_authority_aggregate_rollback(client):
    case=client.get('/api/cases/case-clear').json()
    r=client.post('/api/cases/case-clear/takeover',json=dict(actionId='take',operatorId='demo-agent',expectedCaseVersion=case['version']))
    version=r.json()['version'];sources=[dict(sourceId='review',version='1')]
    position=dict(type='REIMBURSEMENT',amountMinor=6000,currency='EUR',explanation='Expense',sources=sources)
    payload=dict(actionId='over',caseId='case-clear',expectedCaseVersion=version,type='RESOLVE',sources=sources,payload=dict(outcome='MANUAL',explanation='Review',replyDe='Simulated approval',sources=sources,financialPositions=[position,position]))
    r=client.post('/api/cases/case-clear/actions',json=payload)
    assert r.status_code==409 and r.json()['error']['code']=='AUTHORITY_LIMIT'
    case=client.get('/api/cases/case-clear').json()
    assert case['version']==version and len(case['snapshot']['messages'])==1
    with client.app.state.db.session() as s:
        assert not list(s.scalars(select(Operation).where(Operation.kind=='financial')))

def test_interrupted_run_recovery(client):
    from backend.contracts import RunRequest
    from backend.operations import dump
    with client.app.state.db.session() as s:
        from backend.operations import detail
        c=s.get(Case,'case-clear');snap=detail(s,c).snapshot
        req=RunRequest(run_id='interrupted',case_id=c.id,case_version=c.version,trigger='test',snapshot=snap)
        s.add(Operation(id='command:interrupted',case_id=c.id,kind='command',data={'fingerprint':'test'}))
        s.add(Operation(id='interrupted',case_id=c.id,kind='run',data={'state':'RUNNING','request':dump(req),'command':'command:interrupted'}));s.commit()
    client.app.state.operations.recover()
    case=client.get('/api/cases/case-clear').json()
    assert case['runResults'][-1]['technicalError']['code']=='RUN_INTERRUPTED'
    assert process(client,'case-clear','fresh').json()['case']['status']=='RESOLVED'

def test_legacy_event_migration(tmp_path):
    import sqlite3
    from backend.database import Database
    path=tmp_path/'care-hub.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE events (sequence INTEGER PRIMARY KEY AUTOINCREMENT,id VARCHAR UNIQUE,case_id VARCHAR,type VARCHAR,step_id VARCHAR,timestamp VARCHAR,summary VARCHAR,data JSON)')
        db.execute("INSERT INTO events (id,case_id,type,timestamp,summary,data) VALUES ('old','case','case.updated','2026-01-01T00:00:00Z','old','{}')")
    Database(tmp_path).engine.dispose();Database(tmp_path).engine.dispose()
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT sequence,run_id FROM events').fetchall()==[(1,None)]
        assert db.execute('SELECT version FROM schema_versions').fetchall()==[(1,)]

def test_uploaded_receipt_closes_evidence_loop(client):
    import json
    from pathlib import Path
    assert process(client,'case-evidence','ask').json()['case']['status']=='WAITING_FOR_CUSTOMER'
    metadata=dict(messageId='upload-reply',caseId='case-evidence',channel='PORTAL',sender='test@example.com',subject='Receipt',body='Evidence attached.')
    r=client.post('/api/inbound/messages',data={'metadata':json.dumps(metadata)},files=[('files',('receipt.png',Path('backend/demo-files/preparation-receipt.png').read_bytes(),'image/png'))])
    assert r.status_code==200,r.text
    r=process(client,'case-evidence','evidence-run')
    assert r.status_code==200 and r.json()['case']['status']=='RESOLVED',r.text
    with client.app.state.db.session() as s:
        runs=list(s.scalars(select(Operation).where(Operation.kind=='run')))
        assert all('interpretedRequest' in run.data for run in runs)

def test_second_payment_is_rejected(client):
    assert process(client,'case-clear').json()['case']['status']=='RESOLVED'
    r=client.post('/api/inbound/messages',json=dict(messageId='reopen',caseId='case-clear',channel='PORTAL',sender='test@example.com',subject='More expenses',body='42.00 EUR'))
    version=r.json()['caseVersion']
    take=client.post('/api/cases/case-clear/takeover',json=dict(actionId='take-paid',operatorId='demo-agent',expectedCaseVersion=version))
    sources=[dict(sourceId='manual',version='1')]
    payload=dict(actionId='second-payment',caseId='case-clear',expectedCaseVersion=take.json()['version'],sources=sources,type='RESOLVE',payload=dict(outcome='MANUAL',explanation='Review',replyDe='Simulation',sources=sources,financialPositions=[dict(type='REIMBURSEMENT',currency='EUR',amountMinor=100,explanation='Expense',sources=sources)]))
    r=client.post('/api/cases/case-clear/actions',json=payload)
    assert r.status_code==409 and r.json()['error']['code']=='DUPLICATE_FINANCIAL_ACTION'
