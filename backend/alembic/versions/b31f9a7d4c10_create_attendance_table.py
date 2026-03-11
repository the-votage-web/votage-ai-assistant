"""create attendance table

Revision ID: b31f9a7d4c10
Revises: 8c9b0f7a1d22
Create Date: 2026-03-04 15:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b31f9a7d4c10"
down_revision: Union[str, None] = "8c9b0f7a1d22"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("attendance"):
        op.create_table(
            "attendance",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("service_type", sa.String(length=32), nullable=False, server_default="sunday_service"),
            sa.Column("connect_name", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("service_date", sa.Date(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["member_id"], ["members.id"], name="fk_attendance_member_id"),
            sa.ForeignKeyConstraint(["service_id"], ["service.id"], name="fk_attendance_service_id_uuid"),
            sa.PrimaryKeyConstraint("id", name="pk_attendance"),
            sa.UniqueConstraint(
                "member_id",
                "service_date",
                "service_type",
                "connect_name",
                name="uq_member_day_service_connect",
            ),
        )

        op.alter_column("attendance", "service_type", server_default=None)
        op.alter_column("attendance", "connect_name", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("attendance"):
        op.drop_table("attendance")
