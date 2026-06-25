# AI Interaction Log

This document records every meaningful prompt issued to Claude Code (claude-sonnet-4-6) during the development of this project, along with outputs, corrections, and a final reflection.

---

## Session 1 — Project Structure

**Prompt:**
> Read the README.md file in the current directory. Use it only as context for the challenge requirements. Do not implement the full application yet. Your task now is only to create the initial project structure for a fullstack take-home challenge using this stack: [stack details and folder tree provided].

**Output:**
Claude created all scaffold files in a single pass: docker-compose.yml, .env.example, backend Dockerfile, requirements.txt, alembic setup, FastAPI app skeleton, and the React/Vite/TypeScript frontend shell. It respected the "do not overwrite README.md" constraint and left business logic files empty with docstring stubs.

**Corrections / redirections:** None at this stage.

---

## Session 2 — Backend Models & Database Layer

**Prompt:**
> Implement only the backend database foundation. Models: Vehicle, TelemetryEvent, ZoneCounter, Anomaly, Mission, MaintenanceRecord. Pydantic schemas for all endpoints. Alembic initial migration (hand-written — no live DB). Idempotent seed script for 50 vehicles and 20 zones. Do not implement services or API logic yet.

**Output:**
Claude created:
- `app/models/enums.py` — shared Python enums (`VehicleStatus`, `MissionStatus`, `MaintenanceStatus`) used by both ORM models and Pydantic schemas
- Six model files (`vehicle.py`, `telemetry.py`, `zone.py`, `anomaly.py`, `mission.py`, `maintenance.py`) using SQLAlchemy 2.x `Mapped`/`mapped_column` style with proper FK constraints, indexes, and relationships
- Five schema files (`telemetry.py`, `vehicle.py`, `fleet.py`, `zone.py`, `anomaly.py`) with `field_validator` for `vehicle_id` format (v-01..v-50), zone whitelist validation, and `battery_pct` range constraints
- `alembic/versions/0001_initial_schema.py` — hand-written migration that creates enum types first, then tables in FK-dependency order
- `seed.py` at the backend root — idempotent async seed via `ON CONFLICT DO NOTHING`

**Key decisions made:**
- All child tables FK on `vehicles.vehicle_id` (string), not integer PK — avoids a lookup on every telemetry ingestion since the payload already carries the string ID
- `create_type=False` on `vehiclestatus` enum in `TelemetryEvent` to prevent double-creation of the PostgreSQL type
- `ZoneCounter.entry_count` uses `Integer` (not BigInteger) — sufficient for the prototype's scale; noted in assumptions
- `latest_anomaly` field on `VehicleResponse` defaults to `None` — service layer populates it; Pydantic's `from_attributes=True` falls back to default if attribute is absent on the ORM object

**Corrections / redirections:** None.

---

## Session 3 — Service Logic & API Endpoints

**Prompt:**
> Implement backend service logic and API endpoints. POST /api/telemetry (ingest + anomaly detection + zone increment). GET /api/zones/counts (atomic counters). GET /api/vehicles + PATCH /api/vehicles/{id}/status (with fault transaction). GET /api/fleet/state (GROUP BY aggregate). GET /api/anomalies (filtered query). Keep business logic in services, DB access in repositories. All routes under /api. No auth, no websockets.

**Output:**
Claude created:
- **6 repository files** (`vehicle`, `telemetry`, `zone`, `anomaly`, `mission`, `maintenance`) — thin async SQLAlchemy wrappers; no business logic
- **5 service files** (`telemetry`, `vehicle`, `zone`, `fleet`, `anomaly`) — all orchestration and business rules live here
- **5 API routers** (fully wired; previously stubs) — thin controllers that call exactly one service method each
- Updated `main.py` to add `/api` prefix to all routers to match the Vite proxy configuration

