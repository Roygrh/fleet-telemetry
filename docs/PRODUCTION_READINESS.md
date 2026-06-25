# Production Readiness

This document describes what is already solid in the project, what was added as post-interview hardening, and what would still need to be done before a production deployment.

---

## What is already solid

### Backend

- **Async throughout.** FastAPI + SQLAlchemy 2 (async) + asyncpg. Every DB operation is non-blocking; a slow query never stalls the event loop.
- **Atomic writes.** Zone counter upserts and fault transitions use SQL-level atomicity (`INSERT … ON CONFLICT`, `SELECT FOR UPDATE`). No in-process locking needed.
- **Repository / service separation.** Business logic is isolated from DB access; changing the storage layer does not touch the business rules.
- **Real database tests.** All 44 backend tests hit a real PostgreSQL instance — no mocks. Concurrency correctness (20 simultaneous zone increments) is validated in `test_zones.py`.
- **Schema migrations.** Alembic manages all schema changes. The migration history is reproducible.
- **Environment-based configuration.** `DATABASE_URL` is read from the environment; no credentials are hardcoded.
- **Health endpoint.** `GET /health` allows a load balancer or orchestrator to probe liveness.
- **Pydantic validation.** All API inputs are validated at the boundary; invalid vehicle IDs and unknown zones are rejected with 422.

### Frontend

- **Type-safe throughout.** Strict TypeScript with no `any`. All API response shapes have matching interfaces.
- **Dual error handling.** First-poll failure shows a full-page error state; subsequent poll failures show an inline banner while keeping stale data visible.
- **Separated concerns.** API fetches (`services/api.ts`), polling logic (`hooks/usePolling.ts`), and data orchestration (`hooks/useFleetData.ts`) are independent and individually testable.

### Infrastructure

- **Docker Compose** fully describes all three services (PostgreSQL, backend, frontend) with health checks and dependency ordering.
- **Simple telemetry delivery.** The original telemetry dashboard still uses 2-second HTTP polling — reliable for 50 vehicles and requires no server-side connection state. The teleoperation prototype intentionally adds WebSockets only for the operator-to-vehicle command and simulated sensor flow, where bidirectional real-time communication is required.

---

## Post-interview improvements

These were added after the technical discussion to address feedback and demonstrate continued engineering judgment:

| Addition | Purpose |
|---|---|
| **Frontend tests** (Vitest + React Testing Library) | Cover component rendering, loading/error states, hook behaviour with mocked fetch |
| **GitHub Actions CI** (`.github/workflows/ci.yml`) | Validate backend tests, frontend tests, and frontend build on every push |
| **Concurrency demo script** (`scripts/concurrent_zone_test.py`) | Make the atomic zone counter easy to demonstrate outside of pytest |
| **Scalability notes** (`docs/SCALABILITY_NOTES.md`) | Explain current limits and what would change at higher event volume |
| **Production readiness notes** (this file) | Enumerate what would be needed before a real deployment |
| **Teleoperation Handoff Prototype** | WebSocket command flow, mock vehicle client, session lifecycle (requested → claimed → active → released), frontend control panel, 44 backend + 43 frontend tests. See below. |

### Teleoperation Handoff Prototype — current state

The teleoperation module demonstrates a real-time operator-to-vehicle command channel using FastAPI WebSockets. What is solid:

- Session lifecycle is persisted in PostgreSQL — requests, claims, activations, and releases are durable and auditable.
- The WebSocket command loop guards against stale connections: the backend checks session status before forwarding any command.
- Releasing a session immediately closes the operator WebSocket — commands are rejected both server-side (status guard) and client-side (UI disables buttons synchronously).
- The mock vehicle WebSocket is intentionally left open after release, reflecting the physical reality that a vehicle stays online regardless of operator session state.
- Backend and frontend tests cover the full HTTP lifecycle and the command button guard logic.

What is not yet production-ready for teleoperation:

- **No operator authentication** — `operator_id` is a free string. JWT or session token verification is required.
- **No audit log** — every command with operator identity, timestamp, and vehicle response should be persisted for incident review.
- **No command acknowledgements** — commands are fire-and-forget. A sequence number + ACK protocol is needed so the operator knows whether each command was received.
- **No deadman switch** — if the operator WebSocket drops unexpectedly, the vehicle receives no automatic stop command. A server-side watchdog timer should send `stop` and mark the session `failed`.
- **No video feed** — the `camera_frame_label` is a text string. WebRTC with a STUN/TURN server is the production path for real-time video.
- **In-memory connection manager** — does not survive a backend restart or scale to multiple replicas. Redis Pub/Sub or a dedicated WebSocket gateway would be required.

---

## What is not yet production-ready

The following are knowingly out of scope for the take-home prototype. They are standard concerns for any production API.

### Authentication and authorisation

All API endpoints are publicly accessible. A production deployment would require:

- Token-based auth (JWT or OAuth 2.0 / OIDC).
- Role-based access control — operators can update vehicle status; read-only dashboards cannot.
- API key management for the telemetry ingestion endpoint (vehicle clients authenticate before posting events).

### Rate limiting

The telemetry endpoint accepts unlimited requests. A misbehaving vehicle or a misconfigured client can flood the database. A reverse proxy (nginx, Traefik) or API gateway should enforce per-client rate limits.

### Secrets management

The database credentials are in a `.env` file that is gitignored locally but must be injected securely in deployed environments. A secret manager (AWS Secrets Manager, HashiCorp Vault, Kubernetes Secrets) is required.

### Environment-specific configuration

`settings.py` reads from a single `.env` file. Production deployments need distinct configs for staging and production, with separate databases and credentials.

### Cloud deployment

The project runs on Docker Compose. A production deployment would use:

- A container orchestrator (Kubernetes, ECS, or Cloud Run).
- A managed PostgreSQL service (RDS, Cloud SQL, or similar) with automated backups, point-in-time recovery, and failover.
- A CDN or object storage for the compiled frontend assets.
- TLS termination at the load balancer.

### Observability

- Structured JSON logging with request IDs for correlation.
- Application metrics (Prometheus / OpenTelemetry exporter) for ingestion rate, latency percentiles, and error rates.
- A distributed tracing system (Jaeger, Tempo) for slow-request diagnosis.
- Alerting on anomaly spike rates, error rates above threshold, and disk/memory pressure.

### Data retention

`telemetry_events` grows indefinitely. A retention policy (e.g., delete events older than 90 days, or partition the table and drop old partitions) is required before the database reaches storage limits.

### Frontend end-to-end tests

Component-level tests (added post-interview) validate rendering in isolation. End-to-end tests (Playwright or Cypress) would validate the full browser → API → database round trip, including the polling cycle and dashboard update behaviour.

### Deployment pipeline

A CI pipeline (added post-interview) validates code correctness. A CD pipeline would additionally:

- Run Alembic migrations before the new backend version starts.
- Perform a canary or rolling deployment to avoid downtime.
- Roll back automatically if the health check fails after deployment.

### Automatic migrations on startup

Currently, `alembic upgrade head` must be run manually. In production, migrations should run as part of the deployment process (an init container in Kubernetes, or a pre-start hook in the deployment script), not as a manual step.
