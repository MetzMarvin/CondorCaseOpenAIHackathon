import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfWriter
from sqlalchemy import func, select

from backend.database import Attachment, Case, Event, Message
from backend.main import create_app


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path)) as test_client:
        yield test_client


def message(**changes):
    return {"messageId": "msg-test", "channel": "PORTAL", "sender": "demo@example.com",
            "subject": "My claim", "body": "  My suitcase is missing.\nPlease help me.  ", **changes}


def image_bytes(color="white", format="PNG"):
    target = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(target, format=format)
    return target.getvalue()


def pdf_bytes():
    target = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(target)
    return target.getvalue()


def upload(client, payload, files=None):
    return client.post("/api/inbound/messages", data={"metadata": json.dumps(payload)},
                       files=files or [("files", ("beleg.png", image_bytes(), "image/png"))])


def counts(client):
    with client.app.state.db.session() as session:
        return tuple(session.scalar(select(func.count()).select_from(model)) for model in (Case, Message, Attachment, Event))


def test_seed_and_new_intake_do_not_process_or_handoff(client):
    assert len(client.get("/api/cases").json()) == 10
    assert client.get("/api/health").json()["scope"] == "intake-and-preparation"
    for index, channel in enumerate(("PORTAL", "EMAIL")):
        payload = message(messageId=f"msg-{index}", channel=channel)
        response = client.post("/api/inbound/messages", json=payload)
        assert response.status_code == 200
        receipt = response.json()
        case = client.get(f"/api/portal/cases/{receipt['caseId']}").json()
        assert case["status"] == "NEW" and case["caseVersion"] == 1
        assert len(case["messages"]) == 1
        assert case["messages"][0]["body"] == payload["body"]
        assert case["messages"][0]["channel"] == channel
    assert len(client.get("/api/cases").json()) == 12  # No matching by subject or sender.


def test_cross_channel_reply_preserves_case_and_download(client):
    before = counts(client)
    response = upload(client, message(caseId="case-evidence"))
    assert response.status_code == 200
    assert response.json()["caseId"] == "case-evidence"
    detail = client.get("/api/portal/cases/case-evidence").json()
    assert detail["status"] == "NEW" and detail["caseVersion"] == 2
    assert len(detail["messages"]) == 2
    attachment = detail["messages"][-1]["attachments"][0]
    download = client.get(attachment["url"])
    assert download.content == image_bytes()
    assert download.headers["content-type"] == "image/png"
    assert "attachment" in download.headers["content-disposition"]
    assert counts(client) == (before[0], before[1] + 1, before[2] + 1, before[3] + 4)
    wrong_url = attachment["url"].replace("case-evidence", "case-clear")
    assert client.get(wrong_url).status_code == 404


def test_idempotency_covers_files_and_original_receipt(client):
    payload = message(caseId="case-evidence")
    first = upload(client, payload)
    initial_counts = counts(client)
    assert upload(client, payload).json() == first.json()
    assert counts(client) == initial_counts
    assert len(list(client.app.state.db.attachments.iterdir())) == 1
    changed = upload(client, payload, [("files", ("beleg.png", image_bytes("red"), "image/png"))])
    assert changed.status_code == 409
    assert counts(client) == initial_counts
    client.post("/api/inbound/messages", json=message(messageId="later", caseId="case-evidence"))
    assert upload(client, payload).json() == first.json()  # Original version, even after a later reply.
    assert client.post("/api/inbound/messages", json=message(messageId="later", caseId="case-evidence", body="changed")).status_code == 409


def test_concurrent_duplicates_create_once(client):
    before = counts(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.post("/api/inbound/messages", json=message()), range(2)))
    assert [r.status_code for r in results] == [200, 200]
    assert results[0].json() == results[1].json()
    assert counts(client) == (before[0] + 1, before[1] + 1, before[2], before[3] + 4)


@pytest.mark.parametrize("changes,status", [
    ({"caseId": "missing"}, 404),
    ({"caseId": "case-evidence", "inReplyTo": "msg-case-clear-in"}, 409),
    ({"caseId": "case-evidence", "inReplyTo": "missing"}, 409),
    ({"channel": "EMAIL", "caseId": "case-evidence"}, 422),
    ({"inReplyTo": "msg-case-evidence-in"}, 422),
    ({"sender": "not-an-email"}, 422),
    ({"subject": "  "}, 422),
    ({"body": "\n "}, 422),
    ({"attachmentIds": ["att-foreign"]}, 422),
])
def test_invalid_input_leaves_no_records(client, changes, status):
    before = counts(client)
    response = upload(client, message(**changes))
    assert response.status_code == status, response.text
    assert counts(client) == before
    assert not list(client.app.state.db.attachments.iterdir())


def test_email_reply_parent_is_stored(client):
    result = client.post("/api/inbound/messages", json=message(channel="EMAIL", caseId="case-evidence", inReplyTo="msg-case-evidence-in"))
    assert result.status_code == 200
    detail = client.get("/api/portal/cases/case-evidence").json()
    assert detail["messages"][-1]["inReplyTo"] == "msg-case-evidence-in"


