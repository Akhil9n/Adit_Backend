"""Dashboard aggregation. All sums run in SQL; only grouped rows come back to Python."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.constants import PaymentStatus
from app.models import Expense, Journey
from app.schemas.dashboard import CategoryAmount, DailyFinancial, DashboardSummary, PlatformAmount
from app.services.common import dec, iter_days, money, safe_div


def journey_conditions(
    user_id: uuid.UUID, from_date: date | None, to_date: date | None, vehicle_id: uuid.UUID | None = None
) -> list[ColumnElement[bool]]:
    conds = [Journey.user_id == user_id, Journey.deleted_at.is_(None)]
    if from_date:
        conds.append(Journey.journey_date >= from_date)
    if to_date:
        conds.append(Journey.journey_date <= to_date)
    if vehicle_id:
        conds.append(Journey.vehicle_id == vehicle_id)
    return conds


def expense_conditions(
    user_id: uuid.UUID, from_date: date | None, to_date: date | None, vehicle_id: uuid.UUID | None = None
) -> list[ColumnElement[bool]]:
    conds = [Expense.user_id == user_id, Expense.deleted_at.is_(None)]
    if from_date:
        conds.append(Expense.expense_date >= from_date)
    if to_date:
        conds.append(Expense.expense_date <= to_date)
    if vehicle_id:
        conds.append(Expense.vehicle_id == vehicle_id)
    return conds


def journey_totals(db: Session, conds: list) -> tuple[int, Decimal, Decimal]:
    count, revenue, distance = db.execute(
        select(
            func.count(Journey.id),
            func.coalesce(func.sum(Journey.net_revenue), 0),
            func.coalesce(func.sum(Journey.distance_km), 0),
        ).where(*conds)
    ).one()
    return int(count), money(dec(revenue)), dec(distance)


def expense_total(db: Session, conds: list) -> Decimal:
    return money(dec(db.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(*conds))))


def revenue_by_platform(db: Session, conds: list) -> list[PlatformAmount]:
    total = func.sum(Journey.net_revenue)
    rows = db.execute(
        select(Journey.platform, total, func.count(Journey.id))
        .where(*conds)
        .group_by(Journey.platform)
        .order_by(total.desc())
    ).all()
    return [PlatformAmount(platform=p, amount=money(dec(a)), journeys=int(c)) for p, a, c in rows]


def expenses_by_category(db: Session, conds: list) -> list[CategoryAmount]:
    total = func.sum(Expense.amount)
    rows = db.execute(
        select(Expense.category, total, func.count(Expense.id))
        .where(*conds)
        .group_by(Expense.category)
        .order_by(total.desc())
    ).all()
    return [CategoryAmount(category=cat, amount=money(dec(a)), count=int(c)) for cat, a, c in rows]


def daily_financials(
    db: Session, journey_conds: list, expense_conds: list, from_date: date, to_date: date
) -> list[DailyFinancial]:
    revenue = dict(
        db.execute(
            select(Journey.journey_date, func.sum(Journey.net_revenue))
            .where(*journey_conds)
            .group_by(Journey.journey_date)
        ).all()
    )
    expenses = dict(
        db.execute(
            select(Expense.expense_date, func.sum(Expense.amount)).where(*expense_conds).group_by(Expense.expense_date)
        ).all()
    )
    result = []
    for day in iter_days(from_date, to_date):
        r, e = money(dec(revenue.get(day))), money(dec(expenses.get(day)))
        result.append(DailyFinancial(date=day, revenue=r, expenses=e, profit=r - e))
    return result


def get_dashboard(
    db: Session, user_id: uuid.UUID, from_date: date, to_date: date, vehicle_id: uuid.UUID | None
) -> DashboardSummary:
    jc = journey_conditions(user_id, from_date, to_date, vehicle_id)
    ec = expense_conditions(user_id, from_date, to_date, vehicle_id)

    journeys, revenue, distance = journey_totals(db, jc)
    expenses = expense_total(db, ec)
    profit = revenue - expenses

    outstanding_conds = journey_conditions(user_id, None, None, vehicle_id) + [
        Journey.payment_status != PaymentStatus.PAID
    ]
    outstanding, outstanding_count = db.execute(
        select(func.coalesce(func.sum(Journey.net_revenue - Journey.amount_paid), 0), func.count(Journey.id)).where(
            *outstanding_conds
        )
    ).one()

    return DashboardSummary(
        from_date=from_date,
        to_date=to_date,
        vehicle_id=vehicle_id,
        total_revenue=revenue,
        total_expenses=expenses,
        net_profit=profit,
        total_journeys=journeys,
        total_distance_km=distance,
        average_revenue_per_km=safe_div(revenue, distance),
        average_profit_per_journey=safe_div(profit, journeys),
        outstanding_amount=money(dec(outstanding)),
        outstanding_journeys=int(outstanding_count),
        revenue_by_platform=revenue_by_platform(db, jc),
        expenses_by_category=expenses_by_category(db, ec),
        daily_financials=daily_financials(db, jc, ec, from_date, to_date),
    )
