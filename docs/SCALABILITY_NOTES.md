# Scalability Notes

## Current target scale

The take-home spec defines **50 autonomous vehicles** each emitting one telemetry event per second (1 Hz). That is at most 50 writes/second and 50 + (dashboard poll) reads/second — a workload well within the range of a single PostgreSQL instance on commodity hardware.

---

## Why PostgreSQL is sufficient at this scale

### Zone counter atomicity

Zone counters use a single `INSERT … ON CONFLICT DO UPDATE` (upsert). PostgreSQL serialises concurrent updates to the same row at the storage level, so there is no lost-update race condition. The atomic upsert approach was stress-tested with 20 simultaneous requests in `tests/test_zones.py` and validated with `scripts/concurrent_zone_test.py`.

### Fault transition atomicity

Status changes to `fault` use `SELECT … FOR UPDATE` to lock the vehicle row, then cancel active missions and create a maintenance record in a single transaction. No external coordination is needed.

### Connection overhead

FastAPI uses an async SQLAlchemy 2 engine with asyncpg. Connection pool reuse means 50 writes/second translates to far fewer than 50 concurrent DB connections.

---

## Likely limits as volume grows

| Threshold | Bottleneck |
|---|---|
| ~500 events/s | Single-node PostgreSQL WAL throughput; write amplification from indexes |
| ~2 000 events/s | `telemetry_events` table scans for anomaly queries; connection pool saturation |
| ~10 000 events/s | Row-level lock contention on zone counters with many concurrent upserts |
| Millions of rows | `telemetry_events` table grows unbounded; queries slow without partitioning |

---

## What would change at high event volume

### Ingestion buffer (message broker)

At thousands of events per second, the HTTP → PostgreSQL write path becomes a bottleneck. An ingestion buffer decouples producers from the database:

- **Kafka / Redpanda** — high-throughput, durable, replay-capable. A consumer group reads from the topic and writes batches to PostgreSQL.
- **AWS Kinesis / Google Pub/Sub** — managed equivalents for cloud deployments.
- **Benefit:** the API returns 202 immediately and the database never receives a spike.

The current code returns 202 Accepted by design (the endpoint comment in `api/telemetry.py` notes this), so adopting an async write path would not change the contract.

### Zone counter sharding

At high write rates, all upserts for the same zone_id contend on a single row. Alternatives:

- **Redis INCR** — atomic, in-memory, sub-millisecond. A background job periodically flushes to PostgreSQL for persistence.
- **Sharded counters** — write to multiple rows per zone, read by summing them. Adds complexity; Redis is simpler.

### Table partitioning

The `telemetry_events` table will grow without bound. Partition by time range (e.g., monthly):

```sql
CREATE TABLE telemetry_events (…) PARTITION BY RANGE (timestamp);
CREATE TABLE telemetry_events_2026_06 PARTITION OF telemetry_events
  FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
```

Benefits: queries filtered by time stay in one partition; old partitions can be detached and archived or dropped.

### Retention policy

Without pruning, the database grows indefinitely. A retention job (cron or pg_cron) should delete events older than the retention window:

```sql
DELETE FROM telemetry_events WHERE timestamp < NOW() - INTERVAL '90 days';
```

Or drop old partitions entirely (near-instant compared to row-level deletes).

### Read replicas

Dashboard queries (fleet state aggregation, vehicle list with anomaly join) can be served from a read replica, taking pressure off the primary write node. SQLAlchemy 2 supports routing queries to a secondary engine.

### Observability and metrics

At scale, unobserved systems fail silently. Key additions:

- **Structured logging** (JSON) with request ID, vehicle_id, and timing.
- **Application metrics** (Prometheus / OpenTelemetry) for ingestion latency, error rate, queue depth.
- **Database metrics** — connection pool saturation, long-running queries, replication lag.
- **Alerting** — anomaly spike rate, zone counter divergence, disk growth.

### Dashboard delivery

At 5 000+ vehicles, polling every 2 seconds from every connected browser generates significant read traffic. Alternatives:

- **Server-Sent Events (SSE)** — server pushes updates; no repeated polling overhead.
- **WebSockets** — bidirectional, useful if the dashboard ever sends commands.

The current polling architecture was a deliberate choice for 50 vehicles (see `docs/ADR.md`). Switching requires a connection manager (e.g., Redis pub/sub fanout) and client reconnection logic.

---

## Why these were not implemented in the take-home version

The challenge specified 50 vehicles at 1 Hz, a scope where:

- A single PostgreSQL node handles the load with headroom.
- Atomic SQL upserts eliminate the need for Redis or external coordination.
- Polling every 2 seconds is responsive without the operational cost of WebSockets.
- There is no need to partition a table that fits comfortably in memory.

Adding Kafka, Redis, partitioning, or WebSockets would have introduced significant infrastructure complexity without improving correctness or demonstrating additional engineering judgment for the stated requirements. These choices are documented in `docs/ADR.md`.
