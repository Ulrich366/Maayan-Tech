"""
Live IoT telemetry registry for Phase 2 hardware integration.

Stores the latest reading from each physical sensor node (ESP32 + LoRa).
When a node has a fresh reading here, the simulation broadcast loop
overrides that junction's pressure with the real transducer value before
leak detection and dashboard push — so operators see live hardware data
the moment a node connects, without any frontend changes.

Stale readings (older than IOT_STALE_SECONDS) are ignored and the
simulation value is used instead, so a disconnected node never blocks
the dashboard.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional, Any


IOT_STALE_SECONDS = float(os.getenv("IOT_STALE_SECONDS", "120"))


@dataclass
class TelemetryReading:
    node_id: str
    pressure: float
    device_type: str = "esp32"
    battery_level: Optional[float] = None
    rssi: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    firmware_version: Optional[str] = None
    status: str = "normal"
    received_at: float = 0.0  # unix timestamp

    def is_fresh(self) -> bool:
        return (time.time() - self.received_at) <= IOT_STALE_SECONDS

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["last_seen"] = datetime.utcfromtimestamp(self.received_at).isoformat()
        d["is_live"] = self.is_fresh()
        return d


class TelemetryRegistry:
    """Thread-safe in-memory store for the latest reading per sensor node."""

    def __init__(self):
        self._readings: Dict[str, TelemetryReading] = {}
        self._lock = Lock()
        self.mqtt_connected = False
        self.mqtt_last_error: Optional[str] = None
        self.total_ingested = 0

    def ingest(
        self,
        node_id: str,
        pressure: float,
        *,
        device_type: str = "esp32",
        battery_level: Optional[float] = None,
        rssi: Optional[float] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        firmware_version: Optional[str] = None,
        status: str = "normal",
    ) -> TelemetryReading:
        node_id = node_id.upper()
        reading = TelemetryReading(
            node_id=node_id,
            pressure=float(pressure),
            device_type=device_type,
            battery_level=battery_level,
            rssi=rssi,
            latitude=latitude,
            longitude=longitude,
            firmware_version=firmware_version,
            status=status,
            received_at=time.time(),
        )
        with self._lock:
            self._readings[node_id] = reading
            self.total_ingested += 1
        return reading

    def get(self, node_id: str) -> Optional[TelemetryReading]:
        node_id = node_id.upper()
        with self._lock:
            reading = self._readings.get(node_id)
        if reading and reading.is_fresh():
            return reading
        return None

    def list_fresh(self) -> List[TelemetryReading]:
        with self._lock:
            readings = list(self._readings.values())
        return [r for r in readings if r.is_fresh()]

    def live_node_ids(self) -> List[str]:
        return [r.node_id for r in self.list_fresh()]

    def apply_to_snapshot(self, snap_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Override junction pressures in a network snapshot with fresh IoT
        readings. Recomputes pressure_drop against each node's baseline.
        """
        fresh = {r.node_id: r for r in self.list_fresh()}
        if not fresh:
            return snap_dict

        nodes = snap_dict.get("nodes", [])
        for node in nodes:
            nid = node.get("id", "")
            reading = fresh.get(nid)
            if not reading:
                continue
            baseline = node.get("pressure_baseline", reading.pressure)
            node["pressure"] = round(reading.pressure, 4)
            node["pressure_drop"] = round(max(0.0, baseline - reading.pressure), 4)
            node["is_anomaly"] = node["pressure_drop"] > 0.02

        snap_dict["iot_live_nodes"] = list(fresh.keys())
        snap_dict["iot_mode"] = "hybrid" if len(fresh) < len(nodes) else "live"
        return snap_dict

    def status(self) -> Dict[str, Any]:
        fresh = self.list_fresh()
        with self._lock:
            total_registered = len(self._readings)
        return {
            "enabled": True,
            "mqtt_connected": self.mqtt_connected,
            "mqtt_last_error": self.mqtt_last_error,
            "live_nodes": len(fresh),
            "registered_nodes": total_registered,
            "total_ingested": self.total_ingested,
            "stale_threshold_seconds": IOT_STALE_SECONDS,
            "live_node_ids": [r.node_id for r in fresh],
        }


# Singleton used across routes, MQTT ingest, and the WebSocket loop.
registry = TelemetryRegistry()
