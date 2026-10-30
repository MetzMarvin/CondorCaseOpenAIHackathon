/** Exploratory design only. Current demo contracts belong in Pydantic; see
 * docs/architecture/subsystems-and-contracts.md. Async jobs and broader scope
 * here are deferred and this file is not an application dependency. */
/** Workflow contract v1. Design contract; runtime validation is required at ingress. */
export type Id = string;
export type Timestamp = string; // RFC 3339 UTC
export type Language = 'de' | 'en';
export type Channel = 'email' | 'form' | 'app_chat';
export type Category = 'delay' | 'cancellation' | 'denied_boarding' | 'baggage' | 'refund' | 'service' | 'unknown';
export type Status = 'New' | 'Triage' | 'Ready' | 'InProgress' | 'WaitingForCustomer'
  | 'WaitingForSpecialist' | 'PendingApproval' | 'WaitingForBudgetApproval' | 'Resolved' | 'Closed';
export type Owner = { kind: 'queue' | 'human' | 'ai'; id: Id };
export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export interface Money { currency: 'EUR'; minor_units: number } // nonnegative integer cents
export interface SourceRef {
  kind: 'message' | 'attachment' | 'booking' | 'flight' | 'knowledge';
  id: Id;
  version: string;
  locator: string; // JSON pointer, page/region, or character range
}
export interface Fact {
  id: Id;
  field: string;
  value: Json;
  state: 'observed' | 'confirmed' | 'conflicting';
  confidence: 'low' | 'medium' | 'high';
  sources: SourceRef[];
}
export interface Attachment {
  id: Id;
  case_id: Id;
  media_type: string;
  file_name: string;
  size_bytes: number;
  sha256: string;
  content_url: string; // application-controlled, access-checked URL
  version: string;
  synthetic: boolean;
}
export interface Message {
  id: Id;
  case_id: Id;
  channel: Channel;
  direction: 'inbound' | 'outbound';
  subject: string;
  body: string;
  sender: string;
  recipient: string;
  thread_id: Id;
  received_at: Timestamp | null;
  sent_at: Timestamp | null;
  delivery_status: 'received' | 'pending' | 'sent' | 'failed';
  attachment_ids: Id[];
}
export interface Sentiment {
  message_id: Id;
  label: 'positive' | 'neutral' | 'negative' | 'mixed' | 'uncertain';
  intensity: 'low' | 'medium' | 'high';
  confidence: 'low' | 'medium' | 'high';
  evidence: SourceRef[];
  trend: 'improving' | 'stable' | 'worsening' | 'unknown';
}
export interface CaseSummary {
  id: Id;
  version: number; // optimistic concurrency token, starts at 1
  subject: string;
  language: Language;
  channel: Channel;
  status: Status;
  category: Category;
  service_queue_id: Id;
  owner: Owner;
  priority: 'low' | 'normal' | 'high' | 'urgent';
  priority_reason: string;
  severity: 'routine' | 'serious' | 'uncertain';
  sentiment: Sentiment | null;
  next_action: string;
  created_at: Timestamp;
  updated_at: Timestamp;
  response_due_at: Timestamp | null;
  synthetic: boolean;
}
export interface PolicyContext {
  version: string;
  supported_categories: Category[];
  max_clarification_rounds_without_progress: number;
  ai_goodwill_limit: Money;
}
export interface CaseSnapshot {
  schema_version: '1.0';
  case: CaseSummary;
  contact: { id: Id; name: string; email: string; language: Language } | null;
  booking: {
    id: Id; reference: string; contact_id: Id; flight_ids: Id[];
    passengers: { id: Id; name: string }[]; currency: 'EUR';
  } | null;
  flights: {
    id: Id; flight_number: string; origin: string; destination: string;
    operating_carrier: string; scheduled_departure: Timestamp;
    scheduled_arrival: Timestamp; actual_arrival: Timestamp | null;
    cancelled: boolean; cause_code: string | null;
  }[];
  messages: Message[];
  attachments: Attachment[];
  facts: Fact[];
  clarification_history: {
    message_id: Id; requested_fields: string[]; answered_fields: string[];
    progress: 'pending' | 'made_progress' | 'no_progress';
  }[];
  policy: PolicyContext;
}
export interface InboundMessage {
  source: string; // connector namespace, e.g. demo_mailbox
  external_message_id: string;
  channel: Channel;
  thread_id: Id | null;
  case_id: Id | null;
  subject: string;
  body: string;
  sender: string;
  recipient: string;
  received_at: Timestamp;
  language: Language;
  attachment_ids: Id[]; // staged and validated by platform upload operation
}
export interface MissingField { field: string; reason: string; issue_id: Id }
export interface Issue { id: Id; category: Category; summary: string; fact_ids: Id[] }
export interface FinancialPosition {
  id: Id;
  issue_id: Id;
  kind: 'statutory_compensation' | 'refund_or_expense' | 'goodwill';
  amount: Money;
  reason: string;
  sources: SourceRef[];
}
export interface ResponseDraft { language: Language; subject: string; body: string }
export type HandoverReason = 'unsupported_action' | 'unresolved_conflict' | 'unclear_policy'
  | 'authority_limit' | 'technical_failure' | 'serious_incident' | 'clarification_exhausted';
