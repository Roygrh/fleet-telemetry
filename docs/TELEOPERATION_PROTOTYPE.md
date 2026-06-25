# Teleoperation Handoff Prototype

A focused extension to the Fleet Telemetry Monitoring Service that demonstrates
real-time operator-to-vehicle command streaming via WebSockets.

> **Note on polling vs WebSockets:** The original fleet telemetry dashboard continues to
> use 2-second HTTP polling — that decision is unchanged and documented in `docs/ADR.md`.
> WebSockets are used only in this teleoperation module, where bidirectional real-time
> communication between the operator and the mock vehicle is required.

---

## What was added

### Backend

| Path | Purpose |
|---|---|
| `app/models/teleoperation.py` | `TeleoperationSession` ORM model |
| `app/schemas/teleoperation.py` | Pydantic schemas for create / claim / release / command / sensor messages |
| `app/repositories/teleoperation.py` | DB access layer (no business logic) |
| `app/services/teleoperation.py` | Session lifecycle business logic |
| `app/api/teleoperation.py` | HTTP routes + WebSocket routes + in-memory connection manager |
| `alembic/versions/0002_add_teleoperation_sessions.py` | Migration for `teleoperation_sessions` table |
| `tests/test_teleoperation.py` | Backend tests for session lifecycle |

### Frontend

| Path | Purpose |
|---|---|
| `src/types/index.ts` | Added `TeleoperationSession`, `VehicleSensorPayload` types |
| `src/services/api.ts` | Added `fetch*` / `create*` / `claim*` / `release*` helpers |
| `src/hooks/useTeleoperation.ts` | Session polling + WebSocket state management |
| `src/components/TeleoperationPanel.tsx` | Full teleoperation UI panel |
| `src/__tests__/TeleoperationPanel.test.tsx` | Frontend component tests |

### Scripts

| Path | Purpose |
|---|---|
| `scripts/mock_vehicle_client.py` | Python script that simulates the vehicle/device side of the WebSocket |

---

## Session lifecycle

```
POST /sessions          → requested
POST …/claim            → claimed       (operator assigned; WS not yet open)
operator WS connects    → active        (live command channel open)
POST …/release          → released      (operator returns control)
                        → completed     (documented terminal state; no HTTP trigger yet)
                        → failed        (documented error state; no HTTP trigger yet)
```

The `status` field is a plain string — no PostgreSQL enum — so additional states can
be introduced without a new migration.

### Release behavior

When `POST …/release` is called:

1. The session status is set to `released` in the database.
2. If an operator WebSocket is registered for that session, the backend sends
   `{"type": "session_closed", "status": "released"}` and closes the connection.
3. The frontend `session_closed` handler immediately clears `activeSessionId`,
   sets `wsStatus` to `disconnected`, and refreshes the session list — command
   buttons disappear without a page refresh.
4. The mock vehicle WebSocket is intentionally left open. The mock vehicle
   represents a physical device that stays online regardless of session state;
   it may continue sending simulated sensor data after the operator releases.
5. If a command arrives at the backend WebSocket handler before the close frame
   is processed, a status guard re-checks the DB and rejects the command if the
   session is no longer `active`.

Command buttons require all three of the following to be true:
- `wsStatus === 'connected'`
- `activeSessionId` is set
- The matching session's DB status is `'active'`

---

## Why WebSockets, not WebRTC

WebRTC is the production answer for bidirectional video + audio + low-latency data between
a browser operator and a remote vehicle. It handles NAT traversal (TURN/STUN), adaptive
bitrate video, and peer-to-peer data channels.

However, WebRTC requires:

- A signalling server (at minimum a few hundred lines of async code)
- STUN/TURN infrastructure (e.g. Coturn) for NAT traversal
- `aiortc` or a native browser `RTCPeerConnection` with careful SDP negotiation
- A real camera or a software camera feed for anything non-trivial

For this prototype the goal was to demonstrate **the session lifecycle and command flow**,
not to build video infrastructure. WebSockets give us:

- Real-time bidirectional messaging in the browser without extra dependencies
- Simple fan-out via an in-memory connection manager
- A natural fit for text-based command and sensor JSON payloads
- Zero infrastructure beyond the existing FastAPI backend

