from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CallRecordCreate(BaseModel):
    customer_id: str
    campaign_id: str
    attempt_number: int = 1


class CallRecordUpdate(BaseModel):
    twilio_call_sid: Optional[str] = None
    status: Optional[str] = None
    outcome: Optional[str] = None
    duration_seconds: Optional[int] = None
    error_message: Optional[str] = None
    notes: Optional[str] = None
    initiated_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class ConversationTurnResponse(BaseModel):
    id: str
    turn_number: int
    speaker: str
    message: str
    intent_detected: Optional[str]
    confidence_score: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class CallRecordResponse(BaseModel):
    id: str
    customer_id: str
    campaign_id: str
    twilio_call_sid: Optional[str]
    status: str
    outcome: Optional[str]
    attempt_number: int
    duration_seconds: Optional[int]
    error_message: Optional[str]
    notes: Optional[str]
    initiated_at: Optional[datetime]
    answered_at: Optional[datetime]
    ended_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    conversations: list[ConversationTurnResponse] = []

    model_config = {"from_attributes": True}


class CallRecordListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[CallRecordResponse]