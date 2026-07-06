# Maayan — Intelligent Water Leak Detection System

> **Smart Water Infrastructure** · MVP v1.0 · © 2026

A real-time intelligent water network monitoring and leak detection platform for municipal water utility operators, powered by EPANET hydraulic simulation, Machine Learning, and LLM-powered analysis.

---

## Screenshots

| Dashboard | Live Network | AI Report |
|-----------|-------------|-----------|
| *Command center with KPI metrics* | *Digital twin with leak visualization* | *GPT-powered hydraulic report* |

*(Run the application to see live screenshots)*

---

## Live Data — What's Real vs. What Needs a Resource From You

This MVP runs on **genuine EPANET 2.2 hydraulics**, not mock/random numbers. Every pressure, flow, and head value comes from an actual solve of the compiled EPANET toolkit (via WNTR) against a real `.inp` network file. Nothing is invented client-side. The dashboard header always shows a badge — **"Real EPANET 2.2"** (cyan) or **"Synthetic Fallback"** (amber) — so it's never ambiguous which mode produced the data.

### Two simulated municipalities, switchable live

Two independent EPANET networks ship out of the box, selectable from the dashboard header or Settings page (`POST /api/networks/select {"city": "bafoussam"}`):

| City | File | Notes |
|---|---|---|
| Douala (Littoral Region) | `simulation/douala_network.inp` | Coastal network, elevations 36–55m |
| Bafoussam (West Region, Mifi Department) | `simulation/bafoussam_network.inp` | Highland-plateau network, elevations ~1500m, real Bafoussam quarter names (Tamdja, Kamkop, Djeleng, Tougang, Famla, Banengo, Ndiengdam, Kouogouo, Nylon, Zone Industrielle, Kaptchou, Kouekong) |

**Edit either `.inp` file directly in EPANET Desktop and save — your changes (pipe diameters, node elevations, positions, demands, roughness, etc.) reflect on the live dashboard within one simulation tick (~2s), no backend restart required.** The backend watches the active file's modification time every tick and hot-reloads it automatically. This only applies to a locally-running backend reading from your local filesystem — a Railway/cloud deployment serves its own uploaded copy of the file and won't see edits made on your machine.