**Key implementation details:**
- Zone increment uses a single `INSERT ... ON CONFLICT DO UPDATE SET entry_count = entry_count + 1` — no Python read-modify-write; concurrent increments for the same zone are serialized atomically by PostgreSQL
- Fault transition uses `SELECT ... FOR UPDATE` to lock the vehicle row, then cancels missions and creates a maintenance record in the same transaction; a rollback undoes all three changes together
- Anomaly detection runs four rules per telemetry event (LOW_BATTERY <15%, VEHICLE_FAULT, ERROR_CODE_REPORTED, HIGH_SPEED >8 m/s); each triggered rule produces one anomaly row
- Fleet state uses a single `GROUP BY current_status` query — a consistent read at READ COMMITTED isolation; safe under concurrent status updates
- `session.flush()` is called after TelemetryEvent INSERT so the auto-generated PK is available for Anomaly FK within the same uncommitted transaction

**Assumptions made:**
- Telemetry ingestion updates vehicle state with last-write-wins (no timestamp guard); vehicle state is a cache, the telemetry table is the source of truth
- Explicit PATCH /vehicles/{id}/status is the only path that triggers mission cancellation; telemetry ingestion only updates the vehicle snapshot and records a VEHICLE_FAULT anomaly
- If a vehicle's `vehicle_id` is not in the DB (not seeded), the TelemetryEvent INSERT will fail with a FK violation — seeding is a precondition, not a runtime concern

**Corrections / redirections:** None.

---

## Session 4 — Frontend Dashboard

*Deferred.* The frontend was implemented across two later sessions (7 and 8) after the backend test infrastructure was stabilised. No separate "Session 4" prompt was issued; the numbering gap reflects the order in which work actually happened.

---

## Session 5 — Tests

**Prompt:**
> Add backend tests for: telemetry ingestion + vehicle state update, all four anomaly rules, zone counter concurrency (20 simultaneous requests), fault transition atomicity (vehicle + mission + maintenance), fleet state aggregation. Use pytest-asyncio. Test against a real test database, not mocks.

**Output:**
Claude created:
- `backend/pytest.ini` — `asyncio_mode = auto`, `testpaths = tests`
- `backend/tests/conftest.py` — shared fixtures: `reset_db` (autouse, drops + recreates all tables per test), `client` (httpx AsyncClient with ASGITransport + `get_db` override pointing to test DB), `db` (raw async session for assertions)
- `backend/tests/test_telemetry.py` — 12 tests: ingestion, vehicle state update, all four anomaly rules with boundary cases, multi-rule firing, anomaly↔telemetry_event FK linkage, validation rejection
- `backend/tests/test_zones.py` — 5 tests: increment, null zone, sequential accumulation, independent zone counting, and the concurrency test (`asyncio.gather` with 20 simultaneous POSTs)
- `backend/tests/test_vehicles.py` — 8 tests: non-fault patch, 404 for unknown vehicle, fault transition updating vehicle/mission/maintenance, all-missions-cancelled (not just one), atomicity assertion (all three state changes verified together)
- `backend/tests/test_fleet.py` — 4 tests: empty DB, all idle, mixed statuses, live update after PATCH

**Key design decisions:**
- Real test PostgreSQL database (`fleet_telemetry_test`) instead of mocks or SQLite — concurrent zone test requires real PostgreSQL atomicity semantics
- `reset_db` with `drop_all()` + `create_all()` per test — guarantees isolation; avoids TRUNCATE complexity with enum types
- `get_db` override set at conftest module-level so all HTTP requests hit the test DB without per-test patching
- `asyncio.gather()` for the concurrency test — httpx AsyncClient with ASGITransport dispatches all 20 requests concurrently in the same event loop; each gets a real separate DB session from the pool

**Bugs found and fixed:** None — the existing implementation was correct. Boundary conditions (battery == 15.0 not flagged, speed == 8.0 not flagged) were explicitly tested.

**Assumptions:**
- Test DB must be created before running tests: `docker compose exec postgres createdb -U fleet fleet_telemetry_test`
- Tests run from inside the backend container (or with correct `DATABASE_URL` / `TEST_DATABASE_URL` env vars)
- `asyncio_mode = auto` removes the need for `@pytest.mark.asyncio` on every test function

