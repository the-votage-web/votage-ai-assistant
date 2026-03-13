"""add attendance connect_name

Revision ID: 7a1f0b3c4d9e
Revises: f4d2a1c7b113
Create Date: 2026-03-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7a1f0b3c4d9e"
down_revision: Union[str, None] = "f4d2a1c7b113"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Only proceed if the table exists
    if "attendance" in inspector.get_table_names():
        attendance_cols = {c["name"] for c in inspector.get_columns("attendance")}
        if "connect_name" not in attendance_cols:
            op.add_column(
                "attendance",
                sa.Column("connect_name", sa.String(length=80), nullable=False, server_default=""),
            )
            op.alter_column("attendance", "connect_name", server_default=None)

        # Normalize nulls/legacy data before applying stricter uniqueness.
        op.execute("UPDATE attendance SET connect_name = '' WHERE connect_name IS NULL")

        attendance_uq = {c["name"] for c in inspector.get_unique_constraints("attendance")}
        if "uq_member_day_service_connect" not in attendance_uq:
            if "uq_member_day_service" in attendance_uq:
                op.drop_constraint("uq_member_day_service", "attendance", type_="unique")
            if "uq_member_day" in attendance_uq:
                op.drop_constraint("uq_member_day", "attendance", type_="unique")
            op.create_unique_constraint(
                "uq_member_day_service_connect",
                "attendance",
                ["member_id", "service_date", "service_type", "connect_name"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "attendance" in inspector.get_table_names():
        attendance_uq = {c["name"] for c in inspector.get_unique_constraints("attendance")}
        if "uq_member_day_service_connect" in attendance_uq:
            op.drop_constraint("uq_member_day_service_connect", "attendance", type_="unique")

        if "uq_member_day_service" not in attendance_uq:
            op.create_unique_constraint(
                "uq_member_day_service",
                "attendance",
                ["member_id", "service_date", "service_type"],
            )

        attendance_cols = {c["name"] for c in inspector.get_columns("attendance")}
        if "connect_name" in attendance_cols:
            op.drop_column("attendance", "connect_name")
