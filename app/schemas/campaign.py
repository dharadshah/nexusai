from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from app.constants.app_constants import CampaignType, CampaignStatus


class CampaignCreate(BaseModel):
    name: str
    description: Optional[str] = None
    campaign_type: str = CampaignType.PAYMENT_REMINDER
    company_name: str = "NexusAI"
    system_prompt_override: Optional[str] = None
    max_retries: int = 3
    retry_delay_minutes: int = 60
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    call_window_start: str = "09:00"
    call_window_end: str = "18:00"

    @field_validator("campaign_type")
    @classmethod
    def validate_campaign_type(cls, v: str) -> str:
        if v not in CampaignType.ALL:
            raise ValueError(f"campaign_type must be one of: {CampaignType.ALL}")
        return v

    @field_validator("max_retries")
    @classmethod
    def validate_max_retries(cls, v: int) -> int:
        if not 1 <= v <= 10:
            raise ValueError("max_retries must be between 1 and 10")
        return v


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    company_name: Optional[str] = None
    system_prompt_override: Optional[str] = None
    max_retries: Optional[int] = None
    retry_delay_minutes: Optional[int] = None
    scheduled_start: Optional[datetime] = None
    scheduled_end: Optional[datetime] = None
    call_window_start: Optional[str] = None
    call_window_end: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is None:
            return v
        valid = [
            CampaignStatus.DRAFT,
            CampaignStatus.ACTIVE,
            CampaignStatus.PAUSED,
            CampaignStatus.COMPLETED,
            CampaignStatus.ARCHIVED,
        ]
        if v not in valid:
            raise ValueError(f"status must be one of: {valid}")
        return v


class CampaignResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    campaign_type: str
    status: str
    company_name: str
    max_retries: int
    retry_delay_minutes: int
    scheduled_start: Optional[datetime]
    scheduled_end: Optional[datetime]
    call_window_start: str
    call_window_end: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CampaignListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[CampaignResponse]