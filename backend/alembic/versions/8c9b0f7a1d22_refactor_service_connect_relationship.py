"""refactor service-connect relationship and attendance service date

Revision ID: 8c9b0f7a1d22
Revises: 56f03ad16787
Create Date: 2026-03-04 14:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "8c9b0f7a1d22"
down_revision: Union[str, None] = "56f03ad16787"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _has_column(inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def _has_fk_on_column(inspector, table: str, column: str) -> bool:
    return any(fk.get("constrained_columns") == [column] for fk in inspector.get_foreign_keys(table))


def _drop_fk_on_column(inspector, table: str, column: str) -> None:
    for fk in inspector.get_foreign_keys(table):
        if fk.get("constrained_columns") == [column] and fk.get("name"):
            op.drop_constraint(fk["name"], table, type_="foreignkey")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1) connect_group.service_id
    if _table_exists(inspector, "connect_group") and not _has_column(inspector, "connect_group", "service_id"):
        op.add_column("connect_group", sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=True))

    inspector = sa.inspect(bind)
    if (
        _table_exists(inspector, "service")
        and _table_exists(inspector, "connect_group")
        and _has_column(inspector, "service", "connect_group_id")
        and _has_column(inspector, "connect_group", "service_id")
    ):
        # Backfill each connect group with the latest linked service row.
        op.execute(
            """
            WITH ranked AS (
                SELECT
                    s.connect_group_id,
                    s.id AS service_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY s.connect_group_id
                        ORDER BY s.created_at DESC NULLS LAST, s.id
                    ) AS rn
                FROM service s
                WHERE s.connect_group_id IS NOT NULL
            )
            UPDATE connect_group cg
            SET service_id = r.service_id
            FROM ranked r
            WHERE cg.id = r.connect_group_id
              AND r.rn = 1
              AND cg.service_id IS NULL
            """
        )

    inspector = sa.inspect(bind)
    if (
        _table_exists(inspector, "connect_group")
        and _table_exists(inspector, "service")
        and _has_column(inspector, "connect_group", "service_id")
        and not _has_fk_on_column(inspector, "connect_group", "service_id")
    ):
        op.create_foreign_key(
            "fk_connect_group_service_id",
            "connect_group",
            "service",
            ["service_id"],
            ["id"],
        )

    # 2) attendance.service_date (ensure exists and is populated)
    inspector = sa.inspect(bind)
    if _table_exists(inspector, "attendance") and not _has_column(inspector, "attendance", "service_date"):
        op.add_column("attendance", sa.Column("service_date", sa.Date(), nullable=True))

    inspector = sa.inspect(bind)
    if (
        _table_exists(inspector, "attendance")
        and _table_exists(inspector, "service")
        and _has_column(inspector, "attendance", "service_date")
        and _has_column(inspector, "attendance", "service_id")
        and _has_column(inspector, "service", "service_date")
    ):
        op.execute(
            """
            UPDATE attendance a
            SET service_date = s.service_date
            FROM service s
            WHERE a.service_id = s.id
              AND a.service_date IS NULL
              AND s.service_date IS NOT NULL
            """
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "attendance") and _has_column(inspector, "attendance", "service_date"):
        op.execute("UPDATE attendance SET service_date = CURRENT_DATE WHERE service_date IS NULL")
        op.alter_column("attendance", "service_date", nullable=False)

    # 3) Drop old service columns
    inspector = sa.inspect(bind)
    if _table_exists(inspector, "service") and _has_column(inspector, "service", "connect_group_id"):
        _drop_fk_on_column(inspector, "service", "connect_group_id")
        op.drop_column("service", "connect_group_id")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "service") and _has_column(inspector, "service", "service_date"):
        op.drop_column("service", "service_date")


def downgrade() -> None:
    raise RuntimeError("Downgrade is not supported for service/connect relationship refactor.")
