"""System 1 preparation: durable queue, best-effort enrichment, no business actions."""
from uuid import uuid4
from sqlalchemy import select, text
from .database import Case, Message, Attachment, Preparation, PreparationRequest, Event
from .contracts import CaseSnapshot, RunRequest, Owner, Message as SnapshotMessage, PreparationDiagnostic
from .preparation_contracts import PreparedClaim, LookupResult
from .extraction import Extractor
from .salesforce_mock import SalesforceMock
from .intake import IntakeError, now


def enqueue(session, case):
    for old in session.scalars(select(Preparation).where(Preparation.case_id==case.id)):
        if old.case_version != case.version:
            old.state='SUPERSEDED'
    identity=f'{case.id}:{case.version}'
    row=session.get(Preparation,identity)
    if row is None:
        row=Preparation(id=identity,case_id=case.id,case_version=case.version,state='PENDING')
        session.add(row)
    return row


def view(row):
    return dict(preparationId=row.id,caseId=row.case_id,caseVersion=row.case_version,state=row.state,claim=row.payload)


class PreparationService:
    def __init__(self, db, extractor=None, mock=None):
        self.db=db
        self.extractor=extractor or Extractor()
        self.mock=mock or SalesforceMock()

    def event(self, session, case_id, kind, stage):
        session.add(Event(id='evt-'+uuid4().hex,case_id=case_id,type=kind,step_id='extract_evidence',
            timestamp=now(),summary='Claim preparation '+stage,data={'stage':stage,'simulation':self.extractor.mode=='offline'}))

    def prepare(self, case_id, version, request_id=None):
        identity=f'{case_id}:{version}'
        attempt=uuid4().hex
        with self.db.session() as session:
            session.execute(text('BEGIN IMMEDIATE'))
            prior=session.get(PreparationRequest,request_id) if request_id else None
            if prior:
                if prior.preparation_id!=identity:
                    raise IntakeError(409,'IDEMPOTENCY_CONFLICT','Request ID has different content.')
                if prior.result:
                    return prior.result
            case=session.get(Case,case_id)
            if not case:
                raise IntakeError(404,'CASE_NOT_FOUND','Case not found.')
            if case.version!=version:
                raise IntakeError(409,'STALE_CASE_VERSION','Case has changed.')
            row=enqueue(session,case)
            if row.state=='PREPARING':
                raise IntakeError(409,'PREPARATION_RUNNING','Preparation is already running.')
            if not request_id and row.state in ('READY','READY_WITH_ERRORS'):
                return view(row)
            if request_id and not prior:
                session.add(PreparationRequest(id=request_id,preparation_id=identity))
            row.state='PREPARING';row.attempt=attempt
            messages=[dict(messageId=m.id,channel=m.channel,direction=m.direction,sender=m.sender,subject=m.subject,body=m.body,timestamp=m.timestamp)
                for m in session.scalars(select(Message).where(Message.case_id==case_id).order_by(Message.sequence))]
            attachments=list(session.scalars(select(Attachment).where(Attachment.case_id==case_id)))
            self.event(session,case_id,'step.started','started')
            session.commit()
        facts=[];documents=[];diagnostics=[]
        def extract(body, source):
            try:
                facts.extend(self.extractor.facts(body,source))
            except Exception:
                diagnostics.append(PreparationDiagnostic(stage='facts',code='FACT_EXTRACTION_UNAVAILABLE',source_id=source))
        for message in messages:
            if message['direction']=='INBOUND':
                extract(message['body'],message['messageId'])
        for attachment in attachments:
            try:
                path=(self.db.attachments/attachment.storage_name).resolve()
                if path.parent!=self.db.attachments.resolve():
                    raise ValueError('Invalid path')
                extracted=self.extractor.documents(attachment,path)
                documents.extend(extracted)
                for doc in extracted:
                    source=f'{doc.attachment_id}:page:{doc.page}'
                    if doc.error:
                        diagnostics.append(PreparationDiagnostic(stage='document',code=doc.error,source_id=source))
                    if doc.text:
                        extract(doc.text,source)
            except Exception:
                diagnostics.append(PreparationDiagnostic(stage='document',code='DOCUMENT_READ_FAILED',source_id=attachment.id))
        try:
            lookup=self.mock.lookup(facts)
        except Exception:
            lookup=LookupResult(status='NOT_ATTEMPTED')
            diagnostics.append(PreparationDiagnostic(stage='lookup',code='LOOKUP_UNAVAILABLE'))
        claim=PreparedClaim(case_id=case_id,case_version=version,mode=self.extractor.mode,messages=messages,
            facts=tuple(facts),documents=tuple(documents),lookup=lookup,diagnostics=tuple(diagnostics))
        with self.db.session() as session:
            session.execute(text('BEGIN IMMEDIATE'))
            row=session.get(Preparation,identity);case=session.get(Case,case_id)
            if row.attempt!=attempt or case.version!=version or row.state=='SUPERSEDED':
                row.state='SUPERSEDED'
            else:
                row.payload=claim.model_dump(mode='json',by_alias=True)
                row.state='READY_WITH_ERRORS' if diagnostics else 'READY'
            result=view(row)
            if request_id:
                session.get(PreparationRequest,request_id).result=result
            self.event(session,case_id,'step.completed',row.state.lower())
            session.commit()
            return result

    def run_request(self, case_id, version, run_id, permitted_actions=(), financial_limits=()):
        """Called only by System 1 orchestration with server-owned authority, never HTTP input."""
        with self.db.session() as session:
            case=session.get(Case,case_id);row=session.get(Preparation,f'{case_id}:{version}')
            if not case or case.version!=version or not row or row.state not in ('READY','READY_WITH_ERRORS'):
                raise IntakeError(409,'STALE_PREPARATION','A current prepared claim is required.')
            if case.owner!='AI' or case.status!='IN_PROGRESS':
                raise IntakeError(409,'INVALID_AI_CONTEXT','An active AI-owned case is required.')
            claim=PreparedClaim.model_validate(row.payload)
            snapshot=CaseSnapshot(status=case.status,owner=Owner(type='AI',id='demo-ai'),language='en',
                messages=tuple(SnapshotMessage(message_id=m['messageId'],channel=m['channel'],sender=m['sender'],body=m['body'],timestamp=m['timestamp']) for m in claim.messages),
                attachments=(),known_facts=claim.facts,issues=(),missing_information=(),customer_context=claim.lookup.customer_context,
                booking_context=claim.lookup.booking_context,flight_context=claim.lookup.flight_context,
                permitted_actions=permitted_actions,financial_limits=financial_limits,extracted_documents=claim.documents,preparation_diagnostics=claim.diagnostics)
            return RunRequest(run_id=run_id,case_id=case_id,case_version=version,trigger='prepared_claim',snapshot=snapshot)


def recover(db):
    """Single-process demo startup: interrupted calls are explicitly retryable."""
    with db.session() as session:
        for row in session.scalars(select(Preparation).where(Preparation.state=='PREPARING')):
            row.state='PENDING';row.attempt=None
        session.commit()
