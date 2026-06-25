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

The original fleet telemetry dashboard intentionally uses 2-second polling, as explained in the ADR. This keeps the base solution simple and appropriate for 50 vehicles at 1 Hz. The Teleoperation Handoff Prototype (added later) uses WebSockets only for the remote-control flow, where bidirectional real-time communication is required between the operator UI and the mock vehicle client. See `docs/ADR.md` for the reasoning behind each major decision.

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

# Run all 44 tests
docker compose exec backend pytest -v
```

Tests cover: telemetry ingestion, all four anomaly rules (including boundary values), zone counter concurrency (20 simultaneous requests via `asyncio.gather`), fault transition atomicity, fleet state aggregation, and the full teleoperation session lifecycle. All tests hit a real PostgreSQL database — no mocks.

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

### Teleoperation API

HTTP endpoints manage the session lifecycle. WebSocket endpoints handle live operator commands and mock vehicle sensor updates.

| Method | Path | Description |
|---|---|---|
| POST | `/api/teleoperation/sessions` | Create a teleoperation handoff session |
| GET | `/api/teleoperation/sessions` | List teleoperation sessions |
| POST | `/api/teleoperation/sessions/{session_id}/claim` | Claim a requested session for an operator |
| POST | `/api/teleoperation/sessions/{session_id}/release` | Release operator control |
| WS | `/ws/teleoperation/operator/{session_id}` | Operator WebSocket for live commands and sensor feedback |
| WS | `/ws/teleoperation/vehicle/{vehicle_id}` | Mock vehicle WebSocket for sensor updates and command reception |

---

## Project Structure

```
fleet-telemetry/
├── .github/
│   └── workflows/
│       └── ci.yml                          # GitHub Actions CI
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── telemetry.py                # POST /api/telemetry
│   │   │   ├── vehicles.py                 # GET/PATCH /api/vehicles
│   │   │   ├── zones.py                    # GET /api/zones/counts
│   │   │   ├── anomalies.py                # GET /api/anomalies
│   │   │   ├── fleet.py                    # GET /api/fleet/state
│   │   │   └── teleoperation.py            # HTTP + WS routes + connection manager
│   │   ├── core/                           # DB engine, config
│   │   ├── models/
│   │   │   ├── vehicle.py
│   │   │   ├── telemetry.py
│   │   │   ├── zone.py
│   │   │   ├── anomaly.py
│   │   │   ├── mission.py
│   │   │   ├── maintenance.py
│   │   │   └── teleoperation.py            # TeleoperationSession model
│   │   ├── repositories/                   # DB access layer (no business logic)
│   │   │   └── teleoperation.py
│   │   ├── schemas/                        # Pydantic request/response models
│   │   │   └── teleoperation.py
│   │   └── services/                       # Business logic
│   │       └── teleoperation.py
│   ├── alembic/
│   │   └── versions/
│   │       ├── 0001_initial_schema.py
│   │       └── 0002_add_teleoperation_sessions.py
│   ├── tests/
│   │   ├── test_telemetry.py
│   │   ├── test_vehicles.py
│   │   ├── test_zones.py
│   │   ├── test_fleet.py
│   │   └── test_teleoperation.py
│   ├── seed.py
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── FleetSummary.tsx
│       │   ├── VehicleTable.tsx
│       │   ├── ZoneCounts.tsx
│       │   ├── StatusBadge.tsx
│       │   └── TeleoperationPanel.tsx
│       ├── hooks/
│       │   ├── useFleetData.ts
│       │   ├── usePolling.ts
│       │   └── useTeleoperation.ts
│       ├── services/
│       │   └── api.ts
│       ├── types/
│       │   └── index.ts
│       └── __tests__/
│           ├── TeleoperationPanel.test.tsx
│           └── TeleoperationPanelCommands.test.tsx
├── scripts/
│   ├── concurrent_zone_test.py             # Atomic zone counter concurrency demo
│   └── mock_vehicle_client.py              # Mock vehicle WebSocket client
├── docs/
│   ├── ADR.md                              # Architecture Decision Record
│   ├── AI_LOG.md                           # AI interaction log
│   ├── TELEOPERATION_PROTOTYPE.md          # Teleoperation design and demo guide
│   ├── SCALABILITY_NOTES.md
│   └── PRODUCTION_READINESS.md
└── docker-compose.yml
```

---

## Running Tests

All tests run inside Docker — no local Python or Node installation required beyond the containers.

### Backend tests (44 tests)

```bash
# One-time setup: create the test database
docker compose exec postgres createdb -U fleet fleet_telemetry_test

# Run all 44 tests
docker compose exec backend pytest -v
```

### Frontend tests (43 tests)

```bash
# Run all tests
docker compose exec frontend npm run test:run

