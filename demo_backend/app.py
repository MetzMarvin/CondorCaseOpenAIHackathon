"""Integrated synthetic System 1: persistence and validated System 2 execution.

All financial effects and deliveries are local simulations. AI_MODE defaults to
'offline'; explicitly set the shell variable to opt into another backend mode.
"""
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.contracts import (
    ActionResponse, ApiError, CaseDetail, CaseSummary, EventPage, ExecutionResult,
    Fact, InboundMessageRequest, Message, Owner, ProcessEvent, ProcessRequest,
    ProcessResponse, ProposedAction, RunRequest, RunResult, SourceRef,
    TakeoverRequest, AttachmentRef,
)
from backend.ai_service.fixtures import demo_request
from backend.ai_service.service import process_case

ROOT = Path(__file__).parent
# A saved explicit live/offline choice is honored; 'auto' never accidentally
# turns a demo live merely because a developer has credentials on this machine.
_saved_mode = (dotenv_values(ROOT.parent / '.env').get('AI_MODE') or '').strip().lower()
os.environ.setdefault('AI_MODE', _saved_mode if _saved_mode in {'openai', 'offline'} else 'offline')
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


class ResetRequest(BaseModel):
    actionId: str = Field(min_length=1)


Base.metadata.create_all(engine)
app = FastAPI(title='Condor Care · Integrated Demo', description='Systems 1 and 2, synthetic data and simulated deliveries/payments.', version='0.2.0')
in_flight = {}


def now():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid.uuid4())


def dump(model):
    return model.model_dump(mode='json', by_alias=True)


def fail(code, message, case=None, status=409):
    raise HTTPException(status, detail=dump(ApiError(code=code, message=message, current_case_version=case and case.version)))


@app.exception_handler(HTTPException)
def http_error(_, exc):
    detail = exc.detail if isinstance(exc.detail, dict) else dump(ApiError(code='HTTP_ERROR', message=str(exc.detail)))
    return JSONResponse(status_code=exc.status_code, content=detail)


@app.exception_handler(RequestValidationError)
def validation_error(_, exc):
    return JSONResponse(status_code=422, content=dump(ApiError(code='INVALID_INPUT', message='Please check the submitted fields and action payload.')))


def read(s, cid):
    row = s.get(Record, cid)
    if not row:
        fail('NOT_FOUND', 'Case not found.', status=404)
    data = json.loads(row.data)
    if data.get('schema') != 2:
        fail('LEGACY_DEMO_DATA', 'Older standalone demo data is preserved. Use Reset demos to initialize the integrated expense scenarios.')
    return data


def detail_value(s, record):
    case = CaseDetail.model_validate(record['case'])
    rows = s.query(Event).filter(Event.case_id == case.case_id).order_by(Event.sequence).all()
    return case.model_copy(update={'history': tuple(ProcessEvent.model_validate_json(row.data) for row in rows)})


def save(s, record, case):
    record['case'] = dump(case.model_copy(update={'history': ()}))
    s.merge(Record(id=case.case_id, data=json.dumps(record)))


def event(s, case, step, summary, kind='step.completed', run=None, data=None):
    row = Event(case_id=case.case_id, data='{}')
    s.add(row)
    s.flush()
    item = ProcessEvent(event_id=uid(), case_id=case.case_id, run_id=run, sequence=row.sequence,
                        type=kind, step_id=step, timestamp=now(), summary=summary,
                        data={'simulation': True, **(data or {})})
    row.data = item.model_dump_json(by_alias=True)


def message(body, sender='guest@example.com', mid=None, attachments=()):
    return Message(message_id=mid or uid(), channel='EMAIL', sender=sender, body=body,
                   timestamp=now(), attachment_ids=tuple(attachments))


def update(case, **changes):
    """Keep summary and snapshot ownership/state authoritative and consistent."""
    snapshot = changes.pop('snapshot', case.snapshot)
    snapshot = snapshot.model_copy(update={k: changes[k] for k in ('status', 'owner') if k in changes})
    return case.model_copy(update={'snapshot': snapshot, **changes})


