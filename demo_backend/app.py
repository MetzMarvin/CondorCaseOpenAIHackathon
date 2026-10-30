"""Replaceable System 1/2 stand-in for console integration; all decisions are fixtures."""
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker

ROOT = Path(__file__).parent
engine = create_engine('sqlite:///' + os.environ.get('DEMO_DB', str(ROOT / 'demo.sqlite')), connect_args={'check_same_thread': False})
Session = sessionmaker(bind=engine)
Base = declarative_base()
lock = threading.RLock()
class Record(Base):
    __tablename__ = 'cases'
    id = Column(String, primary_key=True)
    data = Column(Text, nullable=False)
class Event(Base):
    __tablename__ = 'events'
    sequence = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String, nullable=False)
    data = Column(Text, nullable=False)
class Command(Base):
    __tablename__ = 'commands'
    id = Column(String, primary_key=True)
    payload = Column(Text)
    response = Column(Text)
Base.metadata.create_all(engine)
app = FastAPI(title='Condor Care · Integration Mock', description='Synthetic System 1/2 stand-in. No real AI, email or payments.', version='0.1.0')

class ProcessRequest(BaseModel):
    requestId: str = Field(min_length=1)
    expectedCaseVersion: int
class TakeoverRequest(BaseModel):
    actionId: str = Field(min_length=1)
    expectedCaseVersion: int
    operatorId: Literal['demo-agent']
class InboundRequest(BaseModel):
    messageId: str = Field(min_length=1)
    channel: Literal['EMAIL'] = 'EMAIL'
    sender: str = Field(min_length=1)
    body: str = Field(min_length=1)
    caseId: Optional[str] = None
    attachmentIds: list[str] = Field(default_factory=list)
class Resolution(BaseModel):
    outcome: str
    explanation: str
    reply: str = Field(min_length=1)
    sourceIds: list[str]
    financialPositions: list = Field(default_factory=list)
class HumanAction(BaseModel):
    actionId: str = Field(min_length=1)
    caseId: str
    expectedCaseVersion: int
    type: Literal['RESOLVE']
    payload: Resolution
class ResetRequest(BaseModel):
    actionId: str
class Case(BaseModel):
    id: str
    subject: str
    scenario: str
    status: str
    owner: dict
    queue: str
    priority: str
    category: str
    nextAction: str
    caseVersion: int
    messages: list[dict]
    attachments: list[dict]
    facts: list[str]
    sourceReferences: list[dict]
    missingInformation: list[str]
    runResults: list[dict]
    handoff: Optional[dict] = None
    financialPositions: list = Field(default_factory=list)
    simulation: bool = True

def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid.uuid4())
def fail(code, message, case=None, status=409):
    raise HTTPException(status, detail={'code':code, 'message':message, 'currentCaseVersion':case and case['caseVersion']})
def read(s, cid):
    row = s.get(Record, cid)
    if not row: fail('NOT_FOUND', 'Case not found.', status=404)
    return json.loads(row.data)
def save(s, c):
    Case.model_validate(c)
    s.merge(Record(id=c['id'], data=json.dumps(c)))
def event(s, c, step, summary, kind='step.completed', run=None):
    data = {'schemaVersion':1,'eventId':uid(),'caseId':c['id'],'runId':run,'type':kind,'stepId':step,'timestamp':now(),'summary':summary,'data':{'simulation':True,'sourceIds':['demo-policy-1']}}
    s.add(Event(case_id=c['id'], data=json.dumps(data)))
def message(body, direction='INBOUND', mid=None):
    return {'messageId':mid or uid(),'direction':direction,'body':body,'timestamp':now(),'simulation':True}
def fresh(cid, subject, scenario, body):
    return Case(id=cid, subject=subject, scenario=scenario, status='NEW', owner={'type':'AI','id':'demo-ai'}, queue='Service', priority='High' if scenario=='serious' else 'Normal', category='Service request', nextAction='Start AI assessment',caseVersion=1,messages=[message(body)],attachments=[],facts=['Flight DE1234 · Frankfurt → Palma', 'Customer data is synthetic'],sourceReferences=[{'id':'demo-policy-1','version':'1','title':'Demo service guide · synthetic policy'}],missingInformation=['Booking reference'] if scenario=='evidence' else [],runResults=[]).model_dump()
SEEDS = [
 ('case-clear','Resend booking confirmation','clear','Please resend my booking confirmation for DE1234. Booking ABC123.'),
 ('case-evidence','Missing booking reference','evidence','I need a copy of my booking confirmation. Can you help?'),
 ('case-serious','Onboard injury reported','serious','I would like to report an injury during the flight. Please review the incident personally.'),
 ('case-angry','Frustrated, but clear','angry','I am really frustrated! Please finally send my confirmation for booking ABC123.'),
 ('case-unsupported','Unsupported special arrangement','unsupported','Please confirm an individual arrangement outside your demo policies.'),
 ('case-standard','Resend travel documents','clear','Please resend my travel documents. My booking reference is XYZ789.'),
]
def seed(s):
    for cid, subject, scenario, body in SEEDS:
        c = fresh(cid, subject, scenario, body); save(s,c)
        event(s,c,'intake','Message linked to case. Synthetic customer data loaded.')
