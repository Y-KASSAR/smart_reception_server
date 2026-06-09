# Smart Reception Assistant

An AI-powered hotel reception system: a Raspberry Pi 4 with a USB camera and
PIR sensor streams JPEG frames to a laptop FastAPI server, which runs person
detection (YOLOv8), face recognition (MTCNN + FaceNet 512-D), dwell-time
monitoring, alert dispatch (dashboard + email + SMS), and rule-based upsell
recommendations. A React dashboard served by the same FastAPI process gives
reception staff a live view + alert management + guest enrollment.

Senior project — AUL Computer & Communications Engineering · Youssef Kassar.

---

## Architecture

```
   ┌──────────────────────────────┐    HTTP POST /api/edge/frame    ┌────────────────────────────────────────┐
   │  Raspberry Pi 4 (8 GB)       │  ───────────────────────────▶  │  Laptop AI Server  (this repo)         │
   │  ─────────────────────────── │                                │  ──────────────────────────────────────│
   │  edge/edge_client.py         │                                │  FastAPI (uvicorn :5000)               │
   │   ├─ VideoCapture (USB cam)  │                                │   ├─ api/routes/*  (REST + WS)         │
   │   ├─ MotionDetector (PIR)    │                                │   ├─ detection/person_detector.py      │
   │   ├─ FrameStreamer           │                                │   ├─ modules/recognition (MTCNN+FaceNet)│
   │   └─ EdgeNetworkClient       │  ◀──── /ws  (live feed,        │   ├─ modules/monitoring (dwell+alerts) │
   │                              │         alerts, detections)    │   ├─ modules/upselling (8 rules)       │
   └──────────────────────────────┘                                │   ├─ modules/alerts (email+SMS+WS)     │
                                                                   │   ├─ database/ (SQLAlchemy + SQLite)   │
                                                                   │   └─ frontend/dist/ (React SPA)        │
                                                                   └────────────────────────────────────────┘
                                                                                       │
                                                                            ┌──────────┴──────────┐
                                                                            │  Browsers on LAN    │
                                                                            │  (Vite-built SPA    │
                                                                            │   served by FastAPI)│
                                                                            └─────────────────────┘
```

Per SDD §2.1 the laptop handles all heavy compute so the Pi never has to
load torch / facenet-pytorch / ultralytics — it stays a thin camera+sensor
edge node.

---

## Repository layout

```
api/                  FastAPI app + 14 route modules + Pydantic schemas
core/                 SystemController (lifespan), EventBus (pub/sub)
modules/
  recognition/        FaceRecognitionEngine (MTCNN + FaceNet 512-D, cosine match)
  monitoring/         PersonMonitor (dwell tracking + threshold events)
  upselling/          RecommendationEngine (5 rules, capped at 1.0)
  alerts/             AlertNotifier (event_bus → Alert row → email + SMS)
detection/            person_detector.py (YOLOv8 + MobileNet-SSD fallback)
database/             SQLAlchemy models + 8 repositories + WAL connection
edge/                 edge_client.py (deployed to the Pi — see RPI_DEPLOYMENT.md)
frontend/             Vite + React 18 + TypeScript + Tailwind dashboard
config/               YAML settings, structured logging, .env loading
utils/                Auth (JWT + RBAC), crypto, image, time helpers
scripts/              backup_database.py, seed_database.py, etc.
tests/                pytest suite — 158 tests passing
docs/                 SysRS, SDD, RPi deployment guide, progress reports
```

---

## Bill of materials

| Item | Notes | ~Cost (USD) |
|---|---|---|
| Raspberry Pi 4 — 8 GB | Edge device | 85 |
| microSD ≥ 32 GB (Class 10) | Pi OS + edge_client | 10 |
| USB-C 5.1 V / 3 A PSU | Official Pi PSU | 10 |
| Acer/UVC USB webcam, 1080p | Plugs into USB-3 | 30 |
| HC-SR501 PIR motion sensor | + 3 F-F jumpers | 5 |
| Ethernet cable | Reliability over Wi-Fi | 10 |
| Laptop (your own) | AI server | — |
| **Total** | | **~$150** |

Software is all open-source.

---

## Quick start (development)

> Tested with Python 3.12 and Node 24 on Windows 11. Linux / macOS work the
> same modulo path separators.

### 1 — Backend (laptop)

```powershell
# from repo root
python -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
# (Optional, for actual face recognition + person detection)
pip install torch torchvision facenet-pytorch ultralytics

copy .env.example .env
# edit .env — set at least API_KEY, JWT_SECRET_KEY, DEFAULT_ADMIN_PASSWORD

# Seed the test database (creates admin/admin123, plus services & alerts)
$env:PYTHONIOENCODING="utf-8"
python -m scripts.seed_database

python server_app.py
# Server listens on http://0.0.0.0:5000
# OpenAPI docs:  http://localhost:5000/docs
```

### 2 — Frontend dashboard

```powershell
cd frontend
npm install
npm run build         # produces frontend/dist — served automatically by FastAPI

# Or for hot-reload development with proxy → :5000
npm run dev           # opens http://localhost:5173
```

Once the backend is running and `frontend/dist` exists, the React dashboard is
available at **http://localhost:5000/**.

### 3 — Edge device (Raspberry Pi)

