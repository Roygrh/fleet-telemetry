# Architecture Decision Record

Key decisions made while building the Fleet Telemetry Monitoring Service.

---

## Decision 1 — PostgreSQL over SQLite

**Chosen for:** row-level locking (`SELECT ... FOR UPDATE`), atomic upserts (`INSERT ... ON CONFLICT`), and async support via `asyncpg`.

SQLite serializes all writes through a single lock. At 50 vehicles × 1 Hz that is 50 concurrent writes/second; SQLite's global write lock would turn this into a queue. PostgreSQL locks at the row level, so each vehicle's telemetry write is independent.

---

## Decision 2 — FastAPI + async SQLAlchemy

FastAPI's async request handling pairs directly with asyncpg's event-loop-native driver: each HTTP request gets a non-blocking async session, and all 50 vehicles can be served concurrently without a thread pool. SQLAlchemy 2.x's `Mapped`/`mapped_column` style gives type-safe models with no boilerplate.

Business logic lives in service classes; DB access is isolated in thin repository functions. This separation is what made the async session swap straightforward in tests.

---

## Decision 3 — Polling over WebSockets

Client-side 2-second polling is sufficient at this scale. With 50 vehicles emitting at 1 Hz, data changes several times per poll interval regardless — a 2 s lag is imperceptible to a warehouse operator.

WebSockets add reconnection logic, server-side fanout state, and deployment complexity that are not justified here. The trade-off is explicit: at 10,000+ vehicles or sub-second latency requirements, switch to Server-Sent Events or WebSockets.

---

## Decision 4 — Anomaly Detection Rules

Four rules are evaluated per telemetry event. Each triggered rule produces one persisted anomaly row.

| Rule | Condition | Rationale |
|---|---|---|
| `LOW_BATTERY` | `battery_pct < 15` | Risk of mid-mission shutdown |
| `VEHICLE_FAULT` | `status == "fault"` | Explicit hardware/software error |
| `ERROR_CODE_REPORTED` | `len(error_codes) > 0` | Device-reported error |
| `HIGH_SPEED` | `speed_mps > 8.0` | Exceeds safe warehouse speed limit |

Thresholds are hardcoded constants. A production system would store them in configuration.

---

## Decision 5 — Atomic Zone Counter

Zone entry counters use a single SQL statement:

```sql
INSERT INTO zone_counters (zone_id, entry_count) VALUES (:zone, 1)
ON CONFLICT (zone_id) DO UPDATE
  SET entry_count = zone_counters.entry_count + 1
```

There is no Python read-modify-write. PostgreSQL serializes concurrent increments for the same row at the storage level, so the counter is exact regardless of how many vehicles enter the same zone simultaneously. A naive `SELECT` + `UPDATE` pair under concurrent load would lose counts.

---

## Decision 6 — Fault Transition via SELECT FOR UPDATE

`PATCH /vehicles/{id}/status` with `status=fault` runs atomically:

1. `SELECT ... FOR UPDATE` — locks the vehicle row so no concurrent write can interleave.
2. `UPDATE missions SET status='cancelled'` for all active missions.
3. `INSERT INTO maintenance_records` with reason.
4. `UPDATE vehicles SET current_status='fault'`.
5. Single `COMMIT` — all three changes land together or none do.

A rollback on any step leaves vehicles, missions, and maintenance records unchanged.

---

## Unclear Constraints & Assumptions

1. **Mission model** — The spec mentions "active mission" but provides no schema. Assumed a `missions` table with `vehicle_id`, `status` (active / cancelled / completed), and `started_at`.
2. **Zone geometry** — The edge client is assumed to handle boundary detection. The backend only counts `zone_entered` events; it does not validate coordinates against zone polygons.
3. **Fleet size** — Fixed at 50 vehicles (`v-01` through `v-50`). The seed script must run before telemetry ingestion (enforced by a foreign key constraint).
4. **Anomaly storage** — Anomalies are persisted, not just streamed, to support the filtered query endpoint and the per-vehicle "latest anomaly" enrichment on the vehicle list.
5. **No auth** — Out of scope per the spec's time budget; would be the first addition in a production hardening pass.

---

## What Would Change at Scale

"Significantly" = 10,000+ vehicles, sub-100 ms latency, multi-region.

- **Message broker** (Kafka / Redpanda) between the ingest endpoint and the DB write — decouples HTTP throughput from database latency and enables replay.
- **WebSockets / SSE** to replace polling; a stateful gateway handles connection fanout.
- **Table partitioning** on `telemetry_events` by time bucket or `vehicle_id` hash.
- **Redis `INCR`** for zone counters — eliminates PostgreSQL row contention at 10k concurrent zone events/second.
- **Read replicas** for dashboard queries so reads don't compete with writes.
- **Retention jobs** to prune old telemetry rows on a configurable TTL.

---

## Deliberate Omissions

| Omission | Reason |
|---|---|
| Auth / RBAC | Not required by spec; significant added scope |
| Telemetry retention / TTL | Out of scope; DB grows indefinitely in this prototype |
| Geospatial rendering | Zone counts satisfy the spec; a map requires a mapping library |
| Push alerts | Anomalies are stored and queryable; no webhooks or notification channels |
| Lat / lon in vehicle list | Present in telemetry events and DB; the spec's dashboard only requires status, battery, and anomaly |

## Decision 7 — Post-interview hardening without changing the core architecture

After the technical interview, I added a small hardening pass focused on the main discussion points: frontend test coverage, CI validation, a manual concurrency demo script, scalability notes, and production readiness documentation.

I deliberately did not introduce Kafka, WebSockets, Kubernetes, or a cloud deployment implementation in this version. Those are valid next steps at higher scale, but they would have changed the scope of the take-home. The goal was to strengthen the existing vertical slice while keeping the original architecture intact.

The additions were:
- Vitest and React Testing Library tests for the dashboard and data hook.
- GitHub Actions CI for backend tests, frontend tests, and frontend build.
- A concurrency demo script for the atomic zone counter.
- Scalability notes explaining what would change at thousands of events per second.
- Production readiness notes listing the next steps before a real deployment.