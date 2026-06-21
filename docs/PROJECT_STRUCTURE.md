# Project Structure

> **Codebase size:** 11 425 LOC Python + 4 927 LOC TypeScript/TSX = ~16 350 LOC total.
> **Companion docs:** [`PROJECT_DIRECTORY_REFERENCE.md`](PROJECT_DIRECTORY_REFERENCE.md) (per-file reference), [`SYSRS_COMPLIANCE.md`](SYSRS_COMPLIANCE.md) (functional + non-functional requirements audit), [`SDD_COMPLIANCE.md`](SDD_COMPLIANCE.md) (design-document audit).

This document describes the layout of the repository as it ships. Every directory listed below contains code or configuration that participates in delivering a numbered functional (FR-) or non-functional (NFR-) requirement; nothing in the tree is scratch, build-output cache, or dev-only artwork.

---

## 1. Top-level tree

```
smart_reception_server/
├── api/                  FastAPI app + routers + Pydantic schemas
├── config/               Settings loader + structured logging
├── core/                 Cross-cutting controller + in-process event bus
├── data/                 SQLite database + drop-folders (backups / PMS imports)
├── database/             SQLAlchemy models + 8 repositories
├── detection/            YOLOv8 person detector + centroid tracker
├── docs/                 Specifications + compliance audit + deployment guides
├── edge/                 Raspberry-Pi edge clients (frames + audio)
├── frontend/             React + TypeScript + Vite single-page dashboard
├── logs/                 Rotating server log + alert-dispatch outbox
├── modules/              Domain modules — recognition / monitoring / alerts / upselling / speech
├── scripts/              Operational scripts (seed / import / benchmark / smoke test)
├── tests/                pytest suite (158 tests baseline + smoke harnesses)
├── utils/                Cross-cutting utilities (JWT/RBAC, AES-256 crypto, time)
│
├── .env                  Local secrets (gitignored)
├── .env.example          Template for the above
├── config.yaml           Runtime settings (thresholds, model choices)
├── Caddyfile             Caddy reverse proxy → HTTPS/WSS (NFR-2.2/2.3)
├── requirements.txt      Pinned Python dependencies
├── server_app.py         Server entry point
├── yolov8n.pt            Pre-downloaded YOLOv8n weights (6.5 MB)
└── README.md             Project overview + quick-start
```

---

## 2. Backend — `api/`

```
api/
├── app.py                FastAPI application factory + lifespan hook
├── routes/               15 routers, one file per HTTP-prefix group
│   ├── health.py            GET /api/health
│   ├── staff.py             /api/staff (login + RBAC + staff CRUD)
│   ├── guests.py            /api/guests (CRUD + multi-field search + watchlist
│   │                                    + staff-badge + summary + embed)
│   ├── alerts.py            /api/alerts (CRUD + acknowledge + resolve)
│   ├── visits.py            /api/visits (visit history)
│   ├── reservations.py      /api/reservations (+ /in-house / /arrivals / /departures)
│   ├── services.py          /api/services (admin CRUD)
│   ├── recommendations.py   /api/recommendations (generate + list + status)
│   ├── enrollment.py        /api/enrollment (capture + complete)
│   ├── monitoring.py        /api/monitoring (track snapshot)
│   ├── system.py            /api/system (status + stats + test-email + test-sms)
│   ├── edge.py              /api/edge (frame ingest + heartbeat) — X-API-Key
│   ├── audio.py             /api/audio (chunk ingest + status) — X-API-Key
│   ├── exports.py           /api/exports (CSV: guests / visits / reservations / alerts)
│   └── websocket.py         /api/ws + /ws + /ws/translation
└── schemas/              Pydantic request/response models (all endpoints)
```

Implements **FR-5** (dashboard back-end), **FR-6** (database management), **FR-2.8** (recommendation status mutations), **FR-2.11** (admin service CRUD), **FR-6.12** (CSV exports), **NFR-2.5/2.6/2.7/2.8** (auth + RBAC + API key + login rate-limiting).