export type ProposedAction =
  | { kind: 'clarify'; missing_fields: MissingField[]; response: ResponseDraft }
  | { kind: 'resolve'; decision: string; positions: FinancialPosition[]; response: ResponseDraft }
  | { kind: 'handover'; reason: HandoverReason; summary: string;
      unresolved_questions: string[]; attempted_steps: string[];
      recommended_queue_id: Id; suggested_response: ResponseDraft | null };
export interface Proposal {
  schema_version: '1.0';
  id: Id;
  run_id: Id;
  case_id: Id;
  based_on_case_version: number;
  policy_version: string;
  issues: Issue[];
  facts: Fact[];
  sentiment: Sentiment[];
  severity: { level: 'routine' | 'serious' | 'uncertain'; reason: string; sources: SourceRef[] };
  sources: SourceRef[];
  rationale: string; // concise decision justification, not hidden model reasoning
  action: ProposedAction;
}
export interface RunReport {
  run_id: Id;
  mode: 'live' | 'recorded';
  workflow_version: string;
  model: string | null;
  started_at: Timestamp;
  finished_at: Timestamp;
  usage: { input_tokens: number; output_tokens: number; cost: Money | null };
}
export type AnalysisResult =
  | { kind: 'completed'; proposal: Proposal; report: RunReport }
  | { kind: 'failed'; code: 'timeout' | 'provider_error' | 'invalid_output' | 'unreadable_evidence';
      retryable: boolean; message: string; report: RunReport };
export interface MutationContext { expected_case_version: number; idempotency_key: string }
export type ExecutionResult =
  | { kind: 'applied'; case: CaseSummary; event_ids: Id[]; outbox_message_id: Id | null }
  | { kind: 'blocked'; code: 'policy_conflict' | 'authority_limit' | 'quality_failed';
      reasons: string[]; case: CaseSummary; event_ids: Id[] };
export interface WorkflowError {
  code: 'invalid_request' | 'not_found' | 'forbidden' | 'stale_version'
    | 'idempotency_conflict' | 'invalid_transition' | 'unavailable';
  message: string;
  retryable: boolean;
  current_case_version?: number;
  field_errors?: { field: string; message: string }[];
}
export type Result<T> = { ok: true; value: T } | { ok: false; error: WorkflowError };
export interface CaseEvent {
  id: Id; case_id: Id; case_version: number; at: Timestamp;
  actor: Owner; type: string; reason: string;
  correlation_id: Id; payload: { [key: string]: Json };
}
export interface Page<T> { items: T[]; next_cursor: string | null }

/** Person 1 implements; person 3 consumes. Actor comes from server session. */
export interface CasePlatform {
  ingest(input: InboundMessage): Promise<Result<{ case_id: Id; message_id: Id; duplicate: boolean }>>;
  get(case_id: Id): Promise<Result<CaseSnapshot>>;
  list(filter: { status?: Status; queue_id?: Id; owner_id?: Id; category?: Category;
    cursor?: string; limit?: number }): Promise<Result<Page<CaseSummary>>>;
  events(case_id: Id, cursor?: string): Promise<Result<Page<CaseEvent>>>;
  assign(case_id: Id, input: MutationContext & { owner: Owner; service_queue_id: Id; reason: string }): Promise<Result<CaseSummary>>;
  start_run(case_id: Id, input: MutationContext): Promise<Result<{ run_id: Id }>>;
  execute(case_id: Id, input: MutationContext & { proposal_id: Id }): Promise<Result<ExecutionResult>>;
  human_action(case_id: Id, input: MutationContext & { action: ProposedAction; reason: string }): Promise<Result<ExecutionResult>>;
}
/** Person 2 implements. Platform supplies immutable snapshot and reads stored result. */
export interface AiProcessor {
  analyze(input: { run_id: Id; snapshot: CaseSnapshot; deadline_at: Timestamp }): Promise<AnalysisResult>;
}
/** Private to AI processing; original bytes available through an injected attachment reader. */
export interface EvidenceExtractor {
  extract(attachment: Attachment): Promise<{
    attachment_id: Id; status: 'readable' | 'partial' | 'unreadable';
    text: string; facts: Fact[]; warnings: string[];
  }>;
}
export interface KnowledgeLookup {
  search(input: { categories: Category[]; facts: Fact[]; language: Language;
    policy_version: string; effective_at: Timestamp }): Promise<{
      source: SourceRef; title: string; passage: string;
      valid_from: Timestamp; valid_until: Timestamp | null;
    }[]>;
}
