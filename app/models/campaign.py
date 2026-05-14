import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.constants.app_constants import CampaignType, CampaignStatus


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    campaign_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=CampaignType.PAYMENT_REMINDER
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CampaignStatus.DRAFT
    )
    company_name: Mapped[str] = mapped_column(
        String(200), nullable=False, default="NexusAI"
    )
    system_prompt_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    retry_delay_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60
    )
    scheduled_start: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    scheduled_end: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    call_window_start: Mapped[str] = mapped_column(
        String(5), nullable=False, default="09:00"
    )
    call_window_end: Mapped[str] = mapped_column(
        String(5), nullable=False, default="18:00"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    call_records: Mapped[list["CallRecord"]] = relationship(  # noqa: F821
        "CallRecord", back_populates="campaign", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Campaign id={self.id} name={self.name} type={self.campaign_type}>"