with lock, Session.begin() as s:
    if not s.query(Record).count(): seed(s)

def mutate(scope, key, payload, fn):
    encoded = json.dumps(payload, sort_keys=True)
    # A short transaction serializes the synchronous mock, including owner/version checks.
    with lock, Session.begin() as s:
        command = s.get(Command, key)
        fingerprint = scope + ':' + encoded
        if command:
            if command.payload != fingerprint: fail('IDEMPOTENCY_CONFLICT','This ID has already been used for another action.')
            return json.loads(command.response)
        result = fn(s)
        s.add(Command(id=key, payload=fingerprint, response=json.dumps(result)))
        return result

def version(c, expected):
    if c['caseVersion'] != expected: fail('STALE_VERSION','The case has changed. Please reload.',c)

@app.get('/api/cases', response_model=list[Case])
def cases(status: Optional[str]=None, queue: Optional[str]=None, owner: Optional[str]=None):
    with Session() as s:
        rows = [json.loads(r.data) for r in s.query(Record).order_by(Record.id)]
        return [c for c in rows if (not status or c['status']==status) and (not queue or c['queue']==queue) and (not owner or c['owner']['type']==owner)]
@app.get('/api/cases/{cid}', response_model=Case)
def detail(cid: str):
    with Session() as s: return read(s,cid)
@app.get('/api/events')
def events(caseId: str, after: int=0):
    with Session() as s:
        read(s,caseId)
        rows = s.query(Event).filter(Event.case_id==caseId, Event.sequence>after).order_by(Event.sequence).all()
        return {'events':[dict(json.loads(r.data), sequence=r.sequence) for r in rows], 'cursor':rows[-1].sequence if rows else after}
@app.post('/api/inbound/messages', response_model=Case)
def inbound(req: InboundRequest):
    def execute(s):
        c = read(s,req.caseId) if req.caseId else fresh('case-'+uid()[:8], 'New demo service request', 'clear', req.body)
        if any(a not in [ref['attachmentId'] for ref in c['attachments']] for a in req.attachmentIds): fail('INVALID_ATTACHMENT','Attachment does not belong to this case.',status=422)
        if req.caseId:
            c['messages'].append(message(req.body, mid=req.messageId)); c['caseVersion']+=1
            c['status']='IN_PROGRESS'
            # Explicit deterministic evidence fixture, not language understanding.
            if 'ABC123' in req.body.upper(): c['missingInformation']=[]
        else: c['messages'][0]['messageId']=req.messageId
        c['nextAction']='Assess reply'
        event(s,c,'intake','Customer reply recorded on the existing case.' if req.caseId else 'New demo case created.')
        save(s,c); return c
    return mutate('inbound',req.messageId,req.model_dump(),execute)
@app.post('/api/cases/{cid}/process')
def process(cid: str, req: ProcessRequest):
    def execute(s):
        c = read(s,cid); version(c,req.expectedCaseVersion)
        if c['owner']['type']!='AI': fail('OWNER_CONFLICT','This case belongs to a human or specialist queue.',c)
        if c['status'] not in ['NEW','IN_PROGRESS']: fail('INVALID_STATE','Submit a customer reply before reassessing this case.',c)
        run=uid(); c['status']='IN_PROGRESS'
        for step, text in [('extract_evidence','Message, booking and attachments assembled as case context.'),('assess','Completeness and severity assessed. Sentiment alone does not trigger a handoff.'),('retrieve_policy','Stored demo service guide v1 consulted.'),('validate_action','Ownership, case version and permitted demo action validated.')]: event(s,c,step,text,run=run)
        if c['scenario'] in ['serious','unsupported']:
            action='HANDOFF'; reason='SERIOUS_ISSUE' if c['scenario']=='serious' else 'UNSUPPORTED_ACTION'
            c['handoff']={'reasonCode':reason,'suggestedQueue':'Specialists','summary':c['subject'],'facts':c['facts'],'evidence':[m['messageId'] for m in c['messages']],'unresolvedQuestions':['Personal specialist review required'],'priorAttempts':['Automatic assessment completed; no customer commitment sent.']}
            c.update(status='WAITING_FOR_SPECIALIST',owner={'type':'QUEUE','id':'specialists'},queue='Specialists',nextAction='Take over personally')
            event(s,c,'human_handoff','Reasoned handoff with facts, history and open questions: '+reason,run=run)
        elif c['missingInformation']:
            action='REQUEST_INFORMATION'; question='Please provide your booking reference so we can locate your documents.'
            c['messages'].append(message(question,'OUTBOUND')); c.update(status='WAITING_FOR_CUSTOMER',nextAction='Provide booking reference')
            event(s,c,'request_information','Clear question sent automatically. AI retains ownership.',run=run)
            event(s,c,'wait_for_customer','Waiting for booking reference. A reply continues the same case.',run=run)
        else:
            action='RESOLVE'; c.update(status='RESOLVED',nextAction='Completed')
            c['messages'].append(message('Thank you for your message. Your booking confirmation has been resent. This is a simulated delivery.','OUTBOUND'))
            event(s,c,'send_reply','Confirmation resent automatically. No human approval required.',run=run)
        c['caseVersion']+=1
        result={'runId':run,'caseId':cid,'basedOnCaseVersion':req.expectedCaseVersion,'status':'SUCCEEDED','assessment':{'nextActionExplanation':c['nextAction'],'missingFacts':c['missingInformation'],'sentiment':'NEGATIVE' if c['scenario']=='angry' else 'NEUTRAL'},'proposedAction':{'actionId':uid(),'caseId':cid,'expectedCaseVersion':req.expectedCaseVersion,'runId':run,'type':action,'payload': c['handoff'] if action=='HANDOFF' else ({'missingFacts':c['missingInformation'],'reasons':['Booking identification required'],'question':c['messages'][-1]['body']} if action=='REQUEST_INFORMATION' else {'outcome':'DOCUMENTS_RESENT','explanation':'Supported demo service case','sourceIds':['demo-policy-1'],'sourceVersions':['1'],'reply':c['messages'][-1]['body'],'financialPositions':[]})}}
        c['runResults'].append(result)
        event(s,c,None,'Action applied: '+action,'action.applied',run)
        save(s,c); return {'case':c,'runResult':result,'appliedAction':result['proposedAction']}
    return mutate('process:'+cid,req.requestId,req.model_dump(),execute)
