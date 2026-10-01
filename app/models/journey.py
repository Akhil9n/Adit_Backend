import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.driver import Driver
from app.models.vehicle import Vehicle


class Journey(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "journeys"
    __table_args__ = (
        Index("ix_journeys_user_date", "user_id", "journey_date"),
        Index("ix_journeys_vehicle_date", "vehicle_id", "journey_date"),
        Index("ix_journeys_driver_date", "driver_id", "journey_date"),
        CheckConstraint(
            "ending_odometer IS NULL OR starting_odometer IS NULL OR ending_odometer >= starting_odometer",
            name="ck_journeys_odometer_order",
        ),
        CheckConstraint(
            "gross_fare >= 0 AND platform_commission >= 0 AND other_deductions >= 0 AND net_revenue >= 0 "
            "AND amount_paid >= 0",
            name="ck_journeys_non_negative_money",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False)
    driver_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("drivers.id", ondelete="SET NULL"))

    # Calendar date of the trip in the business timezone. Stored as DATE, never as a timestamp,
    # so timezone conversion can never move it to another day.
    journey_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    trip_type: Mapped[str | None] = mapped_column(String(30))
    pickup_location: Mapped[str | None] = mapped_column(Text)
    drop_location: Mapped[str | None] = mapped_column(Text)

    starting_odometer: Mapped[Decimal | None] = mapped_column(Numeric)
    ending_odometer: Mapped[Decimal | None] = mapped_column(Numeric)
    distance_km: Mapped[Decimal | None] = mapped_column(Numeric)
    distance_overridden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    gross_fare: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default="0", nullable=False)
    platform_commission: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default="0", nullable=False)
    other_deductions: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default="0", nullable=False)
    net_revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default="0", nullable=False)
    net_revenue_overridden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    payment_status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending", nullable=False)
    # Amount actually collected so far; drives the outstanding balance.
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, server_default="0", nullable=False)

    notes: Mapped[str | None] = mapped_column(Text)

    vehicle: Mapped[Vehicle] = relationship(lazy="raise")
    driver: Mapped[Driver | None] = relationship(lazy="raise")