# TypeScript build check
docker compose exec frontend npm run build
```

### Running frontend tests locally (optional)

```bash
cd frontend
npm install           # first time only
npm run test          # watch mode
npm run test:run      # single run (CI mode)
npm run build
```

### Concurrency demo

Demonstrate the atomic zone counter under concurrent load (requires the app to be running):

```bash
# Default: 20 concurrent requests to charging_bay_2
python scripts/concurrent_zone_test.py

# Custom: 40 concurrent requests
python scripts/concurrent_zone_test.py 40 charging_bay_2
```

Then verify the final count:

```bash
curl http://localhost:8000/api/zones/counts | python -m json.tool
```

---

## Teleoperation Prototype

A focused extension that demonstrates real-time operator-to-vehicle command streaming
using FastAPI WebSockets. The original telemetry dashboard is unchanged and continues
to use 2-second HTTP polling.

### Session lifecycle

```
requested → claimed → active → released
                             → completed
                             → failed
```

- **requested** — created, waiting for an operator
- **claimed** — operator assigned, WebSocket not yet open
- **active** — operator WebSocket is live; commands and sensor data are flowing
- **released** — operator returned control to the vehicle
- **completed** / **failed** — documented terminal states; no separate HTTP endpoint yet

### What it adds

- **Session lifecycle** persisted in PostgreSQL (`teleoperation_sessions` table)
- **WebSocket command channel** (`/ws/teleoperation/operator/{session_id}`) — operator sends commands
- **WebSocket sensor channel** (`/ws/teleoperation/vehicle/{vehicle_id}`) — mock vehicle sends data back
- **Frontend control panel** — claim/release, command buttons, live sensor feed
- **Mock vehicle client** (`scripts/mock_vehicle_client.py`) — simulates the vehicle/device side

### Demo commands

```bash
# 1. Build and start the full stack
docker compose build backend frontend
docker compose up -d postgres
docker compose up -d backend
docker compose exec backend alembic upgrade head
docker compose exec backend python seed.py
docker compose up -d frontend

# 2. Open http://localhost:5173 and scroll to the Teleoperation panel

# 3. Request a session (select v-01, click "Request Session")

# 4. Claim the session (click "Claim" → status changes to "claimed")

# 5. In a second terminal, run the mock vehicle client
#    Requires: pip install websockets==13.1
python scripts/mock_vehicle_client.py --vehicle-id v-01

# 6. Click "Connect" in the dashboard → WS status turns green, session becomes "active"

# 7. Click Forward / Left / Right / Backward / Stop
#    Commands appear in the mock client terminal; sensor feed updates in the UI

# 8. Click "Release" → status changes to "released"
#    Command buttons disappear immediately without a page refresh.
#    The backend closes the operator WebSocket and rejects any in-flight commands.
#    The mock vehicle client may continue sending simulated sensor data — this is
#    expected; the physical vehicle stays online after the operator releases control.
```

**Note on WebRTC:** This prototype uses WebSockets for text-based command and sensor JSON payloads. Real-time video from the vehicle would require WebRTC (with STUN/TURN infrastructure). WebRTC is not implemented and is documented as a production evolution path in `docs/TELEOPERATION_PROTOTYPE.md`.

See `docs/TELEOPERATION_PROTOTYPE.md` for the full design and production evolution notes.

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
| **Teleoperation Handoff Prototype** | WebSocket command/sensor flow, mock vehicle client (`scripts/mock_vehicle_client.py`), session lifecycle (requested → claimed → active → released), frontend control panel, backend/frontend tests, `docs/TELEOPERATION_PROTOTYPE.md` |TELEOPERATION_PROTOTYPE.md` |

---

## Known Limitations

- **No authentication.** All endpoints are publicly accessible. Auth is out of scope for this prototype.
- **Seeding is required before ingesting telemetry.** `vehicle_id` must be `v-01` through `v-50` and the vehicle must exist in the database (enforced by a foreign key).
- **No retention policy.** Every telemetry event is persisted. The database will grow indefinitely without a pruning job.
- **2-second polling (telemetry dashboard).** The original fleet telemetry dashboard polls every 2 seconds. Sub-second updates would require WebSockets or Server-Sent Events. The Teleoperation prototype uses WebSockets only for the operator-to-vehicle command and sensor flow, not for the telemetry dashboard.
- **Migrations are not automatic.** Run `alembic upgrade head` manually after the containers start.
- **Single-node only.** No horizontal scaling or read replicas. See `docs/ADR.md` for what would change at larger scale.
- **Teleoperation: no WebRTC video.** The `camera_frame_label` in sensor data is a text string. Real-time video would require WebRTC with STUN/TURN infrastructure.
- **Teleoperation: no operator authentication.** `operator_id` is a free string. JWT enforcement, audit logs, command acknowledgements, and a deadman-switch watchdog are production requirements not yet implemented.
- **Teleoperation: single-process connection manager.** The in-memory WebSocket registry does not survive a backend restart or scale to multiple replicas. Redis Pub/Sub would be required for multi-instance deployments.
