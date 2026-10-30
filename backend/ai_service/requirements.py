"""Evidence collection matrix, not legal entitlement rules.

Only expense_reimbursement has a synthetic resolution policy. Other supported
issues permit intake collection; their adjudication remains unsupported.
"""
from dataclasses import dataclass
from typing import Literal

from backend.ai_service.assessment import CONTROL_FACTS, INTAKE_REQUIREMENTS, INTERNAL_FACTS

Authority = Literal['customer', 'crm', 'operational', 'policy', 'control']


@dataclass(frozen=True)
class EvidenceRequirement:
    name: str
    authority: Authority
    when_absent: Literal['ask_customer', 'enrich_internal', 'retrieve_policy']
    when_conflicting: Literal['clarify_customer', 'reconcile_internal', 'clarify_rule']
    freshness: str

    def accepts_origin(self, origin: Authority) -> bool:
        """Source origin is adapter-owned metadata, never a customer-supplied label."""
        return origin == self.authority


# Authoritative matched records supplement identifiers supplied by the customer.
_CRM = ('customer_match', 'booking_match', 'flight_match')
_OPERATIONAL_BY_ISSUE = {
    'expense_reimbursement': ('expense_eligibility', 'payment_history'),
    'flight_delay': ('actual_arrival', 'operating_carrier', 'flight_distance', 'disruption_cause', 'reasonable_measures', 'payment_history'),
    'flight_cancellation': ('notification_log', 'operating_carrier', 'disruption_cause', 'reasonable_measures', 'payment_history'),
    'denied_boarding': ('operating_carrier', 'payment_history'),
    'baggage_delay': ('payment_history',),
    'baggage_damage': ('payment_history',),
    'baggage_loss': ('payment_history',),
    'service_complaint': (),
}
_POLICY_FACTS = {'policy_version', 'legal_regime'}


def requirement_for_fact(name: str, *, authority: Authority | None = None) -> EvidenceRequirement:
    """Classify known authority first; callers cannot downgrade internal controls."""
    if name in CONTROL_FACTS or name in {'permitted_actions', 'financial_limits'}:
        origin = 'control'
    elif name in _POLICY_FACTS:
        origin = 'policy'
    elif name in INTERNAL_FACTS:
        origin = 'operational'
    elif name in _CRM:
        origin = 'crm'
    else:
        origin = authority or 'customer'
    if authority is not None and authority != origin:
        raise ValueError('Cannot change the authoritative origin of a protected fact')
    return EvidenceRequirement(name, origin,
        'ask_customer' if origin == 'customer' else 'retrieve_policy' if origin == 'policy' else 'enrich_internal',
        'clarify_customer' if origin == 'customer' else 'clarify_rule' if origin == 'policy' else 'reconcile_internal',
        'attachment/message version at snapshot' if origin == 'customer' else
        'approved version effective on event date' if origin == 'policy' else
        'current at exact case version; stale or unknown requires refresh')


def requirements_for_issue(issue: str) -> tuple[EvidenceRequirement, ...]:
    if issue not in INTAKE_REQUIREMENTS:
        raise ValueError('Issue is outside supported evidence collection')
    names = (*INTAKE_REQUIREMENTS[issue], *_CRM, *_OPERATIONAL_BY_ISSUE[issue],
             'policy_version', *(() if issue == 'expense_reimbursement' else ('legal_regime',)),
             *sorted(CONTROL_FACTS), 'permitted_actions', 'financial_limits')
    return tuple(requirement_for_fact(name) for name in dict.fromkeys(names))