@pytest.mark.parametrize("filename,content,media", [
    ("script.html", b"<script>alert(1)</script>", "text/html"),
    ("fake.png", b"not an image", "image/png"),
    ("fake.pdf", b"%PDF-1.7\nnot a document", "application/pdf"),
    ("wrong.png", image_bytes(format="JPEG"), "image/png"),
    ("large.png", b"x" * (10 * 1024 * 1024 + 1), "image/png"),
])
def test_invalid_file_atomic_rejection(client, filename, content, media):
    before = counts(client)
    response = upload(client, message(), [("files", ("valid.png", image_bytes(), "image/png")), ("files", (filename, content, media))])
    assert response.status_code == 422, response.text
    assert counts(client) == before
    assert not list(client.app.state.db.attachments.iterdir())


def test_all_supported_formats_and_file_limit(client):
    files = [("files", ("rechnung.pdf", pdf_bytes(), "application/pdf")),
             ("files", ("foto.jpg", image_bytes(format="JPEG"), "image/jpeg")),
             ("files", ("../beleg.png", image_bytes(), "image/png"))]
    response = upload(client, message(), files)
    assert response.status_code == 200
    detail = client.get(f"/api/portal/cases/{response.json()['caseId']}").json()
    assert [a["filename"] for a in detail["messages"][0]["attachments"]] == ["rechnung.pdf", "foto.jpg", "beleg.png"]
    before = counts(client)
    assert upload(client, message(messageId="too-many"), files * 2).status_code == 422
    assert counts(client) == before


def test_cleanup_after_disk_failure_and_retry(client, monkeypatch):
    original_open = Path.open
    writes = 0

    def failing_open(path, *args, **kwargs):
        nonlocal writes
        if args and args[0] == "xb" and path.parent == client.app.state.db.attachments:
            writes += 1
            if writes == 2:
                raise OSError("Simulated disk failure")
        return original_open(path, *args, **kwargs)

    before = counts(client)
    files = [("files", (f"beleg-{i}.png", image_bytes(), "image/png")) for i in range(2)]
    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", failing_open)
        assert upload(client, message(), files).status_code == 503
    assert counts(client) == before
    assert not list(client.app.state.db.attachments.iterdir())
    assert upload(client, message(), files).status_code == 200


@pytest.mark.parametrize("case_id,owner,queue,status", [
    ("case-human", "HUMAN", "CUSTOMER_SERVICE", "IN_PROGRESS"),
    ("case-serious", "QUEUE", "SPECIALIST", "WAITING_FOR_SPECIALIST"),
    ("case-resolved", "HUMAN", "CUSTOMER_SERVICE", "IN_PROGRESS"),
])
def test_reply_preserves_ownership_and_routing(client, case_id, owner, queue, status):
    if case_id == 'case-serious':
        with client.app.state.db.session() as session:
            c = session.get(Case, case_id)
            c.owner, c.queue, c.status = owner, queue, status
            session.commit()
    assert client.post("/api/inbound/messages", json=message(caseId=case_id)).status_code == 200
    with client.app.state.db.session() as session:
        case = session.get(Case, case_id)
        assert (case.owner, case.queue, case.status) == (owner, queue, status)


def test_portal_excludes_internal_records_and_files(client):
    with client.app.state.db.session() as session:
        session.add(Message(id="internal-message", case_id="case-clear", channel="EMAIL", direction="OUTBOUND",
                            sender="internal@example.com", subject="SECRET", body="PRIVATE", timestamp="2026-10-30T11:00:00Z", customer_visible=False))
        session.flush()
        session.add(Attachment(id="internal-file", case_id="case-clear", message_id="internal-message", filename="secret.pdf",
                               media_type="application/pdf", size=1, storage_name="secret"))
        session.commit()
    response = client.get("/api/portal/cases/case-clear")
    assert response.status_code == 200
    assert set(response.json()) == {"caseId", "subject", "status", "caseVersion", "createdAt", "updatedAt", "messages"}
    assert "SECRET" not in response.text and "PRIVATE" not in response.text and "fixtureExpectedAction" not in response.text
    assert len(response.json()["messages"]) == 1
    assert client.get("/api/cases/case-clear/attachments/internal-file").status_code == 404
    assert client.post("/api/inbound/messages", json=message(caseId="case-clear", inReplyTo="internal-message")).status_code == 409


def test_event_cursor_and_restart(tmp_path):
    with TestClient(create_app(tmp_path)) as first:
        result = upload(first, message()).json()
        url = f"/api/portal/cases/{result['caseId']}"
        detail = first.get(url).json()
        events = first.get(f"/api/events?caseId={result['caseId']}").json()
        assert [e["type"] for e in events["events"]] == ["step.completed", "case.updated", "step.started", "step.completed"]
        assert events["events"][0]["stepId"] == "intake"
        assert events["events"][0]["runId"] is None
        assert first.get(f"/api/events?after={events['cursor']}").json()["events"] == []
    with TestClient(create_app(tmp_path)) as restarted:
        assert restarted.get(url).json() == detail
        assert len(restarted.get("/api/cases").json()) == 11
        assert restarted.get(detail["messages"][0]["attachments"][0]["url"]).content == image_bytes()
        assert upload(restarted, message()).json() == result
        assert restarted.get("/api/cases?owner=HUMAN").status_code == 200
        assert restarted.get("/openapi.json").status_code == 200
