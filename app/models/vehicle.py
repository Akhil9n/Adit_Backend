import uuid
from decimal import Decimal

from sqlalchemy import Integer, Numeric, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Vehicle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vehicles"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    registration_number: Mapped[str] = mapped_column(String(50), nullable=False)
    make: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    year: Mapped[int | None] = mapped_column(Integer)
    fuel_type: Mapped[str | None] = mapped_column(String(30))
    current_odometer: Mapped[Decimal | None] = mapped_column(Numeric)
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
