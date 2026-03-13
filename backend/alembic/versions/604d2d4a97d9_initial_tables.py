from sqlalchemy.dialects import postgresql

def upgrade() -> None:

    op.create_table(
        "members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("first_name", sa.String(80), nullable=False),
        sa.Column("last_name", sa.String(80), nullable=False),
        sa.Column("phone_number", sa.String(32), nullable=False, unique=True),
        sa.Column("email", sa.String(254), nullable=True, unique=True),
        sa.Column("gender", sa.String(32), nullable=True),
        sa.Column("marital_status", sa.String(32), nullable=True),
        sa.Column("first_timer", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("connect_name", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("date_joined", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "service",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("theme", sa.String(80), nullable=True),
        sa.Column("location", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "connect_group",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("service.id"), nullable=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.String(254), nullable=False),
        sa.Column("meeting_time", sa.String(80), nullable=False),
        sa.Column("meeting_day", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("state_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

def downgrade() -> None:

    op.drop_table("chat_sessions")
    op.drop_table("connect_group")
    op.drop_table("service")
    op.drop_table("members")