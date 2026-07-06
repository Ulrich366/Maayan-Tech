"""
Maayan - Intelligent Water Leak Detection System
Main FastAPI Application Entry Point

Run with: python backend/app.py
Or:        uvicorn backend.app:app --reload
"""

import os
import sys
import asyncio
from contextlib import asynccontextmanager

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from loguru import logger

from backend.epanet.simulator import EpanetSimulator
from backend.ai.leak_detector import LeakDetectionEngine
from backend.ai.llm_reporter import LLMReporter
from backend.api.routes import router, set_services
from backend.api.websocket import manager, simulation_broadcast_loop
from backend.iot.mqtt_ingest import start_mqtt_ingest, stop_mqtt_ingest
from backend.iot.telemetry import registry as iot_registry

# ── Configuration ─────────────────────────────────────────────────────────────

APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
# Railway (and most PaaS providers) inject a dynamic $PORT the app must bind to.
# Fall back to APP_PORT / 8000 for local/Docker Compose usage where PORT isn't set.
APP_PORT = int(os.getenv("PORT", os.getenv("APP_PORT", "8000")))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
# Which simulated city network loads at startup — "douala" or "bafoussam".
# Switchable live from the dashboard afterwards via POST /api/networks/select.
DEFAULT_CITY = os.getenv("DEFAULT_CITY", "douala")
SIM_INTERVAL = float(os.getenv("SIMULATION_INTERVAL_SECONDS", "2.0"))

# ── Logging ───────────────────────────────────────────────────────────────────

os.makedirs("logs", exist_ok=True)
logger.add("logs/maayan.log", rotation="10 MB", retention="7 days", level="INFO")
logger.info("Starting Maayan Water Leak Detection System...")

# ── Service Instances ─────────────────────────────────────────────────────────

simulator = EpanetSimulator(city=DEFAULT_CITY)
detector = LeakDetectionEngine()
reporter = LLMReporter()


# ── Application Lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown logic."""
    logger.info("Maayan backend starting up...")

    # Inject services into routes
    set_services(simulator, detector, reporter)

    # Start WebSocket broadcast loop
    broadcast_task = asyncio.create_task(
        simulation_broadcast_loop(simulator, detector, reporter, interval=SIM_INTERVAL)
    )

    # Phase 2: optional MQTT subscriber for live ESP32/LoRa sensor nodes
    start_mqtt_ingest()

    logger.info(f"Server ready at http://{APP_HOST}:{APP_PORT}")
    logger.info(f"API docs: http://{APP_HOST}:{APP_PORT}/docs")

    yield  # App is running

    # Shutdown
    broadcast_task.cancel()
    stop_mqtt_ingest()
    try:
        await broadcast_task
    except asyncio.CancelledError:
        pass
    logger.info("Maayan backend shut down cleanly.")


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Maayan - Water Leak Detection System",
    description=(
        "Intelligent water network monitoring and leak detection platform "
        "for municipal water utility operators. "
        "Powered by EPANET simulation, Machine Learning, and LLM analysis."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS + ["*"],  # Relaxed for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────

app.include_router(router)


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker / load balancer."""
    return {
        "status": "healthy",
        "service": "maayan-backend",
        "version": "1.0.0",
        "scenario": simulator.current_scenario,
    }


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "Maayan Water Leak Detection API",
        "version": "1.0.0",
        "docs": "/docs",
        "websocket": "ws://localhost:8000/ws",
        "endpoints": [
            "GET  /api/network",
            "GET  /api/pressures",
            "GET  /api/leaks",
            "GET  /api/report",
            "POST /api/scenario",
            "GET  /api/networks",
            "POST /api/networks/select",
            "GET  /api/history",
            "GET  /api/nodes",
            "GET  /api/status",
            "GET  /api/iot/nodes",
            "GET  /api/iot/status",
            "POST /api/iot/telemetry",
            "WS   /ws",
        ],
    }


# ── WebSocket Endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket connection for real-time dashboard updates.
    Clients receive full network + leak analysis every 2 seconds.
    """
    await manager.connect(websocket)
    try:
        # Send initial state immediately on connect
        snap = simulator.run_simulation()
        snap_dict = iot_registry.apply_to_snapshot(simulator.to_json(snap))
        report = detector.analyze(snap_dict)

        await manager.send_to(websocket, {
            "type": "connected",
            "message": "Connected to Maayan real-time feed",
            "network": snap_dict,
            "leak_analysis": detector.to_dict(report),
            "iot": iot_registry.status(),
        })

        # Keep connection alive, handle incoming messages
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Handle client commands (e.g., scenario change via WS)
                import json as json_lib
                try:
                    msg = json_lib.loads(data)
                    if msg.get("type") == "set_scenario":
                        scenario = msg.get("scenario", "normal")
                        simulator.set_scenario(scenario)
                        await manager.send_to(websocket, {
                            "type": "scenario_changed",
                            "scenario": scenario,
                        })
                    elif msg.get("type") == "set_network":
                        city = msg.get("city", "douala")
                        ok = simulator.set_network(city)
                        await manager.send_to(websocket, {
                            "type": "network_changed",
                            "city": simulator.city,
                            "success": ok,
                        })
                except Exception:
                    pass
            except asyncio.TimeoutError:
                # Send heartbeat
                await manager.send_to(websocket, {"type": "heartbeat"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.app:app",
        host=APP_HOST,
        port=APP_PORT,
        reload=DEBUG,
        log_level="info",
    )