**Corrections / redirections:** None.

---

## Session 6 — Async Test Infrastructure Fix

**Prompt:**
> The backend tests are now connecting to the test database, but only the first test passes. The rest fail during reset_db with: RuntimeError: got Future attached to a different loop and also: asyncpg.exceptions.InterfaceError: cannot perform operation: another operation is in progress. Fix the async test setup in backend/tests/conftest.py. Requirements: Do not change application business logic. Do not change API endpoints. Fix only the test infrastructure unless strictly necessary. Use SQLAlchemy NullPool for the test engine. Default TEST_DATABASE_URL should work inside Docker: postgresql+asyncpg://fleet:fleet@postgres:5432/fleet_telemetry_test. Update pytest.ini if needed.

**Output:**
Claude applied two targeted fixes:
- `backend/pytest.ini` — added `asyncio_default_fixture_loop_scope = session` to force a single shared event loop for the entire test session
- `backend/tests/conftest.py` — added `poolclass=NullPool` to the test engine (no connection caching between tests) and changed the default `TEST_DATABASE_URL` host from `localhost` to `postgres` (Docker service hostname)

**Root cause:**
pytest-asyncio 0.24 creates a new event loop per test function by default. The shared `_engine` used asyncpg's built-in connection pool, caching connections that were bound to test 1's event loop. When test 2 ran in a new loop, `reset_db`'s `engine.begin()` retrieved a pooled connection from the old loop → "Future attached to a different loop". `asyncio_default_fixture_loop_scope = session` removes the per-test loop rotation; `NullPool` ensures no connections are cached at the SQLAlchemy level regardless.

**Changes made:**
- `pytest.ini`: `asyncio_default_fixture_loop_scope = session`
- `conftest.py`: `from sqlalchemy.pool import NullPool`, `create_async_engine(..., poolclass=NullPool)`, default URL host `localhost` → `postgres`

**Corrections / redirections:** The NullPool fix alone was insufficient. asyncpg's "another operation is in progress" error still fired because `Base.metadata.drop_all` issues multiple DDL statements over the same connection while asyncpg considers a previous statement still in-flight at the driver level. Replaced the per-test drop_all/create_all entirely with a session-scoped schema creation (once per run) and a per-test `TRUNCATE … RESTART IDENTITY CASCADE` on all tables. TRUNCATE is a single atomic statement per connection; no driver-level interleaving possible. Each test module's own autouse fixtures seed their required rows into the freshly-emptied tables.

---

## Session 7 — Frontend API Integration Layer

**Prompt:**
> Implement the frontend API integration layer: TypeScript types, API service layer (fetch, no extra libraries, /api relative paths), usePolling and useFleetData hooks (2-second polling, loading/error/data, no memory leaks), and update App.tsx to prove data loads. Do not build the final dashboard UI.

**Output:**
Claude created:
- `frontend/src/types/index.ts` — TypeScript interfaces matching backend Pydantic schemas exactly: `VehicleStatus` union, `Anomaly`, `Vehicle` (with `last_seen_at`/`battery_pct`/`latest_anomaly`), `FleetState`, `ZoneCount`, `ZoneCountResponse` (wrapped `{ zones: ZoneCount[] }`)
- `frontend/src/services/api.ts` — Four typed `fetch` wrappers (`fetchVehicles`, `fetchFleetState`, `fetchZoneCounts`, `fetchAnomalies`); `fetchZoneCounts` unwraps the `zones` array from the backend envelope; shared `apiFetch<T>` helper throws on non-ok status
- `frontend/src/hooks/usePolling.ts` — Generic `usePolling(callback, intervalMs)` using a `useRef` pattern so the interval is never rescheduled when the callback identity changes, only when the duration changes; calls callback immediately on mount
- `frontend/src/hooks/useFleetData.ts` — `useFleetData()` fires all four fetches concurrently via `Promise.all`; exposes `loading`, `error`, and the four data arrays; `loading` becomes `false` after the first response (success or failure) and stays false on subsequent polls
- `frontend/src/App.tsx` — Wired to `useFleetData`; renders loading/error states, vehicle count, fleet state JSON, zone counts JSON
- `frontend/vite.config.ts` — Removed incorrect `rewrite` that was stripping `/api` before forwarding; backend routes live under `/api/*` so the prefix must be preserved