SEEDS = [
    ('case-clear', 'Meal expense reimbursement', 'clear', 'Please reimburse my meal expense of 42.00 EUR during the documented disruption.'),
    ('case-evidence', 'Receipt amount missing', 'missing', 'Please reimburse my meal during the disruption. I have not supplied the receipt amount yet.'),
    ('case-serious', 'Onboard injury reported', 'serious', 'I suffered an injury during the flight and need personal specialist assistance.'),
    ('case-angry', 'Frustrated customer, complete evidence', 'clear', 'I am frustrated! Please reimburse my documented meal expense of 42.00 EUR.'),
    ('case-unsupported', 'Unsupported special arrangement', 'unsupported', 'Please confirm an individual arrangement outside the supported demo policy.'),
    ('case-standard', 'Complete meal expense claim', 'clear', 'Here is my complete claim for a meal expense of 42.00 EUR.'),
]


def fresh(cid, subject, scenario, body, mid=None):
    snapshot = demo_request(scenario).snapshot.model_copy(update={
        'status': 'NEW', 'messages': (message(body, mid=mid),),
    })
    case = CaseDetail(case_id=cid, subject=subject, status='NEW', category='Expense reimbursement' if scenario in {'clear', 'missing'} else 'Specialist review',
                      owner=snapshot.owner, queue='Service', priority='High' if scenario == 'serious' else 'Normal',
                      next_action='Start AI assessment', version=1, snapshot=snapshot,
                      source_references=(SourceRef(source_id='demo-expense-policy', version='2'),), run_results=(), history=())
    return {'schema': 2, 'scenario': scenario, 'case': dump(case), 'financialLedger': []}, case


def seed(s):
    for cid, subject, scenario, body in SEEDS:
        record, case = fresh(cid, subject, scenario, body)
        save(s, record, case)
        event(s, case, 'intake', 'Synthetic message linked to the case. Internal booking and payment checks loaded.')


with lock, Session.begin() as s:
    if not s.query(Record).count():
        seed(s)


def mutate(scope, key, payload, fn):
    fingerprint = scope + ':' + json.dumps(payload, sort_keys=True)
    with lock, Session.begin() as s:
        if key in in_flight:
            fail('IDEMPOTENCY_CONFLICT', 'This ID belongs to a running processing request.')
        command = s.get(Command, key)
        if command:
            if command.payload != fingerprint:
                fail('IDEMPOTENCY_CONFLICT', 'This ID has already been used for another action.')
            return json.loads(command.response)
        result = fn(s)
        s.add(Command(id=key, payload=fingerprint, response=json.dumps(result)))
        return result


def version(case, expected):
    if case.version != expected:
        fail('STALE_VERSION', 'The case has changed. Please reload.', case)


@app.get('/api/cases', response_model=list[CaseSummary])
def cases(status: str | None = None, queue: str | None = None, owner: str | None = None):
    with Session() as s:
        result = []
        for row in s.query(Record).order_by(Record.id):
            case = CaseDetail.model_validate(read(s, row.id)['case'])
            if (not status or case.status == status) and (not queue or case.queue == queue) and (not owner or case.owner.type == owner):
                result.append(CaseSummary.model_validate({k: v for k, v in dump(case).items() if k in CaseSummary.model_json_schema(by_alias=True)['properties']}))
        return result


@app.get('/api/cases/{cid}', response_model=CaseDetail)
def detail(cid: str):
    with Session() as s:
        return detail_value(s, read(s, cid))


@app.get('/api/events', response_model=EventPage)
def events(caseId: str, after: int = 0):
    with Session() as s:
        read(s, caseId)
        rows = s.query(Event).filter(Event.case_id == caseId, Event.sequence > after).order_by(Event.sequence).all()
        return EventPage(events=tuple(ProcessEvent.model_validate_json(row.data) for row in rows), cursor=rows[-1].sequence if rows else max(0, after))


def extract_receipt(snapshot, body, source):
    # Deliberate demo parser, not OCR or a model: only a decimal amount next to EUR.
    match = re.search(r'(?<![\w.])(\d{1,5})[,.](\d{2})\s*EUR\b', body, re.I)
    if not match:
        return snapshot
    amount = int(match[1]) * 100 + int(match[2])
    facts = tuple(f for f in snapshot.known_facts if f.name not in {'receipt_amount_minor', 'receipt_currency'})
    facts += (Fact(name='receipt_amount_minor', value=amount, sources=(source,)), Fact(name='receipt_currency', value='EUR', sources=(source,)))
    return snapshot.model_copy(update={'known_facts': facts, 'missing_information': ()})