---

## 3. Domain modules — `modules/`

```
modules/
├── recognition/          MTCNN + FaceNet engine
│   ├── face_recognizer.py   Lazy model load, in-memory embedding cache,
│   │                        cosine matcher (vectorised matrix path)
│   └── _facenet_patch.py    Runtime monkey-patch fixing 2 upstream MTCNN bugs
├── monitoring/           PersonMonitor (dwell + staff badge + thresholds)
├── alerts/               AlertNotifier (event_bus subscriber → DB row + email/SMS/WhatsApp;
│                         email recipients Bcc'd) + notification_templates (per-incident
│                         email + WhatsApp bodies)
├── upselling/            RecommendationEngine (7 scoring rules, R1–R7; R1 popularity
│                         baseline is statistics-driven via recompute_popularity)
└── speech/               SpeechTranslator wrapping faster-whisper-small
```

Implements **FR-1** (recognition), **FR-2** (recommendations including R6 winback and R7 business-pattern rules), **FR-3** (lobby monitoring + three-state classification + dwell tracking), **FR-4** (alerts including the WANTED watchlist type), and the live English speech-translation pipeline.

---

## 4. Person detection — `detection/`

```
detection/
└── person_detector.py    YOLOv8n strategy (CUDA imgsz 960) + CentroidTracker
                          (max_distance 250 px, max_disappeared 8 frames)
```

Implements **FR-3.1/3.2/3.3/3.4** (person detection + colour-coded bbox + centroid tracking).

---

## 5. Data layer — `database/` and `data/`

```
database/
├── connection.py         Engine factory + WAL-mode init
├── models.py             9 entities, full schema (Guest, Reservation, Visit,
│                         FaceEmbedding, Service, Recommendation, Alert, Staff,
│                         SystemLog) with cascade-delete relationships
└── repositories/         8 repository classes wrapping CRUD
    ├── alert_repository.py
    ├── face_embedding_repository.py
    ├── guest_repository.py
    ├── recommendation_repository.py
    ├── reservation_repository.py
    ├── service_repository.py
    ├── staff_repository.py
    └── visit_repository.py

data/
├── smart_reception.db    SQLite database (WAL mode)
├── backups/              Daily DB backups (NFR-3.6) — managed by core.controller
├── face_encodings/       Reserved for raw-embedding cold storage (currently empty)
├── knowledge/            Reserved for future knowledge-base content
└── pms_imports/          Drop folder for guests.csv + reservations.csv (PMS sync)
```

Implements **FR-6** (database management), **NFR-2.11** (GDPR cascade delete), **NFR-3.6/3.7** (daily backup + 7-day retention).

---

## 6. Edge clients — `edge/`

```
edge/
├── edge_client.py        Video frame capture + JPEG + HTTP POST loop
│                         (always-on, latest-frame thread pattern)
└── audio_client.py       PyAudio capture, 8-s WAV chunks → /api/audio/chunk
```

Implements SDD components **C1** (VideoCapture), **C3** (FrameStreamer), **C4** (EdgeNetworkClient), plus the audio companion service. SDD **C2** (PIR MotionDetector) is deliberately superseded per **FR-7.8** "always-on override".

Deploys to the Pi as two `systemd` services (`smart-reception-edge.service`, `smart-reception-audio.service`) — see [`RPI_DEPLOYMENT.md`](RPI_DEPLOYMENT.md).

---

## 7. Frontend — `frontend/`

