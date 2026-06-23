# Fleet Telemetry Monitoring Service

A real-time fleet monitoring system for 50 autonomous warehouse vehicles. Built as a fullstack take-home challenge.

## Stack

| Layer | Technologies |
|---|---|
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2 (async) · Alembic · asyncpg |
| Database | PostgreSQL 16 |
| Frontend | React 18 · TypeScript · Vite |
| Infrastructure | Docker · Docker Compose |

## Architecture

```
Browser :5173
  └─ Vite dev server  (proxies /api/* to backend)
       └─ FastAPI :8000
            └─ PostgreSQL :5432
```

The dashboard polls all four API endpoints every 2 seconds. There are no WebSockets. See `docs/ADR.md` for the reasoning behind each major decision.

---

## Quick Start

### Prerequisites

- Docker and Docker Compose

### 1. Copy the environment file

```bash
cp .env.example .env
```

The defaults in `.env.example` work out of the box with Docker Compose.

### 2. Start all services

```bash
docker compose up
```

Postgres starts first (health-checked); backend and frontend start once it is ready.

### 3. Run database migrations

```bash
docker compose exec backend alembic upgrade head
```

### 4. Seed reference data

Seeds 50 vehicles (`v-01` through `v-50`) and 20 warehouse zones. Safe to re-run.

```bash
docker compose exec backend python seed.py
```

### 5. Open the dashboard

```
http://localhost:5173
```

### API docs (Swagger UI)

```
http://localhost:8000/docs
```

---

## Running Backend Tests

The tests require a separate PostgreSQL database. Create it once, then run pytest inside the backend container.

```bash
# One-time setup
docker compose exec postgres createdb -U fleet fleet_telemetry_test

# Run all tests
docker compose exec backend pytest
```

Tests cover: telemetry ingestion, all four anomaly rules (including boundary values), zone counter concurrency (20 simultaneous requests via `asyncio.gather`), fault transition atomicity, and fleet state aggregation. All tests hit a real PostgreSQL database — no mocks.

---

## API Reference

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/api/telemetry` | Ingest one telemetry event |
| GET | `/api/vehicles` | All vehicles with latest state and most recent anomaly |
| PATCH | `/api/vehicles/{id}/status` | Update vehicle status; transitioning to `fault` atomically cancels active missions and creates a maintenance record |
| GET | `/api/fleet/state` | Aggregate counts by status (idle / moving / charging / fault / total) |
| GET | `/api/zones/counts` | Entry count per zone |
| GET | `/api/anomalies` | Anomaly list; filterable by `vehicle_id`, `since`, `until`, `limit` |

### Example curl commands

```bash
# Health check
curl http://localhost:8000/health

# Ingest a telemetry event — triggers LOW_BATTERY anomaly, increments charging_bay_1 counter
curl -X POST http://localhost:8000/api/telemetry \
  -H "Content-Type: application/json" \
  -d '{
    "vehicle_id": "v-01",
    "timestamp": "2026-05-21T10:00:00Z",
    "lat": 37.41,
    "lon": -122.08,
    "battery_pct": 12.0,
    "speed_mps": 1.2,
    "status": "moving",
    "error_codes": [],
    "zone_entered": "charging_bay_1"
  }'

# Fleet aggregate
curl http://localhost:8000/api/fleet/state

# Zone entry counts
curl http://localhost:8000/api/zones/counts

# Anomalies for a specific vehicle
curl "http://localhost:8000/api/anomalies?vehicle_id=v-01&limit=10"

# Trigger fault transition (atomically cancels active missions, creates maintenance record)
curl -X PATCH http://localhost:8000/api/vehicles/v-01/status \
  -H "Content-Type: application/json" \
  -d '{"status": "fault"}'
```

---

## Project Structure

```
fleet-telemetry/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers (thin controllers)
│   │   ├── core/         # DB engine, config
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── repositories/ # DB access layer (no business logic)
│   │   ├── schemas/      # Pydantic request/response models
│   │   └── services/     # Business logic
│   ├── alembic/          # Database migrations
│   ├── tests/            # pytest suite (real PostgreSQL)
│   ├── seed.py           # Reference data seeder
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/   # React UI components
│       ├── hooks/        # useFleetData, usePolling
│       ├── services/     # fetch wrappers
│       └── types/        # TypeScript interfaces
├── docs/
│   ├── ADR.md            # Architecture Decision Record
│   └── AI_LOG.md         # AI interaction log
└── docker-compose.yml
```

---

## Running Tests

### Backend tests

The backend tests require a separate PostgreSQL database. Run these inside the running Docker environment.

```bash
# One-time setup (creates the test database)
docker compose exec postgres createdb -U fleet fleet_telemetry_test

# Run all backend tests
docker compose exec backend pytest -v
```

### Frontend tests

```bash
cd frontend

# Install dependencies (first time only, or after adding new packages)
npm install

# Run tests in watch mode
npm run test

# Run tests once (CI mode)
npm run test:run

# Build the frontend
npm run build
```

### Concurrency demo

Demonstrate the atomic zone counter under concurrent load (requires the app to be running):

```bash
python scripts/concurrent_zone_test.py
# Optional: python scripts/concurrent_zone_test.py 40 charging_bay_1
python scripts/concurrent_zone_test.py
# Optional: python scripts/concurrent_zone_test.py 40 charging_bay_2
```

Then verify the final count:

```bash
curl http://localhost:8000/api/zones/counts | python -m json.tool
```

---

## Post-interview improvements

The following were added after the technical interview to address discussion points about testing, CI, concurrency demonstration, and production readiness planning. The core architecture was not changed.

| Addition | What it covers |
|---|---|
| **Frontend tests** (`src/__tests__/`) | Vitest + React Testing Library. Covers dashboard states (loading, error, data), `FleetSummary`, `ZoneCounts`, `VehicleTable`, and `useFleetData` hook with mocked fetch |
| **GitHub Actions CI** (`.github/workflows/ci.yml`) | Backend tests (with PostgreSQL service container), frontend tests, and frontend build on every push |
| **Concurrency demo script** (`scripts/concurrent_zone_test.py`) | Sends N concurrent zone events and compares before/after counts to demonstrate atomic upsert correctness outside of pytest |
| **Scalability notes** (`docs/SCALABILITY_NOTES.md`) | Explains current limits, what changes at thousands of events/second (Kafka, Redis counters, table partitioning, read replicas) |
| **Production readiness notes** (`docs/PRODUCTION_READINESS.md`) | Enumerates what is solid now vs. what would be needed before a real deployment (auth, rate limiting, secrets, CD pipeline, observability) |

---

## Known Limitations

- **No authentication.** All endpoints are publicly accessible. Auth is out of scope for this prototype.
- **Seeding is required before ingesting telemetry.** `vehicle_id` must be `v-01` through `v-50` and the vehicle must exist in the database (enforced by a foreign key).
- **No retention policy.** Every telemetry event is persisted. The database will grow indefinitely without a pruning job.
- **2-second polling.** Sub-second dashboard updates would require WebSockets or Server-Sent Events.
- **Migrations are not automatic.** Run `alembic upgrade head` manually after the containers start.
- **Single-node only.** No horizontal scaling or read replicas. See `docs/ADR.md` for what would change at larger scale.
