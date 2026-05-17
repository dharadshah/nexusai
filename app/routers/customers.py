from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.customer import Customer
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerListResponse,
)
from app.constants.messages import (
    CUSTOMER_CREATED,
    CUSTOMER_UPDATED,
    CUSTOMER_DELETED,
    CUSTOMER_NOT_FOUND,
)
from app.constants.app_constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post("/", response_model=dict, status_code=201)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    existing = db.query(Customer).filter(
        Customer.phone_number == payload.phone_number
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A customer with this phone number already exists.")

    customer = Customer(
        first_name=payload.first_name,
        last_name=payload.last_name,
        phone_number=payload.phone_number,
        email=payload.email,
        status=payload.status,
        preferred_language=payload.preferred_language,
        timezone=payload.timezone,
    )
    if payload.metadata_dict:
        customer.metadata_dict = payload.metadata_dict

    db.add(customer)
    db.commit()
    db.refresh(customer)

    return {
        "message": CUSTOMER_CREATED,
        "data": CustomerResponse.model_validate(customer),
    }


@router.get("/", response_model=CustomerListResponse)
def list_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Customer)
    if status:
        query = query.filter(Customer.status == status)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return CustomerListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[CustomerResponse.model_validate(c) for c in items],
    )


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: str, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=404,
            detail=CUSTOMER_NOT_FOUND.format(customer_id=customer_id),
        )
    return CustomerResponse.model_validate(customer)


@router.put("/{customer_id}", response_model=dict)
def update_customer(
    customer_id: str, payload: CustomerUpdate, db: Session = Depends(get_db)
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=404,
            detail=CUSTOMER_NOT_FOUND.format(customer_id=customer_id),
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "metadata_dict":
            customer.metadata_dict = value
        else:
            setattr(customer, field, value)

    db.commit()
    db.refresh(customer)

    return {
        "message": CUSTOMER_UPDATED,
        "data": CustomerResponse.model_validate(customer),
    }


@router.delete("/{customer_id}", response_model=dict)
def delete_customer(customer_id: str, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=404,
            detail=CUSTOMER_NOT_FOUND.format(customer_id=customer_id),
        )

    db.delete(customer)
    db.commit()

    return {"message": CUSTOMER_DELETED}
