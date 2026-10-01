"""Expense business rules: ownership of referenced records, category resolution,
fuel amount calculation and soft deletion."""

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.constants import FUEL_CATEGORY
from app.errors import ConflictError, NotFoundError, ValidationFailed
from app.models import Driver, Expense, ExpenseCategory, Journey, Vehicle
from app.models.base import utcnow
from app.schemas.expense import CategoryCreate, ExpenseCreate, ExpenseRead, ExpenseUpdate
from app.services.common import apply_updates, ensure_owned, get_owned, money

REQUIRED = ("expense_date", "category", "amount", "vehicle_id")
FUEL_FIELDS = ("fuel_type", "quantity", "price_per_unit", "fuel_station", "odometer_reading")


@dataclass
class ExpenseFilters:
    from_date: date | None = None
    to_date: date | None = None
    vehicle_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None
    journey_id: uuid.UUID | None = None
    category: str | None = None
    payment_method: str | None = None
    # "journey" = linked to a journey, "general" = vehicle-level expense
    scope: str | None = None
    search: str | None = None


def expense_read(expense: Expense) -> ExpenseRead:
    return ExpenseRead.model_validate(expense, from_attributes=True)


# --- categories --------------------------------------------------------------------------


def list_categories(db: Session, user_id: uuid.UUID) -> list[ExpenseCategory]:
    stmt = (
        select(ExpenseCategory)
        .where(or_(ExpenseCategory.user_id.is_(None), ExpenseCategory.user_id == user_id))
        .order_by(ExpenseCategory.is_system.desc(), ExpenseCategory.created_at, ExpenseCategory.name)
    )
    return list(db.scalars(stmt))


def resolve_category(db: Session, user_id: uuid.UUID, name: str) -> str:
    """Return the canonical spelling of a category visible to the user, or 422."""
    match = db.scalars(
        select(ExpenseCategory.name).where(
            or_(ExpenseCategory.user_id.is_(None), ExpenseCategory.user_id == user_id),
            func.lower(ExpenseCategory.name) == name.strip().lower(),
        )
    ).first()
    if match is None:
        raise ValidationFailed(f"Unknown expense category '{name}'", field="category")
    return match


def create_category(db: Session, user_id: uuid.UUID, payload: CategoryCreate) -> ExpenseCategory:
    try:
        resolve_category(db, user_id, payload.name)
    except ValidationFailed:
        category = ExpenseCategory(user_id=user_id, name=payload.name, is_system=False)
        db.add(category)
        db.commit()
        db.refresh(category)
        return category
    raise ConflictError("This category already exists", field="name")


def delete_category(db: Session, user_id: uuid.UUID, category_id: uuid.UUID) -> None:
    category = db.scalars(
        select(ExpenseCategory).where(ExpenseCategory.id == category_id, ExpenseCategory.user_id == user_id)
    ).first()
    if category is None:
        raise NotFoundError("Category not found")
    in_use = db.scalar(
        select(exists().where(Expense.user_id == user_id, func.lower(Expense.category) == category.name.lower()))
    )
    if in_use:
        raise ConflictError("This category is used by existing expenses")
    db.delete(category)
    db.commit()


# --- queries -----------------------------------------------------------------------------


def apply_expense_filters(stmt: Select, user_id: uuid.UUID, f: ExpenseFilters) -> Select:
    stmt = stmt.where(Expense.user_id == user_id, Expense.deleted_at.is_(None))
    if f.from_date:
        stmt = stmt.where(Expense.expense_date >= f.from_date)
    if f.to_date:
        stmt = stmt.where(Expense.expense_date <= f.to_date)
    if f.vehicle_id:
        stmt = stmt.where(Expense.vehicle_id == f.vehicle_id)
    if f.driver_id:
        stmt = stmt.where(Expense.driver_id == f.driver_id)
    if f.journey_id:
        stmt = stmt.where(Expense.journey_id == f.journey_id)
    if f.category:
        stmt = stmt.where(func.lower(Expense.category) == f.category.lower())
    if f.payment_method:
        stmt = stmt.where(Expense.payment_method == f.payment_method)
    if f.scope == "journey":
        stmt = stmt.where(Expense.journey_id.is_not(None))
    elif f.scope == "general":
        stmt = stmt.where(Expense.journey_id.is_(None))
    if f.search:
        like = f"%{f.search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Expense.description).like(like),
                func.lower(Expense.notes).like(like),
                func.lower(Expense.fuel_station).like(like),
            )
        )
    return stmt


