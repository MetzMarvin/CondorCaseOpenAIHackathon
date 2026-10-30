"""Per-run private processing bundle; never serialized into progress events."""
from dataclasses import dataclass, field
from backend.contracts import RunRequest


@dataclass
class ProcessingBundle:
    request: RunRequest
    effective_request: RunRequest | None = None
    attachments: list = field(default_factory=list)
    extractions: list = field(default_factory=list)
    retrieval: object | None = None

    mode: str = 'unknown'
    model: str | None = None
    model_started: bool = False
    retrieval_configuration_version: str = 'lexical-approved-v1'


def expert_context(bundle, baseline, *, max_bytes=32000):
    """Allowlisted factual projections and whole approved support; no raw case prose."""
    import json
    from backend.ai_service.assessment import INTAKE_REQUIREMENTS, INTERNAL_FACTS, CONTROL_FACTS, SERIOUS_ISSUES
    from backend.ai_service.questions import QUESTIONS
    request = bundle.effective_request or bundle.request
    snapshot = request.snapshot
    facts = []
    enums = {'expense_eligibility': {'eligible', 'ineligible'},
             'payment_history': {'no_prior_reimbursement', 'prior_reimbursement'},
             'conflict_review_status': {'unresolved', 'resolved'},
             'evidence_access_status': {'available'}, 'policy_status': {'available'}}
    grouped = [(fact, 'customer') for fact in snapshot.known_facts + snapshot.customer_context]
    grouped += [(fact, 'internal') for fact in snapshot.booking_context + snapshot.flight_context]
    for fact, origin in grouped:
        if origin != 'internal' and fact.name in INTERNAL_FACTS | CONTROL_FACTS:
            continue
        if fact.name not in QUESTIONS and fact.name not in INTERNAL_FACTS | CONTROL_FACTS:
            continue
        if not fact.sources:
            continue
        value = {'present': fact.value is not None and fact.value != ''}
        if fact.name == 'receipt_amount_minor' and type(fact.value) is int and fact.value >= 0:
            value = fact.value
        elif fact.name == 'receipt_currency' and fact.value in ('EUR', 'USD', 'GBP'):
            value = fact.value
        elif fact.name in enums and isinstance(fact.value, str) and fact.value in enums[fact.name]:
            value = fact.value
        elif fact.name in {'receipt_readable', 'legal_review_required'} and type(fact.value) is bool:
            value = fact.value
        facts.append(dict(name=fact.name, origin=origin, value=value, sources=[s.model_dump() for s in fact.sources]))
    passages = bundle.retrieval.passages if bundle.retrieval else ()
    citations = [dict(source_id=p.source_id, version=p.version, passage_id=p.passage_id) for p in passages]
    action = baseline.proposed_action
    draft = dict(action_type=action.type, explanation='The deterministic proposal remains unchanged.', sentiment='not_assessed')
    if action.type == 'REQUEST_INFORMATION':
        draft.update(opening='Thank you for getting back to us.' if request.trigger == 'customer_reply' else 'Thank you for contacting us.',
            questions=[dict(fact_name=m.name, question=('We found differing details in the information provided. ' if m.reason.startswith('The supplied evidence contains different values.') else '') + QUESTIONS[m.name][1]) for m in action.payload.missing_facts])
    else:
        draft['customer_message'] = action.payload.reply_de if action.type == 'RESOLVE' else 'A specialist review is proposed. No settlement or execution is claimed.'
    context = dict(facts=facts, issues=[i if i in INTAKE_REQUIREMENTS or i in SERIOUS_ISSUES else 'unsupported_request' for i in snapshot.issues],
        missing_fields=[m.name for m in baseline.assessment.missing_facts if m.name in QUESTIONS],
        permitted_actions=list(snapshot.permitted_actions), financial_limits=[x.model_dump() for x in snapshot.financial_limits],
        approved_passages=[p.model_dump() for p in passages], required_citations=citations,
        required_source_ids=sorted({s['source_id'] for f in facts for s in f['sources']} | {p.source_id for p in passages}),
        reviewed_draft=draft)
    if len(json.dumps(context, ensure_ascii=False).encode('utf-8')) > max_bytes:
        raise ValueError('Required context exceeds budget; support cannot be truncated')
    return context
