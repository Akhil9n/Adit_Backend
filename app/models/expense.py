import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin, utcnow
from app.models.driver import Driver
from app.models.journey import Journey
from app.models.vehicle import Vehicle


class Expense(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "expenses"
    __table_args__ = (
        Index("ix_expenses_user_date", "user_id", "expense_date"),
        Index("ix_expenses_vehicle_date", "vehicle_id", "expense_date"),
        Index("ix_expenses_journey", "journey_id"),
        Index("ix_expenses_category", "category"),
        CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False)
    driver_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("drivers.id", ondelete="SET NULL"))
    journey_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("journeys.id", ondelete="SET NULL"))

    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[str | None] = mapped_column(String(30))
    description: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    fuel_type: Mapped[str | None] = mapped_column(String(30))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric)
    price_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    fuel_station: Mapped[str | None] = mapped_column(String(150))
    odometer_reading: Mapped[Decimal | None] = mapped_column(Numeric)

    vehicle: Mapped[Vehicle] = relationship(lazy="raise")
    driver: Mapped[Driver | None] = relationship(lazy="raise")
    journey: Mapped[Journey | None] = relationship(lazy="raise")


class ExpenseCategory(Base):
    __tablename__ = "expense_categories"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # NULL user_id = system category visible to every user.
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )
