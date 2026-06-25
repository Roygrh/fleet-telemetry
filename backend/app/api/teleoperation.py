"""
Teleoperation Handoff Prototype — HTTP and WebSocket endpoints.

HTTP routes (prefix /api/teleoperation):
  POST   /sessions                          — create a session
  GET    /sessions                          — list sessions
  POST   /sessions/{session_id}/claim       — operator claims a session
  POST   /sessions/{session_id}/release     — operator releases a session

WebSocket routes (prefix /ws/teleoperation):
  /operator/{session_id}  — operator browser connects here to send commands
  /vehicle/{vehicle_id}   — mock vehicle client connects here to receive commands

Architecture note:
The connection manager is in-process memory. This is correct for a single-server
prototype. A production deployment with multiple replicas would require a shared
pub/sub channel (e.g. Redis Pub/Sub) so that operator messages reach the vehicle
client regardless of which backend instance it is connected to.
"""

import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.teleoperation import (
    OperatorCommandMessage,
    TeleoperationSessionClaim,
    TeleoperationSessionCreate,
    TeleoperationSessionResponse,
    VehicleSensorMessage,
)
from app.services import teleoperation as teleop_service

http_router = APIRouter()
ws_router = APIRouter()


# ------------------------------------------------------------------ #
# In-memory connection manager                                         #
# ------------------------------------------------------------------ #

class _ConnectionManager:
    """Tracks live operator and vehicle WebSocket connections.

    Keys:
      _operators  — session_id → (WebSocket, vehicle_id)
      _vehicles   — vehicle_id → WebSocket
      _send_locks — per-socket asyncio.Lock to serialise concurrent sends
    """

    def __init__(self) -> None:
        self._operators: dict[str, tuple[WebSocket, str]] = {}
        self._vehicles: dict[str, WebSocket] = {}
        self._locks: dict[int, asyncio.Lock] = {}

    def _lock(self, ws: WebSocket) -> asyncio.Lock:
        key = id(ws)
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    def _remove_lock(self, ws: WebSocket) -> None:
        self._locks.pop(id(ws), None)

    async def _safe_send(self, ws: WebSocket, data: dict) -> None:
        async with self._lock(ws):
            await ws.send_json(data)

    async def connect_operator(
        self, session_id: str, vehicle_id: str, ws: WebSocket
    ) -> None:
        await ws.accept()
        self._operators[session_id] = (ws, vehicle_id)

    def disconnect_operator(self, session_id: str) -> None:
        entry = self._operators.pop(session_id, None)
        if entry:
            self._remove_lock(entry[0])

    async def close_operator_session(self, session_id: str) -> None:
        """Notify the operator that the session is closed, then close the WebSocket.

        Called by the HTTP release route so that already-open operator connections
        are terminated immediately rather than waiting for the next client action.
        The vehicle WebSocket is intentionally left open — the mock vehicle may
        continue sending simulated sensor data.
        """
        entry = self._operators.pop(session_id, None)
        if not entry:
            return
        ws, _ = entry
        self._remove_lock(ws)
        try:
            await ws.send_json({"type": "session_closed", "status": "released"})
        except Exception:
            pass
        try:
            await ws.close()
        except Exception:
            pass

    async def connect_vehicle(self, vehicle_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._vehicles[vehicle_id] = ws

    def disconnect_vehicle(self, vehicle_id: str) -> None:
        ws = self._vehicles.pop(vehicle_id, None)
        if ws:
            self._remove_lock(ws)

    def is_vehicle_connected(self, vehicle_id: str) -> bool:
        return vehicle_id in self._vehicles

    async def forward_command_to_vehicle(
        self, session_id: str, command: str
    ) -> bool:
        entry = self._operators.get(session_id)
        if not entry:
            return False
        _, vehicle_id = entry
        ws = self._vehicles.get(vehicle_id)
        if not ws:
            return False
        await self._safe_send(ws, {"type": "command", "command": command, "session_id": session_id})
        return True

    async def forward_sensor_to_operator(
        self, vehicle_id: str, payload: dict
    ) -> None:
        for sid, (ws, vid) in list(self._operators.items()):
            if vid == vehicle_id:
                try:
                    await self._safe_send(ws, {"type": "sensor_update", **payload})
                except Exception:
                    pass


_manager = _ConnectionManager()


# ------------------------------------------------------------------ #
# HTTP routes                                                          #
# ------------------------------------------------------------------ #

@http_router.post("/sessions", response_model=TeleoperationSessionResponse, status_code=201)
async def create_session(
    body: TeleoperationSessionCreate,
    db: AsyncSession = Depends(get_db),
) -> TeleoperationSessionResponse:
    record = await teleop_service.create_session(db, body)
    return TeleoperationSessionResponse.model_validate(record)


@http_router.get("/sessions", response_model=list[TeleoperationSessionResponse])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
) -> list[TeleoperationSessionResponse]:
    sessions = await teleop_service.list_sessions(db)
    return [TeleoperationSessionResponse.model_validate(s) for s in sessions]


@http_router.post(
    "/sessions/{session_id}/claim", response_model=TeleoperationSessionResponse
)
async def claim_session(
    session_id: str,
    body: TeleoperationSessionClaim,
    db: AsyncSession = Depends(get_db),
) -> TeleoperationSessionResponse:
    record = await teleop_service.claim_session(db, session_id, body)
    return TeleoperationSessionResponse.model_validate(record)


@http_router.post(
    "/sessions/{session_id}/release", response_model=TeleoperationSessionResponse
)
async def release_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> TeleoperationSessionResponse:
    record = await teleop_service.release_session(db, session_id)
    # Close any live operator WebSocket immediately so the browser loses the
    # command channel without waiting for a page refresh. Vehicle WS is left open.
    await _manager.close_operator_session(session_id)
    return TeleoperationSessionResponse.model_validate(record)


# ------------------------------------------------------------------ #
# WebSocket routes                                                     #
# ------------------------------------------------------------------ #

@ws_router.websocket("/operator/{session_id}")
async def operator_ws(
    session_id: str,
    ws: WebSocket,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Operator browser connects here to send control commands.

    Messages received (JSON):
        {"command": "forward" | "backward" | "left" | "right" | "stop"}

    Messages sent (JSON):
        {"type": "sensor_update", ...VehicleSensorMessage fields}
        {"type": "status", "status": "vehicle_not_connected"}
        {"type": "error", "message": "invalid_command"}
        {"type": "session_closed", "status": "<current status>"}
    """
    session_record = await teleop_service.get_session(db, session_id)
    if session_record is None:
        await ws.close(code=4004, reason="session_not_found")
        return

    vehicle_id = session_record.vehicle_id
    await _manager.connect_operator(session_id, vehicle_id, ws)

    # Mark the session active now that the operator WebSocket is live.
    await teleop_service.activate_session(db, session_id)

    if not _manager.is_vehicle_connected(vehicle_id):
        await ws.send_json({"type": "status", "status": "vehicle_not_connected"})

    try:
        while True:
            data = await ws.receive_json()
            try:
                msg = OperatorCommandMessage(**data)
            except (ValidationError, Exception):
                await ws.send_json({"type": "error", "message": "invalid_command"})
                continue

            # Defensive guard: check the session is still active before recording
            # or forwarding. The HTTP release endpoint closes this WS via
            # close_operator_session, but a command may have arrived in the same
            # event-loop tick before the close frame was processed.
            current = await teleop_service.get_session(db, session_id)
            if current is None or current.status != "active":
                await ws.send_json(
                    {
                        "type": "session_closed",
                        "status": current.status if current else "unknown",
                    }
                )
                await ws.close()
                break

            await teleop_service.record_command(db, session_id, msg.command)

            forwarded = await _manager.forward_command_to_vehicle(session_id, msg.command)
            if not forwarded:
                await ws.send_json({"type": "status", "status": "vehicle_not_connected"})
    except WebSocketDisconnect:
        pass
    finally:
        _manager.disconnect_operator(session_id)


@ws_router.websocket("/vehicle/{vehicle_id}")
async def vehicle_ws(
    vehicle_id: str,
    ws: WebSocket,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Mock vehicle client connects here to receive commands and send sensor data.

    Messages received (JSON): VehicleSensorMessage payload from the vehicle
    Messages sent (JSON):     {"type": "command", "command": "...", "session_id": "..."}
    """
    await _manager.connect_vehicle(vehicle_id, ws)
    try:
        while True:
            data = await ws.receive_json()
            try:
                sensor = VehicleSensorMessage(**data)
            except (ValidationError, Exception):
                continue

            await teleop_service.record_sensor_payload(db, vehicle_id, data)
            await _manager.forward_sensor_to_operator(vehicle_id, sensor.model_dump())
    except WebSocketDisconnect:
        pass
    finally:
        _manager.disconnect_vehicle(vehicle_id)
