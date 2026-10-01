"""Initial schema: vehicles, drivers, journeys, expenses, expense categories.

Revision ID: 0001
Revises:
Create Date: 2026-10-01
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.constants import SYSTEM_EXPENSE_CATEGORIES

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USER_TABLES = ("vehicles", "drivers", "journeys", "expenses")


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.Uuid, nullable=False),
        sa.Column("registration_number", sa.String(50), nullable=False),
        sa.Column("make", sa.String(100)),
        sa.Column("model", sa.String(100)),
        sa.Column("year", sa.Integer),
        sa.Column("fuel_type", sa.String(30)),
        sa.Column("current_odometer", sa.Numeric),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("notes", sa.Text),
        *_timestamps(),
    )
    op.create_index("ix_vehicles_user_id", "vehicles", ["user_id"])

    op.create_table(
        "drivers",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.Uuid, nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("phone", sa.String(30)),
        sa.Column("joining_date", sa.Date),
        sa.Column("payment_model", sa.String(30)),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("notes", sa.Text),
        *_timestamps(),
    )
    op.create_index("ix_drivers_user_id", "drivers", ["user_id"])

    op.create_table(
        "journeys",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.Uuid, nullable=False),
        sa.Column("vehicle_id", sa.Uuid, sa.ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("driver_id", sa.Uuid, sa.ForeignKey("drivers.id", ondelete="SET NULL")),
        sa.Column("journey_date", sa.Date, nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True)),
        sa.Column("end_time", sa.DateTime(timezone=True)),
        sa.Column("platform", sa.String(30), nullable=False),
        sa.Column("trip_type", sa.String(30)),
        sa.Column("pickup_location", sa.Text),
        sa.Column("drop_location", sa.Text),
        sa.Column("starting_odometer", sa.Numeric),
        sa.Column("ending_odometer", sa.Numeric),
        sa.Column("distance_km", sa.Numeric),
        sa.Column("distance_overridden", sa.Boolean, server_default=sa.false(), nullable=False),
        sa.Column("gross_fare", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("platform_commission", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("other_deductions", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("net_revenue", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("net_revenue_overridden", sa.Boolean, server_default=sa.false(), nullable=False),
        sa.Column("payment_status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("amount_paid", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("notes", sa.Text),
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "ending_odometer IS NULL OR starting_odometer IS NULL OR ending_odometer >= starting_odometer",
            name="ck_journeys_odometer_order",
        ),
        sa.CheckConstraint(
            "gross_fare >= 0 AND platform_commission >= 0 AND other_deductions >= 0 AND net_revenue >= 0 "
            "AND amount_paid >= 0",
            name="ck_journeys_non_negative_money",
        ),
    )
    op.create_index("ix_journeys_user_date", "journeys", ["user_id", "journey_date"])
    op.create_index("ix_journeys_vehicle_date", "journeys", ["vehicle_id", "journey_date"])
    op.create_index("ix_journeys_driver_date", "journeys", ["driver_id", "journey_date"])

    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.Uuid, nullable=False),
        sa.Column("vehicle_id", sa.Uuid, sa.ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("driver_id", sa.Uuid, sa.ForeignKey("drivers.id", ondelete="SET NULL")),
        sa.Column("journey_id", sa.Uuid, sa.ForeignKey("journeys.id", ondelete="SET NULL")),
        sa.Column("expense_date", sa.Date, nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_method", sa.String(30)),
        sa.Column("description", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("fuel_type", sa.String(30)),
        sa.Column("quantity", sa.Numeric),
        sa.Column("price_per_unit", sa.Numeric(12, 2)),
        sa.Column("fuel_station", sa.String(150)),
        sa.Column("odometer_reading", sa.Numeric),
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
    )
    op.create_index("ix_expenses_user_date", "expenses", ["user_id", "expense_date"])
    op.create_index("ix_expenses_vehicle_date", "expenses", ["vehicle_id", "expense_date"])
    op.create_index("ix_expenses_journey", "expenses", ["journey_id"])
    op.create_index("ix_expenses_category", "expenses", ["category"])

    categories = op.create_table(
        "expense_categories",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.Uuid),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_system", sa.Boolean, server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_expense_categories_user_id", "expense_categories", ["user_id"])
    op.bulk_insert(
        categories,
        [{"id": uuid.uuid4(), "user_id": None, "name": name, "is_system": True} for name in SYSTEM_EXPENSE_CATEGORIES],
    )

    _enable_supabase_rls()


def _enable_supabase_rls() -> None:
    """Defence in depth for Supabase: tables in the public schema are reachable through the
    Data API with the anon key. RLS ensures that path only ever exposes the caller's own rows.
    The FastAPI backend connects as the table owner and enforces ownership itself.
    Skipped on plain PostgreSQL where Supabase's auth schema/roles don't exist."""
    statements = []
    for table in USER_TABLES:
        statements += [
            f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
            f"CREATE POLICY {table}_owner ON {table} FOR ALL TO authenticated "
            f"USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid())",
        ]
    statements += [
        "ALTER TABLE expense_categories ENABLE ROW LEVEL SECURITY",
        "CREATE POLICY expense_categories_read ON expense_categories FOR SELECT TO authenticated "
        "USING (user_id IS NULL OR user_id = auth.uid())",
        "CREATE POLICY expense_categories_write ON expense_categories FOR ALL TO authenticated "
        "USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid())",
        # No policies: Alembic's bookkeeping table is never reachable through the Data API.
        "ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY",
    ]
    body = ";\n    ".join(s.replace("'", "''") for s in statements)
    op.execute(
        f"""
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated')
     AND EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                 WHERE n.nspname = 'auth' AND p.proname = 'uid') THEN
    {body};
  END IF;
END $$;
"""
    )


def downgrade() -> None:
    op.drop_table("expense_categories")
    op.drop_table("expenses")
    op.drop_table("journeys")
    op.drop_table("drivers")
    op.drop_table("vehicles")
