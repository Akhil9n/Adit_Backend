import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUserId, DbSession
from app.constants import VehicleStatus
from app.models import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleRead, VehicleUpdate
from app.services import vehicle as service
from app.services.common import get_owned

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("", response_model=list[VehicleRead])
def list_vehicles(db: DbSession, user_id: CurrentUserId, status: VehicleStatus | None = None):
    return service.list_vehicles(db, user_id, status)


@router.post("", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
def create_vehicle(payload: VehicleCreate, db: DbSession, user_id: CurrentUserId):
    return service.create_vehicle(db, user_id, payload)


@router.get("/{vehicle_id}", response_model=VehicleRead)
def get_vehicle(vehicle_id: uuid.UUID, db: DbSession, user_id: CurrentUserId):
    return get_owned(db, Vehicle, vehicle_id, user_id, "Vehicle")


@router.patch("/{vehicle_id}", response_model=VehicleRead)
def update_vehicle(vehicle_id: uuid.UUID, payload: VehicleUpdate, db: DbSession, user_id: CurrentUserId):
    return service.update_vehicle(db, user_id, vehicle_id, payload)


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(vehicle_id: uuid.UUID, db: DbSession, user_id: CurrentUserId) -> None:
    service.delete_vehicle(db, user_id, vehicle_id)
