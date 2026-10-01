import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _to_float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


# Decimals are used for all arithmetic; they are emitted as JSON numbers for convenience.
# NUMERIC(12,2) values are exactly representable for display purposes.
Money = Annotated[Decimal, PlainSerializer(_to_float, return_type=float, when_used="json")]
Quantity = Annotated[Decimal, PlainSerializer(_to_float, return_type=float, when_used="json")]


def _as_utc(value: datetime) -> datetime:
    # Timestamps are stored in UTC; some drivers (SQLite) return them naive.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


# Response timestamps: always timezone-aware UTC so clients convert to IST correctly.
UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]

# Optional text input: trims whitespace and turns "" into None.
OptStr = Annotated[str | None, BeforeValidator(_blank_to_none)]

MoneyIn = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
PositiveMoneyIn = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
NonNegative = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=3)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VehicleRef(ORMModel):
    id: uuid.UUID
    registration_number: str
    make: str | None = None
    model: str | None = None


class DriverRef(ORMModel):
    id: uuid.UUID
    name: str


class JourneyRef(ORMModel):
    id: uuid.UUID
    journey_date: date
    platform: str
    pickup_location: str | None = None
    drop_location: str | None = None


class Page[T](BaseModel):
    items: list[T]
    total: int


class DateRange(BaseModel):
    from_date: date
    to_date: date
