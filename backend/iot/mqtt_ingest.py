"""
Optional MQTT subscriber for Phase 2 IoT nodes.

When MQTT_ENABLED=true the backend connects to the configured broker and
listens on the topic tree documented in docs/hardware.md:

  maayan/sensors/{node_id}/pressure   → pressure (bar), plain float or JSON
  maayan/sensors/{node_id}/battery      → battery %, plain float or JSON
  maayan/sensors/{node_id}/status       → JSON with rssi, firmware, gps, etc.

Incoming readings are written to the shared TelemetryRegistry and become
visible on the dashboard within the next WebSocket tick (~2s).

Uses paho-mqtt in a background thread so it does not block the FastAPI
event loop. If paho-mqtt is not installed or the broker is unreachable,
the HTTP ingest endpoint (POST /api/iot/telemetry) still works.
"""

from __future__ import annotations

import json
import os
import re
import threading
from typing import Optional

from loguru import logger

from backend.iot.telemetry import registry

try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False

_TOPIC_RE = re.compile(
    r"^maayan/sensors/(?P<node_id>[A-Za-z0-9_-]+)/(?P<metric>pressure|battery|status)$"
)

_client: Optional["mqtt.Client"] = None
_thread: Optional[threading.Thread] = None


def _parse_payload(payload: bytes) -> dict:
    text = payload.decode("utf-8", errors="replace").strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    try:
        return {"value": float(text)}
    except ValueError:
        return {"raw": text}


def _on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0 or str(reason_code) == "Success":
        registry.mqtt_connected = True
        registry.mqtt_last_error = None
        topic = os.getenv("MQTT_TOPIC_PREFIX", "maayan/sensors") + "/#"
        client.subscribe(topic)
        logger.info(f"MQTT connected — subscribed to {topic}")
    else:
        registry.mqtt_connected = False
        registry.mqtt_last_error = str(reason_code)
        logger.warning(f"MQTT connect failed: {reason_code}")


def _on_disconnect(client, userdata, flags, reason_code, properties=None):
    registry.mqtt_connected = False
    logger.warning(f"MQTT disconnected: {reason_code}")


def _on_message(client, userdata, msg):
    match = _TOPIC_RE.match(msg.topic)
    if not match:
        return

    node_id = match.group("node_id").upper()
    metric = match.group("metric")
    data = _parse_payload(msg.payload)
    value = data.get("value") or data.get(metric)

    existing = registry.get(node_id)
    pressure = existing.pressure if existing else 0.0
    battery = existing.battery_level if existing else None
    rssi = existing.rssi if existing else None
    lat = existing.latitude if existing else None
    lon = existing.longitude if existing else None
    firmware = existing.firmware_version if existing else None
    device_type = existing.device_type if existing else "lora"

    if metric == "pressure" and value is not None:
        pressure = float(value)
    elif metric == "battery" and value is not None:
        battery = float(value)
    elif metric == "status":
        if "pressure" in data:
            pressure = float(data["pressure"])
        if "battery_level" in data:
            battery = float(data["battery_level"])
        if "rssi" in data:
            rssi = float(data["rssi"])
        if "latitude" in data:
            lat = data.get("latitude")
        if "longitude" in data:
            lon = data.get("longitude")
        if "firmware_version" in data:
            firmware = data.get("firmware_version")
        if "device_type" in data:
            device_type = data.get("device_type", device_type)

    if metric == "pressure" or (metric == "status" and "pressure" in data):
        registry.ingest(
            node_id,
            pressure,
            device_type=device_type,
            battery_level=battery,
            rssi=rssi,
            latitude=lat,
            longitude=lon,
            firmware_version=firmware,
        )
        logger.debug(f"MQTT telemetry: {node_id} pressure={pressure:.3f} bar")


def start_mqtt_ingest() -> bool:
    """Start the MQTT background subscriber. Returns True if started."""
    global _client, _thread

    if not PAHO_AVAILABLE:
        logger.warning("paho-mqtt not installed — MQTT ingest disabled (HTTP ingest still available)")
        return False

    if os.getenv("MQTT_ENABLED", "false").lower() != "true":
        logger.info("MQTT ingest disabled (set MQTT_ENABLED=true to enable)")
        return False

    host = os.getenv("MQTT_BROKER_HOST", "localhost")
    port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    user = os.getenv("MQTT_BROKER_USER", "")
    password = os.getenv("MQTT_BROKER_PASSWORD", "")

    if _thread and _thread.is_alive():
        return True

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="maayan-backend")
    if user:
        client.username_pw_set(user, password or None)
    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect
    client.on_message = _on_message

    def _run():
        try:
            client.connect(host, port, keepalive=60)
            client.loop_forever()
        except Exception as e:
            registry.mqtt_connected = False
            registry.mqtt_last_error = str(e)
            logger.error(f"MQTT ingest error: {e}")

    _client = client
    _thread = threading.Thread(target=_run, name="mqtt-ingest", daemon=True)
    _thread.start()
    logger.info(f"MQTT ingest thread started → {host}:{port}")
    return True


def stop_mqtt_ingest():
    global _client, _thread
    if _client:
        try:
            _client.disconnect()
        except Exception:
            pass
    _client = None
    _thread = None
    registry.mqtt_connected = False
