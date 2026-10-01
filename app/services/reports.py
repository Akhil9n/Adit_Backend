import csv
import io
import uuid
from collections.abc import Iterable, Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Driver, Expense, Journey, Vehicle
from app.schemas.report import (
    DayAmount,
    DriverReport,
    DriverRow,
    ExpenseReport,
    JourneyRevenueRow,
    PlatformProfit,
    ProfitabilityReport,
    RevenueReport,
    VehicleAmount,
)
from app.services.common import ZERO, dec, iter_days, money, safe_div
from app.services.dashboard import (
    daily_financials,
    expense_conditions,
    expense_total,
    expenses_by_category,
    journey_conditions,
    journey_totals,
    revenue_by_platform,
)
from app.services.journey import journey_expense_totals


def _by_day(rows: Iterable[tuple[date, Any, Any]], from_date: date, to_date: date) -> list[DayAmount]:
    lookup = {d: (a, c) for d, a, c in rows}
    out = []
    for day in iter_days(from_date, to_date):
        amount, count = lookup.get(day, (0, 0))
        out.append(DayAmount(date=day, amount=money(dec(amount)), count=int(count)))
    return out


def revenue_report(
    db: Session, user_id: uuid.UUID, from_date: date, to_date: date, vehicle_id: uuid.UUID | None = None
) -> RevenueReport:
    jc = journey_conditions(user_id, from_date, to_date, vehicle_id)
    gross, commission, deductions = db.execute(
        select(
            func.coalesce(func.sum(Journey.gross_fare), 0),
            func.coalesce(func.sum(Journey.platform_commission), 0),
            func.coalesce(func.sum(Journey.other_deductions), 0),
        ).where(*jc)
    ).one()
    count, revenue, _ = journey_totals(db, jc)

    day_rows = db.execute(
        select(Journey.journey_date, func.sum(Journey.net_revenue), func.count(Journey.id))
        .where(*jc)
        .group_by(Journey.journey_date)
    ).all()

    totals = journey_expense_totals(user_id)
    journey_rows = db.execute(
        select(Journey, func.coalesce(totals.c.total, 0))
        .outerjoin(totals, totals.c.journey_id == Journey.id)
        .where(*jc)
        .order_by(Journey.journey_date.desc(), Journey.start_time.desc().nulls_last())
    ).all()
    by_journey = [
        JourneyRevenueRow(
            id=j.id,
            journey_date=j.journey_date,
            platform=j.platform,
            pickup_location=j.pickup_location,
            drop_location=j.drop_location,
            distance_km=j.distance_km,
            gross_fare=j.gross_fare,
            platform_commission=j.platform_commission,
            other_deductions=j.other_deductions,
            net_revenue=j.net_revenue,
            expenses=money(dec(exp)),
            profit=money(j.net_revenue - dec(exp)),
            payment_status=j.payment_status,
        )
        for j, exp in journey_rows
    ]

    return RevenueReport(
        from_date=from_date,
        to_date=to_date,
        total_revenue=revenue,
        total_gross_fare=money(dec(gross)),
        total_commission=money(dec(commission)),
        total_deductions=money(dec(deductions)),
        total_journeys=count,
        by_platform=revenue_by_platform(db, jc),
        by_day=_by_day(day_rows, from_date, to_date),
        by_journey=by_journey,
    )