**Bug fixed:**
The original `vite.config.ts` rewrote `/api/vehicles` → `/vehicles` before sending to `http://backend:8000`. The backend exposes all routes under `/api/*`, so this produced 404s. Removed the `rewrite` entirely; Vite now forwards `/api/*` verbatim to `http://backend:8000/api/*`.

**Assumptions:**
- No authentication — all API calls are unauthenticated
- Stale data is shown on polling errors rather than clearing the display; error message appears alongside last-known data
- `loading` is `true` only until the first response (any outcome); not reset to `true` on each poll cycle
- No AbortController for in-flight fetches on unmount — acceptable for a prototype, noted as a known gap

---

## Session 8 — React Dashboard UI

**Prompt:**
> Build the React dashboard UI using the existing API integration layer. Components: FleetSummary, VehicleTable, ZoneCounts, AnomalyBadge, StatusBadge, ErrorState, LoadingState. Show fleet state aggregate, all 50 vehicles with status/battery/last_seen/latest_anomaly, zone counts. Poll every 2s. Show last-updated timestamp. Handle loading/error/empty states. Plain CSS, no UI library.

**Output:**
Claude created:
- `frontend/src/App.css` — Full stylesheet: CSS custom properties, dark header, fleet summary grid (5 cards with colored left border per status), two-column content grid (vehicles | zones), sticky table headers, status/anomaly badge colors, spinner animation, responsive breakpoints at 960 px and 540 px
- `frontend/src/components/LoadingState.tsx` — Spinner + "Loading fleet data…"
- `frontend/src/components/ErrorState.tsx` — Full-page error display for first-load failures; shows description and "will retry" hint
- `frontend/src/components/StatusBadge.tsx` — Pill badge colored by `VehicleStatus`; uses CSS classes `status--idle/moving/charging/fault`
- `frontend/src/components/AnomalyBadge.tsx` — Colored badge with human-readable type label; tooltip shows description + timestamp; CSS classes keyed by lowercased `anomaly_type`
- `frontend/src/components/FleetSummary.tsx` — Row of 5 summary cards (idle, moving, charging, fault, total) with colored left borders
- `frontend/src/components/VehicleTable.tsx` — Scrollable table (max-height 660 px, sticky headers) sorted by vehicle_id; shows StatusBadge, battery (red if < 15 %), formatted last_seen_at, AnomalyBadge or "—"; fault rows get a red background tint
- `frontend/src/components/ZoneCounts.tsx` — Table sorted by entry_count descending; charging zones highlighted blue; zone names humanized (underscores replaced with spaces)
- `frontend/src/hooks/useFleetData.ts` — Added `lastUpdated: Date | null` field; set on each successful poll
- `frontend/src/App.tsx` — Composes all components; loading → LoadingState; first-poll error → ErrorState; normal → full dashboard with inline error banner for subsequent poll failures (stale data remains visible)

**Key design decisions:**
- First-load error replaces the page; subsequent poll errors show a banner above stale data — users can see their last known state while the backend recovers
- `latest_anomaly` comes directly from `VehicleResponse` (populated by service layer) — no client-side join against the anomalies list needed
- Battery threshold for red coloring is < 15 % — matches the backend anomaly detection rule (LOW_BATTERY)
- Zone table sorted by entry_count descending so the busiest zones appear first

**Assumptions:**
- No routing needed for a single-page dashboard at this scale
- `anomalies` from `useFleetData` is fetched but not displayed as a separate section — covered per-vehicle via `latest_anomaly`
- Responsive layout collapses to single column below 960 px

---

## Session 9 — Final Documentation & Cleanup

