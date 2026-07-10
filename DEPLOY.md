# Maayan — Production Deployment (GERCAM Railway)

## Live URLs

| Service | URL |
|---------|-----|
| **Frontend (dashboard)** | https://frontend-production-0540.up.railway.app |
| **Backend (API)** | https://backend-production-357a.up.railway.app |
| **API docs** | https://backend-production-357a.up.railway.app/docs |
| **WebSocket** | `wss://backend-production-357a.up.railway.app/ws?token=<jwt>` |

**Railway project:** [Maayan-tech](https://railway.com/project/392f449e-d1b0-43a9-973e-77df345867c0)  
**GitHub:** `Ulrich366/Maayan-Tech` (branch `master`)

## Operator login

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `Maayan@2026` |

## Railway service configuration

### Backend (`Dockerfile.backend`, root `/`)

| Variable | Value |
|----------|-------|
| `CORS_ORIGINS` | `https://frontend-production-0540.up.railway.app` |
| `AUTH_ENABLED` | `true` |
| `AUTH_USERNAME` | `admin` |
| `AUTH_PASSWORD` | *(set in Railway secrets)* |
| `JWT_SECRET` | *(set in Railway secrets)* |
| `GROQ_API_KEY` | *(set in Railway secrets)* |
| `DEFAULT_CITY` | `douala` |

### Frontend (`frontend/Dockerfile`, root `frontend/`)

| Variable | Value |
|----------|-------|
| `PORT` | `3000` |
| `VITE_API_URL` | `https://backend-production-357a.up.railway.app` |
| `VITE_WS_URL` | `wss://backend-production-357a.up.railway.app` |

> Frontend rebuilds are required when `VITE_*` variables change.

## IoT telemetry (Phase 2)

```http
POST https://backend-production-357a.up.railway.app/api/iot/telemetry
X-Maayan-Key: <your IOT_INGEST_API_KEY>
Content-Type: application/json

{"node_id": "J1", "pressure": 4.2, "device_type": "esp32"}
```

## Local development against production API

Copy production overrides into `.env` or run:

```bash
# frontend/.env.production.local
VITE_API_URL=https://backend-production-357a.up.railway.app
VITE_WS_URL=wss://backend-production-357a.up.railway.app
```
