import uuid
import json
from datetime import datetime

from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.constants.app_constants import CustomerStatus


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=CustomerStatus.ACTIVE
    )
    preferred_language: Mapped[str] = mapped_column(
        String(10), nullable=False, default="en"
    )
    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Asia/Kolkata"
    )
    _metadata: Mapped[str | None] = mapped_column(
        "metadata", Text, nullable=True, default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    call_records: Mapped[list["CallRecord"]] = relationship(  # noqa: F821
        "CallRecord", back_populates="customer", cascade="all, delete-orphan"
    )

    @property
    def metadata_dict(self) -> dict:
        try:
            return json.loads(self._metadata or "{}")
        except (json.JSONDecodeError, TypeError):
            return {}

    @metadata_dict.setter
    def metadata_dict(self, value: dict) -> None:
        self._metadata = json.dumps(value)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Customer id={self.id} name={self.full_name} phone={self.phone_number}>"