"""Unified case operations. All effects are simulated and committed atomically."""
import json
from uuid import uuid4
from sqlalchemy import select,text
from .database import Case,Message,Attachment,Event,Operation,Preparation
from .contracts import (Owner, Fact, SourceRef, CaseSnapshot, AttachmentRef, MissingFact, RunResult, ProcessEvent, CaseDetail, FinancialLimit, ActionResponse, ExecutionResult, RunRequest, TechnicalError, ProcessResponse)
from .intake import IntakeError,now
from .preparation_contracts import PreparedClaim
from .ai_service.service import process_case

LIMITS=(FinancialLimit(type='REIMBURSEMENT',maximum_minor=10000,currency='EUR'),)
ACTIONS=('REQUEST_INFORMATION','RESOLVE','HANDOFF')
def dump(value): return value.model_dump(mode='json',by_alias=True)
def error(code,message,case=None,status=409):
    exc=IntakeError(status,code,message);exc.current_version=case.version if case else None;raise exc

def emit(s,c,kind,summary,step=None,run=None,data=None):
    s.add(Event(id='evt-'+uuid4().hex,case_id=c.id,type=kind,summary=summary,step_id=step,run_id=run,timestamp=now(),data={'simulation':True,**(data or {})}))

def owner(s,c):
    row=s.get(Operation,'owner:'+c.id)
    return Owner(type=c.owner,id=row.data['id'] if row and c.owner=='HUMAN' else c.queue if c.owner=='QUEUE' else 'demo-agent' if c.owner=='HUMAN' else 'demo-ai')

def detail(s,c):
    assessment=c.assessment or {}
    prepared=s.get(Preparation,f'{c.id}:{c.version}')
    if not prepared or not prepared.payload:
        prepared=s.scalar(select(Preparation).where(Preparation.case_id==c.id,Preparation.payload.is_not(None)).order_by(Preparation.case_version.desc()))
    claim=PreparedClaim.model_validate(prepared.payload) if prepared and prepared.payload else None
    messages=list(s.scalars(select(Message).where(Message.case_id==c.id).order_by(Message.sequence)))
    attachments=list(s.scalars(select(Attachment).where(Attachment.case_id==c.id)))
    facts=tuple(Fact.model_validate(f) for f in assessment.get('normalizedFacts',[])) or (claim.facts if claim else ())
    internal=list(claim.lookup.flight_context if claim else ())
    # Eligibility is trusted demo context, never inferred from customer prose.
    if c.id in ('case-clear','case-evidence'):
        internal.append(Fact(name='expense_eligibility',value='eligible',sources=(SourceRef(source_id='demo-eligibility:'+c.id,version='1'),)))
    paid=s.scalar(select(Operation).where(Operation.case_id==c.id,Operation.kind=='financial'))
    internal.append(Fact(name='payment_history',value='prior_reimbursement_exists' if paid else 'no_prior_reimbursement',sources=(SourceRef(source_id='ledger:'+c.id,version='1'),)))
    def context(values, kind):
        names={'id':kind+'_record_id','reference':'booking_reference','language':'customer_language','name':'customer_name','synthetic':kind+'_synthetic'}
        return tuple(f.model_copy(update={'name':names.get(f.name, f.name)}) for f in values)
    snap=CaseSnapshot(status=c.status,owner=owner(s,c),language='en',messages=tuple(
        MessageContract(message_id=m.id,channel=m.channel,sender=m.sender,body=m.body,timestamp=m.timestamp,direction=m.direction,subject=m.subject,attachment_ids=tuple(a.id for a in attachments if a.message_id==m.id)) for m in messages),
        attachments=tuple(AttachmentRef(attachment_id=a.id,filename=a.filename,media_type=a.media_type,local_reference=a.id) for a in attachments),known_facts=facts,
        issues=tuple(assessment.get('issues',[])),missing_information=tuple(MissingFact.model_validate(x) for x in assessment.get('missingFacts',[])),
        customer_context=context(claim.lookup.customer_context,'customer') if claim else (),booking_context=context(claim.lookup.booking_context,'booking') if claim else (),flight_context=context(internal,'flight'),
        permitted_actions=ACTIONS,financial_limits=LIMITS,extracted_documents=claim.documents if claim else (),preparation_diagnostics=claim.diagnostics if claim else ())
    runs=[RunResult.model_validate(r.data['result']) for r in s.scalars(select(Operation).where(Operation.case_id==c.id,Operation.kind=='run')) if r.data.get('result')]
    history=[ProcessEvent(event_id=e.id,case_id=e.case_id,run_id=e.run_id,sequence=e.sequence,type=e.type,step_id=e.step_id,timestamp=e.timestamp,summary=e.summary,data=e.data) for e in s.scalars(select(Event).where(Event.case_id==c.id).order_by(Event.sequence))]
    next_action={'NEW':'Start assessment','WAITING_FOR_CUSTOMER':'Provide requested information','WAITING_FOR_SPECIALIST':'Specialist review','RESOLVED':'Completed','CLOSED':'Closed'}.get(c.status,'Review personally' if c.owner=='HUMAN' else 'Assess claim')
    return CaseDetail(case_id=c.id,subject=c.subject,status=c.status,owner=snap.owner,queue=c.queue,category=next(iter(snap.issues),'UNCLASSIFIED'),priority='HIGH' if assessment.get('severity')=='serious' else 'NORMAL',next_action=next_action,version=c.version,snapshot=snap,source_references=tuple(dict.fromkeys(src for f in facts+tuple(internal) for src in f.sources)),run_results=tuple(runs),history=tuple(history))

