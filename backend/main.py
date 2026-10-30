import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException

from .intake_contracts import CaseSummary, EventFeed, InboundMessage, IntakeReceipt, PortalCase
from .database import Attachment, Case, Database, Event, Message, Preparation
from .preparation import PreparationService, recover, view
from .contracts import ProcessRequest, CaseDetail, ProcessResponse, TakeoverRequest, ActionResponse, ProposedAction
from .operations import Operations, detail
from .fixtures import seed
from .intake import IncomingFile, IntakeError, IntakeService, MAX_FILE_BYTES

logger = logging.getLogger(__name__)


def create_app(data_dir: Path | None = None, seed_demo: bool = True):
    @asynccontextmanager
    async def lifespan(app):
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
        folder = data_dir or Path(os.environ.get("CONDOR_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
        app.state.db = Database(folder)
        if seed_demo:
            seed(app.state.db)
        recover(app.state.db)
        app.state.preparation = PreparationService(app.state.db)
        app.state.operations = Operations(app.state.db, app.state.preparation)
        app.state.operations.recover()
        yield
        app.state.db.engine.dispose()

    app = FastAPI(title="Condor Care Hub · Intake demo", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(IntakeError)
    async def intake_error(_, exc):
        return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message, "currentCaseVersion": getattr(exc, "current_version", None)}})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_, exc):
        return JSONResponse(status_code=422, content={"error": {"code": "INVALID_INPUT", "message": "Please check your input."}})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "simulation": True, "scope": "intake-and-preparation"}

    @app.post("/api/inbound/messages", response_model=IntakeReceipt, openapi_extra={
        "requestBody": {"required": True, "content": {
            "application/json": {"schema": InboundMessage.model_json_schema()},
            "multipart/form-data": {"schema": {"type": "object", "required": ["metadata"], "properties": {
                "metadata": {"type": "string", "description": "JSON-encoded InboundMessage; same schema as application/json"},
                "files": {"type": "array", "maxItems": 5, "items": {"type": "string", "format": "binary"}},
            }}},
        }},
    })
    async def inbound(request: Request):
        files = []
        media_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
        try:
            if media_type == "application/json":
                raw = await request.body()
                if len(raw) > 128 * 1024:
                    raise IntakeError(422, "MESSAGE_TOO_LARGE", "The message is too large.")
                payload = InboundMessage.model_validate_json(raw)
            elif media_type == "multipart/form-data":
                async with request.form(max_files=5, max_fields=1, max_part_size=128 * 1024) as form:
                    if set(form.keys()) - {"metadata", "files"} or len(form.getlist("metadata")) != 1:
                        raise IntakeError(422, "INVALID_INPUT", "The message metadata or files are invalid.")
                    payload = InboundMessage.model_validate_json(form["metadata"])
                    for upload in form.getlist("files"):
                        if not isinstance(upload, UploadFile):
                            raise IntakeError(422, "INVALID_INPUT", "Please select a valid file.")
                        content = await upload.read(MAX_FILE_BYTES + 1)
                        if len(content) > MAX_FILE_BYTES:
                            raise IntakeError(422, "FILE_TOO_LARGE", "Each file must be no larger than 10 MB.")
                        files.append(IncomingFile(upload.filename or "", upload.content_type or "", content))
            else:
                raise IntakeError(415, "UNSUPPORTED_CONTENT_TYPE", "Please send JSON or a multipart form with files.")
        except (ValidationError, ValueError, TypeError, KeyError) as exc:
            raise IntakeError(422, "INVALID_INPUT", "Please check the email address, subject, message and reply reference.") from exc
        except HTTPException as exc:
            raise IntakeError(422, "INVALID_MULTIPART", "Please send up to five files with valid message metadata.") from exc
        try:
            receipt = await run_in_threadpool(IntakeService(request.app.state.db).accept, payload, files)
            try:
                await run_in_threadpool(request.app.state.preparation.prepare, receipt.case_id, receipt.case_version)
            except Exception:
                logger.warning("Preparation remains recoverable through the internal queue")
            return receipt
        except IntakeError:
            raise
        except Exception as exc:
            logger.exception("Intake storage failed")
            raise IntakeError(503, "STORAGE_UNAVAILABLE", "Storage is currently unavailable. Please retry the same message.") from exc

    @app.get("/api/cases", response_model=list[CaseSummary])
    def cases(request: Request, status: str | None = None, queue: str | None = None, owner: str | None = None):
        with request.app.state.db.session() as session:
            query = select(Case).order_by(Case.updated_at.desc(), Case.id)
            for field, value in ((Case.status, status), (Case.queue, queue), (Case.owner, owner)):
                if value is not None:
                    query = query.where(field == value)
            return [detail(session, c) for c in session.scalars(query)]

    @app.get("/api/portal/cases/{case_id}", response_model=PortalCase)
    def portal_case(case_id: str, request: Request):
        with request.app.state.db.session() as session:
            case = session.get(Case, case_id)
            if not case:
                raise IntakeError(404, "CASE_NOT_FOUND", "This case was not found.")
            messages = []
            for msg in session.scalars(select(Message).where(Message.case_id == case_id, Message.customer_visible.is_(True)).order_by(Message.sequence)):
                attachments = [dict(
                    attachmentId=a.id, filename=a.filename, mediaType=a.media_type, size=a.size,
                    url=f"/api/cases/{case_id}/attachments/{a.id}",
                ) for a in session.scalars(select(Attachment).where(Attachment.message_id == msg.id))]
                messages.append(dict(messageId=msg.id, channel=msg.channel, direction=msg.direction, sender=msg.sender,
                                     subject=msg.subject, body=msg.body, timestamp=msg.timestamp, inReplyTo=msg.in_reply_to,
                                     storedExample=msg.stored_example, attachments=attachments))
            return dict(caseId=case.id, subject=case.subject, status=case.status, caseVersion=case.version,
                        createdAt=case.created_at, updatedAt=case.updated_at, messages=messages)

    @app.get("/api/cases/{case_id}/attachments/{attachment_id}")
    def attachment(case_id: str, attachment_id: str, request: Request):
        db = request.app.state.db
        with db.session() as session:
            row = session.scalar(select(Attachment).join(Message, Attachment.message_id == Message.id).where(
                Attachment.id == attachment_id, Attachment.case_id == case_id, Message.customer_visible.is_(True)))
            if not row:
                raise IntakeError(404, "ATTACHMENT_NOT_FOUND", "This attachment was not found.")
            path = (db.attachments / row.storage_name).resolve()
            if path.parent != db.attachments.resolve() or not path.is_file():
                raise IntakeError(404, "ATTACHMENT_NOT_FOUND", "This attachment is unavailable.")
            return FileResponse(path, media_type=row.media_type, filename=row.filename,
                                headers={"X-Content-Type-Options": "nosniff"})

    @app.get("/api/events", response_model=EventFeed)
    def events(request: Request, caseId: str | None = None, after: int = Query(default=0, ge=0)):
        with request.app.state.db.session() as session:
            query = select(Event).where(Event.sequence > after).order_by(Event.sequence).limit(200)
            if caseId:
                if not session.get(Case, caseId):
                    raise IntakeError(404, "CASE_NOT_FOUND", "This case was not found.")
                query = query.where(Event.case_id == caseId)
            rows = list(session.scalars(query))
            return {"events": [dict(eventId=e.id, caseId=e.case_id, sequence=e.sequence, runId=e.run_id, type=e.type,
                                    stepId=e.step_id, timestamp=e.timestamp, summary=e.summary, data=e.data) for e in rows],
                    "cursor": rows[-1].sequence if rows else after}

    @app.get("/api/preparation/queue")
    def preparation_queue(request: Request):
        with request.app.state.db.session() as session:
            return [view(row) for row in session.scalars(select(Preparation).order_by(Preparation.case_id, Preparation.case_version))]

    @app.get("/api/cases/{case_id}/preparation")
    def preparation_detail(case_id: str, request: Request):
        with request.app.state.db.session() as session:
            case = session.get(Case, case_id)
            if not case:
                raise IntakeError(404, "CASE_NOT_FOUND", "Case not found.")
            row = session.get(Preparation, f"{case_id}:{case.version}")
            if not row:
                raise IntakeError(404, "PREPARATION_NOT_FOUND", "Prepare this case first.")
            return view(row)

    @app.post("/api/cases/{case_id}/prepare")
    def prepare_case(case_id: str, payload: ProcessRequest, request: Request):
        return request.app.state.preparation.prepare(case_id, payload.expected_case_version, payload.request_id)

    @app.get('/api/cases/{case_id}', response_model=CaseDetail)
    def internal_case(case_id: str, request: Request):
        with request.app.state.db.session() as session:
            return detail(session, request.app.state.operations.get(session, case_id))

    @app.post('/api/cases/{case_id}/process', response_model=ProcessResponse)
    def process(case_id: str, payload: ProcessRequest, request: Request):
        return request.app.state.operations.process(case_id, payload)

    @app.post('/api/cases/{case_id}/takeover', response_model=CaseDetail)
    def takeover(case_id: str, payload: TakeoverRequest, request: Request):
        return request.app.state.operations.mutate(case_id, payload, takeover=True)

    @app.post('/api/cases/{case_id}/actions', response_model=ActionResponse)
    def action(case_id: str, payload: ProposedAction, request: Request):
        return request.app.state.operations.mutate(case_id, payload)

    return app


app = create_app()