@app.post('/api/inbound/messages', response_model=CaseDetail)
def inbound(req: InboundMessageRequest):
    def execute(s):
        if req.case_id:
            record = read(s, req.case_id)
            case = detail_value(s, record)
            if any(a not in {ref.attachment_id for ref in case.snapshot.attachments} for a in req.attachment_ids):
                fail('INVALID_ATTACHMENT', 'Attachment does not belong to this case.', status=422)
            msg = message(req.body, req.sender, req.message_id, req.attachment_ids)
            snapshot = case.snapshot.model_copy(update={'messages': case.snapshot.messages + (msg,)})
            snapshot = extract_receipt(snapshot, req.body, SourceRef(source_id=req.message_id, version='1'))
            case = update(case, snapshot=snapshot, status='IN_PROGRESS', version=case.version + 1, next_action='Assess customer reply')
        else:
            if req.attachment_ids:
                fail('INVALID_ATTACHMENT', 'Create a case before uploading evidence.', status=422)
            # Deterministic demo intake supports expense collection and two specialist fixtures.
            lower = req.body.lower()
            scenario = 'serious' if any(word in lower for word in ('injury', 'verletzung', 'safety incident')) else 'unsupported' if 'unsupported' in lower else 'missing'
            record, case = fresh('case-' + uid()[:8], 'New synthetic expense claim', scenario, req.body, req.message_id)
            snapshot = case.snapshot.model_copy(update={'messages': (message(req.body, req.sender, req.message_id),)})
            if scenario == 'missing':
                snapshot = extract_receipt(snapshot, req.body, SourceRef(source_id=req.message_id, version='1'))
            case = update(case, snapshot=snapshot)
        save(s, record, case)
        event(s, case, 'intake', 'Customer reply recorded on the existing case.' if req.case_id else 'New synthetic demo case created.')
        return dump(detail_value(s, record))
    return mutate('inbound', req.message_id, dump(req), execute)


def validate_action(case, action, ai=False):
    version(case, action.expected_case_version)
    if action.case_id != case.case_id:
        fail('CASE_MISMATCH', 'Case ID does not match.', status=422)
    if ai and case.owner.type != 'AI':
        fail('OWNER_CONFLICT', 'This case belongs to a human or specialist queue.', case)
    if not ai and (case.owner.type != 'HUMAN' or case.owner.id != 'demo-agent' or action.run_id is not None):
        fail('OWNER_CONFLICT', 'Take over this case with the configured demo operator first.', case)
    if action.type not in case.snapshot.permitted_actions:
        fail('AUTHORITY_LIMIT', 'This action is not permitted.', case)
    if action.type == 'RESOLVE':
        totals = {}
        for pos in action.payload.financial_positions:
            totals[(pos.type, pos.currency)] = totals.get((pos.type, pos.currency), 0) + pos.amount_minor
        for (kind, currency), total in totals.items():
            limits = [x for x in case.snapshot.financial_limits if x.type == kind and x.currency == currency]
            if not limits or any(x.requires_approval or total > x.maximum_minor for x in limits):
                fail('AUTHORITY_LIMIT', 'Financial action exceeds the configured demo authority.', case)


