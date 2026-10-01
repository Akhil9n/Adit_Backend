import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUserId, DbSession
from app.constants import PaymentMethod
from app.schemas.common import Money, Page
from app.schemas.expense import CategoryCreate, CategoryRead, ExpenseCreate, ExpenseRead, ExpenseUpdate
from app.services import expense as service
from app.services.common import dec, money

router = APIRouter(prefix="/expenses", tags=["expenses"])
categories_router = APIRouter(prefix="/expense-categories", tags=["expenses"])


class ExpensePage(Page[ExpenseRead]):
    total_amount: Money


@router.get("", response_model=ExpensePage)
def list_expenses(
    db: DbSession,
    user_id: CurrentUserId,
    from_date: date | None = None,
    to_date: date | None = None,
    vehicle_id: uuid.UUID | None = None,
    driver_id: uuid.UUID | None = None,
    journey_id: uuid.UUID | None = None,
    category: Annotated[str | None, Query(max_length=50)] = None,
    payment_method: PaymentMethod | None = None,
    scope: Literal["journey", "general"] | None = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    filters = service.ExpenseFilters(
        from_date=from_date,
        to_date=to_date,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        journey_id=journey_id,
        category=category,
        payment_method=payment_method,
        scope=scope,
        search=search,
    )
    items, total, amount = service.list_expenses(db, user_id, filters, limit, offset)
    return ExpensePage(items=items, total=total, total_amount=money(dec(amount)))


@router.post("", response_model=ExpenseRead, status_code=status.HTTP_201_CREATED)
def create_expense(payload: ExpenseCreate, db: DbSession, user_id: CurrentUserId):
    return service.create_expense(db, user_id, payload)


@router.get("/{expense_id}", response_model=ExpenseRead)
def get_expense(expense_id: uuid.UUID, db: DbSession, user_id: CurrentUserId):
    return service.get_expense(db, user_id, expense_id)


@router.patch("/{expense_id}", response_model=ExpenseRead)
def update_expense(expense_id: uuid.UUID, payload: ExpenseUpdate, db: DbSession, user_id: CurrentUserId):
    return service.update_expense(db, user_id, expense_id, payload)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: uuid.UUID, db: DbSession, user_id: CurrentUserId) -> None:
    service.delete_expense(db, user_id, expense_id)


@categories_router.get("", response_model=list[CategoryRead])
def list_categories(db: DbSession, user_id: CurrentUserId):
    return service.list_categories(db, user_id)


@categories_router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, db: DbSession, user_id: CurrentUserId):
    return service.create_category(db, user_id, payload)


@categories_router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: uuid.UUID, db: DbSession, user_id: CurrentUserId) -> None:
    service.delete_category(db, user_id, category_id)