def expense_report(
    db: Session, user_id: uuid.UUID, from_date: date, to_date: date, vehicle_id: uuid.UUID | None = None
) -> ExpenseReport:
    ec = expense_conditions(user_id, from_date, to_date, vehicle_id)
    total = expense_total(db, ec)
    journey_linked = expense_total(db, ec + [Expense.journey_id.is_not(None)])
    count = db.scalar(select(func.count(Expense.id)).where(*ec)) or 0

    day_rows = db.execute(
        select(Expense.expense_date, func.sum(Expense.amount), func.count(Expense.id))
        .where(*ec)
        .group_by(Expense.expense_date)
    ).all()
    amount = func.sum(Expense.amount)
    vehicle_rows = db.execute(
        select(Vehicle.id, Vehicle.registration_number, amount, func.count(Expense.id))
        .join(Vehicle, Vehicle.id == Expense.vehicle_id)
        .where(*ec)
        .group_by(Vehicle.id, Vehicle.registration_number)
        .order_by(amount.desc())
    ).all()

    return ExpenseReport(
        from_date=from_date,
        to_date=to_date,
        total_expenses=total,
        journey_expenses=journey_linked,
        general_expenses=total - journey_linked,
        total_count=int(count),
        by_category=expenses_by_category(db, ec),
        by_day=_by_day(day_rows, from_date, to_date),
        by_vehicle=[
            VehicleAmount(vehicle_id=vid, registration_number=reg, amount=money(dec(a)), count=int(c))
            for vid, reg, a, c in vehicle_rows
        ],
    )


def profitability_report(
    db: Session, user_id: uuid.UUID, from_date: date, to_date: date, vehicle_id: uuid.UUID | None = None
) -> ProfitabilityReport:
    jc = journey_conditions(user_id, from_date, to_date, vehicle_id)
    ec = expense_conditions(user_id, from_date, to_date, vehicle_id)
    journeys, revenue, distance = journey_totals(db, jc)
    expenses = expense_total(db, ec)
    journey_expenses = expense_total(db, ec + [Expense.journey_id.is_not(None)])
    profit = revenue - expenses

    # Per-platform profit uses expenses linked to that platform's journeys (general costs can't be attributed).
    totals = journey_expense_totals(user_id)
    platform_rows = db.execute(
        select(
            Journey.platform,
            func.count(Journey.id),
            func.coalesce(func.sum(Journey.distance_km), 0),
            func.coalesce(func.sum(Journey.net_revenue), 0),
            func.coalesce(func.sum(totals.c.total), 0),
        )
        .outerjoin(totals, totals.c.journey_id == Journey.id)
        .where(*jc)
        .group_by(Journey.platform)
        .order_by(func.sum(Journey.net_revenue).desc())
    ).all()

    return ProfitabilityReport(
        from_date=from_date,
        to_date=to_date,
        revenue=revenue,
        expenses=expenses,
        journey_expenses=journey_expenses,
        general_expenses=expenses - journey_expenses,
        profit=profit,
        total_journeys=journeys,
        total_distance_km=distance,
        profit_per_journey=safe_div(profit, journeys),
        profit_per_km=safe_div(profit, distance),
        revenue_per_km=safe_div(revenue, distance),
        by_platform=[
            PlatformProfit(
                platform=p,
                journeys=int(c),
                distance_km=dec(d),
                revenue=money(dec(r)),
                journey_expenses=money(dec(e)),
                profit=money(dec(r) - dec(e)),
            )
            for p, c, d, r, e in platform_rows
        ],
        daily=daily_financials(db, jc, ec, from_date, to_date),
    )


def driver_report(
    db: Session, user_id: uuid.UUID, from_date: date, to_date: date, vehicle_id: uuid.UUID | None = None
) -> DriverReport:
    jc = journey_conditions(user_id, from_date, to_date, vehicle_id)
    ec = expense_conditions(user_id, from_date, to_date, vehicle_id)
    journey_rows = db.execute(
        select(
            Journey.driver_id,
            func.count(Journey.id),
            func.coalesce(func.sum(Journey.distance_km), 0),
            func.coalesce(func.sum(Journey.net_revenue), 0),
        )
        .where(*jc)
        .group_by(Journey.driver_id)
    ).all()
    expense_rows = dict(
        db.execute(select(Expense.driver_id, func.sum(Expense.amount)).where(*ec).group_by(Expense.driver_id)).all()
    )
    names = dict(db.execute(select(Driver.id, Driver.name).where(Driver.user_id == user_id)).all())

    stats: dict[uuid.UUID | None, DriverRow] = {}
    for driver_id, count, distance, revenue in journey_rows:
        stats[driver_id] = DriverRow(
            driver_id=driver_id,
            name=names.get(driver_id, "Unassigned"),
            journeys=int(count),
            distance_km=dec(distance),
            revenue=money(dec(revenue)),
            driver_expenses=ZERO,
        )
    for driver_id, amount in expense_rows.items():
        row = stats.setdefault(
            driver_id,
            DriverRow(
                driver_id=driver_id,
                name=names.get(driver_id, "Unassigned"),
                journeys=0,
                distance_km=ZERO,
                revenue=ZERO,
                driver_expenses=ZERO,
            ),
        )
        row.driver_expenses = money(dec(amount))
    # Named drivers by revenue, "Unassigned" last.
    rows = sorted(stats.values(), key=lambda r: (r.driver_id is None, -r.revenue))
    return DriverReport(from_date=from_date, to_date=to_date, rows=rows)