def apply_action(s, record, case, action, ai=False):
    validate_action(case, action, ai)
    run = action.run_id
    snapshot = case.snapshot
    if action.type == 'REQUEST_INFORMATION':
        snapshot = snapshot.model_copy(update={'messages': snapshot.messages + (message(action.payload.question_de, 'condor-service@example.com'),), 'missing_information': action.payload.missing_facts})
        case = update(case, snapshot=snapshot, status='WAITING_FOR_CUSTOMER', next_action='Provide missing receipt evidence')
        event(s, case, 'request_information', 'Specific evidence question sent automatically in simulation.', run=run)
        event(s, case, 'wait_for_customer', 'AI retains ownership while waiting for the customer.', run=run)
    elif action.type == 'HANDOFF':
        case = update(case, status='WAITING_FOR_SPECIALIST', owner=Owner(type='QUEUE', id=action.payload.suggested_queue), queue=action.payload.suggested_queue, next_action='Take over for specialist review')
        event(s, case, 'human_handoff', action.payload.reason_code + ': ' + action.payload.summary, run=run)
    else:
        if action.payload.financial_positions and record['financialLedger']:
            fail('DUPLICATE_FINANCIAL_ACTION', 'A simulated reimbursement already exists; specialist reconciliation is required.', case)
        snapshot = snapshot.model_copy(update={'messages': snapshot.messages + (message(action.payload.reply_de, 'condor-service@example.com'),), 'missing_information': ()})
        record['financialLedger'].extend({'actionId': action.action_id, 'simulation': True, **dump(pos)} for pos in action.payload.financial_positions)
        if action.payload.financial_positions:
            internal = tuple(f for f in snapshot.flight_context if f.name != 'payment_history') + (Fact(name='payment_history', value='prior_reimbursement_exists', sources=(SourceRef(source_id=action.action_id, version='1'),)),)
            snapshot = snapshot.model_copy(update={'flight_context': internal})
        case = update(case, snapshot=snapshot, status='RESOLVED', next_action='Completed')
        event(s, case, 'send_reply', 'Reply delivered and any authorized reimbursement recorded in simulation.', run=run)
    case = update(case, version=case.version + 1)
    event(s, case, None, 'Action applied: ' + action.type, 'action.applied', run, {'actionId': action.action_id, 'financialPositions': [dump(p) for p in action.payload.financial_positions] if action.type == 'RESOLVE' else []})
    return case


@app.post('/api/cases/{cid}/process', response_model=ProcessResponse)
def process(cid: str, req: ProcessRequest):
    # Keep provider latency outside the transaction/lock. A human may take over
    # while this synchronous request runs; the final apply rechecks the case.
    fingerprint = 'process:' + cid + ':' + json.dumps(dump(req), sort_keys=True)
    with lock, Session.begin() as s:
        command = s.get(Command, req.request_id)
        if command:
            if command.payload != fingerprint:
                fail('IDEMPOTENCY_CONFLICT', 'This ID has already been used for another action.')
            return json.loads(command.response)
        if req.request_id in in_flight:
            fail('RUN_IN_PROGRESS', 'This processing request is already running.')
        record = read(s, cid)
        case = detail_value(s, record)
        version(case, req.expected_case_version)
        if case.owner.type != 'AI':
            fail('OWNER_CONFLICT', 'This case belongs to a human or specialist queue.', case)
        if case.status not in {'NEW', 'IN_PROGRESS'}:
            fail('INVALID_STATE', 'Submit a customer reply before reassessing this case.', case)
        if cid in in_flight.values():
            fail('RUN_IN_PROGRESS', 'This case is already being assessed.', case)
        case = update(case, status='IN_PROGRESS')
        run = uid()
        request = RunRequest(run_id=run, case_id=cid, case_version=case.version, trigger='customer_reply' if len(case.snapshot.messages) > 1 and case.snapshot.messages[-1].sender != 'condor-service@example.com' else 'manual_process', snapshot=case.snapshot)
        in_flight[req.request_id] = cid
    try:
        def emit(progress):
            with lock, Session.begin() as progress_session:
                event(progress_session, case, progress.step_id, progress.summary, progress.type, run,
                      {'sourceIds': list(progress.source_ids), 'simulation': progress.simulation})
        result = RunResult.model_validate(process_case(request, emit))
        with lock, Session.begin() as s:
            record = read(s, cid)
            current = detail_value(s, record)
            # Version/ownership validation immediately precedes accepted effects.
            version(current, request.case_version)
            if current.owner.type != 'AI':
                fail('OWNER_CONFLICT', 'Human ownership superseded this AI run.', current)
            if (result.run_id, result.case_id, result.based_on_case_version) != (run, cid, current.version):
                fail('RUN_MISMATCH', 'The AI result does not match the current case and run.', current)
            current = update(current, status='IN_PROGRESS')
            if result.status == 'SUCCEEDED':
                current = apply_action(s, record, current, result.proposed_action, ai=True)
            else:
                current = update(current, version=current.version + 1, next_action='Technical error: retry assessment or take over manually')
                event(s, current, None, result.technical_error.message, 'run.failed', run, {'code': result.technical_error.code})
            current = update(current, run_results=current.run_results + (result,))
            save(s, record, current)
            response = dump(ProcessResponse(case=detail_value(s, record), run_result=result, applied_action=result.proposed_action))
            s.add(Command(id=req.request_id, payload=fingerprint, response=json.dumps(response)))
            return response
    finally:
        with lock:
            in_flight.pop(req.request_id, None)


