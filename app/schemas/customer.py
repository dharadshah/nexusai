from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator
import re

from app.constants.app_constants import CustomerStatus


class CustomerCreate(BaseModel):
    first_name: str
    last_name: str
    phone_number: str
    email: Optional[str] = None
    status: str = CustomerStatus.ACTIVE
    preferred_language: str = "en"
    timezone: str = "Asia/Kolkata"
    metadata_dict: Optional[dict] = {}

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        pattern = r"^\+?[1-9]\d{7,14}$"
        if not re.match(pattern, v):
            raise ValueError("Phone number must be in E.164 format e.g. +919876543210")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        valid = [CustomerStatus.ACTIVE, CustomerStatus.INACTIVE, CustomerStatus.DO_NOT_CALL]
        if v not in valid:
            raise ValueError(f"Status must be one of: {valid}")
        return v


class CustomerUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    preferred_language: Optional[str] = None
    timezone: Optional[str] = None
    metadata_dict: Optional[dict] = None

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str | None) -> str | None:
        if v is None:
            return v
        pattern = r"^\+?[1-9]\d{7,14}$"
        if not re.match(pattern, v):
            raise ValueError("Phone number must be in E.164 format e.g. +919876543210")
        return v


class CustomerResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    full_name: str
    phone_number: str
    email: Optional[str]
    status: str
    preferred_language: str
    timezone: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomerListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[CustomerResponse]