**Prompt:**
> Perform final documentation and cleanup. Update README.md (overview, stack, architecture, run commands, curl examples, known limitations). Update ADR to cover FastAPI decision, zone counter atomicity, fault transition strategy, and fix the HIGH_SPEED anomaly threshold. Complete the AI_LOG including this session and the reflection. Remove the obsolete `version` field from docker-compose.yml. No feature changes.

**Output:**

- `README.md` — Complete rewrite replacing the raw challenge prompt with: project overview, stack table, architecture diagram, 5-step quick-start (env → up → migrate → seed → open), test instructions, full API reference table, curl examples for every endpoint, project structure tree, known limitations
- `docs/ADR.md` — Full rewrite covering all six decisions (PostgreSQL, FastAPI + async, polling, anomaly rules, atomic zone counter, fault transaction), assumptions, scale plan, and deliberate omissions. Fixed HIGH_SPEED threshold from `> 3.0 AND status != moving` (incorrect) to `> 8.0` (matches code)
- `docs/AI_LOG.md` — Filled in Session 4 (noted deferral), completed Session 9, wrote Reflection
- `docker-compose.yml` — Removed obsolete `version: "3.9"` field (Docker Compose V2 ignores it but emits a warning)

**Bugs caught during review:**
- ADR described HIGH_SPEED as `speed_mps > 3.0 AND status != "moving"`. Actual code: `speed_mps > 8.0` (unconditional). Fixed in ADR.
- ADR was missing three of the eight requested decision areas (FastAPI rationale, zone counter atomicity, fault transaction strategy). Added.

**Corrections / redirections:** None.

---

## Reflection

- **What the AI was good at:** Generating complete, correct implementations from detailed specifications in a single pass. Business logic (atomic upserts, SELECT FOR UPDATE, Pydantic validators, anomaly rules), TypeScript types, and React hook patterns were all produced correctly the first time. It also caught a bug that was present before it touched the code — the Vite proxy `rewrite` that would have caused every frontend API call to return 404.

- **Where it failed:** Async test infrastructure. Getting pytest-asyncio, asyncpg, and SQLAlchemy's async engine to coexist without "Future attached to a different loop" or "another operation is in progress" errors required four separate debugging sessions: (1) adding NullPool, (2) replacing drop\_all/create\_all with TRUNCATE, (3) switching from `async with` to explicit try/finally, (4) replacing the long-lived `db` session fixture with a factory that opens and closes a session per query. Each fix was individually plausible but exposed the next issue.

- **What required manual double-checking:** The ADR anomaly threshold was wrong (3.0 vs 8.0 m/s). Caught by comparing the ADR to the actual service code during the final review pass. The deployment flow — migrations are not auto-run on container start — also needed to be verified before documenting it as a required manual step.

- **What I had to correct or redirect:** Almost exclusively the test infrastructure (four rounds). One redirect on the Vite proxy (the rewrite bug was a scaffold issue that Claude caught when asked to implement the API layer). The rest — models, services, repositories, API endpoints, React components — required no corrections.

- **Overall assessment:** Highly effective for code generation and architecture across a well-specified fullstack project. The main failure mode is infrastructure/configuration subtlety — particularly async runtime behaviour that depends on library version interactions — where the AI's first fix is often directionally correct but incomplete. For a time-boxed take-home challenge, AI assistance made it feasible to deliver a complete, tested, documented application; the human value was in reviewing correctness of the generated artifacts (ADR vs code) and in recognising when a fix was insufficient.

---



## Session 10 — Post-interview Hardening

**Prompt:**
> Improve the project with focused post-interview enhancements before pushing it again to GitHub. Add frontend tests, GitHub Actions CI, a concurrency demo script, scalability notes, production readiness notes, and update the README. Do not rewrite the project or change the core architecture.

**Output:**
Claude added:
- frontend tests with Vitest and React Testing Library
- tests for dashboard states, FleetSummary, ZoneCounts, VehicleTable, and useFleetData
- `.github/workflows/ci.yml`
- `scripts/concurrent_zone_test.py`
- `docs/SCALABILITY_NOTES.md`
- `docs/PRODUCTION_READINESS.md`
- README updates with test commands and post-interview improvements

