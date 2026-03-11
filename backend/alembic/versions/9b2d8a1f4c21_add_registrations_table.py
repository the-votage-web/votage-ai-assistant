"""add registrations table

Revision ID: 9b2d8a1f4c21
Revises: 604d2d4a97d9
Create Date: 2026-02-21 19:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "9b2d8a1f4c21"
down_revision: Union[str, None] = "604d2d4a97d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("registrations"):
        op.create_table(
            "registrations",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("phone_number", sa.String(length=32), nullable=False),
            sa.Column("first_name", sa.String(length=80), nullable=False),
            sa.Column("last_name", sa.String(length=80), nullable=False),
            sa.Column("first_timer", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("gender", sa.String(length=32), nullable=False),
            sa.Column("marital_status", sa.String(length=32), nullable=False),
            sa.Column("service_type", sa.String(length=32), nullable=False),
            sa.Column("connect_name", sa.String(length=80), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("phone_number"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("registrations"):
        op.drop_table("registrations")
