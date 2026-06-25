from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import telemetry, vehicles, zones, anomalies, fleet
from app.api.teleoperation import http_router as teleop_http_router
from app.api.teleoperation import ws_router as teleop_ws_router

app = FastAPI(title="Fleet Telemetry API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(telemetry.router, prefix="/api/telemetry", tags=["telemetry"])
app.include_router(vehicles.router, prefix="/api/vehicles", tags=["vehicles"])
app.include_router(zones.router, prefix="/api/zones", tags=["zones"])
app.include_router(anomalies.router, prefix="/api/anomalies", tags=["anomalies"])
app.include_router(fleet.router, prefix="/api/fleet", tags=["fleet"])
app.include_router(teleop_http_router, prefix="/api/teleoperation", tags=["teleoperation"])
app.include_router(teleop_ws_router, prefix="/ws/teleoperation", tags=["teleoperation-ws"])


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}
