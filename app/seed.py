"""Development seed data.

Usage (after `alembic upgrade head`):
    python -m app.seed --email you@example.com      # look up the Supabase auth user
    python -m app.seed --user-id <uuid>             # or pass the auth user id directly
    python -m app.seed --email you@example.com --reset   # wipe that user's data first

Creates one vehicle, two drivers, ~18 journeys across the last 30 days and a realistic
mix of journey and general expenses. Data goes through the same service layer as the API,
so all calculations match production behaviour.
"""

import argparse
import random
import sys
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import delete, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_sessionmaker
from app.models import Driver, Expense, Journey, Vehicle
from app.schemas.driver import DriverCreate
from app.schemas.expense import ExpenseCreate
from app.schemas.journey import JourneyCreate
from app.schemas.vehicle import VehicleCreate
from app.services import driver as driver_service
from app.services import expense as expense_service
from app.services import journey as journey_service
from app.services import vehicle as vehicle_service
from app.services.common import today_local

ROUTES = [
    ("uber", "local", "Andheri", "BKC", 14, 480),
    ("uber", "local", "Mumbai Central", "Thane", 42, 1250),
    ("ola", "local", "Powai", "Lower Parel", 22, 620),
    ("ola", "airport", "Bandra", "Mumbai Airport T2", 11, 540),
    ("uber", "airport", "Mumbai Airport T2", "Vashi", 28, 980),
    ("direct", "intercity", "Mumbai", "Pune", 150, 3500),
    ("outstation", "outstation", "Mumbai", "Nashik", 170, 5200),
    ("direct", "local", "Dadar", "Colaba", 12, 600),
    ("ola", "local", "Goregaon", "Malad", 9, 260),
]


def resolve_user(db: Session, user_id: str | None, email: str | None) -> uuid.UUID:
    if user_id:
        return uuid.UUID(user_id)
    row = db.execute(text("SELECT id FROM auth.users WHERE email = :email"), {"email": email}).first()
    if row is None:
        sys.exit(f"No Supabase auth user with email {email!r}. Sign up in the app first.")
    return uuid.UUID(str(row[0]))


def reset(db: Session, user_id: uuid.UUID) -> None:
    for model in (Expense, Journey, Driver, Vehicle):
        db.execute(delete(model).where(model.user_id == user_id))
    db.commit()


