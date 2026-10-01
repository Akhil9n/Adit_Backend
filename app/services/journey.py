"""Journey business rules. The backend is the single source of truth for distance,
net revenue, outstanding balance and journey profit."""

import uuid
from dataclasses import dataclass
from datetime import UTC, date
from decimal import Decimal

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.constants import PaymentStatus
from app.errors import NotFoundError, ValidationFailed
from app.models import Driver, Expense, Journey, Vehicle
from app.models.base import utcnow
from app.schemas.journey import JourneyCreate, JourneyDetail, JourneyRead, JourneyUpdate
from app.services.common import ZERO, apply_updates, ensure_owned, get_owned, money
from app.services.expense import expense_read

REQUIRED = (
    "vehicle_id",
    "journey_date",
    "platform",
    "payment_status",
    "gross_fare",
    "platform_commission",
    "other_deductions",
    "distance_overridden",
    "net_revenue_overridden",
)


@dataclass
class JourneyFilters:
    from_date: date | None = None
    to_date: date | None = None
    vehicle_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None
    platform: str | None = None
    trip_type: str | None = None
    payment_status: str | None = None
    search: str | None = None


# --- calculations -------------------------------------------------------------------------


def calculate_net_revenue(gross_fare: Decimal, commission: Decimal, deductions: Decimal) -> Decimal:
    return money(gross_fare - commission - deductions)


def apply_journey_rules(journey: Journey) -> None:
    """Validate cross-field rules and derive computed values in place."""
    start_odo, end_odo = journey.starting_odometer, journey.ending_odometer
    if start_odo is not None and end_odo is not None and end_odo < start_odo:
        raise ValidationFailed("Ending odometer cannot be lower than starting odometer", field="ending_odometer")

    if journey.distance_overridden:
        if journey.distance_km is None:
            raise ValidationFailed("Enter a distance or switch off manual distance", field="distance_km")
    elif start_odo is not None and end_odo is not None:
        journey.distance_km = end_odo - start_odo

    # Store instants in UTC (portable across drivers; display converts to IST).
    for attr in ("start_time", "end_time"):
        value = getattr(journey, attr)
        if value is not None and value.tzinfo is not None:
            setattr(journey, attr, value.astimezone(UTC))
    if journey.start_time and journey.end_time and journey.end_time < journey.start_time:
        raise ValidationFailed("End time cannot be before start time", field="end_time")

    gross = journey.gross_fare or ZERO
    commission = journey.platform_commission or ZERO
    deductions = journey.other_deductions or ZERO
    if journey.net_revenue_overridden:
        if journey.net_revenue is None:
            raise ValidationFailed("Enter the amount received", field="net_revenue")
        journey.net_revenue = money(journey.net_revenue)
    else:
        net = calculate_net_revenue(gross, commission, deductions)
        if net < 0:
            raise ValidationFailed(
                "Commission and deductions cannot exceed the gross fare", field="platform_commission"
            )
        journey.net_revenue = net

    if journey.payment_status == PaymentStatus.PAID:
        journey.amount_paid = journey.net_revenue
    elif journey.payment_status == PaymentStatus.PENDING:
        journey.amount_paid = ZERO
    else:
        paid = journey.amount_paid or ZERO
        if paid <= 0:
            raise ValidationFailed("Enter the amount received so far", field="amount_paid")
        if paid > journey.net_revenue:
            raise ValidationFailed("Amount paid cannot exceed the net amount", field="amount_paid")


def _sync_vehicle_odometer(db: Session, journey: Journey) -> None:
    if journey.ending_odometer is None:
        return
    vehicle = db.get(Vehicle, journey.vehicle_id)
    if vehicle and (vehicle.current_odometer is None or journey.ending_odometer > vehicle.current_odometer):
        vehicle.current_odometer = journey.ending_odometer


def _duration_minutes(journey: Journey) -> int | None:
    if journey.start_time and journey.end_time:
        return int((journey.end_time - journey.start_time).total_seconds() // 60)
    return None


def journey_read(
    journey: Journey, total_expenses: Decimal, schema: type[JourneyRead] = JourneyRead, **extra
) -> JourneyRead:
    data = {col.key: getattr(journey, col.key) for col in Journey.__table__.columns}
    total_expenses = money(total_expenses)
    data.update(
        vehicle=journey.vehicle,
        driver=journey.driver,
        duration_minutes=_duration_minutes(journey),
        total_expenses=total_expenses,
        profit=money(journey.net_revenue - total_expenses),
        outstanding_amount=money(max(journey.net_revenue - journey.amount_paid, ZERO)),
        **extra,
    )
    return schema.model_validate(data, from_attributes=True)


# --- queries -----------------------------------------------------------------------------


def journey_expense_totals(user_id: uuid.UUID):
    return (
        select(Expense.journey_id.label("journey_id"), func.sum(Expense.amount).label("total"))
        .where(Expense.user_id == user_id, Expense.deleted_at.is_(None), Expense.journey_id.is_not(None))
        .group_by(Expense.journey_id)
        .subquery()
    )


def apply_journey_filters(stmt: Select, user_id: uuid.UUID, f: JourneyFilters) -> Select:
    stmt = stmt.where(Journey.user_id == user_id, Journey.deleted_at.is_(None))
    if f.from_date:
        stmt = stmt.where(Journey.journey_date >= f.from_date)
    if f.to_date:
        stmt = stmt.where(Journey.journey_date <= f.to_date)
    if f.vehicle_id:
        stmt = stmt.where(Journey.vehicle_id == f.vehicle_id)
    if f.driver_id:
        stmt = stmt.where(Journey.driver_id == f.driver_id)
    if f.platform:
        stmt = stmt.where(Journey.platform == f.platform)
    if f.trip_type:
        stmt = stmt.where(Journey.trip_type == f.trip_type)
    if f.payment_status:
        stmt = stmt.where(Journey.payment_status == f.payment_status)
    if f.search:
        like = f"%{f.search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Journey.pickup_location).like(like),
                func.lower(Journey.drop_location).like(like),
                func.lower(Journey.notes).like(like),
            )
        )
    return stmt


