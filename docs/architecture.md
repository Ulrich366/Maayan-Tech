# Maayan System Architecture

## Overview

Maayan is a three-tier web application with a simulation/ML backend.

```
┌──────────────────────────────────────────────────────────────────────┐
│  PRESENTATION TIER                                                    │
│  React + TypeScript + Tailwind CSS                                   │
│  ├── WebSocket client (real-time updates, 2s interval)               │
│  ├── REST API client (scenarios, reports, history)                   │
│  └── 7 pages: Dashboard, Network, Pressure, Report, History, IoT, Settings │
├──────────────────────────────────────────────────────────────────────┤
│  APPLICATION TIER                                                     │
│  FastAPI (Python 3.11)                                               │
│  ├── REST API: /api/* endpoints                                      │
│  ├── WebSocket: /ws  (broadcast loop)                                │
│  ├── CORS middleware                                                 │
│  └── Async I/O with uvicorn                                          │
├──────────────────────────────────────────────────────────────────────┤
│  SIMULATION + AI TIER                                                │
│  ├── EpanetSimulator: WNTR hydraulic engine + synthetic fallback     │
│  ├── LeakDetectionEngine:                                            │
│  │   ├── StatisticalDetector: z-score + threshold analysis           │
│  │   └── MLLeakDetector: Isolation Forest + RF + Gradient Boosting   │
│  └── LLMReporter: OpenAI GPT-4o-mini report generation              │
├──────────────────────────────────────────────────────────────────────┤
│  DATA TIER                                                           │
│  SQLite (dev) / PostgreSQL (prod)                                    │
│  ├── leak_events: detected leak records                              │
│  ├── pressure_readings: time-series data                             │
│  ├── network_states: snapshots                                       │
│  └── iot_nodes: hardware registry                                    │
└──────────────────────────────────────────────────────────────────────┘
```

## Data Flow

1. **Simulation tick** (every 2 seconds):
   - EpanetSimulator runs hydraulic model for current scenario
   - Returns NetworkSnapshot (12 nodes, 18 pipes)

2. **Leak Detection**:
   - StatisticalDetector: compares pressures to baseline, z-score analysis
   - MLLeakDetector: runs Isolation Forest on pressure vector, GB severity classification
   - Combined decision: probability, severity, location, flow loss estimate

3. **WebSocket broadcast**:
   - ConnectionManager sends to all connected dashboard clients
   - Payload: {network, leak_analysis, system}

4. **LLM Report** (on-demand):
   - LeakReport dict → OpenAI API prompt → markdown report
   - Fallback: template-based report if no API key

## Key Design Decisions

- **Dual-mode simulation**: WNTR when installed, synthetic when not — ensures demo works without heavy dependencies
- **Separation of detection and explanation**: ML detects, LLM explains — avoids hallucination in safety-critical detection
- **Phase-2 ready IoT interface**: same data schema whether from simulation or MQTT sensors
- **In-memory history ring buffer**: fast, no DB dependency for demo — extend to SQLAlchemy for production
