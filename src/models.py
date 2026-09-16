"""Persistent user, ticket, and decision models."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    tickets: Mapped[List["Ticket"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "order_value_inr IS NULL OR order_value_inr >= 0",
            name="ck_tickets_order_value_nonnegative",
        ),
        CheckConstraint(
            "days_since_delivery IS NULL OR days_since_delivery >= 0",
            name="ck_tickets_delivery_days_nonnegative",
        ),
        CheckConstraint(
            "days_since_dispatch IS NULL OR days_since_dispatch >= 0",
            name="ck_tickets_dispatch_days_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    message: Mapped[str] = mapped_column(Text)
    order_value_inr: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    days_since_delivery: Mapped[Optional[int]] = mapped_column(nullable=True)
    days_since_dispatch: Mapped[Optional[int]] = mapped_column(nullable=True)
    product_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    opened_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    order_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    user: Mapped[User] = relationship(back_populates="tickets")
    decision: Mapped[Optional["Decision"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", uselist=False
    )


class Decision(Base):
    __tablename__ = "decisions"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_decisions_confidence_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), unique=True
    )
    action: Mapped[str] = mapped_column(String(64))
    inferred_issue_type: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float)
    sources: Mapped[List[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    ticket: Mapped[Ticket] = relationship(back_populates="decision")
