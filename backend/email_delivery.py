"""System 1 simulated delivery of authorized customer actions.

The case service must validate ownership, version, state and financial authority
before calling this adapter. This module does not apply actions or move money.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from pydantic import BaseModel

from backend.contracts import ProposedAction, RunResult


class Delivery(BaseModel):
    message_id: str
    action_id: str
    case_id: str
    recipient: str
    subject: str
    body: str
    timestamp: str
    simulation: bool = True


def _render(action: ProposedAction) -> tuple[str, str]:
    if action.type == 'REQUEST_INFORMATION':
        draft = action.payload.question_de
        fallback = 'More information needed for your case'
    elif action.type == 'RESOLVE':
        draft = action.payload.reply_de
        fallback = 'An update on your case'
    else:
        raise ValueError('HANDOFF contains internal context, not a customer email')
    case_id = action.case_id
    if any(char in case_id for char in '\r\n'):
        raise ValueError('Case reference must not contain line breaks')
    draft = draft.replace('\r\n', '\n').strip()
    if draft.startswith('Subject:'):
        subject_line, separator, body = draft.partition('\n\n')
        subject = subject_line.removeprefix('Subject:').strip()
        if not separator or '\n' in subject or '\r' in subject:
            raise ValueError('Expected a single Subject line followed by a blank line')
        if case_id not in subject:
            subject += f' [{case_id}]'
    else:
        subject, body = f'{fallback} {case_id}', draft
    if not subject or not body.strip():
        raise ValueError('Email subject and body must not be blank')
    return subject, body.strip()


class SimulatedEmailSender:
    """Durable local outbox; action IDs deduplicate across process restarts.

    No network delivery occurs. Use only after System 1 authorizes an action.
    The recipient must come from the trusted case contact, not AI-generated text.
    """

    def __init__(self, database: str | Path):
        self.database = str(database)
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute('''CREATE TABLE IF NOT EXISTS email_outbox (
                action_id TEXT PRIMARY KEY,
                fingerprint TEXT NOT NULL,
                delivery TEXT NOT NULL
            )''')

    def send_authorized(self, action: ProposedAction, recipient: str) -> Delivery:
        if (not recipient.strip() or recipient != recipient.strip()
                or any(char in recipient for char in '\r\n')
                or recipient.count('@') != 1 or any(char.isspace() for char in recipient)
                or not all(recipient.split('@'))):
            raise ValueError('A single recipient email address is required')
        subject, body = _render(action)
        fingerprint = hashlib.sha256(json.dumps(
            {'action': action.model_dump(mode='json'), 'recipient': recipient},
            sort_keys=True, separators=(',', ':'),
        ).encode()).hexdigest()
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute('BEGIN IMMEDIATE')
            existing = connection.execute(
                'SELECT fingerprint, delivery FROM email_outbox WHERE action_id = ?',
                (action.action_id,),
            ).fetchone()
            if existing:
                if existing[0] != fingerprint:
                    raise ValueError('Action ID already used with different email content')
                return Delivery.model_validate_json(existing[1])
            delivery = Delivery(
                message_id='email-' + hashlib.sha256(action.action_id.encode()).hexdigest(),
                action_id=action.action_id, case_id=action.case_id, recipient=recipient,
                subject=subject, body=body, timestamp=datetime.now(timezone.utc).isoformat(),
            )
            connection.execute('INSERT INTO email_outbox VALUES (?, ?, ?)',
                               (action.action_id, fingerprint, delivery.model_dump_json()))
            return delivery


def main():
    parser = argparse.ArgumentParser(description='Simulate email delivery from a generated AI result; no email leaves this machine.')
    parser.add_argument('--result', type=Path, required=True, help='RunResult JSON file (not JSONL)')
    parser.add_argument('--to', required=True, help='Demo customer email address')
    parser.add_argument('--database', type=Path, default=Path('email-outbox.sqlite3'))
    args = parser.parse_args()
    try:
        result = RunResult.model_validate_json(args.result.read_text())
        if result.status != 'SUCCEEDED' or result.proposed_action is None:
            raise ValueError('Cannot send email for a failed AI run')
        delivery = SimulatedEmailSender(args.database).send_authorized(result.proposed_action, args.to)
    except (ValueError, OSError, sqlite3.Error) as error:
        parser.error(str(error))
    print(delivery.model_dump_json(indent=2))


if __name__ == '__main__':
    main()
