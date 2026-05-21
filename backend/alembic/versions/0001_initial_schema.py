"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-19

"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enum types are created by the first op.create_table that references them
    # (create_type defaults to True). Every subsequent table that uses the same
    # named type must set create_type=False to prevent a DuplicateObjectError.

    # ------------------------------------------------------------------ #
    # vehicles  — creates vehiclestatus enum                              #
    # ------------------------------------------------------------------ #
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("vehicle_id", sa.String(10), nullable=False),
        sa.Column(
            "current_status",
            sa.Enum("idle", "moving", "charging", "fault", name="vehiclestatus"),
            nullable=False,
            server_default="idle",
        ),
        sa.Column("battery_pct", sa.Float(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vehicle_id", name="uq_vehicles_vehicle_id"),
    )
    op.create_index("ix_vehicles_vehicle_id", "vehicles", ["vehicle_id"])

    # ------------------------------------------------------------------ #
    # zone_counters                                                        #
    # ------------------------------------------------------------------ #
    op.create_table(
        "zone_counters",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("zone_id", sa.String(50), nullable=False),
        sa.Column("entry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("zone_id", name="uq_zone_counters_zone_id"),
    )
    op.create_index("ix_zone_counters_zone_id", "zone_counters", ["zone_id"])

    # ------------------------------------------------------------------ #
    # telemetry_events                                                     #
    # ------------------------------------------------------------------ #
    op.create_table(
        "telemetry_events",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column(
            "vehicle_id",
            sa.String(10),
            sa.ForeignKey("vehicles.vehicle_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("battery_pct", sa.Float(), nullable=False),
        sa.Column("speed_mps", sa.Float(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("idle", "moving", "charging", "fault", name="vehiclestatus", create_type=False),
            nullable=False,
        ),
        sa.Column("error_codes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("zone_entered", sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_telemetry_vehicle_timestamp",
        "telemetry_events",
        ["vehicle_id", "timestamp"],
    )

    # ------------------------------------------------------------------ #
    # missions  — creates missionstatus enum                              #
    # ------------------------------------------------------------------ #
    op.create_table(
        "missions",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column(
            "vehicle_id",
            sa.String(10),
            sa.ForeignKey("vehicles.vehicle_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("active", "cancelled", "completed", name="missionstatus"),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_missions_vehicle_id", "missions", ["vehicle_id"])

    # ------------------------------------------------------------------ #
    # maintenance_records  — creates maintenancestatus enum               #
    # ------------------------------------------------------------------ #
    op.create_table(
        "maintenance_records",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column(
            "vehicle_id",
            sa.String(10),
            sa.ForeignKey("vehicles.vehicle_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "in_progress", "resolved", name="maintenancestatus"),
            nullable=False,
            server_default="open",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_maintenance_vehicle_id", "maintenance_records", ["vehicle_id"])

    # ------------------------------------------------------------------ #
    # anomalies                                                            #
    # ------------------------------------------------------------------ #
    op.create_table(
        "anomalies",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column(
            "vehicle_id",
            sa.String(10),
            sa.ForeignKey("vehicles.vehicle_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("anomaly_type", sa.String(50), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column(
            "telemetry_event_id",
            sa.Integer(),
            sa.ForeignKey("telemetry_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_anomaly_vehicle_timestamp", "anomalies", ["vehicle_id", "timestamp"])


def downgrade() -> None:
    op.drop_index("ix_anomaly_vehicle_timestamp", table_name="anomalies")
    op.drop_table("anomalies")

    op.drop_index("ix_maintenance_vehicle_id", table_name="maintenance_records")
    op.drop_table("maintenance_records")

    op.drop_index("ix_missions_vehicle_id", table_name="missions")
    op.drop_table("missions")

    op.drop_index("ix_telemetry_vehicle_timestamp", table_name="telemetry_events")
    op.drop_table("telemetry_events")

    op.drop_index("ix_zone_counters_zone_id", table_name="zone_counters")
    op.drop_table("zone_counters")

    op.drop_index("ix_vehicles_vehicle_id", table_name="vehicles")
    op.drop_table("vehicles")

    op.execute("DROP TYPE IF EXISTS maintenancestatus")
    op.execute("DROP TYPE IF EXISTS missionstatus")
    op.execute("DROP TYPE IF EXISTS vehiclestatus")