def _with_refs(stmt: Select) -> Select:
    return stmt.options(selectinload(Expense.vehicle), selectinload(Expense.driver), selectinload(Expense.journey))


def list_expenses(
    db: Session, user_id: uuid.UUID, filters: ExpenseFilters, limit: int = 50, offset: int = 0
) -> tuple[list[ExpenseRead], int, Any]:
    total = db.scalar(apply_expense_filters(select(func.count(Expense.id)), user_id, filters)) or 0
    amount = db.scalar(apply_expense_filters(select(func.coalesce(func.sum(Expense.amount), 0)), user_id, filters))
    stmt = apply_expense_filters(_with_refs(select(Expense)), user_id, filters)
    stmt = stmt.order_by(Expense.expense_date.desc(), Expense.created_at.desc()).limit(limit).offset(offset)
    return [expense_read(e) for e in db.scalars(stmt)], total, amount


def get_expense(db: Session, user_id: uuid.UUID, expense_id: uuid.UUID) -> ExpenseRead:
    expense = get_owned(
        db,
        Expense,
        expense_id,
        user_id,
        "Expense",
        options=(selectinload(Expense.vehicle), selectinload(Expense.driver), selectinload(Expense.journey)),
    )
    return expense_read(expense)


# --- mutations ---------------------------------------------------------------------------


def _finalize(db: Session, user_id: uuid.UUID, expense: Expense, recompute_amount: bool) -> None:
    journey = ensure_owned(db, Journey, expense.journey_id, user_id, "journey_id", "Journey")
    if journey is not None:
        if expense.vehicle_id is None:
            expense.vehicle_id = journey.vehicle_id
        elif expense.vehicle_id != journey.vehicle_id:
            raise ValidationFailed("Vehicle must match the selected journey's vehicle", field="vehicle_id")
    if expense.vehicle_id is None:
        raise ValidationFailed("Vehicle is required", field="vehicle_id")
    ensure_owned(db, Vehicle, expense.vehicle_id, user_id, "vehicle_id", "Vehicle")
    ensure_owned(db, Driver, expense.driver_id, user_id, "driver_id", "Driver")

    expense.category = resolve_category(db, user_id, expense.category)
    if expense.category != FUEL_CATEGORY:
        for field in FUEL_FIELDS:
            setattr(expense, field, None)

    if recompute_amount and expense.quantity is not None and expense.price_per_unit is not None:
        expense.amount = money(expense.quantity * expense.price_per_unit)
    if expense.amount is None:
        raise ValidationFailed("Amount is required", field="amount")
    if expense.amount <= 0:
        raise ValidationFailed("Amount must be greater than zero", field="amount")
    expense.amount = money(expense.amount)


def create_expense(db: Session, user_id: uuid.UUID, payload: ExpenseCreate) -> ExpenseRead:
    data = payload.model_dump()
    journey_id = data.get("journey_id")
    if journey_id and "driver_id" not in payload.model_fields_set:
        journey = ensure_owned(db, Journey, journey_id, user_id, "journey_id", "Journey")
        data["driver_id"] = journey.driver_id if journey else None
    expense = Expense(user_id=user_id, **data)
    _finalize(db, user_id, expense, recompute_amount=payload.amount is None)
    db.add(expense)
    db.commit()
    return get_expense(db, user_id, expense.id)


def update_expense(db: Session, user_id: uuid.UUID, expense_id: uuid.UUID, payload: ExpenseUpdate) -> ExpenseRead:
    expense = get_owned(db, Expense, expense_id, user_id, "Expense")
    data = payload.model_dump(exclude_unset=True)
    # An explicit null journey_id detaches the expense, turning it into a general expense.
    recompute = "amount" not in data and bool({"quantity", "price_per_unit"} & data.keys())
    apply_updates(expense, data, REQUIRED)
    _finalize(db, user_id, expense, recompute_amount=recompute)
    db.commit()
    return get_expense(db, user_id, expense.id)


def delete_expense(db: Session, user_id: uuid.UUID, expense_id: uuid.UUID) -> None:
    expense = get_owned(db, Expense, expense_id, user_id, "Expense")
    expense.deleted_at = utcnow()
    db.commit()
