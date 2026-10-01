import uuid
from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.constants import DriverStatus, PaymentModel
from app.schemas.common import OptStr, ORMModel, UtcDatetime

DriverName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


class DriverCreate(BaseModel):
    name: DriverName
    phone: Annotated[OptStr, Field(max_length=30)] = None
    joining_date: date | None = None
    payment_model: PaymentModel | None = None
    status: DriverStatus = DriverStatus.ACTIVE
    notes: OptStr = None


class DriverUpdate(BaseModel):
    name: DriverName | None = None
    phone: Annotated[OptStr, Field(max_length=30)] = None
    joining_date: date | None = None
    payment_model: PaymentModel | None = None
    status: DriverStatus | None = None
    notes: OptStr = None


class DriverRead(ORMModel):
    id: uuid.UUID
    name: str
    phone: str | None
    joining_date: date | None
    payment_model: str | None
    status: str
    notes: str | None
    created_at: UtcDatetime
    updated_at: UtcDatetime