The design is explicitly layered so that WebRTC could replace the WebSocket channel in the
future without changing the HTTP session lifecycle or the database model.

---

## What is real

| Component | Status |
|---|---|
| Session lifecycle (`requested → claimed → active → released`) | Real — persisted in PostgreSQL |
| WebSocket command flow (operator → backend → vehicle) | Real — live WS messages |
| WebSocket sensor flow (vehicle → backend → operator) | Real — live WS messages |
| In-memory connection manager | Real — functional, single-process |
| Frontend control panel with command buttons | Real — browser WebSocket connection |
| `last_command` / `last_sensor_payload` stored in DB | Real — updated on each message |
| Backend tests for HTTP session lifecycle | Real — 15 test cases |

---

## What is mocked

| Component | Status |
|---|---|
| Physical vehicle | Mocked by `scripts/mock_vehicle_client.py` |
| Camera / video feed | Text label only (`"obstacle_ahead"`, `"clear_path"`, etc.) |
| Real sensor hardware | All values randomly generated |
| Operator authentication | `operator_id` is a free string, no auth |

---

## How to run the demo

### 1. Apply the migration

```bash
# Inside the backend container or with DATABASE_URL set
docker compose exec backend alembic upgrade head
```

### 2. Seed vehicles (if not already done)

```bash
docker compose exec backend python seed.py
```

### 3. Start the full stack

```bash
docker compose up
```

### 4. Open the dashboard

Navigate to http://localhost:5173 and scroll to the **Teleoperation** panel at the bottom.

### 5. Request a session

- Select a vehicle (e.g. `v-01`) in the dropdown.
- Optionally add a reason (e.g. "obstacle detected").
- Click **Request Session**.

### 6. Claim the session

Click **Claim** next to the newly created session.
Status changes to `claimed`. The session is now assigned to an operator but the live
WebSocket command channel is not yet open.

### 7. Run the mock vehicle client

```bash
# Install websockets if needed
pip install websockets==13.1

# Run the mock client for vehicle v-01
python scripts/mock_vehicle_client.py --vehicle-id v-01
```

The client connects, starts sending sensor updates every second, and prints each
command it receives.

### 8. Connect the operator WebSocket

Click **Connect** in the dashboard panel (appears when status is `claimed` or `active`).
The backend marks the session `active` and the WS status badge changes to `connected`.
The sensor feed starts displaying live data from the mock client.

### 9. Send commands

Click **Forward**, **Left**, **Right**, **Backward**, or **Stop**.
The mock vehicle client prints the received command and immediately echoes it back
in the next sensor update.

### 10. Release the session

Click **Release** in the dashboard.
Status changes to `released`. The WebSocket disconnects automatically.

---

## How this would evolve in production

### Video / audio
Replace the text `camera_frame_label` with a WebRTC `RTCPeerConnection`.
The backend provides a signalling endpoint; STUN/TURN handles NAT traversal.
`aiortc` (Python) or a dedicated media server (mediasoup, Janus) handles the
server-side media plane.

### Command acknowledgements
Each command should carry a sequence number. The vehicle ACKs every command;
the operator UI shows pending / acknowledged / rejected state per command.
A deadman switch (safety timeout) stops the vehicle if no command arrives within
N seconds.

### Operator authentication and authorization
`operator_id` should be a verified identity (JWT or session token).
Only one operator may hold a session at a time; the backend enforces exclusivity.
An audit log of every command with operator identity, timestamp, and vehicle response
is retained for incident review.

### Reconnect and fail-safe stop
If the operator WebSocket drops, the backend automatically sends a `stop` command
to the vehicle and marks the session `failed`. The vehicle firmware has a local
watchdog that stops autonomously if it loses the WebSocket connection for > N seconds.

### Horizontal scaling
The in-memory connection manager is single-process. With multiple backend replicas,
an operator and its vehicle client could land on different instances.
A Redis Pub/Sub channel (or a lightweight message broker) replaces the in-process
dict so that messages route correctly regardless of which replica each client is
connected to.

### Latency and reliability
Operator commands require low latency. Consider a dedicated WebSocket gateway
(separate from the REST API) deployed geographically close to operators and vehicles.
QoS monitoring should track round-trip command latency and alert if it exceeds a
safety threshold.
