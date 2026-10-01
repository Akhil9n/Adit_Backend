import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.common import Money, Quantity


class PlatformAmount(BaseModel):
    platform: str
    amount: Money
    journeys: int


class CategoryAmount(BaseModel):
    category: str
    amount: Money
    count: int


class DailyFinancial(BaseModel):
    date: date
    revenue: Money
    expenses: Money
    profit: Money


class DashboardSummary(BaseModel):
    from_date: date
    to_date: date
    vehicle_id: uuid.UUID | None

    total_revenue: Money
    total_expenses: Money
    net_profit: Money
    total_journeys: int
    total_distance_km: Quantity
    average_revenue_per_km: Money
    average_profit_per_journey: Money

    # Unpaid balance across all time (not limited to the selected range).
    outstanding_amount: Money
    outstanding_journeys: int

    revenue_by_platform: list[PlatformAmount]
    expenses_by_category: list[CategoryAmount]
    daily_financials: list[DailyFinancial]
