"""add teleoperation_sessions table

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-24

"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teleoperation_sessions",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column(
            "vehicle_id",
            sa.String(10),
            sa.ForeignKey("vehicles.vehicle_id", ondelete="CASCADE"),
            nullable=False,
        ),
        # String status keeps migrations simple — no PostgreSQL enum to manage.
        sa.Column("status", sa.String(20), nullable=False, server_default="requested"),
        sa.Column("operator_id", sa.String(100), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_command", sa.String(20), nullable=True),
        sa.Column("last_command_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sensor_payload", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_teleoperation_sessions_session_id"),
    )
    op.create_index(
        "ix_teleoperation_sessions_vehicle_id",
        "teleoperation_sessions",
        ["vehicle_id"],
    )
    op.create_index(
        "ix_teleoperation_sessions_status",
        "teleoperation_sessions",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_teleoperation_sessions_status", table_name="teleoperation_sessions")
    op.drop_index("ix_teleoperation_sessions_vehicle_id", table_name="teleoperation_sessions")
    op.drop_table("teleoperation_sessions")
