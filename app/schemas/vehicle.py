import uuid
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.constants import FuelType, VehicleStatus
from app.schemas.common import NonNegative, OptStr, ORMModel, Quantity, UtcDatetime

RegistrationNumber = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=1, max_length=50)
]
Year = Annotated[int, Field(ge=1950, le=2100)]


class VehicleCreate(BaseModel):
    registration_number: RegistrationNumber
    make: Annotated[OptStr, Field(max_length=100)] = None
    model: Annotated[OptStr, Field(max_length=100)] = None
    year: Year | None = None
    fuel_type: FuelType | None = None
    current_odometer: NonNegative | None = None
    status: VehicleStatus = VehicleStatus.ACTIVE
    notes: OptStr = None


class VehicleUpdate(BaseModel):
    registration_number: RegistrationNumber | None = None
    make: Annotated[OptStr, Field(max_length=100)] = None
    model: Annotated[OptStr, Field(max_length=100)] = None
    year: Year | None = None
    fuel_type: FuelType | None = None
    current_odometer: NonNegative | None = None
    status: VehicleStatus | None = None
    notes: OptStr = None


class VehicleRead(ORMModel):
    id: uuid.UUID
    registration_number: str
    make: str | None
    model: str | None
    year: int | None
    fuel_type: str | None
    current_odometer: Quantity | None
    status: str
    notes: str | None
    created_at: UtcDatetime
    updated_at: UtcDatetime
