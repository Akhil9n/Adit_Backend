import uuid
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import NotFoundError, ValidationFailed

ZERO = Decimal("0")
CENT = Decimal("0.01")
MAX_RANGE_DAYS = 1100


def dec(value: Any) -> Decimal:
    """Coerce DB aggregate results (Decimal, int, float or None) into Decimal."""
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def safe_div(numerator: Decimal, denominator: Decimal | int) -> Decimal:
    denominator = dec(denominator)
    if denominator == 0:
        return ZERO
    return money(numerator / denominator)


def today_local() -> date:
    return datetime.now(ZoneInfo(get_settings().timezone)).date()


def resolve_range(from_date: date | None, to_date: date | None) -> tuple[date, date]:
    """Default to the current calendar month (business timezone)."""
    today = today_local()
    if from_date is None and to_date is None:
        from_date = today.replace(day=1)
        to_date = today
    elif from_date is None:
        from_date = to_date.replace(day=1)  # type: ignore[union-attr]
    elif to_date is None:
        to_date = max(from_date, today)
    assert from_date is not None and to_date is not None
    if from_date > to_date:
        raise ValidationFailed("From date must be on or before to date", field="from_date")
    if (to_date - from_date).days > MAX_RANGE_DAYS:
        raise ValidationFailed("Date range is too large (max 3 years)", field="to_date")
    return from_date, to_date


def iter_days(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def get_owned[T](db: Session, model: type[T], obj_id: uuid.UUID, user_id: uuid.UUID, label: str, **extra: Any) -> T:
    """Fetch a row owned by the user or raise 404 (never reveals other users' rows)."""
    stmt = select(model).where(model.id == obj_id, model.user_id == user_id)  # type: ignore[attr-defined]
    if hasattr(model, "deleted_at"):
        stmt = stmt.where(model.deleted_at.is_(None))  # type: ignore[attr-defined]
    for opt in extra.get("options", ()):
        stmt = stmt.options(opt)
    obj = db.scalars(stmt).first()
    if obj is None:
        raise NotFoundError(f"{label} not found")
    return obj


def ensure_owned[T](
    db: Session, model: type[T], obj_id: uuid.UUID | None, user_id: uuid.UUID, field: str, label: str
) -> T | None:
    """Validate that a referenced id belongs to the user; 422 on the referencing field otherwise."""
    if obj_id is None:
        return None
    try:
        return get_owned(db, model, obj_id, user_id, label)
    except NotFoundError as exc:
        raise ValidationFailed(f"{label} not found", field=field) from exc


def apply_updates(obj: Any, data: dict[str, Any], required: Iterable[str] = ()) -> None:
    required = set(required)
    for key, value in data.items():
        if value is None and key in required:
            raise ValidationFailed(f"{key.replace('_', ' ').capitalize()} cannot be empty", field=key)
        setattr(obj, key, value)
