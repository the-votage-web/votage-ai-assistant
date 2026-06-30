import uuid
from sqlalchemy import String, Date, DateTime, ForeignKey, UniqueConstraint, func, Text, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from typing import Optional
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Member(Base):
    __tablename__ = "members"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(254), unique=True, nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    gender: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    marital_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    first_timer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    connect_name: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    date_joined: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Service(Base):
    __tablename__ = "service"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    theme: Mapped[str] = mapped_column(String(80), nullable=True)
    location: Mapped[str] = mapped_column(String(80), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ConnectGroup(Base):
    __tablename__ = "connect_group"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("service.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(254), nullable=False)
    meeting_time: Mapped[str] = mapped_column(String(80), nullable=False)
    meeting_day: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

class ConnectGroupMember(Base):
    __tablename__ = "connect_group_members"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connect_group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("connect_group.id"), nullable=False)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())
    left_at:Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class Attendance(Base):
    __tablename__ = "attendance"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)
    service_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("service.id"), nullable=True)
    service_type: Mapped[str] = mapped_column(String(32), nullable=False, default="sunday_service")
    connect_name: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    service_date: Mapped[str] = mapped_column(Date, nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "member_id",
            "service_date",
            "service_type",
            "connect_name",
            name="uq_member_day_service_connect",
        ),
    )

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)   # frontend session id
    state_json: Mapped[str] = mapped_column(Text, default="{}")    # to store pending questions, etc.
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())



class FirstTimerEvent(Base):
    __tablename__ = "first_timer_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)
    service_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("service.id"), nullable=True)
    service_type: Mapped[str] = mapped_column(String(32), nullable=False, default="sunday_service")
    service_name: Mapped[str] = mapped_column(String(120), nullable=False)
    service_date: Mapped[str] = mapped_column(Date, nullable=False)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("member_id", "service_date", "service_name", name="uq_first_timer_member_day_event"),
    )


class ChatLog(Base):
    """One row per chatbot question: the question, the bot's answer, whether it
    was actually answered, and the best similarity score (for review/tuning)."""
    __tablename__ = "chat_logs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answered: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    top_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class KbEntry(Base):
    """Admin-authored knowledge. Stored in the DB (not faq.md) so it survives
    deploys and is used by the bot live. Mirrored into faq_embeddings for search."""
    __tablename__ = "kb_entries"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False, default="admin")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    exported_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
