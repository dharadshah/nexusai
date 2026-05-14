import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    call_record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("call_records.id"), nullable=False
    )
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    speaker: Mapped[str] = mapped_column(
        String(10), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent_detected: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence_score: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    call_record: Mapped["CallRecord"] = relationship(  # noqa: F821
        "CallRecord", back_populates="conversations"
    )

    def __repr__(self) -> str:
        return (
            f"<Conversation id={self.id} call={self.call_record_id} "
            f"turn={self.turn_number} speaker={self.speaker}>"
        )