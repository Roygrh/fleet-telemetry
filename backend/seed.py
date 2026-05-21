"""
Seed script — initialises reference data:
  - 50 vehicles: v-01 through v-50 (status=idle)
  - 20 zone counters from ZONES constant (entry_count=0)

Safe to run multiple times — uses INSERT ... ON CONFLICT DO NOTHING.

Usage:
    # Inside the running backend container:
    docker compose exec backend python seed.py

    # Or locally with DATABASE_URL set:
    DATABASE_URL=postgresql+asyncpg://fleet:fleet@localhost:5432/fleet_telemetry python seed.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text

from app.constants.zones import ZONES
from app.core.database import AsyncSessionLocal


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        vehicle_ids = [f"v-{i:02d}" for i in range(1, 51)]

        for vid in vehicle_ids:
            await session.execute(
                text(
                    "INSERT INTO vehicles (vehicle_id, current_status) "
                    "VALUES (:vid, 'idle') "
                    "ON CONFLICT (vehicle_id) DO NOTHING"
                ),
                {"vid": vid},
            )

        for zone in ZONES:
            await session.execute(
                text(
                    "INSERT INTO zone_counters (zone_id, entry_count) "
                    "VALUES (:zone, 0) "
                    "ON CONFLICT (zone_id) DO NOTHING"
                ),
                {"zone": zone},
            )

        await session.commit()

    print(f"Seeded {len(vehicle_ids)} vehicles and {len(ZONES)} zone counters.")


if __name__ == "__main__":
    asyncio.run(seed())
