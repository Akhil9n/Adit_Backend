import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.common import Money, Quantity
from app.schemas.dashboard import CategoryAmount, DailyFinancial, PlatformAmount


class DayAmount(BaseModel):
    date: date
    amount: Money
    count: int


class JourneyRevenueRow(BaseModel):
    id: uuid.UUID
    journey_date: date
    platform: str
    pickup_location: str | None
    drop_location: str | None
    distance_km: Quantity | None
    gross_fare: Money
    platform_commission: Money
    other_deductions: Money
    net_revenue: Money
    expenses: Money
    profit: Money
    payment_status: str


class RevenueReport(BaseModel):
    from_date: date
    to_date: date
    total_revenue: Money
    total_gross_fare: Money
    total_commission: Money
    total_deductions: Money
    total_journeys: int
    by_platform: list[PlatformAmount]
    by_day: list[DayAmount]
    by_journey: list[JourneyRevenueRow]


class VehicleAmount(BaseModel):
    vehicle_id: uuid.UUID
    registration_number: str
    amount: Money
    count: int


class ExpenseReport(BaseModel):
    from_date: date
    to_date: date
    total_expenses: Money
    journey_expenses: Money
    general_expenses: Money
    total_count: int
    by_category: list[CategoryAmount]
    by_day: list[DayAmount]
    by_vehicle: list[VehicleAmount]


class PlatformProfit(BaseModel):
    platform: str
    journeys: int
    distance_km: Quantity
    revenue: Money
    journey_expenses: Money
    profit: Money


class ProfitabilityReport(BaseModel):
    from_date: date
    to_date: date
    revenue: Money
    expenses: Money
    journey_expenses: Money
    general_expenses: Money
    profit: Money
    total_journeys: int
    total_distance_km: Quantity
    profit_per_journey: Money
    profit_per_km: Money
    revenue_per_km: Money
    by_platform: list[PlatformProfit]
    daily: list[DailyFinancial]


class DriverRow(BaseModel):
    driver_id: uuid.UUID | None
    name: str
    journeys: int
    distance_km: Quantity
    revenue: Money
    driver_expenses: Money


class DriverReport(BaseModel):
    from_date: date
    to_date: date
    rows: list[DriverRow]
