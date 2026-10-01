import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUserId, DbSession
from app.constants import PaymentStatus, Platform, TripType
from app.schemas.common import Page
from app.schemas.journey import JourneyCreate, JourneyDetail, JourneyRead, JourneyUpdate
from app.services import journey as service

router = APIRouter(prefix="/journeys", tags=["journeys"])


@router.get("", response_model=Page[JourneyRead])
def list_journeys(
    db: DbSession,
    user_id: CurrentUserId,
    from_date: date | None = None,
    to_date: date | None = None,
    vehicle_id: uuid.UUID | None = None,
    driver_id: uuid.UUID | None = None,
    platform: Platform | None = None,
    trip_type: TripType | None = None,
    payment_status: PaymentStatus | None = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    filters = service.JourneyFilters(
        from_date=from_date,
        to_date=to_date,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        platform=platform,
        trip_type=trip_type,
        payment_status=payment_status,
        search=search,
    )
    items, total = service.list_journeys(db, user_id, filters, limit, offset)
    return Page(items=items, total=total)


@router.post("", response_model=JourneyDetail, status_code=status.HTTP_201_CREATED)
def create_journey(payload: JourneyCreate, db: DbSession, user_id: CurrentUserId):
    return service.create_journey(db, user_id, payload)


@router.get("/{journey_id}", response_model=JourneyDetail)
def get_journey(journey_id: uuid.UUID, db: DbSession, user_id: CurrentUserId):
    return service.get_journey_detail(db, user_id, journey_id)


@router.patch("/{journey_id}", response_model=JourneyDetail)
def update_journey(journey_id: uuid.UUID, payload: JourneyUpdate, db: DbSession, user_id: CurrentUserId):
    return service.update_journey(db, user_id, journey_id, payload)


@router.delete("/{journey_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_journey(journey_id: uuid.UUID, db: DbSession, user_id: CurrentUserId) -> None:
    service.delete_journey(db, user_id, journey_id)


@router.post("/{journey_id}/restore", response_model=JourneyDetail)
def restore_journey(journey_id: uuid.UUID, db: DbSession, user_id: CurrentUserId):
    return service.restore_journey(db, user_id, journey_id)
