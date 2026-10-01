import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUserId, DbSession
from app.constants import DriverStatus
from app.models import Driver
from app.schemas.driver import DriverCreate, DriverRead, DriverUpdate
from app.services import driver as service
from app.services.common import get_owned

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.get("", response_model=list[DriverRead])
def list_drivers(db: DbSession, user_id: CurrentUserId, status: DriverStatus | None = None):
    return service.list_drivers(db, user_id, status)


@router.post("", response_model=DriverRead, status_code=status.HTTP_201_CREATED)
def create_driver(payload: DriverCreate, db: DbSession, user_id: CurrentUserId):
    return service.create_driver(db, user_id, payload)


@router.get("/{driver_id}", response_model=DriverRead)
def get_driver(driver_id: uuid.UUID, db: DbSession, user_id: CurrentUserId):
    return get_owned(db, Driver, driver_id, user_id, "Driver")


@router.patch("/{driver_id}", response_model=DriverRead)
def update_driver(driver_id: uuid.UUID, payload: DriverUpdate, db: DbSession, user_id: CurrentUserId):
    return service.update_driver(db, user_id, driver_id, payload)


@router.delete("/{driver_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_driver(driver_id: uuid.UUID, db: DbSession, user_id: CurrentUserId) -> None:
    service.delete_driver(db, user_id, driver_id)
