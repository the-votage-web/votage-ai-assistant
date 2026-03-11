"""convert ids to uuid across core tables

Revision ID: 56f03ad16787
Revises: ea932fdbd6ee
Create Date: 2026-03-04 11:11:44.995737

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '56f03ad16787'
down_revision: Union[str, None] = 'ea932fdbd6ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in set(inspector.get_table_names())


def _is_uuid_col(inspector, table: str, column: str) -> bool:
    for c in inspector.get_columns(table):
        if c["name"] == column:
            return isinstance(c["type"], postgresql.UUID)
    return False


def _has_column(inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def _drop_fk_on_column(inspector, table: str, column: str) -> None:
    for fk in inspector.get_foreign_keys(table):
        if fk.get("constrained_columns") == [column] and fk.get("name"):
            op.drop_constraint(fk["name"], table, type_="foreignkey")


def _drop_pk(inspector, table: str) -> None:
    pk = inspector.get_pk_constraint(table)
    name = pk.get("name") if isinstance(pk, dict) else None
    if name:
        op.drop_constraint(name, table, type_="primary")


def _populate_shadow_uuid_ids(bind, inspector, table: str) -> None:
    if not _table_exists(inspector, table):
        return
    if not _has_column(inspector, table, "id") or not _has_column(inspector, table, "id_uuid"):
        return
    rows = bind.execute(sa.text(f"SELECT id FROM {table} WHERE id_uuid IS NULL")).fetchall()
    for row in rows:
        bind.execute(
            sa.text(f"UPDATE {table} SET id_uuid = :new_id WHERE id = :old_id"),
            {"new_id": str(uuid.uuid4()), "old_id": row[0]},
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ---------------------------------------------------------------------
    # Step 1: Add UUID shadow columns for PK/FK fields where needed
    # ---------------------------------------------------------------------
    if _table_exists(inspector, "members") and not _is_uuid_col(inspector, "members", "id"):
        if not _has_column(inspector, "members", "id_uuid"):
            op.add_column(
                "members",
                sa.Column("id_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "connect_group") and not _is_uuid_col(inspector, "connect_group", "id"):
        if not _has_column(inspector, "connect_group", "id_uuid"):
            op.add_column(
                "connect_group",
                sa.Column("id_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "service") and not _is_uuid_col(inspector, "service", "id"):
        if not _has_column(inspector, "service", "id_uuid"):
            op.add_column(
                "service",
                sa.Column("id_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "connect_group_members") and not _is_uuid_col(inspector, "connect_group_members", "id"):
        if not _has_column(inspector, "connect_group_members", "id_uuid"):
            op.add_column(
                "connect_group_members",
                sa.Column("id_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "attendance") and not _is_uuid_col(inspector, "attendance", "id"):
        if not _has_column(inspector, "attendance", "id_uuid"):
            op.add_column(
                "attendance",
                sa.Column("id_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "first_timer_events") and not _is_uuid_col(inspector, "first_timer_events", "id"):
        if not _has_column(inspector, "first_timer_events", "id_uuid"):
            op.add_column(
                "first_timer_events",
                sa.Column("id_uuid", postgresql.UUID(as_uuid=True), nullable=True),
            )

    # Backfill UUID shadow PK columns without DB extensions/functions.
    inspector = sa.inspect(bind)
    for table in ["members", "connect_group", "service", "connect_group_members", "attendance", "first_timer_events"]:
        _populate_shadow_uuid_ids(bind, inspector, table)

    # FK shadow columns
    inspector = sa.inspect(bind)
    if _table_exists(inspector, "service") and _has_column(inspector, "service", "connect_group_id") and not _is_uuid_col(inspector, "service", "connect_group_id"):
        if not _has_column(inspector, "service", "connect_group_id_uuid"):
            op.add_column("service", sa.Column("connect_group_id_uuid", postgresql.UUID(as_uuid=True), nullable=True))

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "connect_group_members") and _has_column(inspector, "connect_group_members", "connect_group_id") and not _is_uuid_col(inspector, "connect_group_members", "connect_group_id"):
        if not _has_column(inspector, "connect_group_members", "connect_group_id_uuid"):
            op.add_column("connect_group_members", sa.Column("connect_group_id_uuid", postgresql.UUID(as_uuid=True), nullable=True))

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "attendance") and _has_column(inspector, "attendance", "service_id") and not _is_uuid_col(inspector, "attendance", "service_id"):
        if not _has_column(inspector, "attendance", "service_id_uuid"):
            op.add_column("attendance", sa.Column("service_id_uuid", postgresql.UUID(as_uuid=True), nullable=True))

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "first_timer_events") and _has_column(inspector, "first_timer_events", "service_id") and not _is_uuid_col(inspector, "first_timer_events", "service_id"):
        if not _has_column(inspector, "first_timer_events", "service_id_uuid"):
            op.add_column("first_timer_events", sa.Column("service_id_uuid", postgresql.UUID(as_uuid=True), nullable=True))

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "connect_group_members") and _has_column(inspector, "connect_group_members", "member_id") and not _is_uuid_col(inspector, "connect_group_members", "member_id"):
        if not _has_column(inspector, "connect_group_members", "member_id_uuid"):
            op.add_column("connect_group_members", sa.Column("member_id_uuid", postgresql.UUID(as_uuid=True), nullable=True))

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "attendance") and _has_column(inspector, "attendance", "member_id") and not _is_uuid_col(inspector, "attendance", "member_id"):
        if not _has_column(inspector, "attendance", "member_id_uuid"):
            op.add_column("attendance", sa.Column("member_id_uuid", postgresql.UUID(as_uuid=True), nullable=True))

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "first_timer_events") and _has_column(inspector, "first_timer_events", "member_id") and not _is_uuid_col(inspector, "first_timer_events", "member_id"):
        if not _has_column(inspector, "first_timer_events", "member_id_uuid"):
            op.add_column("first_timer_events", sa.Column("member_id_uuid", postgresql.UUID(as_uuid=True), nullable=True))

    # ---------------------------------------------------------------------
    # Step 2: Backfill FK shadow columns through joins
    # ---------------------------------------------------------------------
    inspector = sa.inspect(bind)
    if _table_exists(inspector, "service") and _has_column(inspector, "service", "connect_group_id_uuid"):
        op.execute(
            """
            UPDATE service s
            SET connect_group_id_uuid = cg.id_uuid
            FROM connect_group cg
            WHERE s.connect_group_id IS NOT NULL
              AND s.connect_group_id = cg.id
            """
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "connect_group_members") and _has_column(inspector, "connect_group_members", "connect_group_id_uuid"):
        op.execute(
            """
            UPDATE connect_group_members cgm
            SET connect_group_id_uuid = cg.id_uuid
            FROM connect_group cg
            WHERE cgm.connect_group_id = cg.id
            """
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "attendance") and _has_column(inspector, "attendance", "service_id_uuid"):
        op.execute(
            """
            UPDATE attendance a
            SET service_id_uuid = s.id_uuid
            FROM service s
            WHERE a.service_id IS NOT NULL
              AND a.service_id = s.id
            """
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "first_timer_events") and _has_column(inspector, "first_timer_events", "service_id_uuid"):
        op.execute(
            """
            UPDATE first_timer_events fte
            SET service_id_uuid = s.id_uuid
            FROM service s
            WHERE fte.service_id IS NOT NULL
              AND fte.service_id = s.id
            """
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "connect_group_members") and _has_column(inspector, "connect_group_members", "member_id_uuid"):
        op.execute(
            """
            UPDATE connect_group_members cgm
            SET member_id_uuid = m.id_uuid
            FROM members m
            WHERE cgm.member_id = m.id
            """
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "attendance") and _has_column(inspector, "attendance", "member_id_uuid"):
        op.execute(
            """
            UPDATE attendance a
            SET member_id_uuid = m.id_uuid
            FROM members m
            WHERE a.member_id = m.id
            """
        )

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "first_timer_events") and _has_column(inspector, "first_timer_events", "member_id_uuid"):
        op.execute(
            """
            UPDATE first_timer_events fte
            SET member_id_uuid = m.id_uuid
            FROM members m
            WHERE fte.member_id = m.id
            """
        )

    # ---------------------------------------------------------------------
    # Step 3: Drop FKs that depend on old integer columns
    # ---------------------------------------------------------------------
    inspector = sa.inspect(bind)
    if _table_exists(inspector, "service") and _has_column(inspector, "service", "connect_group_id") and not _is_uuid_col(inspector, "service", "connect_group_id"):
        _drop_fk_on_column(inspector, "service", "connect_group_id")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "connect_group_members") and _has_column(inspector, "connect_group_members", "connect_group_id") and not _is_uuid_col(inspector, "connect_group_members", "connect_group_id"):
        _drop_fk_on_column(inspector, "connect_group_members", "connect_group_id")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "attendance") and _has_column(inspector, "attendance", "service_id") and not _is_uuid_col(inspector, "attendance", "service_id"):
        _drop_fk_on_column(inspector, "attendance", "service_id")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "first_timer_events") and _has_column(inspector, "first_timer_events", "service_id") and not _is_uuid_col(inspector, "first_timer_events", "service_id"):
        _drop_fk_on_column(inspector, "first_timer_events", "service_id")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "connect_group_members") and _has_column(inspector, "connect_group_members", "member_id") and not _is_uuid_col(inspector, "connect_group_members", "member_id"):
        _drop_fk_on_column(inspector, "connect_group_members", "member_id")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "attendance") and _has_column(inspector, "attendance", "member_id") and not _is_uuid_col(inspector, "attendance", "member_id"):
        _drop_fk_on_column(inspector, "attendance", "member_id")

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "first_timer_events") and _has_column(inspector, "first_timer_events", "member_id") and not _is_uuid_col(inspector, "first_timer_events", "member_id"):
        _drop_fk_on_column(inspector, "first_timer_events", "member_id")

    # ---------------------------------------------------------------------
    # Step 4: Convert primary keys by swapping id <-> id_uuid
    # ---------------------------------------------------------------------
    for table in ["members", "connect_group", "service", "connect_group_members", "attendance", "first_timer_events"]:
        inspector = sa.inspect(bind)
        if not _table_exists(inspector, table):
            continue
        if _is_uuid_col(inspector, table, "id"):
            continue
        if not _has_column(inspector, table, "id_uuid"):
            continue

        _drop_pk(inspector, table)
        op.drop_column(table, "id")
        op.alter_column(table, "id_uuid", new_column_name="id")
        op.create_primary_key(f"pk_{table}", table, ["id"])

    # ---------------------------------------------------------------------
    # Step 5: Swap FK columns to UUID variants and recreate FKs
    # ---------------------------------------------------------------------
    inspector = sa.inspect(bind)
    if _table_exists(inspector, "service") and _has_column(inspector, "service", "connect_group_id_uuid"):
        op.drop_column("service", "connect_group_id")
        op.alter_column("service", "connect_group_id_uuid", new_column_name="connect_group_id")
        op.create_foreign_key("fk_service_connect_group_id", "service", "connect_group", ["connect_group_id"], ["id"])

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "connect_group_members") and _has_column(inspector, "connect_group_members", "connect_group_id_uuid"):
        op.drop_column("connect_group_members", "connect_group_id")
        op.alter_column("connect_group_members", "connect_group_id_uuid", new_column_name="connect_group_id")
        op.alter_column("connect_group_members", "connect_group_id", nullable=False)
        op.create_foreign_key("fk_cgm_connect_group_id", "connect_group_members", "connect_group", ["connect_group_id"], ["id"])

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "attendance") and _has_column(inspector, "attendance", "service_id_uuid"):
        op.drop_column("attendance", "service_id")
        op.alter_column("attendance", "service_id_uuid", new_column_name="service_id")
        op.create_foreign_key("fk_attendance_service_id_uuid", "attendance", "service", ["service_id"], ["id"])

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "first_timer_events") and _has_column(inspector, "first_timer_events", "service_id_uuid"):
        op.drop_column("first_timer_events", "service_id")
        op.alter_column("first_timer_events", "service_id_uuid", new_column_name="service_id")
        op.create_foreign_key("fk_fte_service_id_uuid", "first_timer_events", "service", ["service_id"], ["id"])

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "connect_group_members") and _has_column(inspector, "connect_group_members", "member_id_uuid"):
        op.drop_column("connect_group_members", "member_id")
        op.alter_column("connect_group_members", "member_id_uuid", new_column_name="member_id")
        op.alter_column("connect_group_members", "member_id", nullable=False)
        op.create_foreign_key("fk_cgm_member_id", "connect_group_members", "members", ["member_id"], ["id"])

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "attendance") and _has_column(inspector, "attendance", "member_id_uuid"):
        op.drop_column("attendance", "member_id")
        op.alter_column("attendance", "member_id_uuid", new_column_name="member_id")
        op.alter_column("attendance", "member_id", nullable=False)
        op.create_foreign_key("fk_attendance_member_id", "attendance", "members", ["member_id"], ["id"])

    inspector = sa.inspect(bind)
    if _table_exists(inspector, "first_timer_events") and _has_column(inspector, "first_timer_events", "member_id_uuid"):
        op.drop_column("first_timer_events", "member_id")
        op.alter_column("first_timer_events", "member_id_uuid", new_column_name="member_id")
        op.alter_column("first_timer_events", "member_id", nullable=False)
        op.create_foreign_key("fk_fte_member_id", "first_timer_events", "members", ["member_id"], ["id"])


def downgrade() -> None:
    raise RuntimeError("Downgrade is not supported for UUID ID conversion migration.")
