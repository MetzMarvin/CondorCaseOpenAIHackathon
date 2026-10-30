from pathlib import Path

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    subject: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="NEW")
    owner: Mapped[str] = mapped_column(String, default="AI")
    queue: Mapped[str | None] = mapped_column(String, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)
    internal_notes: Mapped[str] = mapped_column(Text, default="")
    assessment: Mapped[dict] = mapped_column(JSON, default=dict)


class Message(Base):
    __tablename__ = "messages"
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String, unique=True, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    channel: Mapped[str] = mapped_column(String)
    direction: Mapped[str] = mapped_column(String, default="INBOUND")
    sender: Mapped[str] = mapped_column(String)
    subject: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[str] = mapped_column(String)
    in_reply_to: Mapped[str | None] = mapped_column(ForeignKey("messages.id"), nullable=True)
    customer_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    stored_example: Mapped[bool] = mapped_column(Boolean, default=False)
    fingerprint: Mapped[str | None] = mapped_column(String, nullable=True)
    receipt: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Attachment(Base):
    __tablename__ = "attachments"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), index=True)
    filename: Mapped[str] = mapped_column(String)
    media_type: Mapped[str] = mapped_column(String)
    size: Mapped[int] = mapped_column(Integer)
    storage_name: Mapped[str] = mapped_column(String)


class Event(Base):
    __tablename__ = "events"
    __table_args__ = {"sqlite_autoincrement": True}
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String, unique=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    type: Mapped[str] = mapped_column(String)
    step_id: Mapped[str | None] = mapped_column(String, nullable=True)
    timestamp: Mapped[str] = mapped_column(String)
    summary: Mapped[str] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSON)


class Preparation(Base):
    __tablename__ = "preparations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    case_version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String, default="PENDING")
    attempt: Mapped[str | None] = mapped_column(String, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class PreparationRequest(Base):
    __tablename__ = "preparation_requests"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    preparation_id: Mapped[str] = mapped_column(String)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Database:
    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.attachments = data_dir / "attachments"
        self.attachments.mkdir(exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{(data_dir / 'care-hub.sqlite3').as_posix()}",
            connect_args={"check_same_thread": False, "timeout": 15},
        )

        @event.listens_for(self.engine, "connect")
        def configure(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(self.engine, expire_on_commit=False)
