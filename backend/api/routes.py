"""
FastAPI REST API routes for Maayan.
All simulation, leak detection, and reporting endpoints.
"""

import time
import json
import math
import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from loguru import logger

from backend.iot.telemetry import registry as iot_registry


def _safe_json(obj: Any) -> Any:
    """Recursively convert numpy/non-serializable types to plain Python types."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _safe_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_json(v) for v in obj]
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj

# Import shared state (set by app.py at startup)
_simulator = None
_detector = None
_reporter = None
_history: List[Dict] = []


def set_services(simulator, detector, reporter):
    """Inject service singletons from app startup."""
    global _simulator, _detector, _reporter
    _simulator = simulator
    _detector = detector
    _reporter = reporter


router = APIRouter(prefix="/api", tags=["maayan"])


# ── Request / Response Models ──────────────────────────────────────────────────

class ScenarioRequest(BaseModel):
    scenario: str  # normal | small | medium | burst

class NetworkSelectRequest(BaseModel):
    city: str  # douala | bafoussam

class ReportRequest(BaseModel):
    language: str = "en"   # en | fr
    context: Optional[str] = None

class ScenarioResponse(BaseModel):
    success: bool
    scenario: str
    message: str

class IoTTelemetryRequest(BaseModel):
    """Payload from an ESP32/LoRa gateway or MQTT bridge."""
    node_id: str
    pressure: float = Field(..., description="Pressure reading in bar")
    device_type: str = "esp32"
    battery_level: Optional[float] = None
    rssi: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    firmware_version: Optional[str] = None
    status: str = "normal"


def _verify_iot_ingest_key(x_maayan_key: Optional[str] = Header(None)):
    """Optional API key guard for the telemetry ingest endpoint."""
    expected = os.getenv("IOT_INGEST_API_KEY", "")
    if expected and x_maayan_key != expected:
        raise HTTPException(401, "Invalid or missing X-Maayan-Key header")


# ── Network Endpoints ──────────────────────────────────────────────────────────

@router.get("/network")
async def get_network():
    """Return the full network topology (nodes + pipes)."""
    if _simulator is None:
        raise HTTPException(503, "Simulator not ready")
    snap = _simulator.run_simulation()
    return JSONResponse(content=_safe_json(_simulator.to_json(snap)))


@router.get("/network/state")
async def get_network_state():
    """Current snapshot — same as /network, aliased for clarity."""
    return await get_network()


@router.get("/nodes")
async def get_nodes():
    """Return all node states."""
    if _simulator is None:
        raise HTTPException(503, "Simulator not ready")
    from dataclasses import asdict
    snap = _simulator.run_simulation()
    return JSONResponse(content=_safe_json({"nodes": [asdict(n) for n in snap.nodes]}))


@router.get("/nodes/{node_id}")
async def get_node(node_id: str):
    """Return detailed state for a single node."""
    if _simulator is None:
        raise HTTPException(503, "Simulator not ready")
    info = _simulator.get_node_info(node_id.upper())
    if info is None:
        raise HTTPException(404, f"Node {node_id} not found")
    return info


@router.get("/pressures")
async def get_pressures():
    """Return current pressure readings for all nodes."""
    if _simulator is None:
        raise HTTPException(503, "Simulator not ready")
    snap = _simulator.run_simulation()
    return JSONResponse(content=_safe_json({
        "timestamp": snap.timestamp,
        "scenario": snap.scenario,
        "readings": [
            {
                "node_id": n.id,
                "name": n.name,
                "pressure": n.pressure,
                "baseline": n.pressure_baseline,
                "pressure_drop": n.pressure_drop,
                "is_anomaly": bool(n.is_anomaly),
                "status": n.status,
            }
            for n in snap.nodes
        ],
    }))


@router.get("/networks")
async def list_networks():
    """
    List available simulated city networks (Douala, Bafoussam...) and which
    one is currently active. Each maps to a real, independently-editable
    EPANET .inp file under simulation/ that can be opened directly in
    EPANET Desktop.
    """
    if _simulator is None:
        raise HTTPException(503, "Simulator not ready")
    from backend.epanet.simulator import NETWORKS
    return {
        "active": _simulator.city,
        "networks": [
            {"id": key, "label": cfg["label"], "inp_file": cfg["inp"]}
            for key, cfg in NETWORKS.items()
        ],
    }


@router.post("/networks/select")
async def select_network(request: NetworkSelectRequest):
    """
    Switch the active EPANET city network live. Takes effect on the next
    simulation tick — no restart required.
    """
    if _simulator is None:
        raise HTTPException(503, "Simulator not ready")
    ok = _simulator.set_network(request.city.lower())
    if not ok:
        raise HTTPException(400, f"Unknown network: {request.city}")
    return {"success": True, "active": _simulator.city}


# ── Leak Detection Endpoints ──────────────────────────────────────────────────

@router.get("/leaks")
async def get_leaks():
    """Run full leak detection analysis and return LeakReport."""
    if _simulator is None or _detector is None:
        raise HTTPException(503, "Services not ready")
    snap = _simulator.run_simulation()
    snap_dict = _simulator.to_json(snap)
    report = _detector.analyze(snap_dict)
    result = _safe_json(_detector.to_dict(report))

    # Store in history if a leak is detected
    if report.detected:
        _store_history(result)

    return JSONResponse(content=result)


@router.get("/leaks/latest")
async def get_latest_leak():
    """Return the last detected leak report."""
    if _detector is None:
        raise HTTPException(503, "Detector not ready")
    if _detector.last_report:
        return _detector.to_dict(_detector.last_report)
    return {"detected": False, "message": "No analysis run yet"}


# ── Scenario Control ──────────────────────────────────────────────────────────

@router.post("/scenario", response_model=ScenarioResponse)
async def set_scenario(request: ScenarioRequest):
    """Switch the active simulation scenario."""
    if _simulator is None:
        raise HTTPException(503, "Simulator not ready")

    valid_scenarios = ["normal", "small", "medium", "burst"]
    scenario = request.scenario.lower()

    if scenario not in valid_scenarios:
        raise HTTPException(400, f"Invalid scenario. Choose from: {valid_scenarios}")

    success = _simulator.set_scenario(scenario)
    if not success:
        raise HTTPException(500, "Failed to set scenario")

    # Zone names come from the currently active network definition (Douala,
    # Bafoussam, ...) so the description always matches the live dashboard.
    leak_zone = _simulator.network_def.NODES.get("J7", {}).get("name", "J7")
    upstream_zone = _simulator.network_def.NODES.get("J6", {}).get("name", "J6")
    scenario_descriptions = {
        "normal": "Normal network operation — all pressures baseline",
        "small":  f"Small leak at {leak_zone} (J7) — 1.5 L/s loss",
        "medium": f"Medium leak at {leak_zone} (J7) — 4.5 L/s loss",
        "burst":  f"Pipe burst between {upstream_zone}–{leak_zone} — 12 L/s loss",
    }

    return ScenarioResponse(
        success=True,
        scenario=scenario,
        message=scenario_descriptions[scenario],
    )


# ── AI Report ────────────────────────────────────────────────────────────────

@router.get("/report")
async def get_report(language: str = Query("en", regex="^(en|fr)$")):
    """Generate LLM-powered hydraulic engineering report."""
    if _simulator is None or _detector is None or _reporter is None:
        raise HTTPException(503, "Services not ready")

    snap = _simulator.run_simulation()
    snap_dict = _simulator.to_json(snap)
    leak_report = _detector.analyze(snap_dict)
    leak_dict = _detector.to_dict(leak_report)

    report_text = _reporter.generate_report(leak_dict, language=language)

    return JSONResponse(content={
        "report": report_text,
        "language": language,
        "provider": _reporter.provider or "template",
        "leak_data": _safe_json(leak_dict),
        "generated_at": datetime.utcnow().isoformat(),
    })


@router.post("/report")
async def post_report(request: ReportRequest):
    """Generate report with operator context."""
    if _simulator is None or _detector is None or _reporter is None:
        raise HTTPException(503, "Services not ready")

    snap = _simulator.run_simulation()
    snap_dict = _simulator.to_json(snap)
    leak_report = _detector.analyze(snap_dict)
    leak_dict = _detector.to_dict(leak_report)

    report_text = _reporter.generate_report(
        leak_dict,
        language=request.language,
        additional_context=request.context,
    )

    return JSONResponse(content={
        "report": report_text,
        "language": request.language,
        "provider": _reporter.provider or "template",
        "leak_data": _safe_json(leak_dict),
        "generated_at": datetime.utcnow().isoformat(),
    })


# ── History ───────────────────────────────────────────────────────────────────

@router.get("/history")
async def get_history(
    limit: int = Query(50, ge=1, le=200),
    severity: Optional[str] = Query(None),
):
    """Return timeline of detected leak events."""
    history = list(_history)

    if severity:
        history = [h for h in history if h.get("severity") == severity]

    history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return {
        "total": len(history),
        "events": history[:limit],
    }


@router.delete("/history")
async def clear_history():
    """Clear all recorded history."""
    _history.clear()
    return {"message": "History cleared"}


# ── System Status ─────────────────────────────────────────────────────────────

@router.get("/status")
async def get_status():
    """Return overall system health and metadata."""
    if _simulator is None:
        return JSONResponse(content={"status": "initializing", "ready": False})

    snap = _simulator.run_simulation()
    return JSONResponse(content=_safe_json({
        "status": "operational",
        "ready": True,
        "scenario": _simulator.current_scenario,
        "system_health": snap.system_health,
        "total_demand": snap.total_demand,
        "total_leakage": snap.total_leakage,
        "active_leaks": sum(1 for n in snap.nodes if n.status in ("leak", "burst")),
        "nodes_count": len(snap.nodes),
        "pipes_count": len(snap.pipes),
        "simulation_time": snap.simulation_time,
        "history_count": len(_history),
    }))


# ── IoT Node Registry (Phase 2 ready) ────────────────────────────────────────

@router.get("/iot/status")
async def get_iot_status():
    """Return IoT ingest connection status (MQTT + live node count)."""
    return iot_registry.status()


@router.post("/iot/telemetry")
async def ingest_iot_telemetry(
    payload: IoTTelemetryRequest,
    _: None = Depends(_verify_iot_ingest_key),
):
    """
    Accept a live pressure reading from a physical sensor node or LoRa gateway.

  Phase 2 hardware posts here (or publishes to MQTT — see docs/hardware.md).
  Fresh readings override that junction's pressure on the live dashboard
  within the next WebSocket tick (~2s).
    """
    reading = iot_registry.ingest(
        payload.node_id,
        payload.pressure,
        device_type=payload.device_type,
        battery_level=payload.battery_level,
        rssi=payload.rssi,
        latitude=payload.latitude,
        longitude=payload.longitude,
        firmware_version=payload.firmware_version,
        status=payload.status,
    )
    return {"success": True, "reading": reading.to_dict()}


@router.get("/iot/nodes")
async def get_iot_nodes():
    """Return IoT sensor node registry (Phase 2 hardware integration)."""
    if _simulator is None:
        raise HTTPException(503, "Simulator not ready")

    snap = _simulator.run_simulation()
    import random

    live = {r.node_id: r for r in iot_registry.list_fresh()}
    iot_nodes = []
    for node in snap.nodes:
        reading = live.get(node.id)
        if reading:
            iot_nodes.append({
                "node_id": node.id,
                "name": node.name,
                "device_type": reading.device_type,
                "battery_level": reading.battery_level,
                "rssi": reading.rssi,
                "pressure": reading.pressure,
                "status": reading.status,
                "last_seen": reading.to_dict()["last_seen"],
                "firmware_version": reading.firmware_version or "unknown",
                "latitude": reading.latitude,
                "longitude": reading.longitude,
                "is_live": True,
            })
        else:
            iot_nodes.append({
                "node_id": node.id,
                "name": node.name,
                "device_type": "simulated",
                "battery_level": round(random.uniform(72, 98), 1),
                "rssi": round(random.uniform(-85, -45), 0),
                "pressure": node.pressure,
                "status": node.status,
                "last_seen": datetime.utcnow().isoformat(),
                "firmware_version": "1.0.0-sim",
                "latitude": None,
                "longitude": None,
                "is_live": False,
            })

    return {
        "nodes": iot_nodes,
        "total": len(iot_nodes),
        "live_count": len(live),
        "ingest": iot_registry.status(),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _store_history(event: Dict):
    """Store a leak event in the in-memory history ring buffer."""
    event["recorded_at"] = datetime.utcnow().isoformat()
    _history.append(event)
    # Keep last 500 events
    while len(_history) > 500:
        _history.pop(0)
