#!/usr/bin/env python3
"""
Concurrent zone counter stress test.

Sends N simultaneous POST /api/telemetry requests that all target the same
zone_entered value, then prints the expected vs actual zone entry count so you
can confirm the atomic upsert holds under concurrent load.

Usage:
    python scripts/concurrent_zone_test.py [N] [ZONE] [BASE_URL]

    N         Number of concurrent requests (default: 20)
    ZONE      Zone ID to target (default: charging_bay_2)
    BASE_URL  API base URL (default: http://localhost:8000)

Prerequisites:
    - docker compose up
    - docker compose exec backend alembic upgrade head
    - docker compose exec backend python seed.py

After the script runs, verify the count with:
    curl http://localhost:8000/api/zones/counts | python -m json.tool
"""

import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = sys.argv[3] if len(sys.argv) > 3 else "http://localhost:8000"
N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
ZONE = sys.argv[2] if len(sys.argv) > 2 else "charging_bay_2"

VEHICLES = [f"v-{i:02d}" for i in range(1, 11)]  # v-01 through v-10


def send_event(i: int) -> tuple[int, int]:
    """POST one telemetry event. Returns (request_index, http_status)."""
    payload = json.dumps({
        "vehicle_id": VEHICLES[i % len(VEHICLES)],
        "timestamp": "2026-01-01T00:00:00Z",
        "lat": 37.41,
        "lon": -122.08,
        "battery_pct": 80.0,
        "speed_mps": 1.5,
        "status": "moving",
        "error_codes": [],
        "zone_entered": ZONE,
    }).encode()

    req = urllib.request.Request(
        f"{BASE_URL}/api/telemetry",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return i, resp.status


def get_zone_count(zone_id: str) -> int | None:
    """Fetch the current entry count for zone_id from /api/zones/counts."""
    with urllib.request.urlopen(f"{BASE_URL}/api/zones/counts", timeout=10) as resp:
        data = json.loads(resp.read())
    for z in data.get("zones", []):
        if z["zone_id"] == zone_id:
            return z["entry_count"]
    return None


def main() -> None:
    print(f"Sending {N} concurrent requests → zone '{ZONE}' @ {BASE_URL}")
    print("-" * 60)

    count_before = get_zone_count(ZONE) or 0
    print(f"Zone '{ZONE}' entry count before: {count_before}")

    successes = 0
    errors = 0
    start = time.monotonic()

    with ThreadPoolExecutor(max_workers=N) as pool:
        futures = {pool.submit(send_event, i): i for i in range(N)}
        for future in as_completed(futures):
            try:
                idx, status = future.result()
                if status in (200, 202):
                    successes += 1
                else:
                    print(f"  [req {idx}] unexpected status {status}")
                    errors += 1
            except urllib.error.URLError as exc:
                errors += 1
                print(f"  [req {futures[future]}] error: {exc}")

    elapsed = time.monotonic() - start
    count_after = get_zone_count(ZONE)

    print(f"\nCompleted in {elapsed:.2f}s")
    print(f"  Successful requests : {successes}/{N}")
    print(f"  Failed requests     : {errors}/{N}")
    print(f"\nZone '{ZONE}' entry count before : {count_before}")
    print(f"Zone '{ZONE}' entry count after  : {count_after}")
    expected = count_before + successes
    print(f"Expected count               : {expected}")

    if count_after == expected:
        print("\n✓ Counts match — atomic upsert held under concurrent load.")
    else:
        delta = (count_after or 0) - expected
        print(f"\n✗ Count mismatch by {delta}.")


if __name__ == "__main__":
    main()
