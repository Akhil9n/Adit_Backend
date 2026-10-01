"""Domain enumerations. Stored as plain strings in the database so new values need no migration."""

from enum import StrEnum


class Platform(StrEnum):
    UBER = "uber"
    OLA = "ola"
    DIRECT = "direct"
    OUTSTATION = "outstation"
    OTHER = "other"


class TripType(StrEnum):
    LOCAL = "local"
    OUTSTATION = "outstation"
    AIRPORT = "airport"
    INTERCITY = "intercity"
    OTHER = "other"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"


class PaymentMethod(StrEnum):
    CASH = "cash"
    UPI = "upi"
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    OTHER = "other"


class FuelType(StrEnum):
    CNG = "cng"
    PETROL = "petrol"
    DIESEL = "diesel"
    EV = "ev"
    OTHER = "other"


class VehicleStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SOLD = "sold"


class DriverStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class PaymentModel(StrEnum):
    FIXED_SALARY = "fixed_salary"
    PER_TRIP = "per_trip"
    PERCENTAGE = "percentage"
    DAILY_ALLOWANCE = "daily_allowance"
    OTHER = "other"


FUEL_CATEGORY = "Fuel"

SYSTEM_EXPENSE_CATEGORIES: list[str] = [
    "Fuel",
    "Driver",
    "Toll",
    "Parking",
    "Maintenance",
    "Service",
    "Tyres",
    "Insurance",
    "EMI",
    "Permit",
    "Cleaning",
    "Fine/Penalty",
    "Commission",
    "Miscellaneous",
]