**Corrections / redirections:**
- Changed `@testing-library/jest-dom` to `@testing-library/jest-dom/vitest`.
- Added explicit React Testing Library cleanup after each test.
- Fixed an ambiguous test assertion caused by multiple `—` placeholders.
- Replaced `Array.prototype.at(-1)` with an index-based lookup to match the current TypeScript target.
- Rebuilt the frontend Docker image after adding Vitest dependencies.
- Corrected the concurrency demo input by using a valid zone such as `charging_bay_2` instead of an invalid default zone.

**Result:**
The hardening pass addressed the main interview discussion points: frontend test coverage, CI, concurrency demonstration, scalability planning, and production readiness.

---

## Session 11 — Teleoperation Handoff Prototype

**Prompt:**
> Add a focused Teleoperation Handoff Prototype module. Implement a lightweight teleoperation
> handoff prototype using FastAPI WebSockets. Use a Python mock vehicle client to simulate the
> vehicle side. Add HTTP session lifecycle endpoints, WebSocket operator and vehicle routes,
> a frontend control panel, backend and frontend tests, and full documentation.

**Output:**
Claude created:

**Backend:**
- `app/models/teleoperation.py` — `TeleoperationSession` model with string status (avoids PostgreSQL enum migration complexity), FK to vehicles, nullable fields for operator, timestamps, last command, last sensor payload
- `app/schemas/teleoperation.py` — Create, claim, release, response, operator command (Literal union), and vehicle sensor message schemas with `vehicle_id` format validation reused from telemetry schema
- `app/repositories/teleoperation.py` — Thin async DB access: create, get_by_session_id, list_sessions, claim, release, record_command, record_sensor_payload, get_active_session_for_vehicle
- `app/services/teleoperation.py` — Session lifecycle logic with HTTPException for 404/409 states; business rule: only `requested` sessions can be claimed; only `active`/`requested` sessions can be released
- `app/api/teleoperation.py` — HTTP router (`/api/teleoperation`) + WebSocket router (`/ws/teleoperation`) + `_ConnectionManager` class with per-socket send locks to prevent concurrent write interleaving
- `alembic/versions/0002_add_teleoperation_sessions.py` — Standalone migration, `down_revision = "0001"`, no changes to existing schema
- `tests/test_teleoperation.py` — 12 tests covering create, claim, release, 404 / 409 error paths, full lifecycle with DB assertion

**Frontend:**
- `src/types/index.ts` — Added `TeleoperationStatus`, `VehicleSensorPayload`, `TeleoperationSession` interfaces
- `src/services/api.ts` — Added `apiPost` helper and `fetchTeleoperationSessions`, `createTeleoperationSession`, `claimTeleoperationSession`, `releaseTeleoperationSession`
- `src/hooks/useTeleoperation.ts` — Manages session polling (3 s), WebSocket lifecycle (connect/disconnect/send), sensor data state, and error state; WebSocket URL uses `window.location.hostname` so it works both locally and in Docker
- `src/components/TeleoperationPanel.tsx` — Complete control panel: vehicle selector (v-01..v-50), reason input, session table with Claim/Connect/Disconnect/Release actions, command buttons (Forward/Backward/Left/Right/Stop), live sensor feed grid
- `src/__tests__/TeleoperationPanel.test.tsx` — Mocked API + minimal WebSocket mock; tests panel structure, empty state, WS badge

**Scripts:**
- `scripts/mock_vehicle_client.py` — Async Python script using `websockets`; sends sensor updates every second; prints received commands; echoes last command in next sensor update; uses asyncio.Lock for safe concurrent sends

**Docs:**
- `docs/TELEOPERATION_PROTOTYPE.md` — What was added, what is real vs mocked, how to run the demo step by step, how to evolve in production (WebRTC, command ACKs, auth, fail-safe, Redis Pub/Sub, latency)
- `docs/ADR.md` — Added Decision 8: teleoperation uses WebSockets + mock client
- `README.md` — Added "Teleoperation Prototype" section with demo commands