# --- CSV ---------------------------------------------------------------------------------


def _cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, Decimal) and value.as_tuple().exponent < -2:  # type: ignore[operator]
        # Unscaled NUMERIC (quantities, odometer) — drop insignificant trailing zeros.
        return format(value.normalize(), "f")
    return value


def to_csv(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_cell(v) for v in row])
    return buffer.getvalue()


def report_csv(
    db: Session, user_id: uuid.UUID, kind: str, from_date: date, to_date: date, vehicle_id: uuid.UUID | None
) -> str:
    if kind == "revenue":
        r = revenue_report(db, user_id, from_date, to_date, vehicle_id)
        return to_csv(
            [
                "Date",
                "Platform",
                "Pickup",
                "Drop",
                "Distance (km)",
                "Gross fare",
                "Commission",
                "Other deductions",
                "Net revenue",
                "Expenses",
                "Profit",
                "Payment status",
            ],
            (
                [
                    j.journey_date,
                    j.platform,
                    j.pickup_location,
                    j.drop_location,
                    j.distance_km,
                    j.gross_fare,
                    j.platform_commission,
                    j.other_deductions,
                    j.net_revenue,
                    j.expenses,
                    j.profit,
                    j.payment_status,
                ]
                for j in r.by_journey
            ),
        )
    if kind == "expenses":
        stmt = (
            select(Expense, Vehicle.registration_number, Driver.name)
            .join(Vehicle, Vehicle.id == Expense.vehicle_id)
            .outerjoin(Driver, Driver.id == Expense.driver_id)
            .where(*expense_conditions(user_id, from_date, to_date, vehicle_id))
            .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
        )
        return to_csv(
            [
                "Date",
                "Category",
                "Amount",
                "Payment method",
                "Vehicle",
                "Driver",
                "Journey linked",
                "Description",
                "Fuel type",
                "Quantity",
                "Price per unit",
                "Fuel station",
                "Odometer",
                "Notes",
            ],
            (
                [
                    e.expense_date,
                    e.category,
                    e.amount,
                    e.payment_method,
                    reg,
                    name,
                    "yes" if e.journey_id else "no",
                    e.description,
                    e.fuel_type,
                    e.quantity,
                    e.price_per_unit,
                    e.fuel_station,
                    e.odometer_reading,
                    e.notes,
                ]
                for e, reg, name in db.execute(stmt).all()
            ),
        )
    if kind == "profitability":
        r = profitability_report(db, user_id, from_date, to_date, vehicle_id)
        return to_csv(
            ["Date", "Revenue", "Expenses", "Profit"], ([d.date, d.revenue, d.expenses, d.profit] for d in r.daily)
        )
    if kind == "drivers":
        r = driver_report(db, user_id, from_date, to_date, vehicle_id)
        return to_csv(
            ["Driver", "Journeys", "Distance (km)", "Revenue", "Driver expenses"],
            ([d.name, d.journeys, d.distance_km, d.revenue, d.driver_expenses] for d in r.rows),
        )
    raise ValueError(kind)
