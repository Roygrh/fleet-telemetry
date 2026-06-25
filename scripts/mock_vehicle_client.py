#!/usr/bin/env python3
"""Mock vehicle client for the Teleoperation Handoff Prototype.

Simulates the vehicle/device side of the teleoperation WebSocket channel.
Connect this script to a running backend to demo the operator control flow.

What it does:
  1. Connects to ws://localhost:8000/ws/teleoperation/vehicle/{vehicle_id}
  2. Sends a simulated sensor update once per second.
  3. Prints every command received from an operator.
  4. Sends an immediate sensor update after each command to echo it back.

What is mocked:
  - All sensor values are randomly generated — no real hardware.
  - Camera frames are text labels, not actual video.
  - Speed and obstacle readings are plausible but fictional.

Usage:
    # Install dependency if needed:
    #   pip install websockets
    python scripts/mock_vehicle_client.py --vehicle-id v-01
    python scripts/mock_vehicle_client.py --vehicle-id v-03 --url ws://localhost:8000

Dependency: websockets>=12.0 (pip install websockets)
"""

import argparse
import asyncio
import json
import random
import sys

try:
    import websockets
except ImportError:
    print("ERROR: 'websockets' package not installed. Run: pip install websockets")
    sys.exit(1)

CAMERA_LABELS = [
    "clear_path",
    "obstacle_ahead",
    "turning_left",
    "turning_right",
    "reversing",
    "pedestrian_detected",
]

CONNECTION_QUALITIES = ["excellent", "good", "fair"]


def _sensor_payload(vehicle_id: str, last_command: str | None) -> dict:
    return {
        "vehicle_id": vehicle_id,
        "mode": "teleoperation",
        "speed_mps": round(random.uniform(0.0, 3.5), 2),
        "battery_pct": round(random.uniform(40.0, 95.0), 1),
        "obstacle_distance_m": round(random.uniform(0.5, 12.0), 2),
        "connection_quality": random.choice(CONNECTION_QUALITIES),
        "camera_frame_label": random.choice(CAMERA_LABELS),
        "last_command_echo": last_command or "none",
    }


async def run(vehicle_id: str, backend_url: str) -> None:
    url = f"{backend_url}/ws/teleoperation/vehicle/{vehicle_id}"
    print(f"[{vehicle_id}] Connecting to {url} ...")

    send_lock = asyncio.Lock()
    last_command: list[str | None] = [None]  # mutable cell for closure

    async with websockets.connect(url) as ws:
        print(f"[{vehicle_id}] Connected. Sending sensor updates every 1 s. Ctrl+C to stop.\n")

        async def sensor_loop() -> None:
            while True:
                payload = _sensor_payload(vehicle_id, last_command[0])
                async with send_lock:
                    await ws.send(json.dumps(payload))
                print(
                    f"[{vehicle_id}] sensor | speed={payload['speed_mps']} m/s "
                    f"battery={payload['battery_pct']}% "
                    f"obstacle={payload['obstacle_distance_m']} m "
                    f"camera={payload['camera_frame_label']}"
                )
                await asyncio.sleep(1.0)

        sensor_task = asyncio.create_task(sensor_loop())

        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if msg.get("type") == "command":
                    cmd = msg.get("command", "?")
                    sid = msg.get("session_id", "?")
                    last_command[0] = cmd
                    print(f"\n[{vehicle_id}] COMMAND RECEIVED: {cmd!r}  (session={sid[:8]}…)")

                    # Immediate acknowledgement sensor update
                    payload = _sensor_payload(vehicle_id, cmd)
                    async with send_lock:
                        await ws.send(json.dumps(payload))
        except websockets.exceptions.ConnectionClosedOK:
            print(f"\n[{vehicle_id}] Connection closed by server.")
        except websockets.exceptions.ConnectionClosedError as exc:
            print(f"\n[{vehicle_id}] Connection error: {exc}")
        finally:
            sensor_task.cancel()
            try:
                await sensor_task
            except asyncio.CancelledError:
                pass

    print(f"[{vehicle_id}] Disconnected.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mock vehicle client for teleoperation demo")
    parser.add_argument("--vehicle-id", default="v-01", help="Vehicle ID (e.g. v-01 through v-50)")
    parser.add_argument("--url", default="ws://localhost:8000", help="Backend WebSocket base URL")
    args = parser.parse_args()

    try:
        asyncio.run(run(args.vehicle_id, args.url))
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
