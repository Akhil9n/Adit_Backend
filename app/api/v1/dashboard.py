import uuid
from datetime import date

from fastapi import APIRouter

from app.api.deps import CurrentUserId, DbSession
from app.schemas.dashboard import DashboardSummary
from app.services.common import resolve_range
from app.services.dashboard import get_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardSummary)
def dashboard(
    db: DbSession,
    user_id: CurrentUserId,
    from_date: date | None = None,
    to_date: date | None = None,
    vehicle_id: uuid.UUID | None = None,
):
    """Aggregated figures for the date range (defaults to the current month)."""
    start, end = resolve_range(from_date, to_date)
    return get_dashboard(db, user_id, start, end, vehicle_id)
