import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.constants.app_constants import CallStatus, CallOutcome


class CallRecord(Base):
    __tablename__ = "call_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False
    )
    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campaigns.id"), nullable=False
    )
    twilio_call_sid: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CallStatus.PENDING
    )
    outcome: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default=CallOutcome.UNRESOLVED
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    initiated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    customer: Mapped["Customer"] = relationship(  # noqa: F821
        "Customer", back_populates="call_records"
    )
    campaign: Mapped["Campaign"] = relationship(  # noqa: F821
        "Campaign", back_populates="call_records"
    )
    conversations: Mapped[list["Conversation"]] = relationship(  # noqa: F821
        "Conversation", back_populates="call_record", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<CallRecord id={self.id} customer={self.customer_id} "
            f"status={self.status} outcome={self.outcome}>"
        )