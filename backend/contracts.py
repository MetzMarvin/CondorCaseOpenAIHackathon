"""Shared v1 Pydantic contracts. System 1 alone authorizes business mutations.

Python uses snake_case; JSON uses the agreed camelCase names.
"""
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator
from pydantic.alias_generators import to_camel

Id = Annotated[str, Field(min_length=1)]
Text = Annotated[str, Field(min_length=1)]
Version = Annotated[int, Field(ge=0, strict=True)]
CaseStatus = Literal['NEW', 'IN_PROGRESS', 'WAITING_FOR_CUSTOMER', 'WAITING_FOR_SPECIALIST', 'RESOLVED', 'CLOSED']
ActionType = Literal['REQUEST_INFORMATION', 'RESOLVE', 'HANDOFF']
StepId = Literal['intake', 'extract_evidence', 'assess', 'retrieve_policy', 'validate_action', 'request_information', 'wait_for_customer', 'send_reply', 'human_handoff']
HandoffReason = Literal['UNSUPPORTED_ACTION', 'SERIOUS_ISSUE', 'UNRESOLVED_CONFLICT', 'UNCLEAR_RULE', 'AUTHORITY_LIMIT', 'TECHNICAL_FAILURE']


class Contract(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra='forbid', frozen=True)


class SourceRef(Contract):
    source_id: Id
    version: Id


class Owner(Contract):
    type: Literal['AI', 'HUMAN', 'QUEUE']
    id: Id


class AttachmentRef(Contract):
    attachment_id: Id
    filename: Text
    media_type: Text
    local_reference: Id  # Opaque case-scoped token, resolved only by System 1.


class Message(Contract):
    message_id: Id
    channel: Text
    sender: Text
    body: Text
    timestamp: AwareDatetime
    attachment_ids: tuple[Id, ...] = ()


class Fact(Contract):
    name: Text
    value: JsonValue
    sources: tuple[SourceRef, ...]


class MissingFact(Contract):
    name: Text
    reason: Text


class FinancialPosition(Contract):
    type: Literal['COMPENSATION', 'REIMBURSEMENT', 'GOODWILL']
    amount_minor: Annotated[int, Field(ge=0, strict=True)]
    currency: Annotated[str, Field(pattern=r'^[A-Z]{3}$')]
    explanation: Text
    sources: tuple[SourceRef, ...]


class FinancialLimit(Contract):
    type: Literal['COMPENSATION', 'REIMBURSEMENT', 'GOODWILL']
    maximum_minor: Annotated[int, Field(ge=0, strict=True)]
    currency: Annotated[str, Field(pattern=r'^[A-Z]{3}$')]
    requires_approval: bool = False


class PreparationDiagnostic(Contract):
    stage: str
    code: str
    source_id: str | None = None


class ExtractedDocument(Contract):
    attachment_id: str
    filename: str
    page: int
    text: str
    method: str
    error: str | None = None


class CaseSnapshot(Contract):
    extracted_documents: tuple[ExtractedDocument, ...] = ()
    preparation_diagnostics: tuple[PreparationDiagnostic, ...] = ()
    status: CaseStatus
    owner: Owner
    language: Text
    messages: tuple[Message, ...]
    attachments: tuple[AttachmentRef, ...]
    known_facts: tuple[Fact, ...]
    issues: tuple[Text, ...]
    missing_information: tuple[MissingFact, ...]
    customer_context: tuple[Fact, ...]
    booking_context: tuple[Fact, ...]
    flight_context: tuple[Fact, ...]
    permitted_actions: tuple[ActionType, ...]
    financial_limits: tuple[FinancialLimit, ...]


class RunRequest(Contract):
    schema_version: Literal[1] = 1
    run_id: Id
    case_id: Id
    case_version: Version
    trigger: Text
    snapshot: CaseSnapshot


class Assessment(Contract):
    issues: tuple[Text, ...]
    missing_facts: tuple[MissingFact, ...]
    severity: Text
    sentiment: Text
    sources: tuple[SourceRef, ...]
    next_action_explanation: Text


class InformationPayload(Contract):
    missing_facts: Annotated[tuple[MissingFact, ...], Field(min_length=1)]
    question_de: Text


