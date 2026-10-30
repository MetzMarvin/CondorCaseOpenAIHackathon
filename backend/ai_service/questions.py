"""Reviewed demo wording. Snapshot reasons are evidence, never message templates."""
from backend.contracts import MissingFact

# Stable fact names consumed from System 1; these do not change shared models.
QUESTIONS = {
    'booking_reference': ('Identify the affected booking.', 'Please share your booking reference, or the flight number and travel date, so we can find the right journey.'),
    'flight_number': ('Identify the affected flight.', 'Which flight was affected? Please share the flight number.'),
    'flight_date': ('Identify the date of travel.', 'On which date were you due to travel?'),
    'claim_details': ('Understand the requested help.', 'Please tell us what happened and what you would like us to help with.'),
    'claimant_authority': ('Confirm who the claim covers.', 'Please confirm which passengers you are claiming for and, if you are acting for someone else, provide the relevant authorization.'),
    'receipt': ('Evidence of the expense is missing.', 'Please share an itemized receipt, or other evidence of the expense if you no longer have the receipt.'),
    'receipt_readable': ('The receipt cannot be read reliably.', 'Thank you for the document. Please send a clearer, complete copy showing the items, date, total and currency.'),
    'receipt_amount_minor': ('Confirm the expense amount.', 'Please share a receipt or other evidence showing the total amount paid.'),
    'receipt_currency': ('Confirm the original currency.', 'Please confirm the currency shown on the receipt, for example EUR or USD.'),
    'receipt_date': ('Establish when the expense occurred.', 'Please confirm the purchase date or share the part of the receipt showing it.'),
    'expense_purpose': ('Connect the expense to the disruption.', 'Please briefly explain what the expense was for and how it relates to your disrupted journey.'),
    'baggage_reference': ('Identify the affected baggage.', 'Please share your baggage tag or baggage report reference, if available. Otherwise, tell us which bag was affected.'),
    'baggage_return_date': ('Establish the baggage delay timeline.', 'When was your bag returned to you? If it is still missing, please let us know.'),
    'damage_details': ('Understand the reported baggage damage.', 'Please describe the damage and share any available photos showing it.'),
    'damage_discovery_date': ('Establish when damage was discovered.', 'When did you receive your bag and first notice the damage?'),
    'written_complaint_date': ('Establish the complaint timeline.', 'When did you first report this in writing? Please share a copy or reference if available.'),
    'remedy_choice': ('Understand the preferred available remedy.', 'Would you prefer a ticket refund or help with an alternative journey? We will check the available options for your booking.'),
    'prior_reimbursement': ('Avoid reimbursing the same expense twice.', 'Has any part of this expense already been reimbursed? If so, please tell us the amount and who reimbursed it.'),
}


def missing_fact(name: str, *, conflicting: bool = False) -> MissingFact:
    reason = QUESTIONS[name][0]
    if conflicting:
        reason = 'The supplied evidence contains different values. ' + reason
    return MissingFact(name=name, reason=reason)


def information_message(missing: tuple[MissingFact, ...], *, is_reply: bool) -> str:
    greeting = ('Thank you for getting back to us. We have kept the information you already shared.'
                if is_reply else 'Thank you for contacting us. We are sorry for the inconvenience with your journey.')
    questions = []
    for item in missing:
        question = QUESTIONS[item.name][1]
        if item.reason.startswith('The supplied evidence contains different values.'):
            question = 'We found differing details in the information provided. ' + question
        questions.append('- ' + question)
    return (greeting + '\n\nTo continue reviewing your request, we need a little more information:\n'
            + '\n'.join(questions)
            + '\n\nPlease reply to this message with the missing details. You do not need to resend anything already provided. '
            'You may hide unrelated personal details on documents.\n\nThank you for your help,\nYour Customer Care team')
