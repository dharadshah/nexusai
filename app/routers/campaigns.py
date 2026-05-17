from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.campaign import Campaign
from app.schemas.campaign import (
    CampaignCreate,
    CampaignUpdate,
    CampaignResponse,
    CampaignListResponse,
)
from app.constants.messages import (
    CAMPAIGN_CREATED,
    CAMPAIGN_UPDATED,
    CAMPAIGN_DELETED,
    CAMPAIGN_NOT_FOUND,
)
from app.constants.app_constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


@router.post("/", response_model=dict, status_code=201)
def create_campaign(payload: CampaignCreate, db: Session = Depends(get_db)):
    campaign = Campaign(
        name=payload.name,
        description=payload.description,
        campaign_type=payload.campaign_type,
        company_name=payload.company_name,
        system_prompt_override=payload.system_prompt_override,
        max_retries=payload.max_retries,
        retry_delay_minutes=payload.retry_delay_minutes,
        scheduled_start=payload.scheduled_start,
        scheduled_end=payload.scheduled_end,
        call_window_start=payload.call_window_start,
        call_window_end=payload.call_window_end,
    )

    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    return {
        "message": CAMPAIGN_CREATED,
        "data": CampaignResponse.model_validate(campaign),
    }


@router.get("/", response_model=CampaignListResponse)
def list_campaigns(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    status: str | None = Query(None),
    campaign_type: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Campaign)
    if status:
        query = query.filter(Campaign.status == status)
    if campaign_type:
        query = query.filter(Campaign.campaign_type == campaign_type)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return CampaignListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[CampaignResponse.model_validate(c) for c in items],
    )


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=CAMPAIGN_NOT_FOUND.format(campaign_id=campaign_id),
        )
    return CampaignResponse.model_validate(campaign)


@router.put("/{campaign_id}", response_model=dict)
def update_campaign(
    campaign_id: str, payload: CampaignUpdate, db: Session = Depends(get_db)
):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=CAMPAIGN_NOT_FOUND.format(campaign_id=campaign_id),
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(campaign, field, value)

    db.commit()
    db.refresh(campaign)

    return {
        "message": CAMPAIGN_UPDATED,
        "data": CampaignResponse.model_validate(campaign),
    }


@router.delete("/{campaign_id}", response_model=dict)
def delete_campaign(campaign_id: str, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail=CAMPAIGN_NOT_FOUND.format(campaign_id=campaign_id),
        )

    db.delete(campaign)
    db.commit()

    return {"message": CAMPAIGN_DELETED}