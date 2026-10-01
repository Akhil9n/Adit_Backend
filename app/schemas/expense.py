import uuid
from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.constants import FuelType, PaymentMethod
from app.schemas.common import (
    DriverRef,
    JourneyRef,
    Money,
    NonNegative,
    OptStr,
    ORMModel,
    PositiveMoneyIn,
    Quantity,
    UtcDatetime,
    VehicleRef,
)

CategoryName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
PositiveQuantity = Annotated[NonNegative, Field(gt=0)]


class ExpenseCreate(BaseModel):
    expense_date: date
    category: CategoryName
    # Optional only when quantity and price_per_unit are given (amount = quantity x price).
    amount: PositiveMoneyIn | None = None
    payment_method: PaymentMethod | None = None

    # Defaults to the journey's vehicle when journey_id is given.
    vehicle_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None
    journey_id: uuid.UUID | None = None

    description: OptStr = None
    notes: OptStr = None

    fuel_type: FuelType | None = None
    quantity: PositiveQuantity | None = None
    price_per_unit: PositiveMoneyIn | None = None
    fuel_station: Annotated[OptStr, Field(max_length=150)] = None
    odometer_reading: NonNegative | None = None


class ExpenseUpdate(BaseModel):
    expense_date: date | None = None
    category: CategoryName | None = None
    amount: PositiveMoneyIn | None = None
    payment_method: PaymentMethod | None = None

    vehicle_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None
    journey_id: uuid.UUID | None = None

    description: OptStr = None
    notes: OptStr = None

    fuel_type: FuelType | None = None
    quantity: PositiveQuantity | None = None
    price_per_unit: PositiveMoneyIn | None = None
    fuel_station: Annotated[OptStr, Field(max_length=150)] = None
    odometer_reading: NonNegative | None = None


class ExpenseRead(ORMModel):
    id: uuid.UUID
    expense_date: date
    category: str
    amount: Money
    payment_method: str | None

    vehicle_id: uuid.UUID
    driver_id: uuid.UUID | None
    journey_id: uuid.UUID | None
    vehicle: VehicleRef
    driver: DriverRef | None
    journey: JourneyRef | None

    description: str | None
    notes: str | None

    fuel_type: str | None
    quantity: Quantity | None
    price_per_unit: Money | None
    fuel_station: str | None
    odometer_reading: Quantity | None

    created_at: UtcDatetime
    updated_at: UtcDatetime


class CategoryCreate(BaseModel):
    name: CategoryName


class CategoryRead(ORMModel):
    id: uuid.UUID
    name: str
    is_system: bool