**Key design decisions:**
- String status field instead of PostgreSQL enum — avoids `CREATE TYPE` / `DROP TYPE` complexity in migrations and makes adding new status values trivial
- Separate `http_router` and `ws_router` in `teleoperation.py` — allows clean URL prefixes (`/api/teleoperation` vs `/ws/teleoperation`) without polluting `main.py`
- In-memory `_ConnectionManager` with per-socket `asyncio.Lock` — prevents interleaved concurrent `send_json` calls which would corrupt the WebSocket frame stream
- `window.location.hostname` for WebSocket URL — works for both `localhost` direct access and Docker/proxy environments without hardcoding a port

**Assumptions:**
- One operator per session; concurrent claim attempts return 409
- `operator-1` is the default operator ID if none is provided (demo convenience)
- `websockets` package is added to `requirements.txt` for the mock client; the FastAPI server itself needs no additional packages for WebSocket support
- The conftest `_TRUNCATE` statement is updated to include `teleoperation_sessions` as the first table (child before parent for FK safety)

---

## Session 12 — Teleoperation Cleanup Pass

**Prompt:**
> Make a small final cleanup pass for the Teleoperation Handoff Prototype. Expand statuses,
> fix lifecycle behavior (claimed distinct from active), update tests, fix README architecture
> section, fix concurrency demo duplication, update docs.

**Output:**

**Backend:**
- `app/schemas/teleoperation.py` — expanded `_VALID_STATUSES` to all six values: `requested`, `claimed`, `active`, `released`, `completed`, `failed`
- `app/repositories/teleoperation.py` — `claim()` now sets status to `"claimed"` (not `"active"`); added `activate()` function; `get_active_session_for_vehicle()` now matches both `"claimed"` and `"active"` so vehicle sensor data is stored as soon as a session is claimed
- `app/services/teleoperation.py` — `release_session()` allows release from `requested`, `claimed`, or `active`; added `activate_session()` called when operator WS connects
- `app/api/teleoperation.py` — `operator_ws` handler calls `activate_session` after accepting the connection

**Backend tests (`tests/test_teleoperation.py`):**
- `test_claim_session`: assertion updated to `status == "claimed"`
- Renamed `test_claim_already_active_session_returns_409` → `test_claim_already_claimed_session_returns_409`
- `test_full_session_lifecycle`: claim assertion updated to `"claimed"`
- Added `test_release_session_from_active_returns_released`: forces `active` status via raw SQL, then releases via HTTP

**Frontend:**
- `src/types/index.ts` — `TeleoperationStatus` expanded to include `claimed` and `completed`
- `src/components/TeleoperationPanel.tsx` — `statusColor()` handles all six statuses; Connect button now shows for `claimed` and `active` sessions; Release button shows for `requested`, `claimed`, and `active`
- `src/App.css` — added `.teleop-status--claimed` (indigo) and `.teleop-status--completed` (green) CSS classes
- `src/__tests__/TeleoperationPanel.test.tsx` — refactored mock factory to be self-contained (avoids `vi.mock` hoisting issue with module-level consts); added `test_renders claimed status badge` and `test_command panel only appears after WS connects`

**Documentation:**
- `README.md` — Architecture section updated to distinguish polling (telemetry dashboard) from WebSockets (teleoperation); concurrency demo deduplicated and zone fixed to `charging_bay_2`; Teleoperation section updated with full lifecycle diagram and corrected demo order
- `docs/TELEOPERATION_PROTOTYPE.md` — added polling vs WebSockets note, lifecycle diagram section, updated step descriptions
- `docs/ADR.md` — Decision 8 updated with lifecycle states and polling/WS distinction

**No new migration was needed.** The `status` column is already `String(20)` with no DB-level constraint. All new status values work without schema changes.

