"""
SQLAlchemy ORM models for the Maayan water leak detection system.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class LeakEvent(Base):
    """Stores detected leak events."""
    __tablename__ = "leak_events"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    location = Column(String(100), nullable=False)
    node_id = Column(String(20), nullable=True)
    pipe_id = Column(String(20), nullable=True)
    severity = Column(String(20), nullable=False)  # low, medium, high, burst
    probability = Column(Float, nullable=False)
    pressure_drop = Column(Float, nullable=True)
    estimated_flow_loss = Column(Float, nullable=True)  # L/s
    scenario = Column(String(50), nullable=True)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    ai_report = Column(Text, nullable=True)
    affected_nodes = Column(JSON, nullable=True)


class PressureReading(Base):
    """Time-series pressure data from sensors/simulation."""
    __tablename__ = "pressure_readings"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    node_id = Column(String(20), nullable=False, index=True)
    pressure = Column(Float, nullable=False)
    head = Column(Float, nullable=True)
    demand = Column(Float, nullable=True)
    flow = Column(Float, nullable=True)
    scenario = Column(String(50), nullable=True)
    is_anomaly = Column(Boolean, default=False)


class NetworkState(Base):
    """Snapshot of full network state."""
    __tablename__ = "network_states"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    scenario = Column(String(50), nullable=False)
    nodes_data = Column(JSON, nullable=False)
    pipes_data = Column(JSON, nullable=False)
    system_health = Column(Float, nullable=True)
    total_demand = Column(Float, nullable=True)
    total_leakage = Column(Float, nullable=True)


class IoTNode(Base):
    """IoT sensor node registry (Phase 2 hardware)."""
    __tablename__ = "iot_nodes"

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=True)
    location_name = Column(String(200), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    device_type = Column(String(50), default="simulated")  # simulated, esp32, lora
    battery_level = Column(Float, nullable=True)
    rssi = Column(Float, nullable=True)
    last_seen = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    firmware_version = Column(String(20), nullable=True)