```
frontend/
├── package.json            React 18 + TypeScript + Vite + lucide-react
├── tsconfig.json
├── vite.config.ts
├── dist/                   Built SPA (served by FastAPI at /)
└── src/
    ├── App.tsx             Router with 8 protected routes
    ├── main.tsx
    ├── components/
    │   ├── Layout/         Sidebar (8 nav items) + Topbar + ToastProvider
    │   ├── LiveFeed/       LiveFeedPanel — canvas overlay, 4-tier bbox colours,
    │   │                   pulsing watchlist banner, dwell labels
    │   ├── GuestInfo/      Multi-person recognition card stack with TTL
    │   ├── Recommendations/ RecommendationPanel — Accept/Defer/Decline buttons
    │   ├── Alerts/         AlertPanel
    │   ├── Monitoring/     LobbyOverview (KPI tiles) + LobbyMap (FR-3.10 SVG)
    │   └── Toast/          Module-level toast() API (NFR-4.3)
    ├── hooks/
    │   └── useWebSocket.ts WebSocket subscription hook
    ├── pages/              top-level pages
    │   ├── DashboardPage.tsx       /
    │   ├── AlertsPage.tsx          /alerts
    │   ├── GuestLookupPage.tsx     /guests          (multi-field search)
    │   ├── GuestProfilePage.tsx    /guests/:id      (full profile + attach face)
    │   ├── WatchlistPage.tsx       /watchlist
    │   ├── ReservationsPage.tsx    /reservations    (3 tabs with derived badges)
    │   ├── EnrollmentPage.tsx      /enrollment      (Live / Upload tabs)
    │   ├── LiveTranslationPage.tsx /translation     (Whisper subscriber gate)
    │   ├── ReportsPage.tsx         /reports         (KPIs + CSV downloads)
    │   ├── SettingsPage.tsx        /settings        (system + services CRUD)
    │   └── LoginPage.tsx
    ├── services/
    │   ├── api.ts           Typed axios wrappers + JWT interceptor
    │   └── websocket.ts     Singleton WS client with auto-reconnect
    └── styles/
        └── global.css       Single design system — navy/gold/ivory palette
```

Implements **FR-5** (dashboard system), **FR-1.10/3.3** (colour-coded bboxes), **FR-3.10** (lobby occupancy map), **NFR-4.3** (friendly error messages via toast system).

---

## 8. Cross-cutting — `core/`, `config/`, `utils/`

```
core/
├── controller.py         Background scheduler (daily DB backup at 02:00)
└── event_bus.py          In-process pub/sub for module decoupling

config/
├── settings.py           Pydantic settings + .env loader
├── logging_config.py     Structured rotating-file logging
└── (config.yaml at repo root drives runtime tunables)

utils/
├── crypto_utils.py       AES-256-GCM at-rest embedding encryption (NFR-2.1)
├── security_utils.py     JWT + bcrypt + RBAC dependency
└── time_utils.py
```

---

## 9. Operational scripts — `scripts/`

| Script | Role | FR/NFR link |
|---|---|---|
| `seed_database.py` | Default staff accounts | NFR-2.6 |
| `seed_services.py` | 13 sample hotel services | FR-2.3 |
| `seed_mock_guests.py` | 100 mock guests + ~400 recommendation interactions → statistics-driven popularity (no face embeddings) | FR-1 / FR-2.3 |
| `seed_reservations.py` | 5 sample reservations (In-House / Arrivals / Departures demo) | FR-1.8 |
| `send_test_whatsapp.py` | Manual Twilio WhatsApp/SMS send test (real `send_sms()` path) | FR-4.6 / NFR-1.6 |
| `build_changelog_docx.py` | Generate the v1.2 change-log addendum `.docx` | docs |
| `import_pms.py` | Idempotent CSV upsert of guests + reservations (with `--generate-sample` + `--dry-run`) | FR-6 PMS sync |
| `backup_database.py` | Manual DB backup invocation | NFR-3.6 |
| `preload_facenet.py` | One-shot model weight download | bootstrap |
| `bench_embeddings.py` | 1000-embedding recognition-latency benchmark | NFR-1.10 |
| `accuracy_test.py` | TPR/FPR live harness over WebSocket | AC-2 |
| `stability_test.py` | Long-running stability driver | NFR-3.1 |
| `smoke_test_today.py` | 60-check end-to-end regression of every shipped feature | NFR-3 |
| `smoke_test_e2e.ps1` | 23-endpoint PowerShell smoke (baseline) | NFR-3 |
| `laptop_edge.py` | Mock edge client driven by laptop webcam (dev) | dev |
| `generate_self_signed_cert.py` | Self-signed cert for the direct-uvicorn HTTPS path (Caddy reverse proxy is primary — see `Caddyfile`) | NFR-2.2 |