**Key decisions:**
- `claimed` is the HTTP-accessible state after claim; `active` is set only when the operator WebSocket actually connects — this gives a clear distinction between "assigned" and "live"
- `completed` and `failed` are documented as intended terminal states but have no HTTP endpoint yet — they are listed in the schema and types so the lifecycle is clear without overbuilding
- `vi.mock` factory is kept self-contained to avoid Vitest hoisting interaction with module-level const declarations

---

## Session 13 — Teleoperation Release Bug Fix

**Prompt:**
> Fix a teleoperation release-state bug found during manual testing. After releasing a session,
> the UI allowed command buttons to remain active without a page refresh, and the mock vehicle
> continued to receive commands after the session was already released. The persisted state
> was correct; the live frontend/WebSocket state was stale.

**Output:**

**Root cause:** Three compounding issues:
1. `releaseSession` in the hook called `disconnectOperator()` *after* `loadSessions()` — the WS stayed open during the async round-trip
2. The backend HTTP release route did not close the live operator WebSocket
3. Command buttons checked only `wsStatus !== 'connected'`, not the session's DB-side status

**Backend fixes (`app/api/teleoperation.py`):**
- Added `close_operator_session(session_id)` to `_ConnectionManager`: sends `{"type": "session_closed", "status": "released"}` to the operator WS, then closes it. The vehicle WebSocket is intentionally left open — the mock vehicle represents a physical device that stays online.
- `release_session` HTTP route now calls `_manager.close_operator_session(session_id)` after committing the DB change.
- Command loop in `operator_ws` now checks DB session status before `record_command` / `forward_command_to_vehicle`. If status is not `active`, sends `session_closed` and breaks — provides defence-in-depth against race conditions between HTTP release and in-flight command messages.

**Frontend fixes (`src/hooks/useTeleoperation.ts`):**
- `disconnectOperator` moved before `releaseSession` in the hook file to avoid a temporal dead zone error when adding it to `releaseSession`'s deps array.
- `releaseSession` now calls `disconnectOperator()` immediately after the release API call succeeds, before `loadSessions()` — command buttons are disabled synchronously, not after a network round-trip.
- `connectOperator`'s `onmessage` handler now handles `{"type": "session_closed"}`: clears `activeSessionId`, `wsStatus`, and `sensorData`; closes the WS; refreshes sessions — works even when the backend initiates the close rather than the user clicking Release.
- `loadSessions` added to `connectOperator`'s deps array for correctness.

**Frontend fixes (`src/components/TeleoperationPanel.tsx`):**
- `canSendCommand = wsStatus === 'connected' && activeSession?.status === 'active'` — dual guard: WS connection state AND DB-side session status. Command buttons are disabled if either condition is false.

**Tests added:**
- `src/__tests__/TeleoperationPanelCommands.test.tsx` (new file, 4 tests): mocks `useTeleoperation` hook to verify command buttons are enabled only when `wsStatus === 'connected'` AND session status is `'active'`; verifies buttons are disabled when either condition fails; verifies command panel is absent when `activeSessionId` is null.
- `src/__tests__/TeleoperationPanel.test.tsx`: added test verifying a `released` session shows no Claim, Connect, or Release action buttons.

**Documentation:**
- `docs/TELEOPERATION_PROTOTYPE.md` — added "Release behavior" subsection describing the two-layer protection (HTTP closes WS, status guard in command loop), why the vehicle WS is left open, and the full condition set for command button availability.
- `docs/ADR.md` — reordered Decision 7 before Decision 8; updated Decision 7 to clarify WebSockets were not added to the telemetry dashboard during the hardening pass (they were added later for teleoperation).
- `docs/PRODUCTION_READINESS.md` — fixed test count (30 → 44), updated infrastructure statement, added Teleoperation Handoff Prototype subsection.
- `docs/SCALABILITY_NOTES.md` — clarified that WebSockets were deliberately excluded from the telemetry dashboard but later added for the teleoperation module as a different use case.

**Result:** Backend 44/44, frontend 43/43, build clean. Manual verification confirmed: after clicking Release, command buttons disappear immediately without F5; mock vehicle continued sending sensor data (expected); no further commands reached the mock vehicle after release.