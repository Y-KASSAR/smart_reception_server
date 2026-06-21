# Project Directory Reference

> Per-file reference for every code, config, and documentation artefact in the repository.
> **Sister docs:** [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md) (architectural layout), [`SYSRS_COMPLIANCE.md`](SYSRS_COMPLIANCE.md), [`SDD_COMPLIANCE.md`](SDD_COMPLIANCE.md).

---

## Root

| Path | Role |
|---|---|
| `server_app.py` | Application entry point — `python server_app.py` starts the FastAPI server. |
| `config.yaml` | Runtime tunables (thresholds, model choices, channel flags). |
| `.env` | Local secrets (JWT key, API key, optional SMTP/Twilio creds). Gitignored. |
| `.env.example` | Template for `.env`. |
| `requirements.txt` | Pinned Python dependencies. |
| `Caddyfile` | Caddy reverse-proxy config providing **HTTPS/WSS** (NFR-2.2 / NFR-2.3). Terminates TLS in front of the app on `127.0.0.1:5000` and upgrades `/ws` to WSS. Site blocks for `localhost`, LAN IP (`tls internal`), and public domain (Let's Encrypt). Run with `caddy run`. |
| `README.md` | Project overview, install, troubleshooting. |
| `yolov8n.pt` | Pre-downloaded YOLOv8n weights (6.5 MB) — Ultralytics format. |
| `.gitignore` | Excludes venv, node_modules, .env, logs, caches. |

---

## `api/` — FastAPI server

| Path | Role |
|---|---|
| `api/app.py` | App factory. Lifespan hook hydrates the face-engine cache, captures the asyncio loop for cross-thread broadcasts, subscribes the event-bus alert adapter, mounts all routers, configures CORS, serves the React SPA from `frontend/dist`. |
| `api/__init__.py` | Marks package. |
| `api/routes/health.py` | `GET /api/health` — JSON `{status:"ok"}`. |
| `api/routes/staff.py` | `/api/staff/*` — login (JWT), CRUD, RBAC fixtures. Login rate-limited per IP. |
| `api/routes/guests.py` | `/api/guests/*` — CRUD, multi-field search (`?q=`), `/watchlist`, `/{id}/watch`, `/{id}/staff-badge` (admin), `/{id}/summary` aggregate, `/{id}/embed` (attach face). |
| `api/routes/alerts.py` | `/api/alerts/*` — list, acknowledge, resolve. |
| `api/routes/visits.py` | `/api/visits/*` — visit history. |
| `api/routes/reservations.py` | `/api/reservations/*` — CRUD plus the three filtered endpoints `/in-house`, `/arrivals`, `/departures` (today-only by default, local-time aware). |
| `api/routes/services.py` | `/api/services/*` — service catalogue CRUD (admin / manager only for mutations). |
| `api/routes/recommendations.py` | `/api/recommendations/*` — generate, list-by-guest, set status (Accept / Defer / Decline). |
| `api/routes/enrollment.py` | `/api/enrollment/capture` + `/complete` — accepts any base64 image (works for live frames *and* uploaded passport photos). Consent gate. |
| `api/routes/monitoring.py` | `/api/monitoring/status` — snapshot of active person tracks. |
| `api/routes/system.py` | `/api/system/status`, `/stats`, plus the admin-only `/test-email` and `/test-sms` that exercise the alert dispatch path. |
| `api/routes/edge.py` | `/api/edge/frame` + `/heartbeat` — X-API-Key authed. Frame ingest pipeline: decode → YOLO detect → tracker update → FaceNet recognize → bulk lookup of watched + staff-badge + in-house status → 3-state classification + dwell — broadcast WS events. |
| `api/routes/audio.py` | `/api/audio/chunk` + `/status` — X-API-Key authed. Bounded ring buffer; dispatches Whisper inference only when at least one client is subscribed to `/ws/translation`. |
| `api/routes/exports.py` | `/api/exports/{guests,visits,reservations,alerts}` — CSV downloads. |
| `api/routes/websocket.py` | Three WS endpoints (`/api/ws/alerts` legacy, `/ws` canonical, `/ws/translation` subscriber-counted). 8 broadcast helpers covering live_feed / detection_update / alert_push / guest_identified / recommendation_update / heartbeat / frame_ack / translation. |
| `api/schemas/__init__.py` | All Pydantic request/response models. Notably `GuestResponse` (now carries `id_type`, `id_number`, `is_watched`, `watch_reason`, `is_staff_badge`, `staff_badge_label`), `ReservationResponse` (with eager-loaded `guest`), `RecommendationResponse` (with eager-loaded `service`), `WatchlistUpdate`, `StaffBadgeUpdate`. |

---

## `core/` — cross-cutting plumbing

| Path | Role |
|---|---|
| `core/controller.py` | Background controller — schedules the daily 02:00 DB backup; subscribes the alert pipeline at startup. |
| `core/event_bus.py` | Synchronous in-process pub/sub. Used by PersonMonitor to publish dwell-threshold events without depending on the route layer. |

---

## `config/` — settings + logging

| Path | Role |
|---|---|
| `config/settings.py` | Pydantic settings model. Loads `.env` + `config.yaml`. |
| `config/logging_config.py` | Structured rotating-file logger with `smart_reception.*` namespaces. |

---

## `database/` — ORM + repositories

| Path | Role |
|---|---|
| `database/connection.py` | SQLAlchemy engine factory; enables SQLite WAL. |
| `database/models.py` | All 9 entities — Guest, Reservation, Visit, FaceEmbedding, Service, Recommendation, Alert (with `WANTED` type), Staff, SystemLog. `_utcnow` returns local time so dashboard timestamps match the operator's wall clock. |
| `database/repositories/guest_repository.py` | Guest CRUD. |
| `database/repositories/face_embedding_repository.py` | Embedding insert / list / count / delete. Used for the 5-per-guest cap (FR-1.12). |
| `database/repositories/reservation_repository.py` | Reservation CRUD. |
| `database/repositories/visit_repository.py` | Visit CRUD. |
| `database/repositories/service_repository.py` | Service CRUD. |
| `database/repositories/recommendation_repository.py` | Recommendation persistence + status transitions. |
| `database/repositories/alert_repository.py` | Alert CRUD + pending-list helper + acknowledge / resolve. |
| `database/repositories/staff_repository.py` | Staff CRUD + login lookup. |

---

## `detection/` — person detector + tracker

| Path | Role |
|---|---|
| `detection/person_detector.py` | `PersonDetector` (strategy: `yolov8`/`mobilenet-ssd`/`none`) + `CentroidTracker` (max_distance 250 px, max_disappeared 8 frames — tuned empirically against ghost-track inflation in live testing). |

---

## `modules/` — domain modules

| Path | Role |
|---|---|
| `modules/recognition/face_recognizer.py` | MTCNN + InceptionResnetV1 wrapper. In-memory embedding cache, hydrated on startup. Vectorised cosine matcher (`_emb_matrix`). Bbox-validation pass in `detect_faces` to avoid degenerate-bbox crashes. |
| `modules/recognition/_facenet_patch.py` | Runtime monkey-patch for two bugs in upstream `facenet-pytorch.detect_face` (stage-2/3 off-by-N IndexError + degenerate-bbox extract_face crash). Idempotent; called once at engine init. |
| `modules/monitoring/person_monitor.py` | `TrackedPerson` dataclass + `PersonMonitor` with dwell-time thresholds. Skips alert firing for staff-badged tracks. `tracking_timeout` set to 8 s. |
| `modules/alerts/alert_notifier.py` | Event-bus subscriber. Persists each alert via `AlertRepository.create` then dispatches via email + SMS/WhatsApp. Email recipients are **blind-copied (Bcc)**. **Console-fallback mode** writes JSON lines to `logs/outbox/{email,sms}.log` when real channels aren't configured. Per-guest cooldown shared across all alert kinds. |
| `modules/alerts/notification_templates.py` | Per-incident notification templates for **both** channels: `render_alert_email()` (subject + HTML + text) and `render_whatsapp()`. One `_INCIDENTS` table gives each `AlertType` a consistent icon, label, accent colour and call to action. |
| `modules/upselling/recommendation_engine.py` | 7-rule scoring engine (R1 popularity + R2 VIP boost + R3 dietary + R4 room-type + R5 Arabic-dining + R6 winback bundle + R7 business-booking pattern). Each rule attaches its rationale string. |
| `modules/speech/translator.py` | faster-whisper-small wrapper. `task="translate"` always outputs English. Beam 5, temperature 0, initial-prompt biased for colloquial Lebanese Arabic / French / English. |
| `modules/speech/__init__.py` | Re-exports the `speech_translator` singleton. |

---

## `edge/` — Raspberry-Pi edge clients

| Path | Role |
|---|---|
| `edge/edge_client.py` | Frame capture → JPEG → POST. Always-on; latest-frame thread pattern decouples capture from upload. Network-outage buffer of 200 frames. The original `MotionDetector` (C2) class is kept commented for reference; PIR is no longer used. |
| `edge/audio_client.py` | PyAudio capture in 8-s WAV chunks → POST `/api/audio/chunk`. Runs as its own `systemd` service. |

---

## `frontend/` — React SPA

### Layout, hooks, services

| Path | Role |
|---|---|
| `frontend/src/App.tsx` | Router. 8 protected routes. |
| `frontend/src/main.tsx` | Vite entry. |
| `frontend/src/components/Layout/Layout.tsx` | App shell + `ToastProvider`. |
| `frontend/src/components/Layout/Sidebar.tsx` | 8 nav items. Monitoring + Management groupings. |
| `frontend/src/components/Layout/Topbar.tsx` | Page eyebrow + global search + live status. |
| `frontend/src/hooks/useWebSocket.ts` | `useWebSocketEvent` and `useWebSocketEventLog` hooks. |
| `frontend/src/services/api.ts` | Typed axios wrappers; JWT bearer interceptor; 403/5xx → toast. |
| `frontend/src/services/websocket.ts` | Singleton WS client with exponential-backoff reconnect. |
| `frontend/src/styles/global.css` | Single design system — palette, typography, panels, chips, tables. |

### Pages

| Path | Role |
|---|---|
| `frontend/src/pages/LoginPage.tsx` | JWT login. |
| `frontend/src/pages/DashboardPage.tsx` | Live Monitor. Hosts LobbyOverview + LiveFeedPanel + GuestInfoPanel + RecommendationPanel + LobbyMap + AlertPanel. |
| `frontend/src/pages/AlertsPage.tsx` | Filterable alert log (status + min severity). |
| `frontend/src/pages/GuestLookupPage.tsx` | Multi-field search (name / email / phone / ID number). Side detail pane with watch toggle + "Open full profile" link. |
| `frontend/src/pages/GuestProfilePage.tsx` | `/guests/:id` aggregate view: stat strip, contact + document, reservations history, recommendations history, finance roll-up, FaceEnrollmentPanel (attach face from upload or lobby), admin-only staff-badge toggle. |
| `frontend/src/pages/WatchlistPage.tsx` | Active watchlist + search-to-add. |
| `frontend/src/pages/ReservationsPage.tsx` | 3 tabs (In-House / Arrivals / Departures) with derived contextual badges. Per-row side panel shows guest notes + per-guest recommendations. |
| `frontend/src/pages/EnrollmentPage.tsx` | Two-tab capture (Live / Upload). Same backend pipeline. |
| `frontend/src/pages/LiveTranslationPage.tsx` | Opens its own `/ws/translation` socket — page-presence gates Whisper inference. Scrolling transcript log with source-language badges. |
| `frontend/src/pages/ReportsPage.tsx` | KPI tiles + CSV download buttons (4 entities) + alerts-by-severity chart. |
| `frontend/src/pages/SettingsPage.tsx` | System status table + Services Catalog with admin-only Create/Edit/Delete. |

### Components

| Path | Role |
|---|---|
| `frontend/src/components/LiveFeed/LiveFeedPanel.tsx` | Live frame + canvas overlay. 4-tier bbox colour (blue staff / red watched / green known / gold unknown). Pulsing red watchlist banner. Bbox labels include guest ID + 3-state classification + dwell. |
| `frontend/src/components/GuestInfo/GuestInfoPanel.tsx` | Multi-person recognition stack with TTL. Fades cards 3 s after last sighting, evicts at 10 s. Up to 6 visible. |
| `frontend/src/components/Recommendations/RecommendationPanel.tsx` | Renders service name + category + price + reasoning. Accept / Defer / Decline buttons. Toast confirmation. |
| `frontend/src/components/Alerts/AlertPanel.tsx` | Live alert list with severity icons. |
| `frontend/src/components/Monitoring/LobbyOverview.tsx` | 4 KPI tiles auto-refreshing every 5 s and on detection events. |
| `frontend/src/components/Monitoring/LobbyMap.tsx` | SVG floor plan projecting each person's bbox bottom-centre into the camera FOV cone. Colour-coded same as bboxes. |
| `frontend/src/components/Toast/Toast.tsx` | Module-level `toast.success/error/info` API + ToastProvider. Non-blocking bottom-right surface, tone-specific TTL. |

### Build output

| Path | Role |
|---|---|
| `frontend/dist/` | Pre-built SPA served by FastAPI. Rebuilt by `npm run build`. |

---

## `utils/`

| Path | Role |
|---|---|
| `utils/crypto_utils.py` | AES-256-GCM at-rest embedding encryption. Framed `[version=0x01][12-byte nonce][ciphertext+16-byte GCM tag]`, base64-encoded. Backwards-compatible with legacy Fernet rows and plaintext rows. |
| `utils/security_utils.py` | JWT helpers + `get_current_staff` and `require_role` FastAPI dependencies. bcrypt cost 12. |
| `utils/time_utils.py` | Time-zone helpers. |

---

## `scripts/`

| Path | Role |
|---|---|
| `scripts/seed_database.py` | Inserts default staff accounts. |
| `scripts/seed_services.py` | Inserts 13 sample hotel services. |
| `scripts/seed_mock_guests.py` | Inserts **100 mock guests** (varied locales/VIP/status, ~4% watch-listed) + ~400 recommendation interactions, then recomputes statistics-driven popularity. **Does not** mock face embeddings. Idempotent. |
| `scripts/send_test_whatsapp.py` | Manual Twilio WhatsApp/SMS send test driving the real `send_sms()` path; reports the Twilio SID/status. |
| `scripts/build_changelog_docx.py` | Generates the v1.2 change-log addendum `.docx` for the Final Submission folder. |
| `scripts/seed_reservations.py` | Inserts 5 sample reservations + companion guests (2 in-house, 2 arrivals, 3 departures). |
| `scripts/import_pms.py` | Idempotent CSV upsert of guests + reservations. Includes `--generate-sample` (12 guests + 10 reservations) and `--dry-run`. |
| `scripts/backup_database.py` | Manual DB backup invocation. |
| `scripts/preload_facenet.py` | One-shot model weight download. |
| `scripts/bench_embeddings.py` | NFR-1.10 benchmark — 1000 synthetic embeddings, 500 reps. |
| `scripts/accuracy_test.py` | TPR/FPR live harness over WebSocket. |
| `scripts/stability_test.py` | Long-running stability driver. |
| `scripts/smoke_test_today.py` | 60-check end-to-end regression covering every shipped feature. |
| `scripts/smoke_test_e2e.ps1` | 23-endpoint PowerShell smoke test (baseline). |
| `scripts/laptop_edge.py` | Mock edge client driven by laptop webcam — useful for dev when the Pi isn't on the network. |
| `scripts/generate_self_signed_cert.py` | Generates a self-signed cert for the direct-uvicorn HTTPS path (alternative to the Caddy reverse proxy, which is the primary HTTPS/WSS mechanism — see `Caddyfile`). |

---

## `tests/`

| Path | Role |
|---|---|
| `tests/test_api.py` | 24 endpoint tests (auth + RBAC). |
| `tests/test_database.py` | 11 model + repo + cascade tests. |
| `tests/test_face_recognizer.py` | 18 cosine + cache + matching tests. |
| `tests/test_new_routes.py` | 8 enrollment / system / monitoring tests. |
| `tests/test_person_detector.py` | 21 PersonMonitor + dwell + alerts tests. |
| `tests/test_recommendations.py` | 26 scoring-rule + persistence tests. |
| `tests/test_repositories.py` | 26 CRUD coverage. |
| `tests/test_upselling.py` | 16 API integration. |
| `tests/test_websocket.py` | 8 WS connect + broadcast. |
| `tests/test_faces/` | Sample face images. |
| `tests/test_images/` | Sample frames. |

---

## `data/`

| Path | Role |
|---|---|
| `data/smart_reception.db` | SQLite database (WAL mode). |
| `data/backups/` | Daily DB backups produced by `core.controller`. |
| `data/face_encodings/` | Reserved for raw-embedding cold storage. |
| `data/knowledge/` | Reserved for future knowledge-base content. |
| `data/pms_imports/` | Drop folder for `guests.csv` + `reservations.csv`. |

---

## `logs/`

| Path | Role |
|---|---|
| `logs/smart_reception.log` | Structured rotating application log. |
| `logs/_server.log` / `_server.err` | stdout / stderr of the running server process (when launched via the PowerShell helper). |
| `logs/outbox/email.log` | Console-fallback dispatch log for email channel. |
| `logs/outbox/sms.log` | Console-fallback dispatch log for SMS channel. |

---

## `docs/`

| Path | Role |
|---|---|
| `docs/SysRS_System_Requirements_Specification.pdf` | Original spec — functional + non-functional + acceptance criteria. |
| `docs/SDD_Software_Design_Document (1).pdf` | Original design document — components + algorithms + sequence diagrams. |
| `docs/SYSRS_COMPLIANCE.md` | Per-requirement audit. |
| `docs/SDD_COMPLIANCE.md` | Per-component audit. |
| `docs/PROJECT_STRUCTURE.md` | Architectural layout. |
| `docs/PROJECT_DIRECTORY_REFERENCE.md` | This file. |
| `docs/RPI_DEPLOYMENT.md` | Pi-side deployment recipe. |
| `docs/disaster_recovery.md` | Backup / restore / failure-mode runbook. |
| `docs/assets/Smart_Reception_Dashboard_mockup.html` | UI mockup informing FR-5 dashboard work. |
| `docs/assets/smart_reception_logo.png` | Brand logo used by the SPA + favicon. |
