"""
WebSocket manager for real-time dashboard updates.
Pushes network state + leak analysis to all connected clients every tick.
"""

import asyncio
import json
import math
import time
from typing import Set, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger


def _safe(obj: Any) -> Any:
    """Recursively convert numpy types to plain Python for JSON serialization."""
    try:
        import numpy as np
        if isinstance(obj, dict):
            return {k: _safe(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_safe(v) for v in obj]
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            f = float(obj)
            return None if (math.isnan(f) or math.isinf(f)) else f
    except ImportError:
        pass
    return obj


class ConnectionManager:
    """Manages all active WebSocket connections."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, data: Dict[str, Any]):
        """Send data to all connected clients."""
        if not self.active_connections:
            return
        message = json.dumps(data, default=str)
        dead = set()
        for ws in self.active_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.active_connections.discard(ws)

    async def send_to(self, websocket: WebSocket, data: Dict[str, Any]):
        """Send data to a specific client."""
        try:
            await websocket.send_text(json.dumps(data, default=str))
        except Exception as e:
            logger.warning(f"Failed to send to WebSocket: {e}")


manager = ConnectionManager()


async def simulation_broadcast_loop(simulator, detector, reporter, interval: float = 2.0):
    """
    Background coroutine that runs every `interval` seconds,
    executes the simulation tick, runs leak detection,
    and broadcasts results to all WebSocket clients.
    """
    logger.info(f"WebSocket broadcast loop started (interval={interval}s)")
    tick = 0

    while True:
        try:
            await asyncio.sleep(interval)

            if not manager.active_connections:
                continue

            tick += 1

            # Run simulation tick
            snap = simulator.run_simulation()
            snap_dict = simulator.to_json(snap)

            # Run leak detection
            report = detector.analyze(snap_dict)
            report_dict = detector.to_dict(report)

            # Compose broadcast payload (safe JSON types)
            payload = _safe({
                "type": "network_update",
                "tick": tick,
                "timestamp": time.time(),
                "network": snap_dict,
                "leak_analysis": report_dict,
                "system": {
                    "health": snap.system_health,
                    "scenario": snap.scenario,
                    "total_demand": snap.total_demand,
                    "total_leakage": snap.total_leakage,
                },
            })

            await manager.broadcast(payload)

        except Exception as e:
            logger.error(f"Broadcast loop error: {e}")
            await asyncio.sleep(5)