class ResolutionPayload(Contract):
    outcome: Text
    explanation: Text
    sources: Annotated[tuple[SourceRef, ...], Field(min_length=1)]
    reply_de: Text
    financial_positions: tuple[FinancialPosition, ...] = ()


class HandoffPayload(Contract):
    reason_code: HandoffReason
    suggested_queue: Id
    summary: Text
    facts: tuple[Fact, ...]
    evidence: tuple[SourceRef, ...]
    unresolved_questions: tuple[Text, ...]
    prior_attempts: tuple[Text, ...]


class ActionEnvelope(Contract):
    action_id: Id
    case_id: Id
    expected_case_version: Version
    run_id: Id | None = None  # Required for AI; absent for a human action.
    sources: tuple[SourceRef, ...]


class RequestInformation(ActionEnvelope):
    type: Literal['REQUEST_INFORMATION']
    payload: InformationPayload


class Resolve(ActionEnvelope):
    type: Literal['RESOLVE']
    payload: ResolutionPayload


class Handoff(ActionEnvelope):
    type: Literal['HANDOFF']
    payload: HandoffPayload


ProposedAction = Annotated[RequestInformation | Resolve | Handoff, Field(discriminator='type')]


class TechnicalError(Contract):
    code: Id
    message: Text
    retryable: bool


class RunResult(Contract):
    run_id: Id
    case_id: Id
    based_on_case_version: Version
    status: Literal['SUCCEEDED', 'FAILED']
    assessment: Assessment | None = None
    proposed_action: ProposedAction | None = None
    technical_error: TechnicalError | None = None
    simulation: bool = True

    @model_validator(mode='after')
    def consistent_result(self):
        if self.status == 'FAILED':
            if self.technical_error is None or self.proposed_action is not None:
                raise ValueError('Failed runs require a technical error and cannot propose business actions')
        elif self.assessment is None or self.proposed_action is None or self.technical_error is not None:
            raise ValueError('Successful runs require an assessment and action, without a technical error')
        action = self.proposed_action
        if action and (action.run_id, action.case_id, action.expected_case_version) != (self.run_id, self.case_id, self.based_on_case_version):
            raise ValueError('AI action must match the run, case and snapshot version')
        return self


class ProgressUpdate(Contract):
    step_id: StepId
    type: Literal['step.started', 'step.completed', 'step.failed']
    summary: Text
    source_ids: tuple[Id, ...] = ()
    simulation: bool = True


class ProcessEvent(Contract):
    schema_version: Literal[1] = 1
    event_id: Id
    case_id: Id
    run_id: Id | None = None
    sequence: Annotated[int, Field(ge=1, strict=True)]
    type: Literal['step.started', 'step.completed', 'step.failed', 'case.updated', 'owner.changed', 'action.applied', 'run.failed']
    step_id: StepId | None = None
    timestamp: AwareDatetime
    summary: Text
    data: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode='after')
    def step_required(self):
        if self.type.startswith('step.') and self.step_id is None:
            raise ValueError('Step events require stepId')
        return self


class CaseSummary(Contract):
    case_id: Id
    subject: Text
    status: CaseStatus
    category: Text
    owner: Owner
    queue: Id | None
    priority: Text
    next_action: Text
    version: Version


class CaseDetail(CaseSummary):
    snapshot: CaseSnapshot
    source_references: tuple[SourceRef, ...]
    run_results: tuple[RunResult, ...]
    history: tuple[ProcessEvent, ...]


class InboundMessageRequest(Contract):
    message_id: Id
    channel: Text
    sender: Text
    body: Text
    attachment_ids: tuple[Id, ...] = ()
    case_id: Id | None = None
    thread_id: Id | None = None


class ProcessRequest(Contract):
    request_id: Id
    expected_case_version: Version


class TakeoverRequest(Contract):
    action_id: Id
    expected_case_version: Version
    operator_id: Id


class ExecutionResult(Contract):
    action_id: Id
    case_version: Version
    simulation: bool = True


class ActionResponse(Contract):
    case: CaseDetail
    execution_result: ExecutionResult


class ProcessResponse(Contract):
    run_result: RunResult
    applied_action: ProposedAction | None
    case: CaseDetail


class EventPage(Contract):
    events: tuple[ProcessEvent, ...]
    cursor: Version


class ApiError(Contract):
    code: Id
    message: Text
    current_case_version: Version | None = None
