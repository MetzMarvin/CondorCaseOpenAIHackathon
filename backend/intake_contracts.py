"""Intake-specific models built on the shared backend contract conventions.

Case summaries and process events use the shared types without a parallel schema.
"""
from typing import Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from .contracts import CaseStatus, CaseSummary, Contract, EventPage

EventFeed = EventPage


class InboundMessage(Contract):
    message_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    channel: Literal["PORTAL", "EMAIL"]
    sender: str = Field(min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=20000)
    case_id: str | None = Field(default=None, min_length=1, max_length=128)
    in_reply_to: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("subject", "body")
    @classmethod
    def non_blank(cls, value):
        if not value.strip():
            raise ValueError("Please complete this field.")
        return value

    @model_validator(mode="after")
    def reply_reference(self):
        if self.in_reply_to and not self.case_id:
            raise ValueError("A reply requires a case reference.")
        if self.case_id and self.channel == "EMAIL" and not self.in_reply_to:
            raise ValueError("An email reply requires a parent message reference.")
        return self


class IntakeReceipt(Contract):
    message_id: str
    case_id: str
    case_version: int
    customer_case_url: str


class AttachmentView(Contract):
    attachment_id: str
    filename: str
    media_type: str
    size: int
    url: str


class MessageView(Contract):
    message_id: str
    channel: Literal["PORTAL", "EMAIL"]
    direction: Literal["INBOUND", "OUTBOUND"]
    sender: str
    subject: str
    body: str
    timestamp: AwareDatetime
    in_reply_to: str | None
    stored_example: bool
    attachments: tuple[AttachmentView, ...]


class PortalCase(Contract):
    case_id: str
    subject: str
    status: CaseStatus
    case_version: int
    created_at: AwareDatetime
    updated_at: AwareDatetime
    messages: tuple[MessageView, ...]