@app.post('/api/cases/{cid}/takeover', response_model=CaseDetail)
def takeover(cid: str, req: TakeoverRequest):
    def execute(s):
        record = read(s, cid)
        case = detail_value(s, record)
        version(case, req.expected_case_version)
        if req.operator_id != 'demo-agent':
            fail('INVALID_OPERATOR', 'Only the configured demo operator may take over.', status=422)
        if case.status in {'RESOLVED', 'CLOSED'}:
            fail('INVALID_STATE', 'A completed case cannot be taken over.', case)
        case = update(case, owner=Owner(type='HUMAN', id=req.operator_id), status='IN_PROGRESS', version=case.version + 1, next_action='Review and reply personally')
        event(s, case, None, 'Demo agent took over. Older AI versions are invalid.', 'owner.changed')
        save(s, record, case)
        return dump(detail_value(s, record))
    return mutate('takeover:' + cid, req.action_id, dump(req), execute)


@app.post('/api/cases/{cid}/actions', response_model=ActionResponse)
def action(cid: str, req: ProposedAction):
    def execute(s):
        record = read(s, cid)
        case = detail_value(s, record)
        if case.status != 'IN_PROGRESS':
            fail('INVALID_STATE', 'Case is not in progress.', case)
        case = apply_action(s, record, case, req)
        save(s, record, case)
        return dump(ActionResponse(case=detail_value(s, record), execution_result=ExecutionResult(action_id=req.action_id, case_version=case.version)))
    return mutate('action:' + cid, req.action_id, dump(req), execute)


@app.post('/api/cases/{cid}/attachments', response_model=AttachmentRef)
def upload(cid: str, file: UploadFile = File(...)):
    content = file.file.read(2_000_001)
    if len(content) > 2_000_000:
        fail('FILE_TOO_LARGE', 'Demo attachments are limited to 2 MB.', status=422)
    with lock, Session.begin() as s:
        record = read(s, cid)
        case = detail_value(s, record)
        aid = uid()
        path = ROOT / 'attachments' / aid
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(content)
        ref = AttachmentRef(attachment_id=aid, filename=Path(file.filename or 'evidence').name, media_type=file.content_type or 'application/octet-stream', local_reference=f'/api/cases/{cid}/attachments/{aid}')
        case = update(case, snapshot=case.snapshot.model_copy(update={'attachments': case.snapshot.attachments + (ref,)}), version=case.version + 1)
        save(s, record, case)
        event(s, case, 'extract_evidence', 'Synthetic attachment stored on this case. No OCR performed.')
        return ref


@app.get('/api/cases/{cid}/attachments/{aid}')
def attachment(cid: str, aid: str):
    with Session() as s:
        case = detail_value(s, read(s, cid))
        ref = next((a for a in case.snapshot.attachments if a.attachment_id == aid), None)
        if not ref:
            fail('NOT_FOUND', 'Attachment not found.', status=404)
        return FileResponse(ROOT / 'attachments' / aid, filename=ref.filename, media_type=ref.media_type)


@app.post('/api/demo/reset')
def reset(req: ResetRequest):
    with lock, Session.begin() as s:
        # Reset is an explicit demo-only command, never an automatic migration.
        if in_flight:
            fail('RUN_IN_PROGRESS', 'Wait for the current assessment before resetting demo data.')
        s.query(Command).delete()
        s.query(Event).delete()
        s.query(Record).delete()
        seed(s)
    return {'simulation': True, 'message': 'Six integrated expense demo cases reset.'}