@app.post('/api/cases/{cid}/takeover', response_model=Case)
def takeover(cid: str, req: TakeoverRequest):
    def execute(s):
        c=read(s,cid); version(c,req.expectedCaseVersion)
        if c['status'] in ['RESOLVED','CLOSED']: fail('INVALID_STATE','A completed case cannot be taken over.',c)
        c.update(owner={'type':'HUMAN','id':req.operatorId},status='IN_PROGRESS',nextAction='Reply personally'); c['caseVersion']+=1
        event(s,c,'human_handoff','Demo agent took over. Earlier AI versions are invalid.','owner.changed'); save(s,c); return c
    return mutate('takeover:'+cid,req.actionId,req.model_dump(),execute)
@app.post('/api/cases/{cid}/actions')
def action(cid: str, req: HumanAction):
    def execute(s):
        c=read(s,cid); version(c,req.expectedCaseVersion)
        if req.caseId!=cid: fail('CASE_MISMATCH','Case ID does not match.',status=422)
        if c['owner']['type']!='HUMAN': fail('OWNER_CONFLICT','Take over the case first.',c)
        if c['status']!='IN_PROGRESS': fail('INVALID_STATE','Case is not in progress.',c)
        if req.payload.financialPositions: fail('AUTHORITY_LIMIT','This mock does not permit financial actions.',c)
        c['messages'].append(message(req.payload.reply,'OUTBOUND')); c.update(status='RESOLVED',nextAction='Completed'); c['caseVersion']+=1
        event(s,c,'send_reply','Human reply delivered in simulation and case resolved.','action.applied'); save(s,c)
        return {'case':c,'executionResult':{'status':'APPLIED','actionId':req.actionId}}
    return mutate('action:'+cid,req.actionId,req.model_dump(),execute)
@app.post('/api/cases/{cid}/attachments')
def upload(cid: str, file: UploadFile=File(...)):
    content=file.file.read(2_000_001)
    if len(content)>2_000_000: fail('FILE_TOO_LARGE','Demo attachments are limited to 2 MB.',status=422)
    with lock, Session.begin() as s:
        c=read(s,cid); aid=uid(); path=ROOT/'attachments'/aid; path.parent.mkdir(exist_ok=True); path.write_bytes(content)
        ref={'attachmentId':aid,'filename':Path(file.filename or 'evidence').name,'mediaType':file.content_type or 'application/octet-stream','localReference':f'/api/cases/{cid}/attachments/{aid}'}
        c['attachments'].append(ref); c['caseVersion']+=1; event(s,c,'extract_evidence','Synthetic attachment saved to the case.'); save(s,c); return ref
@app.get('/api/cases/{cid}/attachments/{aid}')
def attachment(cid: str, aid: str):
    with Session() as s:
        c=read(s,cid); ref=next((a for a in c['attachments'] if a['attachmentId']==aid),None)
        if not ref: fail('NOT_FOUND','Attachment not found.',status=404)
        return FileResponse(ROOT/'attachments'/aid, filename=ref['filename'],media_type=ref['mediaType'])
@app.post('/api/demo/reset')
def reset(req: ResetRequest):
    with lock, Session.begin() as s:
        s.query(Command).delete(); s.query(Event).delete(); s.query(Record).delete(); seed(s)
    return {'simulation':True,'message':'Six demo cases reset.'}
