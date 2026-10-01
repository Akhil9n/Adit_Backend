import uuid
from datetime import date
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel

from app.constants import PaymentStatus, Platform, TripType
from app.schemas.common import (
    DriverRef,
    Money,
    MoneyIn,
    NonNegative,
    OptStr,
    ORMModel,
    Quantity,
    UtcDatetime,
    VehicleRef,
)
from app.schemas.expense import ExpenseRead

# Cross-field rules (odometer order, net revenue, amount paid) are enforced in
# services/journey.py so they apply identically to create and partial update.


class JourneyCreate(BaseModel):
    vehicle_id: uuid.UUID
    driver_id: uuid.UUID | None = None

    journey_date: date
    start_time: AwareDatetime | None = None
    end_time: AwareDatetime | None = None

    platform: Platform
    trip_type: TripType | None = None
    pickup_location: OptStr = None
    drop_location: OptStr = None

    starting_odometer: NonNegative | None = None
    ending_odometer: NonNegative | None = None
    distance_km: NonNegative | None = None
    distance_overridden: bool = False

    gross_fare: MoneyIn = Decimal("0")
    platform_commission: MoneyIn = Decimal("0")
    other_deductions: MoneyIn = Decimal("0")
    net_revenue: MoneyIn | None = None
    net_revenue_overridden: bool = False

    payment_status: PaymentStatus = PaymentStatus.PENDING
    amount_paid: MoneyIn | None = None

    notes: OptStr = None


class JourneyUpdate(BaseModel):
    vehicle_id: uuid.UUID | None = None
    driver_id: uuid.UUID | None = None

    journey_date: date | None = None
    start_time: AwareDatetime | None = None
    end_time: AwareDatetime | None = None

    platform: Platform | None = None
    trip_type: TripType | None = None
    pickup_location: OptStr = None
    drop_location: OptStr = None

    starting_odometer: NonNegative | None = None
    ending_odometer: NonNegative | None = None
    distance_km: NonNegative | None = None
    distance_overridden: bool | None = None

    gross_fare: MoneyIn | None = None
    platform_commission: MoneyIn | None = None
    other_deductions: MoneyIn | None = None
    net_revenue: MoneyIn | None = None
    net_revenue_overridden: bool | None = None

    payment_status: PaymentStatus | None = None
    amount_paid: MoneyIn | None = None

    notes: OptStr = None


class JourneyRead(ORMModel):
    id: uuid.UUID
    vehicle_id: uuid.UUID
    driver_id: uuid.UUID | None
    vehicle: VehicleRef
    driver: DriverRef | None

    journey_date: date
    start_time: UtcDatetime | None
    end_time: UtcDatetime | None
    duration_minutes: int | None

    platform: str
    trip_type: str | None
    pickup_location: str | None
    drop_location: str | None

    starting_odometer: Quantity | None
    ending_odometer: Quantity | None
    distance_km: Quantity | None
    distance_overridden: bool

    gross_fare: Money
    platform_commission: Money
    other_deductions: Money
    net_revenue: Money
    net_revenue_overridden: bool

    payment_status: str
    amount_paid: Money
    outstanding_amount: Money

    total_expenses: Money
    profit: Money

    notes: str | None
    created_at: UtcDatetime
    updated_at: UtcDatetime


class JourneyDetail(JourneyRead):
    expenses: list[ExpenseRead]