| Layer | Status out of the box | What it needs from you |
|---|---|---|
| **Hydraulic simulation** (pressures, flows, heads) | ✅ **Fully live.** Real EPANET 2.2 solve every 2s via WNTR, using the bundled `.inp` file. Diurnal variation comes from EPANET's own hourly demand pattern at the real wall-clock time-of-day — not a fake sine wave. | Nothing — WNTR is open source (PyPI, `pip install wntr`) and already installed. No API key, no GitHub access, no account needed. |
| **Leak detection** (statistical + ML) | ✅ **Fully live.** Thresholds and the ML training set (600 samples in `data/training/`) are generated from real EPANET solves across randomized leak locations/severities — not hand-typed formulas. | Nothing. Retrains automatically on first run if `data/models/*.joblib` is missing (~30–120s). |
| **LLM report generation** (human-readable leak explanations, EN/FR) | ✅ **Fully live** via Groq's free tier (Llama 3.3 70B). | A **Groq API key** (free, no payment method required — https://console.groq.com/keys). Add it to `.env` as `GROQ_API_KEY=gsk_...`. `backend/ai/llm_reporter.py` also supports `OPENAI_API_KEY` as a paid alternative/fallback, and degrades to a rule-based template if neither is set. |
| **Physical IoT sensors** (Phase 2 — ESP32 + LoRa) | 🔲 **Not applicable yet — by design.** Per the MVP scope, EPANET *is* the virtual sensor network. | Physical hardware (ESP32 + pressure transducer + LoRa module per node) and a LoRaWAN gateway/MQTT broker. See [Phase 2: Real IoT Hardware](#phase-2-real-iot-hardware) below — no separate code repo is required, this repo already contains the ingestion hook. |

**What you do NOT need:** any external GitHub repository, EPANET desktop license (WNTR ships the toolkit), a database service (SQLite works out of the box), or a paid hosting plan to run this locally.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        MAAYAN SYSTEM                            │
│                                                                 │
│  EPANET 2.2 / WNTR                                              │
│  (Douala Network Simulation)                                    │
│          ↓                                                      │
│  Python FastAPI Backend                                         │
│  ├── Simulation Engine (epanet/simulator.py)                    │
│  ├── Statistical Detector (ai/leak_detector.py)                 │
│  ├── ML Models: Isolation Forest + Random Forest                │
│  ├── LLM Reporter: OpenAI GPT-4o-mini                          │
│  └── WebSocket Broadcaster (real-time feed)                     │
│          ↓ WebSocket / REST API                                 │
│  React + TypeScript Frontend                                    │
│  ├── Dashboard (KPIs, alerts, charts)                           │
│  ├── Live Network (SVG digital twin)                            │
│  ├── Pressure Analytics (Recharts)                              │
│  ├── AI Report (markdown renderer)                              │
│  ├── Event History (timeline)                                   │
│  └── IoT Node Registry (Phase 2 ready)                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Option 1: Docker (recommended)

```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY (free — fallback template reports work without it)

docker-compose up
```

- Frontend: http://localhost:3000  
- Backend API: http://localhost:8000  
- API Docs: http://localhost:8000/docs

### Option 2: Local development

**Backend:**
```bash
# Create Python virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env

# Start backend
python backend/app.py
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

- Frontend: http://localhost:5173  
- Backend: http://localhost:8000

---

## Project Structure

```
MAAYAN/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── docker-compose.yml           # Docker orchestration
├── .env.example                 # Environment variables template
├── Dockerfile.backend           # Python backend container
│
├── backend/
│   ├── app.py                   # FastAPI main application + WebSocket
│   ├── api/
│   │   ├── routes.py            # REST API endpoints
│   │   └── websocket.py         # Real-time broadcast loop
│   ├── epanet/
│   │   └── simulator.py         # EPANET/WNTR simulation engine
│   ├── ai/
│   │   ├── leak_detector.py     # Statistical + ML leak detection
│   │   ├── llm_reporter.py      # OpenAI LLM report generator
│   │   └── training_data_generator.py  # Synthetic training data
│   └── database/
│       ├── models.py            # SQLAlchemy ORM models
│       └── connection.py        # DB session management
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Root app + routing
│   │   ├── components/
│   │   │   ├── Sidebar.tsx      # Navigation sidebar
│   │   │   ├── Header.tsx       # Top bar + scenario selector
│   │   │   ├── NetworkDiagram.tsx  # SVG digital twin
│   │   │   ├── LeakAlert.tsx    # Alert component
│   │   │   └── ui/              # Reusable UI components
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx   # Main command center
│   │   │   ├── NetworkPage.tsx     # Full-screen network view
│   │   │   ├── PressurePage.tsx    # Charts & analytics
│   │   │   ├── ReportPage.tsx      # AI report generator
│   │   │   ├── HistoryPage.tsx     # Event timeline
│   │   │   ├── IoTPage.tsx         # Sensor node registry
│   │   │   └── SettingsPage.tsx    # Configuration
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts     # Real-time WS connection
│   │   │   └── useApi.ts           # REST API hooks
│   │   ├── types/index.ts          # TypeScript definitions
│   │   └── utils/index.ts          # Utility functions
│   └── package.json
│
├── simulation/
│   ├── douala_network.inp       # EPANET network definition — Douala
│   ├── bafoussam_network.inp    # EPANET network definition — Bafoussam
│   └── scenarios/               # Scenario configuration files
│
└── data/
    ├── training/                # Generated ML training datasets
    └── models/                  # Trained ML model files (.joblib)
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/network` | Full network state (nodes + pipes) |
| GET | `/api/network/state` | Alias for /api/network |
| GET | `/api/nodes` | All node states |
| GET | `/api/nodes/{id}` | Single node detail |
| GET | `/api/pressures` | Current pressure readings |
| GET | `/api/leaks` | Run leak detection analysis |
| GET | `/api/leaks/latest` | Last detection result |
| POST | `/api/scenario` | Change simulation scenario |
| GET | `/api/networks` | List available city networks + active one |
| POST | `/api/networks/select` | Switch active city network (`{"city": "bafoussam"}`) |
| GET | `/api/report?language=en` | Generate AI report (GET) |
| POST | `/api/report` | Generate AI report (POST with context) |
| GET | `/api/history` | Event history |
| DELETE | `/api/history` | Clear history |
| GET | `/api/status` | System status |
| GET | `/api/iot/nodes` | IoT sensor node registry |
| GET | `/api/iot/status` | IoT ingest connection status |
| POST | `/api/iot/telemetry` | Ingest live sensor reading (Phase 2) |
| WS | `/ws` | Real-time WebSocket feed |

### Example Requests

```bash
# Change to medium leak scenario
curl -X POST http://localhost:8000/api/scenario \
  -H "Content-Type: application/json" \
  -d '{"scenario": "medium"}'

# Get current network state
curl http://localhost:8000/api/network

# Run leak detection
curl http://localhost:8000/api/leaks

# Generate English report
curl http://localhost:8000/api/report?language=en

# Generate French report
curl -X POST http://localhost:8000/api/report \
  -H "Content-Type: application/json" \
  -d '{"language": "fr", "context": "Équipe terrain alertée"}'
```

---

## Simulation Scenarios

| Scenario | Description | Leak Node | Flow Loss | Status |
|----------|-------------|-----------|-----------|--------|
| `normal` | Baseline operation | None | 0 L/s | ✅ Green |
| `small` | Minor leak at Makepe | J7 | 1.5 L/s | ⚠️ Yellow |
| `medium` | Significant leak | J7 | 4.5 L/s | 🟠 Orange |
| `burst` | Full pipe burst | J7/P7 | 12 L/s | 🔴 Red |

Switch scenarios via:
- UI header dropdown
- `POST /api/scenario {"scenario": "medium"}`
- WebSocket message `{"type": "set_scenario", "scenario": "burst"}`

---

## Machine Learning

The system uses three ML models:

1. **Isolation Forest** — Unsupervised anomaly detection on pressure vectors
2. **Random Forest Regressor** — Leak localization (which node is affected)
3. **Gradient Boosting Classifier** — Severity classification (normal/low/medium/burst)

Models are automatically trained from 600+ **real EPANET hydraulic solves** (randomized leak location + severity, actual solver output — not hand-tuned formulas) on first startup. Training data is saved to `data/training/`.

### Retrain models manually:
```bash
python -m backend.ai.training_data_generator
```

---

## LLM Integration

The LLM module (`backend/ai/llm_reporter.py`) generates professional hydraulic engineering reports using, in order of priority:

1. **Groq** (free tier, `llama-3.3-70b-versatile`) — used if `GROQ_API_KEY` is set
2. **OpenAI** (`gpt-4o-mini`, paid) — used if no Groq key but `OPENAI_API_KEY` is set
3. **Rule-based template** — used automatically if neither key is configured, or if the live API call fails for any reason

**The LLM does NOT detect leaks — it explains them.**

- Get a free Groq key at https://console.groq.com/keys (no payment method required) and set `GROQ_API_KEY` in `.env`
- Reports available in English and French
- The active provider is returned in the API response (`provider: "groq" | "openai" | "template"`) and shown in the AI Report page footer

---

## Phase 2: Real IoT Hardware

The system is designed for seamless Phase 2 hardware integration:

```
Phase 1 (Current):          Phase 2 (Future):
EPANET 2.2 hydraulic solve  →   ESP32 + LoRa Nodes
Virtual pressure sensors    →   Real pressure transducers
WebSocket broadcast (2s)    →   MQTT pub/sub ingestion
Simulated battery           →   Real battery monitoring
```

No frontend changes required — the IoT page and data format are already designed for real hardware.

```
Hardware per node:
- ESP32-S3 microcontroller
- LoRa SX1276 (915 MHz for Cameroon)
- Pressure transducer (0–10 bar)
- Solar panel + LiPo battery
- Waterproof enclosure (IP67)
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | (empty) | Groq API key for LLM reports (free tier — tried first) |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq-hosted model to use |
| `OPENAI_API_KEY` | (empty) | OpenAI API key for LLM reports (paid fallback if no Groq key) |
| `OPENAI_MODEL` | `gpt-4o-mini` | GPT model to use |
| `DATABASE_URL` | `sqlite:///./maayan.db` | Database connection string |
| `DEFAULT_CITY` | `douala` | Which simulated network loads at startup (`douala` or `bafoussam`); switchable live afterwards via `/api/networks/select` |
| `SIMULATION_INTERVAL_SECONDS` | `2.0` | WebSocket broadcast interval |
| `CORS_ORIGINS` | `localhost:3000,localhost:5173` | Allowed CORS origins |
| `APP_PORT` | `8000` | Backend port |
| `DEBUG` | `true` | Enable debug mode |
| `SENSOR_NOISE_STD_BAR` | `0.0` | Optional simulated transducer noise (bar) layered on top of real EPANET output, to emulate imperfect physical sensors. `0.0` = pure solver output, no randomness. |

---

## Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Tailwind CSS, Framer Motion |
| Charts | Recharts |
| Network Viz | Custom SVG Digital Twin |
| Backend | Python 3.11, FastAPI, Uvicorn |
| Real-time | WebSocket (native) |
| Simulation | WNTR + EPANET 2.2 |
| ML | Scikit-Learn (Isolation Forest, RF, GB) |
| LLM | Groq (Llama 3.3 70B, free tier) with OpenAI GPT-4o-mini fallback |
| Database | SQLite (dev) / PostgreSQL (prod) |
| ORM | SQLAlchemy 2.0 |
| Container | Docker + Docker Compose |

---

## Roadmap

### Phase 1 (Current — MVP)
- [x] EPANET hydraulic simulation
- [x] 4 leak scenarios
- [x] Statistical + ML detection
- [x] LLM report generation (EN/FR)
- [x] Real-time WebSocket dashboard
- [x] Digital twin network visualization
- [x] Event history

### Phase 2 (Hardware)
- [ ] ESP32 + LoRa node deployment
- [ ] MQTT broker integration
- [ ] GPS node location
- [ ] Mobile operator app
- [ ] SMS/email alerts

### Phase 3 (Scale)
- [ ] PostgreSQL + TimescaleDB
- [x] Multi-city support (Douala + Bafoussam, live-switchable, live-editable in EPANET Desktop)
- [ ] Predictive maintenance AI
- [ ] GIS map integration
- [ ] SCADA system integration

---

## License

Proprietary — Maayan Water Intelligence

---

*Developed with EPANET, FastAPI, React, Groq, and OpenAI*