See [docs/RPI_DEPLOYMENT.md](docs/RPI_DEPLOYMENT.md) for the step-by-step
guide. TL;DR: flash Pi OS, wire the PIR to GPIO 17, scp `edge/edge_client.py`
to the Pi, install via systemd.

---

## Test suite

```powershell
.\venv\Scripts\python.exe -m pytest tests\ -v
# 158 passed in ~8s
```

Coverage:
- `test_api.py` — 24 tests, REST endpoints with mocked auth
- `test_database.py` — 11 tests, ORM + repository CRUD + crypto
- `test_face_recognizer.py` — 18 tests, cosine math + embedding cache + matching
- `test_new_routes.py` — 8 tests, enrollment / system / monitoring routes
- `test_person_detector.py` — 21 tests, PersonMonitor + dwell + alert events
- `test_recommendations.py` — 26 tests, all 5 scoring rules + persistence
- `test_repositories.py` — 26 tests, repository-level coverage
- `test_upselling.py` — 16 tests, upselling API integration
- `test_websocket.py` — 8 tests, WS connection + broadcast helpers

---

## API endpoints (REST)

| Group | Endpoints |
|---|---|
| Auth | `POST /api/staff/login` |
| Guests | `GET/POST/PUT/DELETE /api/guests/...` + `/vip` + `/search` + `/{id}/embed` |
| Staff | `GET/POST/PUT/DELETE /api/staff/...` (admin) |
| Alerts | `GET /api/alerts/[pending]` + `POST /{id}/acknowledge,resolve` |
| Reservations | full CRUD `/api/reservations/...` |
| Services | full CRUD `/api/services/...` (admin/manager for mutations) |
| Recommendations | `GET /api/recommendations/...` + `POST /generate/{guest_id}` |
| **Enrollment** | `POST /api/enrollment/capture` + `POST /complete` |
| **System** | `GET /api/system/status` + `GET /stats` (manager) |
| **Monitoring** | `GET /api/monitoring/status` |
| Edge ingest | `POST /api/edge/frame` (X-API-Key) + `/status` + `/heartbeat` |
| WebSocket | `/ws` (canonical) and `/api/ws/alerts` (legacy) |
| Exports | `GET /api/exports/...` |
| Health | `GET /api/health` |

Full Swagger at **http://localhost:5000/docs** when the server is running.

---

## WebSocket event types

| Event | Payload | When fired |
|---|---|---|
| `connected` | `{message, ts}` | On client connect |
| `live_feed` | `{camera_id, frame_b64, detections, ts}` | Each frame processed by `/api/edge/frame` |
| `detection_update` | `{persons, faces, tracks, ts}` | After each detection pass |
| `guest_identified` | `{guest_id, name, confidence, ts}` | Every face match above threshold |
| `recommendation_update` | `{guest_id, recommendations, ts}` | When new recs generated |
| `alert_push` | `{alert_id, alert_type, severity, title, ts}` | Every Alert created via `event_bus` |
| `heartbeat` | `{ts, active_tracks, camera_status}` | Every 30s on quiet sockets |

---

## Defaults shipped by `seed_database.py`

| Username | Password | Role |
|---|---|---|
| `admin` | `admin123` | admin |
| `receptionist` | `reception123` | receptionist |
| `security` | `secure123` | security |

**Change these in production.** See `.env.example`.

---

## Known limitations (v0.9)

1. **AI models are optional.** With `torch + facenet-pytorch + ultralytics`
   uninstalled the system reports `backend="none"` and serves zero
   detections / recognitions. Everything else (REST, dashboard, alerts,
   recommendations against seeded data) works.
2. **Encryption at rest is opt-in.** Set `ENCRYPTION_KEY` in `.env` to a
   valid Fernet key to encrypt face embeddings. With the key unset the
   blobs are stored plaintext.
3. **SettingsPage is read-only.** Threshold edits require restarting the
   server with a modified `config.yaml`. Live edits land in a later version.
4. **Single-camera support only.** SDD architecture is multi-camera-ready
   (camera_id field everywhere) but the dashboard currently shows one feed.
5. **No HTTPS by default.** Use a reverse proxy (Caddy, nginx) for TLS in
   production. The PWA is dev-mode HTTP only.

---

## Documentation

| Doc | Purpose |
|---|---|
| [docs/SysRS_System_Requirements_Specification.pdf](docs/SysRS_System_Requirements_Specification.pdf) | Full requirements per IEEE 830-1998 |
| [docs/SDD_Software_Design_Document (1).pdf](<docs/SDD_Software_Design_Document (1).pdf>) | Software design document |
| [docs/SYSRS_COMPLIANCE.md](docs/SYSRS_COMPLIANCE.md) | Per-requirement audit (FR + NFR + AC) |
| [docs/SDD_COMPLIANCE.md](docs/SDD_COMPLIANCE.md) | Per-component audit (C1–C25) |
| [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) | Repository layout + module index |
| [docs/PROJECT_DIRECTORY_REFERENCE.md](docs/PROJECT_DIRECTORY_REFERENCE.md) | Per-file reference |
| [docs/RPI_DEPLOYMENT.md](docs/RPI_DEPLOYMENT.md) | Step-by-step Pi setup |
| [docs/disaster_recovery.md](docs/disaster_recovery.md) | Backup / restore / failure-mode runbook |

---

## License

Senior project — not yet licensed for redistribution.
