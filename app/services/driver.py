import uuid

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.errors import ConflictError
from app.models import Driver, Expense, Journey
from app.schemas.driver import DriverCreate, DriverUpdate
from app.services.common import apply_updates, get_owned

REQUIRED = ("name", "status")


def list_drivers(db: Session, user_id: uuid.UUID, status: str | None = None) -> list[Driver]:
    stmt = select(Driver).where(Driver.user_id == user_id)
    if status:
        stmt = stmt.where(Driver.status == status)
    stmt = stmt.order_by((Driver.status != "active"), Driver.name)
    return list(db.scalars(stmt))


def create_driver(db: Session, user_id: uuid.UUID, payload: DriverCreate) -> Driver:
    driver = Driver(user_id=user_id, **payload.model_dump())
    db.add(driver)
    db.commit()
    db.refresh(driver)
    return driver


def update_driver(db: Session, user_id: uuid.UUID, driver_id: uuid.UUID, payload: DriverUpdate) -> Driver:
    driver = get_owned(db, Driver, driver_id, user_id, "Driver")
    apply_updates(driver, payload.model_dump(exclude_unset=True), REQUIRED)
    db.commit()
    db.refresh(driver)
    return driver


def delete_driver(db: Session, user_id: uuid.UUID, driver_id: uuid.UUID) -> None:
    driver = get_owned(db, Driver, driver_id, user_id, "Driver")
    in_use = db.scalar(
        select(exists().where(Journey.driver_id == driver.id) | exists().where(Expense.driver_id == driver.id))
    )
    if in_use:
        raise ConflictError("This driver is linked to journeys or expenses. Mark them inactive instead.")
    db.delete(driver)
    db.commit()
