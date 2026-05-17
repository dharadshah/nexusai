import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.call_record import CallRecord
from app.models.customer import Customer
from app.models.campaign import Campaign
from app.schemas.call_record import (
    CallRecordCreate,
    CallRecordUpdate,
    CallRecordResponse,
    CallRecordListResponse,
)
from app.constants.messages import (
    CALL_NOT_FOUND,
    CALL_INITIATED,
    CALL_INITIATION_FAILED,
    CUSTOMER_NOT_FOUND,
    CAMPAIGN_NOT_FOUND,
    DO_NOT_CALL_RESTRICTED,
)
from app.constants.app_constants import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    CustomerStatus,
    CallStatus,
)
from app.services.twilio_service import initiate_call

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calls", tags=["Calls"])


@router.post("/", response_model=dict, status_code=201)
def create_call_record(payload: CallRecordCreate, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == payload.customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=404,
            detail=CUSTOMER_NOT_FOUND.format(customer_id=payload.customer_id),
        )
    if customer.status == CustomerStatus.DO_NOT_CALL:
        raise HTTPException(status_code=403, detail=DO_NOT_CALL_RESTRICTED)

    campaign = db.query(Campaign).filter(Campaign.id == payload.campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=CAMPAIGN_NOT_FOUND.format(campaign_id=payload.campaign_id),
        )

    call_record = CallRecord(
        customer_id=payload.customer_id,
        campaign_id=payload.campaign_id,
        attempt_number=payload.attempt_number,
    )
    db.add(call_record)
    db.commit()
    db.refresh(call_record)

    return {
        "message": "Call record created successfully.",
        "data": CallRecordResponse.model_validate(call_record),
    }


@router.post("/{call_id}/initiate", response_model=dict)
def initiate_call_endpoint(call_id: str, db: Session = Depends(get_db)):
    """
    Trigger an actual outbound Twilio call for an existing call record.
    """
    call_record = db.query(CallRecord).filter(CallRecord.id == call_id).first()
    if not call_record:
        raise HTTPException(
            status_code=404,
            detail=CALL_NOT_FOUND.format(call_id=call_id),
        )

    # Prevent duplicate calls
    if call_record.status == CallStatus.IN_PROGRESS:
        raise HTTPException(status_code=409, detail="Call is already in progress.")

    customer = db.query(Customer).filter(
        Customer.id == call_record.customer_id
    ).first()
    if not customer:
        raise HTTPException(
            status_code=404,
            detail=CUSTOMER_NOT_FOUND.format(customer_id=call_record.customer_id),
        )
    if customer.status == CustomerStatus.DO_NOT_CALL:
        raise HTTPException(status_code=403, detail=DO_NOT_CALL_RESTRICTED)

    try:
        result = initiate_call(
            to_phone_number=customer.phone_number,
            call_record_id=call_record.id,
            customer_name=customer.full_name,
        )

        # Update call record with Twilio SID
        call_record.twilio_call_sid = result["call_sid"]
        call_record.status = CallStatus.IN_PROGRESS
        call_record.initiated_at = datetime.utcnow()
        db.commit()
        db.refresh(call_record)

        logger.info(
            f"Call initiated: record={call_id} "
            f"SID={result['call_sid']} "
            f"to={customer.phone_number}"
        )

        return {
            "message": CALL_INITIATED,
            "call_sid": result["call_sid"],
            "twilio_status": result["status"],
            "data": CallRecordResponse.model_validate(call_record),
        }

    except Exception as e:
        # Mark call as failed in DB
        call_record.status = CallStatus.FAILED
        call_record.error_message = str(e)
        db.commit()
        logger.error(f"Call initiation failed for record {call_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=CALL_INITIATION_FAILED.format(error=str(e)),
        )


@router.get("/", response_model=CallRecordListResponse)
def list_call_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    status: str | None = Query(None),
    outcome: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(CallRecord).options(joinedload(CallRecord.conversations))
    if status:
        query = query.filter(CallRecord.status == status)
    if outcome:
        query = query.filter(CallRecord.outcome == outcome)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return CallRecordListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[CallRecordResponse.model_validate(c) for c in items],
    )


@router.get("/customer/{customer_id}", response_model=CallRecordListResponse)
def get_calls_by_customer(
    customer_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=404,
            detail=CUSTOMER_NOT_FOUND.format(customer_id=customer_id),
        )

    query = (
        db.query(CallRecord)
        .options(joinedload(CallRecord.conversations))
        .filter(CallRecord.customer_id == customer_id)
    )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return CallRecordListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[CallRecordResponse.model_validate(c) for c in items],
    )


@router.get("/campaign/{campaign_id}", response_model=CallRecordListResponse)
def get_calls_by_campaign(
    campaign_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=CAMPAIGN_NOT_FOUND.format(campaign_id=campaign_id),
        )

    query = (
        db.query(CallRecord)
        .options(joinedload(CallRecord.conversations))
        .filter(CallRecord.campaign_id == campaign_id)
    )
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return CallRecordListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[CallRecordResponse.model_validate(c) for c in items],
    )


@router.get("/{call_id}", response_model=CallRecordResponse)
def get_call_record(call_id: str, db: Session = Depends(get_db)):
    call_record = (
        db.query(CallRecord)
        .options(joinedload(CallRecord.conversations))
        .filter(CallRecord.id == call_id)
        .first()
    )
    if not call_record:
        raise HTTPException(
            status_code=404,
            detail=CALL_NOT_FOUND.format(call_id=call_id),
        )
    return CallRecordResponse.model_validate(call_record)


@router.put("/{call_id}", response_model=dict)
def update_call_record(
    call_id: str, payload: CallRecordUpdate, db: Session = Depends(get_db)
):
    call_record = db.query(CallRecord).filter(CallRecord.id == call_id).first()
    if not call_record:
        raise HTTPException(
            status_code=404,
            detail=CALL_NOT_FOUND.format(call_id=call_id),
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(call_record, field, value)

    db.commit()
    db.refresh(call_record)

    return {
        "message": "Call record updated successfully.",
        "data": CallRecordResponse.model_validate(call_record),
    }