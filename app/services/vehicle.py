import uuid

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.errors import ConflictError
from app.models import Expense, Journey, Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleUpdate
from app.services.common import apply_updates, get_owned

REQUIRED = ("registration_number", "status")


def list_vehicles(db: Session, user_id: uuid.UUID, status: str | None = None) -> list[Vehicle]:
    stmt = select(Vehicle).where(Vehicle.user_id == user_id)
    if status:
        stmt = stmt.where(Vehicle.status == status)
    # Active vehicles first, then alphabetical.
    stmt = stmt.order_by((Vehicle.status != "active"), Vehicle.registration_number)
    return list(db.scalars(stmt))


def _ensure_unique_registration(db: Session, user_id: uuid.UUID, reg: str, exclude: uuid.UUID | None = None) -> None:
    stmt = select(Vehicle.id).where(Vehicle.user_id == user_id, func.upper(Vehicle.registration_number) == reg.upper())
    if exclude:
        stmt = stmt.where(Vehicle.id != exclude)
    if db.scalars(stmt).first():
        raise ConflictError("A vehicle with this registration number already exists", field="registration_number")


def create_vehicle(db: Session, user_id: uuid.UUID, payload: VehicleCreate) -> Vehicle:
    _ensure_unique_registration(db, user_id, payload.registration_number)
    vehicle = Vehicle(user_id=user_id, **payload.model_dump())
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def update_vehicle(db: Session, user_id: uuid.UUID, vehicle_id: uuid.UUID, payload: VehicleUpdate) -> Vehicle:
    vehicle = get_owned(db, Vehicle, vehicle_id, user_id, "Vehicle")
    data = payload.model_dump(exclude_unset=True)
    if data.get("registration_number"):
        _ensure_unique_registration(db, user_id, data["registration_number"], exclude=vehicle.id)
    apply_updates(vehicle, data, REQUIRED)
    db.commit()
    db.refresh(vehicle)
    return vehicle


def delete_vehicle(db: Session, user_id: uuid.UUID, vehicle_id: uuid.UUID) -> None:
    vehicle = get_owned(db, Vehicle, vehicle_id, user_id, "Vehicle")
    # Financial history (including soft-deleted rows) must keep its vehicle.
    in_use = db.scalar(
        select(exists().where(Journey.vehicle_id == vehicle.id) | exists().where(Expense.vehicle_id == vehicle.id))
    )
    if in_use:
        raise ConflictError("This vehicle has journeys or expenses. Mark it inactive or sold instead.")
    db.delete(vehicle)
    db.commit()
