# Phase 2 IoT Hardware Specification

## Sensor Node (per junction)

| Component | Model | Specification |
|-----------|-------|---------------|
| Microcontroller | ESP32-S3 | 240 MHz, WiFi + BLE, 8MB Flash |
| Radio | SX1276 LoRa | 915 MHz (Cameroon), 20 km range |
| Pressure Sensor | 4-20mA / 0-10 bar | ±0.25% accuracy |
| Power | Solar + LiPo | 10W panel, 3.7V 10Ah battery |
| Enclosure | IP67 | Waterproof, UV-resistant |

## Communication Stack

```
Sensor Node (ESP32 + LoRa)
    ↓ LoRa 915MHz
LoRa Gateway (per district)
    ↓ 4G/WiFi
MQTT Broker (Mosquitto)
    ↓ MQTT subscribe
Maayan Backend (MQTT adapter)
    ↓ Same as simulation data
Dashboard (unchanged)
```

## MQTT Topic Structure

```
maayan/sensors/{node_id}/pressure
maayan/sensors/{node_id}/status
maayan/sensors/{node_id}/battery
maayan/gateway/{gateway_id}/status
```

## Deployment Plan

- Phase 2A: 3 pilot nodes (Akwa, Makepe, Bonaberi)
- Phase 2B: Full 12-node deployment
- Phase 2C: Secondary network (24+ nodes)
