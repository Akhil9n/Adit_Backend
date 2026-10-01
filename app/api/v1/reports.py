import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import Response

from app.api.deps import CurrentUserId, DbSession
from app.schemas.report import DriverReport, ExpenseReport, ProfitabilityReport, RevenueReport
from app.services import reports as service
from app.services.common import resolve_range

router = APIRouter(prefix="/reports", tags=["reports"])

ReportKind = Literal["revenue", "expenses", "profitability", "drivers"]


@router.get("/revenue", response_model=RevenueReport)
def revenue(
    db: DbSession,
    user_id: CurrentUserId,
    from_date: date | None = None,
    to_date: date | None = None,
    vehicle_id: uuid.UUID | None = None,
):
    return service.revenue_report(db, user_id, *resolve_range(from_date, to_date), vehicle_id)


@router.get("/expenses", response_model=ExpenseReport)
def expenses(
    db: DbSession,
    user_id: CurrentUserId,
    from_date: date | None = None,
    to_date: date | None = None,
    vehicle_id: uuid.UUID | None = None,
):
    return service.expense_report(db, user_id, *resolve_range(from_date, to_date), vehicle_id)


@router.get("/profitability", response_model=ProfitabilityReport)
def profitability(
    db: DbSession,
    user_id: CurrentUserId,
    from_date: date | None = None,
    to_date: date | None = None,
    vehicle_id: uuid.UUID | None = None,
):
    return service.profitability_report(db, user_id, *resolve_range(from_date, to_date), vehicle_id)


@router.get("/drivers", response_model=DriverReport)
def drivers(
    db: DbSession,
    user_id: CurrentUserId,
    from_date: date | None = None,
    to_date: date | None = None,
    vehicle_id: uuid.UUID | None = None,
):
    return service.driver_report(db, user_id, *resolve_range(from_date, to_date), vehicle_id)


@router.get("/{kind}/csv", response_class=Response, responses={200: {"content": {"text/csv": {}}}})
def export_csv(
    kind: ReportKind,
    db: DbSession,
    user_id: CurrentUserId,
    from_date: date | None = None,
    to_date: date | None = None,
    vehicle_id: uuid.UUID | None = None,
) -> Response:
    start, end = resolve_range(from_date, to_date)
    content = service.report_csv(db, user_id, kind, start, end, vehicle_id)
    filename = f"{kind}-report-{start.isoformat()}-to-{end.isoformat()}.csv"
    # BOM so Excel opens the ₹/UTF-8 content correctly.
    return Response(
        content="\N{BYTE ORDER MARK}" + content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