def list_journeys(
    db: Session, user_id: uuid.UUID, filters: JourneyFilters, limit: int = 50, offset: int = 0
) -> tuple[list[JourneyRead], int]:
    total = db.scalar(apply_journey_filters(select(func.count(Journey.id)), user_id, filters)) or 0

    totals = journey_expense_totals(user_id)
    stmt = (
        select(Journey, func.coalesce(totals.c.total, 0))
        .outerjoin(totals, totals.c.journey_id == Journey.id)
        .options(selectinload(Journey.vehicle), selectinload(Journey.driver))
    )
    stmt = apply_journey_filters(stmt, user_id, filters)
    stmt = (
        stmt.order_by(Journey.journey_date.desc(), Journey.start_time.desc().nulls_last(), Journey.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = db.execute(stmt).all()
    return [journey_read(j, Decimal(str(t))) for j, t in rows], total


def _load(db: Session, user_id: uuid.UUID, journey_id: uuid.UUID) -> Journey:
    return get_owned(
        db,
        Journey,
        journey_id,
        user_id,
        "Journey",
        options=(selectinload(Journey.vehicle), selectinload(Journey.driver)),
    )


def get_journey_detail(db: Session, user_id: uuid.UUID, journey_id: uuid.UUID) -> JourneyDetail:
    journey = _load(db, user_id, journey_id)
    expenses = list(
        db.scalars(
            select(Expense)
            .where(Expense.journey_id == journey.id, Expense.user_id == user_id, Expense.deleted_at.is_(None))
            .options(selectinload(Expense.vehicle), selectinload(Expense.driver), selectinload(Expense.journey))
            .order_by(Expense.expense_date, Expense.created_at)
        )
    )
    total = sum((e.amount for e in expenses), ZERO)
    return journey_read(journey, total, JourneyDetail, expenses=[expense_read(e) for e in expenses])  # type: ignore[return-value]


# --- mutations ---------------------------------------------------------------------------


def _validate_refs(db: Session, user_id: uuid.UUID, journey: Journey) -> None:
    ensure_owned(db, Vehicle, journey.vehicle_id, user_id, "vehicle_id", "Vehicle")
    ensure_owned(db, Driver, journey.driver_id, user_id, "driver_id", "Driver")


def create_journey(db: Session, user_id: uuid.UUID, payload: JourneyCreate) -> JourneyDetail:
    journey = Journey(user_id=user_id, **payload.model_dump(exclude={"amount_paid"}))
    journey.amount_paid = payload.amount_paid or ZERO
    _validate_refs(db, user_id, journey)
    apply_journey_rules(journey)
    db.add(journey)
    _sync_vehicle_odometer(db, journey)
    db.commit()
    return get_journey_detail(db, user_id, journey.id)


def update_journey(db: Session, user_id: uuid.UUID, journey_id: uuid.UUID, payload: JourneyUpdate) -> JourneyDetail:
    journey = get_owned(db, Journey, journey_id, user_id, "Journey")
    data = payload.model_dump(exclude_unset=True)
    previous_vehicle = journey.vehicle_id
    apply_updates(journey, data, REQUIRED)
    _validate_refs(db, user_id, journey)
    apply_journey_rules(journey)
    if journey.vehicle_id != previous_vehicle:
        # Keep linked expenses consistent with the journey's vehicle.
        db.execute(
            update(Expense)
            .where(Expense.journey_id == journey.id, Expense.user_id == user_id)
            .values(vehicle_id=journey.vehicle_id)
        )
    _sync_vehicle_odometer(db, journey)
    db.commit()
    return get_journey_detail(db, user_id, journey.id)


def delete_journey(db: Session, user_id: uuid.UUID, journey_id: uuid.UUID) -> None:
    """Soft delete the journey together with its expenses (same timestamp, so restore is exact)."""
    journey = get_owned(db, Journey, journey_id, user_id, "Journey")
    now = utcnow()
    journey.deleted_at = now
    db.execute(
        update(Expense)
        .where(Expense.journey_id == journey.id, Expense.user_id == user_id, Expense.deleted_at.is_(None))
        .values(deleted_at=now)
    )
    db.commit()


def restore_journey(db: Session, user_id: uuid.UUID, journey_id: uuid.UUID) -> JourneyDetail:
    journey = db.scalars(
        select(Journey).where(Journey.id == journey_id, Journey.user_id == user_id, Journey.deleted_at.is_not(None))
    ).first()
    if journey is None:
        raise NotFoundError("Deleted journey not found")
    deleted_at = journey.deleted_at
    journey.deleted_at = None
    db.execute(
        update(Expense)
        .where(Expense.journey_id == journey.id, Expense.user_id == user_id, Expense.deleted_at == deleted_at)
        .values(deleted_at=None)
    )
    db.commit()
    return get_journey_detail(db, user_id, journey.id)