def seed(db: Session, user_id: uuid.UUID) -> None:
    rng = random.Random(42)
    tz = ZoneInfo(get_settings().timezone)
    today = today_local()

    vehicle = vehicle_service.create_vehicle(
        db,
        user_id,
        VehicleCreate(
            registration_number="MH-XX-1234",
            make="Maruti Suzuki",
            model="Dzire Tour S",
            year=2023,
            fuel_type="cng",
            current_odometer=Decimal("48210"),
        ),
    )
    drivers = [
        driver_service.create_driver(
            db,
            user_id,
            DriverCreate(
                name="Driver 1",
                phone="98200 11111",
                joining_date=today - timedelta(days=400),
                payment_model="daily_allowance",
            ),
        ),
        driver_service.create_driver(
            db,
            user_id,
            DriverCreate(
                name="Driver 2", phone="98200 22222", joining_date=today - timedelta(days=120), payment_model="per_trip"
            ),
        ),
    ]

    odometer = Decimal("48210")
    journeys = 0
    for days_ago in range(29, -1, -1):
        day = today - timedelta(days=days_ago)
        trips = 0 if days_ago % 6 == 5 else rng.randint(2, 4)  # some idle days
        clock = datetime.combine(day, time(8, 30), tz)
        for _ in range(trips):
            platform, trip_type, pickup, drop, km, fare = rng.choice(ROUTES)
            km = km + rng.randint(-2, 3)
            gross = Decimal(fare + rng.randint(-40, 60))
            commission = (gross * Decimal("0.20")).quantize(Decimal("1")) if platform in ("uber", "ola") else Decimal(0)
            duration = timedelta(minutes=int(km * 2.4) + 15)
            status = "paid" if days_ago > 3 or rng.random() > 0.4 else rng.choice(["pending", "partial"])
            net = gross - commission
            driver = drivers[journeys % 2]
            j = journey_service.create_journey(
                db,
                user_id,
                JourneyCreate(
                    vehicle_id=vehicle.id,
                    driver_id=driver.id,
                    journey_date=day,
                    start_time=clock,
                    end_time=clock + duration,
                    platform=platform,
                    trip_type=trip_type,
                    pickup_location=pickup,
                    drop_location=drop,
                    starting_odometer=odometer,
                    ending_odometer=odometer + km,
                    gross_fare=gross,
                    platform_commission=commission,
                    payment_status=status,
                    amount_paid=(net / 2).quantize(Decimal("1")) if status == "partial" else None,
                ),
            )
            odometer += km + rng.randint(2, 8)  # dead mileage between trips
            clock += duration + timedelta(hours=rng.randint(1, 3))
            journeys += 1

            if trip_type in ("airport", "intercity", "outstation") or km > 25:
                expense_service.create_expense(
                    db,
                    user_id,
                    ExpenseCreate(
                        expense_date=day,
                        category="Toll",
                        amount=Decimal(rng.choice([45, 75, 120, 270])),
                        payment_method="upi",
                        journey_id=j.id,
                        description=f"Toll {pickup} → {drop}",
                    ),
                )
            if trip_type in ("airport",):
                expense_service.create_expense(
                    db,
                    user_id,
                    ExpenseCreate(
                        expense_date=day,
                        category="Parking",
                        amount=Decimal(rng.choice([60, 90])),
                        payment_method="cash",
                        journey_id=j.id,
                        description="Airport parking",
                    ),
                )
            if trip_type in ("intercity", "outstation"):
                expense_service.create_expense(
                    db,
                    user_id,
                    ExpenseCreate(
                        expense_date=day,
                        category="Driver",
                        amount=Decimal(300 if trip_type == "intercity" else 500),
                        payment_method="cash",
                        journey_id=j.id,
                        description="Driver allowance",
                    ),
                )

        if days_ago % 3 == 0:
            qty = Decimal(rng.randint(70, 95)) / 10
            expense_service.create_expense(
                db,
                user_id,
                ExpenseCreate(
                    expense_date=day,
                    category="Fuel",
                    fuel_type="cng",
                    quantity=qty,
                    price_per_unit=Decimal("76.59"),
                    payment_method="upi",
                    vehicle_id=vehicle.id,
                    fuel_station="HP CNG, Andheri East",
                    odometer_reading=odometer,
                ),
            )
        if days_ago % 7 == 1:
            expense_service.create_expense(
                db,
                user_id,
                ExpenseCreate(
                    expense_date=day,
                    category="Cleaning",
                    amount=Decimal(250),
                    payment_method="cash",
                    vehicle_id=vehicle.id,
                    description="Car wash",
                ),
            )

    expense_service.create_expense(
        db,
        user_id,
        ExpenseCreate(
            expense_date=today - timedelta(days=18),
            category="Maintenance",
            amount=Decimal(4200),
            payment_method="card",
            vehicle_id=vehicle.id,
            description="Periodic service + brake pads",
        ),
    )
    expense_service.create_expense(
        db,
        user_id,
        ExpenseCreate(
            expense_date=today - timedelta(days=25),
            category="Driver",
            amount=Decimal(9000),
            payment_method="bank_transfer",
            vehicle_id=vehicle.id,
            driver_id=drivers[0].id,
            description="Monthly salary",
        ),
    )
    expense_service.create_expense(
        db,
        user_id,
        ExpenseCreate(
            expense_date=today.replace(day=1),
            category="EMI",
            amount=Decimal(14500),
            payment_method="bank_transfer",
            vehicle_id=vehicle.id,
            description="Car loan EMI",
        ),
    )

    print(f"Seeded vehicle {vehicle.registration_number}, 2 drivers and {journeys} journeys for user {user_id}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    who = parser.add_mutually_exclusive_group(required=True)
    who.add_argument("--user-id")
    who.add_argument("--email")
    parser.add_argument("--reset", action="store_true", help="delete the user's existing data first")
    args = parser.parse_args()

    with get_sessionmaker()() as db:
        user_id = resolve_user(db, args.user_id, args.email)
        if args.reset:
            reset(db, user_id)
        elif db.query(Vehicle).filter(Vehicle.user_id == user_id).first():
            sys.exit("User already has data. Re-run with --reset to replace it.")
        seed(db, user_id)


if __name__ == "__main__":
    main()
