"""attendance service type and registration phone

Revision ID: c2c9f5a6e812
Revises: 9b2d8a1f4c21
Create Date: 2026-02-21 20:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c2c9f5a6e812"
down_revision: Union[str, None] = "9b2d8a1f4c21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    attendance_cols = {c["name"] for c in inspector.get_columns("attendance")}
    if "service_type" not in attendance_cols:
        op.add_column(
            "attendance",
            sa.Column("service_type", sa.String(length=32), nullable=False, server_default="sunday_service"),
        )
        op.alter_column("attendance", "service_type", server_default=None)

    attendance_uq = {c["name"] for c in inspector.get_unique_constraints("attendance")}
    if "uq_member_day_service" not in attendance_uq:
        if "uq_member_day" in attendance_uq:
            op.drop_constraint("uq_member_day", "attendance", type_="unique")
        op.create_unique_constraint(
            "uq_member_day_service",
            "attendance",
            ["member_id", "service_date", "service_type"],
        )

    reg_cols = {c["name"] for c in inspector.get_columns("registrations")}
    if "phone_number" not in reg_cols:
        op.add_column("registrations", sa.Column("phone_number", sa.String(length=32), nullable=True))
        op.execute("UPDATE registrations SET phone_number = 'tmp-' || id::text WHERE phone_number IS NULL")
        op.alter_column("registrations", "phone_number", nullable=False)

    reg_uq = {c["name"] for c in inspector.get_unique_constraints("registrations")}
    if "uq_registrations_phone_number" not in reg_uq and "phone_number" in {c["name"] for c in inspector.get_columns("registrations")}:
        op.create_unique_constraint("uq_registrations_phone_number", "registrations", ["phone_number"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    reg_uq = {c["name"] for c in inspector.get_unique_constraints("registrations")}
    if "uq_registrations_phone_number" in reg_uq:
        op.drop_constraint("uq_registrations_phone_number", "registrations", type_="unique")

    reg_cols = {c["name"] for c in inspector.get_columns("registrations")}
    if "phone_number" in reg_cols:
        op.drop_column("registrations", "phone_number")

    attendance_uq = {c["name"] for c in inspector.get_unique_constraints("attendance")}
    if "uq_member_day_service" in attendance_uq:
        op.drop_constraint("uq_member_day_service", "attendance", type_="unique")
    if "uq_member_day" not in attendance_uq:
        op.create_unique_constraint("uq_member_day", "attendance", ["member_id", "service_date"])

    attendance_cols = {c["name"] for c in inspector.get_columns("attendance")}
    if "service_type" in attendance_cols:
        op.drop_column("attendance", "service_type")
