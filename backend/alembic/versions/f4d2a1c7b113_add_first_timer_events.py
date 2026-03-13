"""add first timer events

Revision ID: f4d2a1c7b113
Revises: c2c9f5a6e812
Create Date: 2026-02-21 20:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f4d2a1c7b113"
down_revision: Union[str, None] = "c2c9f5a6e812"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "members" in inspector.get_table_names() and not inspector.has_table("first_timer_events"):
        op.create_table(
            "first_timer_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("service_type", sa.String(length=32), nullable=False),
            sa.Column("event_name", sa.String(length=120), nullable=False),
            sa.Column("service_date", sa.Date(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("member_id", "service_date", "event_name", name="uq_first_timer_member_day_event"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("first_timer_events"):
        op.drop_table("first_timer_events")
