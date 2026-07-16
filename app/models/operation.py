from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    DECIMAL,
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database.base import Base
from app.constants import CallbackResult, EventType, IntentStatus, OperationStatus


class Operation(Base):
    __tablename__ = "operations"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(19, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[OperationStatus] = mapped_column(
        SQLEnum(OperationStatus), nullable=False)
    provider_payment_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class Event(Base):
    __tablename__ = "events"

    event_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True)
    operation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[EventType] = mapped_column(
        SQLEnum(EventType), nullable=False)
    from_status: Mapped[Optional[OperationStatus]] = mapped_column(
        SQLEnum(OperationStatus), nullable=True)
    to_status: Mapped[OperationStatus] = mapped_column(
        SQLEnum(OperationStatus), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("operation_id", "event_type",
                         "to_status", name="uq_operation_event_transition"),
    )


class SubmitIntent(Base):
    __tablename__ = "submit_intents"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True)
    operation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[IntentStatus] = mapped_column(
        SQLEnum(IntentStatus), nullable=False)
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0)
    next_retry_at: Mapped[Optional[datetime]
                          ] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        UniqueConstraint("operation_id", name="uq_submit_intent_operation"),
        Index(
            "idx_intents_pending",
            "status",
            "next_retry_at",
            postgresql_where="status IN ('PENDING', 'FAILED')",
        ),
    )


class ProcessedCallback(Base):
    __tablename__ = "processed_callbacks"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True)
    provider_payment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False)
    operation_id: Mapped[str] = mapped_column(String(255), nullable=False)
    result: Mapped[CallbackResult] = mapped_column(
        SQLEnum(CallbackResult), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("provider_payment_id", "operation_id",
                         name="uq_processed_callback"),
    )
