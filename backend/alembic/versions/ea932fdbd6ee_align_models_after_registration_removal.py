"""align models after registration removal

Revision ID: ea932fdbd6ee
Revises: 7a1f0b3c4d9e
Create Date: 2026-03-03 20:18:10.141688

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ea932fdbd6ee'
down_revision: Union[str, None] = '7a1f0b3c4d9e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    table_names = set(inspector.get_table_names())

    # 1) New tables
    if "connect_group" not in table_names:
        op.create_table(
            "connect_group",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("description", sa.String(length=254), nullable=False),
            sa.Column("meeting_time", sa.String(length=80), nullable=False),
            sa.Column("meeting_day", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )

    if "service" not in table_names:
        op.create_table(
            "service",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("connect_group_id", sa.Integer(), sa.ForeignKey("connect_group.id"), nullable=True),
            sa.Column("service_date", sa.Date(), nullable=False),
            sa.Column("theme", sa.String(length=80), nullable=True),
            sa.Column("location", sa.String(length=80), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )

    if "connect_group_members" not in table_names:
        op.create_table(
            "connect_group_members",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("connect_group_id", sa.Integer(), sa.ForeignKey("connect_group.id"), nullable=False),
            sa.Column("member_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("members.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        )

    # 2) Members reshape
    member_cols = {c["name"] for c in inspector.get_columns("members")}
    if "first_name" not in member_cols:
        op.add_column("members", sa.Column("first_name", sa.String(length=80), nullable=True))
    if "last_name" not in member_cols:
        op.add_column("members", sa.Column("last_name", sa.String(length=80), nullable=True))
    if "phone_number" not in member_cols:
        op.add_column("members", sa.Column("phone_number", sa.String(length=32), nullable=True))
    if "email" not in member_cols:
        op.add_column("members", sa.Column("email", sa.String(length=254), nullable=True))
    if "gender" not in member_cols:
        op.add_column("members", sa.Column("gender", sa.String(length=32), nullable=True))
    if "marital_status" not in member_cols:
        op.add_column("members", sa.Column("marital_status", sa.String(length=32), nullable=True))
    if "first_timer" not in member_cols:
        op.add_column("members", sa.Column("first_timer", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.alter_column("members", "first_timer", server_default=None)
    if "connect_name" not in member_cols:
        op.add_column("members", sa.Column("connect_name", sa.String(length=80), nullable=True))
    if "date_joined" not in member_cols:
        op.add_column(
            "members",
            sa.Column("date_joined", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.alter_column("members", "date_joined", server_default=None)

    # Backfill from legacy columns where present.
    member_cols = {c["name"] for c in inspector.get_columns("members")}
    if "full_name" in member_cols:
        op.execute(
            """
            UPDATE members
            SET first_name = COALESCE(NULLIF(split_part(full_name, ' ', 1), ''), first_name, 'Member')
            WHERE first_name IS NULL
            """
        )
        op.execute(
            """
            UPDATE members
            SET last_name = COALESCE(NULLIF(trim(substr(full_name, length(split_part(full_name, ' ', 1)) + 1)), ''), last_name, '')
            WHERE last_name IS NULL
            """
        )
    else:
        op.execute("UPDATE members SET first_name = COALESCE(first_name, 'Member') WHERE first_name IS NULL")
        op.execute("UPDATE members SET last_name = COALESCE(last_name, '') WHERE last_name IS NULL")

    if "phone" in member_cols and "phone_number" in member_cols:
        op.execute(
            "UPDATE members SET phone_number = COALESCE(phone_number, phone) WHERE phone_number IS NULL AND phone IS NOT NULL"
        )

    op.execute("UPDATE members SET first_timer = COALESCE(first_timer, false)")
    op.alter_column("members", "first_name", nullable=False)
    op.alter_column("members", "last_name", nullable=False)
    op.alter_column("members", "phone_number", nullable=False)

    member_uq = {c["name"] for c in inspector.get_unique_constraints("members")}
    if "uq_members_phone_number" not in member_uq:
        op.create_unique_constraint("uq_members_phone_number", "members", ["phone_number"])
    if "uq_members_email" not in member_uq:
        op.create_unique_constraint("uq_members_email", "members", ["email"])

    member_cols = {c["name"] for c in inspector.get_columns("members")}
    if "full_name" in member_cols:
        op.drop_column("members", "full_name")
    if "phone" in member_cols:
        op.drop_column("members", "phone")
    if "aliases" in member_cols:
        op.drop_column("members", "aliases")

    # 3) Attendance reshape
    attendance_cols = {c["name"] for c in inspector.get_columns("attendance")}
    if "service_id" not in attendance_cols:
        op.add_column("attendance", sa.Column("service_id", sa.Integer(), nullable=True))
        op.create_foreign_key("fk_attendance_service_id", "attendance", "service", ["service_id"], ["id"])
    if "connect_name" not in attendance_cols:
        op.add_column("attendance", sa.Column("connect_name", sa.String(length=80), nullable=False, server_default=""))
        op.alter_column("attendance", "connect_name", server_default=None)
    if "service_date" not in attendance_cols:
        op.add_column("attendance", sa.Column("service_date", sa.Date(), nullable=True))
        op.execute("UPDATE attendance SET service_date = CURRENT_DATE WHERE service_date IS NULL")
        op.alter_column("attendance", "service_date", nullable=False)

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

    # 4) First timer events reshape
    fte_cols = {c["name"] for c in inspector.get_columns("first_timer_events")}
    if "service_id" not in fte_cols:
        op.add_column("first_timer_events", sa.Column("service_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_first_timer_events_service_id",
            "first_timer_events",
            "service",
            ["service_id"],
            ["id"],
        )
    if "service_name" not in fte_cols and "event_name" in fte_cols:
        op.alter_column("first_timer_events", "event_name", new_column_name="service_name")

    # 5) Drop obsolete registrations table
    if "registrations" in table_names:
        op.drop_table("registrations")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    # Recreate registrations table (legacy structure).
    if "registrations" not in table_names:
        op.create_table(
            "registrations",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("phone_number", sa.String(length=32), nullable=False),
            sa.Column("first_name", sa.String(length=80), nullable=False),
            sa.Column("last_name", sa.String(length=80), nullable=False),
            sa.Column("first_timer", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("gender", sa.String(length=32), nullable=False),
            sa.Column("marital_status", sa.String(length=32), nullable=False),
            sa.Column("service_type", sa.String(length=32), nullable=False),
            sa.Column("connect_name", sa.String(length=80), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.UniqueConstraint("phone_number", name="uq_registrations_phone_number"),
        )

    # Best-effort rollback of member legacy columns.
    member_cols = {c["name"] for c in inspector.get_columns("members")}
    if "full_name" not in member_cols:
        op.add_column("members", sa.Column("full_name", sa.String(length=160), nullable=True))
        op.execute("UPDATE members SET full_name = trim(first_name || ' ' || last_name)")
        op.alter_column("members", "full_name", nullable=False)
    if "phone" not in member_cols:
        op.add_column("members", sa.Column("phone", sa.String(length=32), nullable=True))
        op.execute("UPDATE members SET phone = phone_number")
        op.alter_column("members", "phone", nullable=False)
    if "aliases" not in member_cols:
        op.add_column("members", sa.Column("aliases", sa.Text(), nullable=False, server_default=""))
        op.alter_column("members", "aliases", server_default=None)

    member_uq = {c["name"] for c in inspector.get_unique_constraints("members")}
    if "uq_members_phone_number" in member_uq:
        op.drop_constraint("uq_members_phone_number", "members", type_="unique")
    if "uq_members_email" in member_uq:
        op.drop_constraint("uq_members_email", "members", type_="unique")

    member_cols = {c["name"] for c in inspector.get_columns("members")}
    for col in ["date_joined", "connect_name", "first_timer", "marital_status", "gender", "email", "phone_number", "last_name", "first_name"]:
        if col in member_cols:
            op.drop_column("members", col)
    if "phone" in {c["name"] for c in inspector.get_columns("members")}:
        op.create_unique_constraint("members_phone_key", "members", ["phone"])

    # Revert first_timer_events column rename if needed.
    fte_cols = {c["name"] for c in inspector.get_columns("first_timer_events")}
    if "service_name" in fte_cols and "event_name" not in fte_cols:
        op.alter_column("first_timer_events", "service_name", new_column_name="event_name")
    if "service_id" in fte_cols:
        fks = inspector.get_foreign_keys("first_timer_events")
        for fk in fks:
            if fk.get("constrained_columns") == ["service_id"] and fk.get("name"):
                op.drop_constraint(fk["name"], "first_timer_events", type_="foreignkey")
        op.drop_column("first_timer_events", "service_id")

    # Revert attendance constraints/columns.
    attendance_uq = {c["name"] for c in inspector.get_unique_constraints("attendance")}
    if "uq_member_day_service_connect" in attendance_uq:
        op.drop_constraint("uq_member_day_service_connect", "attendance", type_="unique")
        op.create_unique_constraint("uq_member_day_service", "attendance", ["member_id", "service_date", "service_type"])

    attendance_cols = {c["name"] for c in inspector.get_columns("attendance")}
    if "service_id" in attendance_cols:
        fks = inspector.get_foreign_keys("attendance")
        for fk in fks:
            if fk.get("constrained_columns") == ["service_id"] and fk.get("name"):
                op.drop_constraint(fk["name"], "attendance", type_="foreignkey")
        op.drop_column("attendance", "service_id")

    # Drop newly added tables.
    table_names = set(inspector.get_table_names())
    if "connect_group_members" in table_names:
        op.drop_table("connect_group_members")
    if "service" in table_names:
        op.drop_table("service")
    if "connect_group" in table_names:
        op.drop_table("connect_group")