Every script in this folder maps to a requirement or to a project bootstrap step. Submission artefacts (report, slides) live outside the runtime repository.

---

## 10. Tests — `tests/`

```
tests/
├── test_api.py                  24 endpoint tests (auth + RBAC)
├── test_database.py             11 model + repo + cascade tests
├── test_face_recognizer.py      18 cosine + cache + matching tests
├── test_new_routes.py            8 enrollment / system / monitoring smoke
├── test_person_detector.py      21 PersonMonitor + dwell + alerts tests
├── test_recommendations.py      26 rules + persistence (R1–R7)
├── test_repositories.py         26 CRUD coverage
├── test_upselling.py            16 API integration
├── test_websocket.py             8 WS connect + broadcast
├── test_faces/                  Test face images
└── test_images/                 Test frames
```

158 pytest tests + 60-check end-to-end smoke + 23-endpoint PowerShell smoke = ~241 automated checks covering every shipped FR / NFR group.

---

## 11. Documentation — `docs/`

| File | Purpose |
|---|---|
| `SysRS_System_Requirements_Specification.pdf` | The original system-requirements specification (April 2026). |
| `SDD_Software_Design_Document (1).pdf` | The original software-design document (April 2026). |
| `SYSRS_COMPLIANCE.md` | Per-requirement audit — every FR and NFR with status and evidence. |
| `SDD_COMPLIANCE.md` | Per-component audit — C1–C17 plus new C18–C25, every algorithm, sequence diagram, deployment piece. |
| `PROJECT_STRUCTURE.md` | This file. |
| `PROJECT_DIRECTORY_REFERENCE.md` | Per-file reference for every code file. |
| `RPI_DEPLOYMENT.md` | Step-by-step Pi-side deployment recipe. |
| `disaster_recovery.md` | Backup / restore / failure-mode runbook. |
| `assets/` | UI mockup HTML + project logo (referenced by FR-5 dashboard work). |

---

## 12. Excluded from the repo (intentionally)

The following are **not** committed but live alongside the repo on a normal development machine:

- `venv/` — Python virtual environment (recreated via `python -m venv venv && pip install -r requirements.txt`).
- `frontend/node_modules/` — JavaScript dependencies (recreated via `npm install` in `frontend/`).
- `.env` — gitignored secrets (use `.env.example` as a template).
- Generated submission artefacts (defense slides, report .docx, etc.) — not part of the runtime project.

---

## 13. Quick-start

```bash
# 1. Backend
python -m venv venv && . venv/Scripts/activate   # Windows
pip install -r requirements.txt
python scripts/preload_facenet.py
python scripts/seed_database.py
python scripts/seed_services.py
python scripts/seed_reservations.py
python scripts/seed_mock_guests.py                # optional: 100 mock guests for full-system testing
python server_app.py                              # serves on :5000

# 2. Frontend (only if you intend to modify it; dist/ is pre-built)
cd frontend
npm install
npm run build                                     # rebuilds dist/

# 3. Pi-side (after the Pi is on the same /24 as the laptop)
scp edge/edge_client.py  ykassar@<pi-ip>:~/smart_reception/
scp edge/audio_client.py ykassar@<pi-ip>:~/smart_reception/
# then create the two systemd units per RPI_DEPLOYMENT.md
```

Default admin credentials after seeding: `admin / admin123` (rotate immediately for any deployment outside dev).
