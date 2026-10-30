import hashlib
import io
import json
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from uuid import uuid4

from PIL import Image
from pypdf import PdfReader
from sqlalchemy import select, text

from .intake_contracts import InboundMessage, IntakeReceipt
from .database import Attachment, Case, Database, Event, Message

MAX_FILES = 5
MAX_FILE_BYTES = 10 * 1024 * 1024


class IntakeError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class IncomingFile:
    filename: str
    media_type: str
    content: bytes


def validate_file(file: IncomingFile):
    if len(file.content) > MAX_FILE_BYTES:
        raise IntakeError(422, "FILE_TOO_LARGE", "Each file must be no larger than 10 MB.")
    name = PurePosixPath(file.filename.replace("\\", "/")).name
    if not name or len(name) > 240 or any(ord(c) < 32 for c in name):
        raise IntakeError(422, "INVALID_FILENAME", "Please use a valid filename.")
    suffix = PurePosixPath(name).suffix.lower()
    types = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
    media = types.get(suffix)
    if not media or file.media_type not in (media, "application/octet-stream", ""):
        raise IntakeError(422, "UNSUPPORTED_FILE", "Only PDF, JPEG and PNG files are supported.")
    try:
        if media == "application/pdf":
            if not file.content.startswith(b"%PDF-"):
                raise ValueError("Invalid PDF header")
            reader = PdfReader(io.BytesIO(file.content), strict=True)
            if reader.is_encrypted or len(reader.pages) == 0:
                raise ValueError("Encrypted or empty PDF")
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(file.content)) as picture:
                    if picture.format != ("PNG" if media == "image/png" else "JPEG"):
                        raise ValueError("Wrong image format")
                    picture.verify()
                with Image.open(io.BytesIO(file.content)) as picture:
                    picture.load()
    except Exception as exc:
        raise IntakeError(422, "INVALID_FILE_CONTENT", "This file is damaged, encrypted or does not match its stated format.") from exc
    return IncomingFile(name, media, file.content)


def record_intake_events(session, case, message_id, timestamp, seeded=False):
    for kind, step, summary in (
        ("step.completed", "intake", "Message and evidence saved"),
        ("case.updated", None, "Case updated"),
    ):
        session.add(Event(
            id=f"evt-{uuid4().hex}", case_id=case.id, type=kind, step_id=step,
            timestamp=timestamp, summary=summary,
            data={"messageId": message_id, "caseVersion": case.version, "simulation": True, "storedExample": seeded},
        ))


class IntakeService:
    def __init__(self, db: Database):
        self.db = db

    def accept(self, payload: InboundMessage, files: list[IncomingFile]):
        if len(files) > MAX_FILES:
            raise IntakeError(422, "TOO_MANY_FILES", "You can attach up to five files per message.")
        files = [validate_file(file) for file in files]
        canonical = {"message": payload.model_dump(by_alias=True), "files": [
            {"filename": f.filename, "mediaType": f.media_type, "sha256": hashlib.sha256(f.content).hexdigest()}
            for f in files
        ]}
        fingerprint = hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        written = []
        try:
            with self.db.session() as session:
                # Acquire the SQLite writer lock before checking idempotency or case state.
                session.execute(text("BEGIN IMMEDIATE"))
                prior = session.scalar(select(Message).where(Message.id == payload.message_id))
                if prior:
                    if prior.fingerprint != fingerprint or prior.receipt is None:
                        raise IntakeError(409, "IDEMPOTENCY_CONFLICT", "This message ID has already been used for different content.")
                    return IntakeReceipt.model_validate(prior.receipt)

                timestamp = now()
                if payload.case_id:
                    case = session.get(Case, payload.case_id)
                    if not case:
                        raise IntakeError(404, "CASE_NOT_FOUND", "The specified case was not found.")
                    if payload.in_reply_to:
                        parent = session.scalar(select(Message).where(Message.id == payload.in_reply_to))
                        if not parent or parent.case_id != case.id or not parent.customer_visible:
                            raise IntakeError(409, "REPLY_REFERENCE_CONFLICT", "The parent message does not belong to this case.")
                    if case.status in ("WAITING_FOR_CUSTOMER", "RESOLVED", "CLOSED"):
                        case.status = "IN_PROGRESS"
                    case.version += 1
                    case.updated_at = timestamp
                else:
                    case = Case(id=f"case-{uuid4().hex}", subject=payload.subject, status="NEW", owner="AI",
                                version=1, created_at=timestamp, updated_at=timestamp)
                    session.add(case)
                    session.flush()

                receipt = IntakeReceipt(messageId=payload.message_id, caseId=case.id,
                                        caseVersion=case.version, customerCaseUrl=f"/portal/cases/{case.id}")
                session.add(Message(
                    id=payload.message_id, case_id=case.id, channel=payload.channel, sender=payload.sender,
                    subject=payload.subject, body=payload.body, timestamp=timestamp,
                    in_reply_to=payload.in_reply_to, fingerprint=fingerprint, receipt=receipt.model_dump(by_alias=True),
                ))
                session.flush()
                for file in files:
                    attachment_id = f"att-{uuid4().hex}"
                    destination = self.db.attachments / attachment_id
                    written.append(destination)
                    with destination.open("xb") as target:
                        target.write(file.content)
                    session.add(Attachment(
                        id=attachment_id, case_id=case.id, message_id=payload.message_id,
                        filename=file.filename, media_type=file.media_type, size=len(file.content), storage_name=attachment_id,
                    ))
                record_intake_events(session, case, payload.message_id, timestamp)
                from .preparation import enqueue
                enqueue(session, case)
                session.commit()
                return receipt
        except Exception:
            for path in written:
                path.unlink(missing_ok=True)
            raise
