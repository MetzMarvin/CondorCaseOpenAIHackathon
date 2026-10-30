"""Stable, synthetic scenarios shared with future AI and console work."""
from sqlalchemy import text

from .database import Case, Message
from .intake import record_intake_events

SCENARIOS = [
    {"id": "case-clear", "subject": "Compensation after a flight delay", "sender": "anna.beispiel@example.com",
     "body": "Hello, my flight DE1234 from Frankfurt to Palma on 28 October 2026 arrived four hours late. My booking reference is DEMO42. Please review my compensation claim.",
     "status": "NEW", "owner": "AI", "expectedAction": "RESOLVE"},
    {"id": "case-evidence", "subject": "Hotel expenses after cancellation", "sender": "ben.beispiel@example.com",
     "body": "My flight DE2345 on 27 October 2026 was cancelled. I had to book a hotel for one night. Please review reimbursement of these expenses.",
     "status": "WAITING_FOR_CUSTOMER", "owner": "AI", "expectedAction": "REQUEST_INFORMATION",
     "reply": "Please provide your hotel receipt and booking reference so we can review your claim."},
    {"id": "case-serious", "subject": "Injury during boarding", "sender": "clara.beispiel@example.com",
     "body": "I fell on the boarding stairs and needed medical treatment. Please ask the appropriate team to review this incident.",
     "status": "WAITING_FOR_SPECIALIST", "owner": "QUEUE", "queue": "SPECIALIST", "expectedAction": "HANDOFF"},
    {"id": "case-incomplete", "subject": "My suitcase is missing", "sender": "david.beispiel@example.com",
     "body": "My suitcase has not arrived. Can you help?",
     "status": "NEW", "owner": "AI", "expectedAction": "REQUEST_INFORMATION"},
    {"id": "case-human", "subject": "Question about a reimbursement", "sender": "eva.beispiel@example.com",
     "body": "I have a question about the reimbursement for my booking DEMO55.",
     "status": "WAITING_FOR_CUSTOMER", "owner": "HUMAN", "queue": "CUSTOMER_SERVICE", "expectedAction": None,
     "reply": "Please tell us which item your question relates to."},
    {"id": "case-resolved", "subject": "Confirmation for travel insurance", "sender": "farid.beispiel@example.com",
     "body": "Please confirm the delay of my flight DE3456 on 26 October 2026.",
     "status": "RESOLVED", "owner": "HUMAN", "queue": "CUSTOMER_SERVICE", "expectedAction": None,
     "reply": "The requested confirmation was provided in this stored demo example."},
]


# Preparation examples remain within the ten-case demo boundary.
from .extraction import SOPHIE
SCENARIOS.extend([
    dict(id='case-sophie',subject='Damaged bag',sender='sophie@example.com',body=SOPHIE,status='NEW',owner='AI',expectedAction=None),
    dict(id='case-unmatched',subject='Unknown customer',sender='unknown@example.com',body='My customer ID is 99999 and flight number is 87B6.',status='NEW',owner='AI',expectedAction=None),
    dict(id='case-ambiguous',subject='Several journeys',sender='repeat@example.com',body='My customer ID is 22222 and flight number is 87B6.',status='NEW',owner='AI',expectedAction=None),
    dict(id='case-conflicting',subject='Conflicting identifiers',sender='conflict@example.com',body='My customer ID is 12345. My customer ID is 99999.',status='NEW',owner='AI',expectedAction=None),
])


def seed(db):
    """Add missing fixtures only; never reset a participant's changes."""
    with db.session() as session:
        session.execute(text("BEGIN IMMEDIATE"))
        for index, scenario in enumerate(SCENARIOS):
            if session.get(Case, scenario["id"]):
                continue
            timestamp = f"2026-10-30T09:{index:02d}:00Z"
            case = Case(
                id=scenario["id"], subject=scenario["subject"], status=scenario["status"],
                owner=scenario["owner"], queue=scenario.get("queue"), version=2 if scenario.get("reply") else 1,
                created_at=timestamp, updated_at=timestamp,
                internal_notes="Internal demo note: do not show in the customer portal.",
                assessment={"fixtureExpectedAction": scenario["expectedAction"], "simulation": True},
            )
            session.add(case)
            session.flush()
            message_id = f"msg-{scenario['id']}-in"
            session.add(Message(
                id=message_id, case_id=case.id, channel="EMAIL", direction="INBOUND",
                sender=scenario["sender"], subject=scenario["subject"], body=scenario["body"],
                timestamp=timestamp, stored_example=True,
            ))
            session.flush()
            if scenario.get("reply"):
                session.add(Message(
                    id=f"msg-{scenario['id']}-out", case_id=case.id, channel="EMAIL", direction="OUTBOUND",
                    sender="service@condor-demo.example", subject=f"Re: {case.subject}", body=scenario["reply"],
                    timestamp=f"2026-10-30T09:{index:02d}:30Z", in_reply_to=message_id, stored_example=True,
                ))
            record_intake_events(session, case, message_id, timestamp, seeded=True)
        from .preparation import enqueue
        from sqlalchemy import select
        for case in session.scalars(select(Case)):
            enqueue(session, case)
        session.commit()