from .contracts import Message as MessageContract
from .database import Message

class Operations:
    def __init__(self,db,preparation): self.db=db;self.preparation=preparation
    def get(self,s,cid):
        c=s.get(Case,cid)
        if not c:error('CASE_NOT_FOUND','Case not found.',status=404)
        return c
    def check(self,c,version):
        if c.version!=version:error('STALE_CASE_VERSION','Case has changed.',c)
    def command(self,s,key,cid,payload):
        identity=json.dumps({'case':cid,'payload':payload},sort_keys=True)
        row=s.get(Operation,'command:'+key)
        if row:
            if row.data['fingerprint']!=identity:error('IDEMPOTENCY_CONFLICT','Command ID reused with different content.')
            if row.data.get('response') is not None:return row,row.data['response']
            if row.data.get('error'):error(row.data['error'],'The previous run was interrupted or superseded; use a new request ID.')
            error('RUN_IN_PROGRESS','Command is running.')
        row=Operation(id='command:'+key,case_id=cid,kind='command',data={'fingerprint':identity});s.add(row)
        return row,None
    def apply(self,s,c,action,ai=False,run=None):
        self.check(c,action.expected_case_version)
        if action.case_id!=c.id:error('CASE_MISMATCH','Action belongs to another case.',c)
        if c.status!='IN_PROGRESS':error('INVALID_STATE','Case is not in progress.',c)
        if ai:
            if c.owner!='AI' or action.run_id!=run:error('OWNER_CONFLICT','AI no longer owns this case.',c)
        elif c.owner!='HUMAN' or owner(s,c).id!='demo-agent' or action.run_id is not None:error('OWNER_CONFLICT','Take over the case first.',c)
        if s.get(Operation,'action:'+action.action_id):error('DUPLICATE_ACTION','Action already applied.',c)
        if action.type=='RESOLVE':
            totals={}
            for p in action.payload.financial_positions:totals[(p.type,p.currency)]=totals.get((p.type,p.currency),0)+p.amount_minor
            if any(k!=('REIMBURSEMENT','EUR') or amount>10000 for k,amount in totals.items()):error('AUTHORITY_LIMIT','Financial authority exceeded.',c)
            if totals and s.scalar(select(Operation).where(Operation.case_id==c.id,Operation.kind=='financial')):error('DUPLICATE_FINANCIAL_ACTION','Previous payment requires reconciliation.',c)
            for i,p in enumerate(action.payload.financial_positions):s.add(Operation(id=f'financial:{action.action_id}:{i}',case_id=c.id,kind='financial',data=dump(p)))
        if action.type in ('RESOLVE','REQUEST_INFORMATION'):
            last=s.scalar(select(Message).where(Message.case_id==c.id,Message.direction=='INBOUND').order_by(Message.sequence.desc()))
            body=action.payload.reply_de if action.type=='RESOLVE' else action.payload.question_de
            s.add(Message(id='msg-'+uuid4().hex,case_id=c.id,channel=last.channel if last else 'PORTAL',direction='OUTBOUND',sender='condor-service@example.com',subject=c.subject,body=body,timestamp=now(),in_reply_to=last.id if last else None))
            c.status='RESOLVED' if action.type=='RESOLVE' else 'WAITING_FOR_CUSTOMER'
            emit(s,c,'step.completed','Simulated customer message recorded','send_reply' if action.type=='RESOLVE' else 'request_information',run)
            if action.type=='REQUEST_INFORMATION':emit(s,c,'step.completed','Waiting for customer evidence','wait_for_customer',run)
        else:
            if action.payload.suggested_queue not in ('demo-specialists','SPECIALIST','CUSTOMER_SERVICE'):error('INVALID_QUEUE','Unknown specialist queue.',c)
            c.status='WAITING_FOR_SPECIALIST';c.owner='QUEUE';c.queue=action.payload.suggested_queue
            emit(s,c,'step.completed',action.payload.reason_code+': '+action.payload.summary,'human_handoff',run)
            emit(s,c,'owner.changed','Assigned to specialist queue',run=run)
        c.version+=1;c.updated_at=now()
        s.add(Operation(id='action:'+action.action_id,case_id=c.id,kind='action',data=dump(action)))
        emit(s,c,'action.applied','Action applied: '+action.type,run=run,data={'actionId':action.action_id,'financialPositions':[dump(p) for p in action.payload.financial_positions] if action.type=='RESOLVE' else []})
        emit(s,c,'case.updated','Case updated',run=run)
    def mutate(self,cid,req,takeover=False):
        with self.db.session() as s:
            s.execute(text('BEGIN IMMEDIATE'));cmd,replay=self.command(s,req.action_id,cid,{'operation':'takeover' if takeover else 'action',**dump(req)})
            if replay is not None:return replay
            c=self.get(s,cid);self.check(c,req.expected_case_version)
            if takeover:
                if req.operator_id!='demo-agent':error('INVALID_OPERATOR','Unknown demo operator.',c,422)
                if c.status in ('RESOLVED','CLOSED'):error('INVALID_STATE','Completed cases cannot be taken over.',c)
                c.owner='HUMAN';c.status='IN_PROGRESS';c.version+=1;c.updated_at=now()
                row=s.get(Operation,'owner:'+cid)
                if row:row.data={'id':req.operator_id}
                else:s.add(Operation(id='owner:'+cid,case_id=cid,kind='owner',data={'id':req.operator_id}))
                emit(s,c,'owner.changed','Human takeover invalidated older AI results');emit(s,c,'case.updated','Case updated')
            else:self.apply(s,c,req)
            s.flush();value=detail(s,c)
            response=dump(value) if takeover else dump(ActionResponse(case=value,execution_result=ExecutionResult(action_id=req.action_id,case_version=c.version)))
            cmd.data={**cmd.data,'response':response};s.commit();return response
    def process(self,cid,req):
        # Prepare before the versioned run reservation; never hold a writer lock around a provider.
        with self.db.session() as s:
            prior=s.get(Operation,'command:'+req.request_id)
            if prior:
                _,replay=self.command(s,req.request_id,cid,{'operation':'process',**dump(req)})
                return replay
            c=self.get(s,cid);self.check(c,req.expected_case_version)
            if c.owner!='AI':error('OWNER_CONFLICT','Case is not AI-owned.',c)
            if c.status not in ('NEW','IN_PROGRESS'):error('INVALID_STATE','Submit a reply before processing again.',c)
        self.preparation.prepare(cid,req.expected_case_version)
        with self.db.session() as s:
            s.execute(text('BEGIN IMMEDIATE'));cmd,replay=self.command(s,req.request_id,cid,{'operation':'process',**dump(req)})
            if replay is not None:return replay
            c=self.get(s,cid);self.check(c,req.expected_case_version)
            if c.owner!='AI':error('OWNER_CONFLICT','Case is not AI-owned.',c)
            if any(r.data.get('state')=='RUNNING' for r in s.scalars(select(Operation).where(Operation.case_id==cid,Operation.kind=='run'))):error('RUN_IN_PROGRESS','A run is already active.',c)
            snapshot=detail(s,c).snapshot
            if c.status=='NEW':c.status='IN_PROGRESS';c.version+=1;c.updated_at=now();emit(s,c,'case.updated','Assessment started')
            run_id='run-'+uuid4().hex
            snapshot=snapshot.model_copy(update={'status':c.status,'attachments':(), 'messages':tuple(m.model_copy(update={'attachment_ids':()}) for m in snapshot.messages)})
            request=RunRequest(run_id=run_id,case_id=cid,case_version=c.version,trigger='customer_reply' if sum(m.direction=='INBOUND' for m in snapshot.messages)>1 else 'manual_process',snapshot=snapshot)
            run=Operation(id=run_id,case_id=cid,kind='run',data={'state':'RUNNING','request':dump(request),'command':cmd.id});s.add(run);s.commit()
        def progress(p):
            with self.db.session() as s:
                emit(s,self.get(s,cid),p.type,p.summary,p.step_id,run_id,{'sourceIds':list(p.source_ids),'simulation':p.simulation});s.commit()
        try:
            from .ai_service.interpretation import interpret
            interpreted=interpret(request)
            with self.db.session() as audit_session:
                audit_run=audit_session.get(Operation,run_id)
                audit_run.data={**audit_run.data,'interpretedRequest':dump(interpreted)}
                audit_session.commit()
            result=RunResult.model_validate(process_case(interpreted,progress))
            if (result.run_id,result.case_id,result.based_on_case_version)!=(run_id,cid,request.case_version):raise ValueError('Mismatched result')
        except Exception:
            result=RunResult(run_id=run_id,case_id=cid,based_on_case_version=request.case_version,status='FAILED',technical_error=TechnicalError(code='PROCESSING_FAILED',message='Assessment failed; retry with a new request ID or take over.',retryable=True))
        rejected=None
        with self.db.session() as s:
            s.execute(text('BEGIN IMMEDIATE'));c=self.get(s,cid);run=s.get(Operation,run_id);cmd=s.get(Operation,'command:'+req.request_id)
            run.data={**run.data,'state':'FINISHED','result':dump(result)}
            if c.version!=request.case_version or c.owner!='AI':
                rejected='STALE_AI_RESULT';run.data={**run.data,'state':'REJECTED'};cmd.data={**cmd.data,'error':rejected}
                emit(s,c,'run.failed','Stale AI result rejected',run=run_id)
            else:
                applied=None
                if result.status=='SUCCEEDED':
                    try:
                        with s.begin_nested():self.apply(s,c,result.proposed_action,True,run_id)
                        applied=result.proposed_action
                        c.assessment={**dump(result.assessment),'normalizedFacts':[dump(f) for f in interpreted.snapshot.known_facts]}
                    except IntakeError as exc:
                        rejected=exc.code;run.data={**run.data,'state':'REJECTED'};cmd.data={**cmd.data,'error':rejected};emit(s,c,'run.failed','Proposed action rejected: '+rejected,run=run_id)
                else:emit(s,c,'run.failed',result.technical_error.message,run=run_id)
                if not rejected:
                    s.flush();cmd.data={**cmd.data,'response':dump(ProcessResponse(run_result=result,applied_action=applied,case=detail(s,c)))}
            s.commit()
            if rejected:error(rejected,'The AI result was retained but not applied.',c)
            return cmd.data['response']
    def recover(self):
        with self.db.session() as s:
            for row in s.scalars(select(Operation).where(Operation.kind=='run')):
                if row.data.get('state')=='RUNNING':
                    req=RunRequest.model_validate(row.data['request'])
                    result=RunResult(run_id=req.run_id,case_id=req.case_id,based_on_case_version=req.case_version,status='FAILED',technical_error=TechnicalError(code='RUN_INTERRUPTED',message='Server restarted; retry with a new request ID.',retryable=True))
                    row.data={**row.data,'state':'INTERRUPTED','result':dump(result)}
                    cmd=s.get(Operation,row.data['command']);cmd.data={**cmd.data,'error':'RUN_INTERRUPTED'}
                    emit(s,self.get(s,row.case_id),'run.failed','Run interrupted by restart',run=req.run_id)
            s.commit()
