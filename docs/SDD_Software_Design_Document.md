# Software Design Document (SDD)
## Compact AI-Powered Smart Reception Assistant

### Document Information

| Field | Value |
|---|---|
| Document Title | Software Design Document (SDD) |
| Project Name | Compact AI-Powered Smart Reception Assistant |
| Author | Youssef Kassar |
| Institution | Arts, Sciences & Technology University in Lebanon (AUL) |
| Department | Computer & Communications Engineering (CCE) |
| Version | 1.1 |
| Date | June 2026 |
| Status | Released for submission |
| Related Documents | System Requirements Specification (SysRS) v1.1 |

### Revision History

| Version | Date | Author | Description |
|---|---|---|---|
| 0.1 | March 2026 | Youssef Kassar | Initial draft — architectural overview |
| 0.5 | March 2026 | Youssef Kassar | Added detailed component designs |
| 1.0 | April 2026 | Youssef Kassar | Complete SDD for submission |
| 1.1 | June 2026 | Youssef Kassar | As-built reconciliation. Baseline design (v1.0) preserved; added **Section 13 — Design Deviations (v1.1 As-Built)** mapping every component (C1–C25), algorithm, and interface to the delivered implementation, with rationale. See also `docs/SDD_COMPLIANCE.md`. |

> **Reading note (v1.1).** Sections 1–12 are the **original April 2026 design baseline**, preserved as written. The delivered system diverged from the baseline in several places (the PIR sensor was removed, FaceNet embeddings are 512-D not 128-D, the recognition threshold is 0.80, at-rest encryption is AES-256-**GCM** not CBC, the framework is FastAPI, and a speech-translation subsystem plus four new dashboard pages were added). Those changes are **not** silently edited into the baseline below — they are recorded in **Section 13 — Design Deviations (v1.1 As-Built)**, with rationale and the affected component IDs, so this document preserves the design-vs-implementation narrative. File-level mapping lives in `docs/SDD_COMPLIANCE.md`.

---

## Table of Contents

1. Introduction
2. System Overview
3. Architectural Design
4. Detailed Component Design
5. Data Design
6. Interface Design
7. Algorithms and Flowcharts
8. Sequence Diagrams
9. Error Handling
10. Security Design
11. Testing Strategy
12. Deployment Design
13. **Design Deviations (v1.1 As-Built)** — new in v1.1

---

## 1. Introduction

### 1.1 Purpose

This Software Design Document (SDD) provides a comprehensive technical blueprint for the **Compact AI-Powered Smart Reception Assistant** system. It translates the requirements defined in the System Requirements Specification (SysRS v1.0) into a detailed software architecture and design that will guide the implementation, testing, and deployment of the system.

This document is intended for:

- **The Developer (Youssef Kassar):** As the primary implementation reference, providing detailed module specifications, algorithms, data structures, and interfaces.
- **Academic Supervisors and Jury Members:** To evaluate the technical soundness, architectural appropriateness, and design quality of the proposed system.
- **Future Maintainers:** To understand the internal structure, component relationships, and design decisions for maintenance and extension.

### 1.2 Scope

This SDD covers the complete software design of the Compact AI-Powered Smart Reception Assistant, including:

- The hybrid distributed architecture comprising an edge device (Raspberry Pi 4) and an AI server (Laptop).
- All software modules on both the edge device and the server.
- The React-based web dashboard frontend.
- The SQLite database schema and data management layer.
- The REST API and WebSocket communication interfaces.
- The AI/ML inference pipeline (person detection, face recognition).
- The rule-based recommendation engine.
- The alert generation and delivery system.
- Error handling, security, testing, and deployment strategies.

### 1.3 Overview

- **Section 2** provides a high-level system overview, context, and design constraints.
- **Section 3** describes the architectural design, including system architecture, component diagrams, and deployment architecture.
- **Section 4** provides detailed design specifications for every software module.
- **Section 5** covers the data design, including the database schema, data structures, and data flow.
- **Section 6** defines the interface design, including API endpoints, UI design, and hardware interfaces.
- **Section 7** presents the algorithms and flowcharts for the core AI and business logic.
- **Section 8** provides sequence diagrams for the primary system interactions.
- **Section 9** describes the error handling strategy.
- **Section 10** covers the security design.
- **Section 11** outlines the testing strategy.
- **Section 12** details the deployment design.
- **Section 13** *(new in v1.1)* records design deviations between this baseline and the delivered system.

### 1.4 Definitions and Acronyms

All definitions, acronyms, and abbreviations are consistent with those defined in the SysRS document (Section 1.3). Additional design-specific terms:

| Term | Definition |
|---|---|
| Bounding Box | A rectangular region defined by (x, y, width, height) that encloses a detected object in an image frame. |
| Centroid Tracking | An object tracking algorithm that assigns IDs to objects based on the proximity of their centroids across frames. |
| Cosine Similarity | A metric measuring the cosine of the angle between two vectors; used to compare facial embeddings (range: -1 to 1; higher = more similar). |
| Embedding | A fixed-dimensional numerical vector that encodes the identity-related features of a face. |
| Inference | The process of running input data through a trained AI model to produce predictions. |
| MTCNN | Multi-task Cascaded Convolutional Networks — a face detection algorithm that simultaneously detects faces and facial landmarks. |
| NMS | Non-Maximum Suppression — a post-processing step that removes overlapping/redundant detection boxes, keeping only the most confident one. |
| SORT | Simple Online and Realtime Tracking — a multi-object tracking algorithm using Kalman filtering and Hungarian assignment. |
| WAL Mode | Write-Ahead Logging — an SQLite journaling mode that allows concurrent reads during writes. |
| Watchdog | A system process that monitors another process and restarts it if it fails. |

---

## 2. System Overview

### 2.1 System Context

The Compact AI-Powered Smart Reception Assistant operates within a hotel reception and lobby environment. It serves as an intelligent auxiliary system that enhances the capabilities of reception staff by providing automated guest identification, personalized service recommendations, and proactive lobby monitoring.

```
┌─────────────────────────────────────────────────────────────────┐
│ HOTEL ENVIRONMENT                                                 │
│  ┌─────────────┐     ┌──────────────────────────────────────┐    │
│  │   LOBBY     │     │ SMART RECEPTION ASSISTANT SYSTEM      │    │
│  │  Guests ────┼─────┼─► Camera ─► RPi ─► Laptop Server      │    │
│  │  Visitors   │     │                    │       │          │    │
│  └─────────────┘     │              Dashboard   Alerts       │    │
│  ┌─────────────┐     └────────────────────┼───────┼──────────┘    │
│  │ Reception   │◄──────────────────────────┘       │              │
│  │   Staff     │                                    │              │
│  └─────────────┘     ┌─────────────┐                │              │
│                      │ Duty Manager│◄───────────────┘              │
│                      └─────────────┘   (Email/SMS)                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 System Architecture (High-Level)

The system follows a **hybrid distributed architecture** with two compute nodes:

1. **Edge Node (Raspberry Pi 4):** Handles hardware interfacing (camera, PIR sensor), video capture, frame preprocessing, and network transmission.
2. **Server Node (Laptop):** Handles all compute-intensive operations including AI inference (person detection, face recognition), business logic (recommendations, alerts), data persistence (SQLite), and serving the web dashboard.

Design principles:

- **Separation of Concerns:** Each module has a single, well-defined responsibility.
- **Edge-Server Offloading:** Computationally intensive tasks are delegated to the server to accommodate the RPi's limited resources.
- **Loose Coupling:** Modules communicate through well-defined interfaces (REST API, WebSocket), enabling independent development and replacement.
- **Event-Driven Processing:** The PIR sensor triggers the capture pipeline; detections trigger alerts; identifications trigger recommendations.

### 2.3 Design Constraints

| Constraint | Impact on Design |
|---|---|
| Raspberry Pi 4 limited CPU/RAM | No AI inference on edge; all ML models run on laptop server. Frame encoding and transmission optimized for low CPU usage. |
| Single USB webcam | Single video stream; no multi-camera aggregation. Camera module designed as singleton. |
| SQLite (single-file DB) | No concurrent write support; WAL mode used for read-write parallelism. Designed for single-server deployment. |
| Budget ($59–$66) | No commercial software licenses; all components open-source. No cloud GPU; inference on laptop CPU/GPU. |
| 2-month timeline | Phased delivery; core features first (Phase 1), advanced features second (Phase 2). Design prioritizes simplicity and proven libraries. |
| Local network only | No cloud dependency; all services run on-premise. Internet required only for email/SMS alert delivery. |
| Python ecosystem | All backend components in Python for consistency. React (JavaScript) for frontend only. |

### 2.4 Assumptions and Dependencies

All assumptions and dependencies listed in the SysRS (Section 2.5) apply. Additional design assumptions:

| ID | Design Assumption |
|---|---|
| DA-1 | The laptop AI server has at least 8GB RAM and a multi-core CPU (Intel i5 or equivalent) for running YOLO and FaceNet simultaneously. |
| DA-2 | Pre-trained model weights for YOLO and FaceNet are available for download and do not require custom training. |
| DA-3 | The local network provides a stable connection with latency < 10ms between the RPi and the laptop. |
| DA-4 | Python virtual environments (venv) are used to manage dependencies on both the RPi and the laptop. |
| DA-5 | The React dashboard is served as a static build from the Flask/FastAPI server, eliminating the need for a separate Node.js server in production. |

---

## 3. Architectural Design

### 3.1 System Architecture

The system is decomposed into five architectural layers:

```
┌─────────────────────────────────────────────────────────────────────┐
│ LAYER 5: PRESENTATION LAYER — React Web Dashboard                     │
│   Live Feed │ Guest Info │ Alerts │ Recommendations components        │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 4: APPLICATION LAYER — Flask/FastAPI Backend Server             │
│   REST API Router │ WebSocket Mgr │ Static File Server                │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 3: BUSINESS LOGIC LAYER                                         │
│   Person Detection │ Face Recognition │ Recommendation Engine         │
│   Alert Manager │ Lobby Monitor │ Guest Manager                       │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 2: DATA ACCESS LAYER — SQLAlchemy ORM / Database Module         │
│   Models │ Repositories │ Migrations │ Backup Mgr                     │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 1: INFRASTRUCTURE LAYER                                         │
│   EDGE DEVICE (RPi): Camera, PIR, Network Client                      │
│   AI SERVER (Laptop): Network Server, SQLite DB, OS/Python Runtime    │
└─────────────────────────────────────────────────────────────────────┘
```

| Layer | Responsibility | Location |
|---|---|---|
| Layer 1: Infrastructure | Hardware interfacing, OS services, network transport, storage | RPi + Laptop |
| Layer 2: Data Access | ORM models, database queries, data persistence, backup | Laptop |
| Layer 3: Business Logic | AI inference, face recognition, recommendations, alerts, monitoring | Laptop |
| Layer 4: Application | HTTP/WS server, routing, request handling, response formatting | Laptop |
| Layer 5: Presentation | User interface rendering, user interaction, real-time display | Browser (Client) |

### 3.2 Component Diagram

The system comprises 14 distinct software components (C1–C17 across edge, server, and browser) in the baseline:

**Raspberry Pi 4 (Edge):**
- **C1: Camera Interface Module** — OpenCV VideoCapture, frame encoding (JPEG), resolution management
- **C2: PIR Sensor Module** — RPi.GPIO interface, motion event detection, debounce logic
- **C3: Network Client Module** — HTTP frame upload, WebSocket streaming, connection management, frame buffering

**Laptop (AI Server):**
- **C4: Network Server** (Flask/FastAPI) — REST API endpoints, WebSocket manager, static file serving (React build)
- **C5: Person Detection Module** — YOLO/MobileNet, NMS, tracking
- **C6: Face Recognition Module** — MTCNN face detection, FaceNet/DeepFace embedding extraction, cosine similarity matching
- **C7: Database Module** — SQLAlchemy, CRUD ops, backup
- **C8: Recommendation Engine** — rule-based analysis, guest history scoring, service ranking, preference matching
- **C9: Alert System Module** — email, SMS (Twilio), logging
- **C10: Lobby Monitor Module** — person classification, dwell time tracking, assistance detection, occupancy counting
- **C11: Dashboard Backend** — API route handlers, WebSocket broadcast, session management, authentication

**Client Browser (Dashboard):**
- **C12: Live Feed Component**
- **C13: Guest Info Component**
- **C14: Alert Panel Component**
- **C15: Recommendation Panel**
- **C16: Search Component**
- **C17: Enrollment Component**

### 3.3 Deployment Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│ LOCAL AREA NETWORK (192.168.1.0/24)                                       │
│  ┌───────────────────────────────────┐                                    │
│  │ RASPBERRY PI 4 (192.168.1.100)    │                                    │
│  │  OS: Raspberry Pi OS (Bullseye)   │                                    │
│  │  Runtime: Python 3.9+             │  Ethernet / Wi-Fi                  │
│  │  Services: edge_capture.py        │◄────────────────────┐             │
│  │  Hardware: USB Webcam, PIR (GPIO17), microSD 32GB        │             │
│  └───────────────────────────────────┘                     │             │
│  ┌───────────────────────────────────────────────────────────┐          │
│  │ LAPTOP AI SERVER (192.168.1.200)                          ┘          │
│  │  OS: Windows 10/11, macOS, or Ubuntu                                  │
│  │  Runtime: Python 3.9+, Node.js 18+ (build only)                       │
│  │  Services: server_app.py → 5000 ; WebSocket → 5001 ; SPA → 5000       │
│  │  Storage: smart_reception.db, /models/, /backups/, /logs/             │
│  └───────────────────────────────────────────────────────────┘          │
│  ┌───────────────────────────────────────────┐                           │
│  │ CLIENT BROWSERS  http://192.168.1.200:5000 │                           │
│  └───────────────────────────────────────────┘                           │
└──────────────────────────────────────────────────────────────────────────┘
   EXTERNAL SERVICES (Internet Required): SMTP Server (email), Twilio API (SMS)
```

**Component Distribution:**

| Component | Runs On | Process | Port |
|---|---|---|---|
| Camera Interface (C1) | Raspberry Pi | edge_capture.py | — |
| PIR Sensor (C2) | Raspberry Pi | edge_capture.py | — |
| Network Client (C3) | Raspberry Pi | edge_capture.py | — |
| Network Server (C4) | Laptop | server_app.py | 5000, 5001 |
| Person Detection (C5) | Laptop | server_app.py | — |
| Face Recognition (C6) | Laptop | server_app.py | — |
| Database (C7) | Laptop | server_app.py | — |
| Recommendation Engine (C8) | Laptop | server_app.py | — |
| Alert System (C9) | Laptop | server_app.py | — |
| Lobby Monitor (C10) | Laptop | server_app.py | — |
| Dashboard Backend (C11) | Laptop | server_app.py | 5000 |
| Dashboard Frontend (C12–C17) | Client Browser | — | — |

---

## 4. Detailed Component Design

### 4.1 Edge Device (Raspberry Pi) Components

#### 4.1.1 Camera Interface Module (C1)

| Attribute | Detail |
|---|---|
| Module Name | `camera_module.py` |
| Purpose | Capture video frames from the connected USB webcam and provide them to the network client for transmission. |
| Location | Raspberry Pi 4 |
| Dependencies | OpenCV (`cv2`), V4L2, NumPy |
| Design Pattern | Singleton (one camera instance), Producer-Consumer (frame queue) |

**Key Classes and Functions:**
```python
class CameraManager:
    """Manages USB webcam capture on the Raspberry Pi."""
    def __init__(self, device_id=0, resolution=(1920,1080), fps=30, jpeg_quality=80): ...
    def initialize_camera(self) -> bool: ...      # V4L2 backend, resolution, FPS, buffer size
    def capture_frame(self) -> Optional[np.ndarray]: ...
    def encode_frame(self, frame) -> bytes: ...   # JPEG, configurable quality
    def stream_frames(self, frame_queue, stop_event): ...  # dedicated thread
    def get_camera_status(self) -> dict: ...
    def release_camera(self): ...
```

**Algorithms:**
- **Frame Capture Loop:** Runs in a dedicated thread. Captures at the configured FPS, encodes to JPEG, enqueues. If the queue is full (max 30 frames), the oldest frame is discarded to prevent memory growth.
- **Adaptive Quality:** If the network client reports slow transmission, JPEG quality is dynamically reduced (80% → 60% → 40%) to decrease frame size.

#### 4.1.2 PIR Sensor Module (C2)

| Attribute | Detail |
|---|---|
| Module Name | `pir_module.py` |
| Purpose | Interface with the HC-SR501 PIR motion sensor via GPIO to detect motion, triggering the camera pipeline. |
| Location | Raspberry Pi 4 |
| Dependencies | RPi.GPIO or gpiozero |
| Design Pattern | Observer (callback-based event handling) |

> **⚠ v1.1: this component was REMOVED.** See §13.

**Key Classes and Functions:**
```python
class PIRSensorManager:
    def __init__(self, gpio_pin=17, debounce_ms=2000, idle_timeout_s=60): ...
    def setup_pir(self) -> bool: ...
    def detect_motion(self) -> bool: ...
    def _motion_callback(self, channel): ...
    def is_active(self) -> bool: ...
    def cleanup(self): ...
```

**Algorithms:**
- **Debounce Logic:** Events within the debounce window (2 s) are ignored to prevent rapid-fire false triggers.
- **Idle Timer:** If no new motion within `idle_timeout_s` (default 60), the camera enters idle mode.

#### 4.1.3 Network Client Module (C3)

| Attribute | Detail |
|---|---|
| Module Name | `network_client.py` |
| Purpose | Transmit frames and sensor data from the RPi to the AI server; handle connection management, buffering, reconnection. |
| Location | Raspberry Pi 4 |
| Dependencies | requests, websocket-client, threading, queue |
| Design Pattern | Client-Server, Producer-Consumer |

**Key Classes and Functions:**
```python
class NetworkClient:
    def __init__(self, server_url, ws_url, api_key, max_buffer=100): ...
    def connect_to_server(self) -> bool: ...
    def send_frame_http(self, frame_data, timestamp, metadata) -> Optional[dict]: ...
    def send_frame_ws(self, frame_data, timestamp): ...
    def start_streaming(self, frame_queue, stop_event): ...
    def receive_response(self) -> Optional[dict]: ...
    def buffer_frames(self, frame_data): ...   # max 100 frames, oldest discarded
    def flush_buffer(self): ...
    def send_heartbeat(self) -> bool: ...
    def reconnect(self, max_retries=5, backoff_factor=2.0): ...
    def disconnect(self): ...
```

**Algorithms:**
- **Exponential Backoff Reconnection:** Retry after 1s, 2s, 4s, 8s, 16s. After `max_retries`, enter a slow-poll mode (retry every 60s).
- **Frame Buffering:** When the network is unavailable, frames are stored in a circular buffer (max 100). On reconnection, buffered frames are sent in chronological order before resuming real-time streaming.

### 4.2 AI Server (Laptop) Components

#### 4.2.1 Network Server Module (C4)

| Attribute | Detail |
|---|---|
| Module Name | `server_app.py` (main), `routes/` (route modules) |
| Purpose | Host the Flask/FastAPI application that receives data from the RPi, serves the REST API, manages WebSocket connections, and serves the React dashboard. |
| Location | Laptop AI Server |
| Dependencies | Flask/FastAPI, Flask-SocketIO/python-socketio, Uvicorn/Gunicorn |
| Design Pattern | MVC, Observer (WebSocket broadcast) |

```python
from fastapi import FastAPI, WebSocket, UploadFile
from fastapi.staticfiles import StaticFiles
app = FastAPI(title="Smart Reception Assistant API", version="1.0")

@app.post("/api/v1/frames/upload")
async def handle_frame_upload(file: UploadFile, timestamp: str, metadata: dict) -> dict: ...

@app.get("/api/v1/health")
async def health_check() -> dict: ...

@app.websocket("/ws/live_feed")
async def websocket_live_feed(websocket: WebSocket): ...

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket): ...

app.mount("/", StaticFiles(directory="frontend/build", html=True))

class ConnectionManager:
    """Manages active WebSocket connections for broadcasting."""
    async def connect(self, websocket): ...
    def disconnect(self, websocket): ...
    async def broadcast(self, message: dict): ...
    async def broadcast_binary(self, data: bytes): ...
```

#### 4.2.2 Person Detection Module (C5)

| Attribute | Detail |
|---|---|
| Module Name | `detection/person_detector.py` |
| Purpose | Detect all persons present in video frames using a pre-trained deep learning model (YOLO or MobileNet SSD). |
| Location | Laptop AI Server |
| Dependencies | ultralytics (YOLOv8), torch, OpenCV, NumPy |
| Design Pattern | Strategy (interchangeable detection models) |

```python
class PersonDetector:
    def __init__(self, model_type="yolov8n", confidence_threshold=0.5, nms_iou_threshold=0.4, device="auto"): ...
    def load_model(self) -> bool: ...
    def detect_persons(self, frame) -> List[Dict]: ...   # filters COCO class 0
    def apply_nms(self, detections) -> List[Dict]: ...
    def annotate_frame(self, frame, detections) -> np.ndarray: ...  # green/yellow/red
    def get_model_info(self) -> dict: ...
```

**Algorithms:**
- **YOLO Inference:** Frame resized to 640×640, passed through the YOLOv8 backbone (CSPDarknet), neck (PANet), and detection head. Only "person" (COCO ID 0) detections above the confidence threshold are retained.
- **Non-Maximum Suppression (NMS):** For overlapping detections (IoU > threshold), only the highest-confidence detection is kept.

#### 4.2.3 Face Recognition Module (C6)

| Attribute | Detail |
|---|---|
| Module Name | `recognition/face_recognizer.py` |
| Purpose | Detect faces within person regions, extract facial embeddings, and match them against the database of known guests. |
| Location | Laptop AI Server |
| Dependencies | facenet-pytorch (MTCNN, InceptionResnetV1), or deepface, NumPy, scipy |
| Design Pattern | Pipeline (detect → align → embed → match) |

```python
class FaceRecognizer:
    def __init__(self, detection_model="mtcnn", recognition_model="facenet", similarity_threshold=0.70, device="auto"): ...
    def load_models(self) -> bool: ...
    def detect_faces(self, image) -> List[Dict]: ...           # MTCNN, bbox + landmarks
    def align_face(self, image, landmarks) -> np.ndarray: ...  # affine → 160×160
    def extract_embedding(self, aligned_face) -> np.ndarray: ...  # FaceNet, L2-normalized
    def match_face(self, embedding, stored_embeddings) -> Dict: ...
    def compute_cosine_similarity(self, emb1, emb2) -> float: ...
    def enroll_face(self, image, guest_id) -> np.ndarray: ...
```

**Algorithms:**
- **Face Detection (MTCNN):** Three-stage cascaded CNN — (1) P-Net generates candidate regions, (2) R-Net refines boxes, (3) O-Net produces final boxes + 5-point landmarks.
- **Face Alignment:** Using eye coordinates, compute the rotation angle to align eyes horizontally; apply an affine transform; scale to 160×160.
- **Embedding Extraction (FaceNet):** Aligned face normalized to [-1, 1], passed through InceptionResnetV1; output vector L2-normalized.
- **Cosine Similarity Matching:** `similarity = (A · B) / (||A|| × ||B||)`. If `similarity ≥ threshold`, a match is reported; the highest-similarity guest is the primary match.

#### 4.2.4 Database Module (C7)

| Attribute | Detail |
|---|---|
| Module Name | `database/db_manager.py`, `database/models.py` |
| Purpose | Manage all persistent data storage using SQLite via SQLAlchemy ORM. |
| Location | Laptop AI Server |
| Dependencies | SQLAlchemy 2.x, SQLite 3.36+, NumPy |
| Design Pattern | Repository Pattern, Data Mapper (ORM) |

ORM models (baseline): `Guest`, `FaceEmbedding`, `Reservation`, `Visit`, `Alert`, `Service`, `RecommendationLog`. `DatabaseManager` exposes CRUD per entity plus `store_embedding`, `get_all_embeddings`, `refresh_embedding_cache`, `backup_database`. See §5 for the full schema.

#### 4.2.5 Recommendation Engine Module (C8)

| Attribute | Detail |
|---|---|
| Module Name | `business/recommendation_engine.py` |
| Purpose | Generate personalized upselling recommendations using a rule-based approach. |
| Location | Laptop AI Server |
| Dependencies | Database Module (C7) |
| Design Pattern | Strategy (rule engine), Chain of Responsibility (rule evaluation) |

```python
class RecommendationEngine:
    def __init__(self, db_manager): ...
    def analyze_guest_history(self, guest) -> dict: ...   # visits, spend, loyalty_tier, booking_pattern
    def generate_recommendations(self, guest, reservation) -> List[Dict]: ...
    def _apply_rules(self, profile_summary, services) -> List[Dict]: ...
    def rank_services(self, scored_services) -> List[Dict]: ...   # top 5
    def log_recommendation(self, guest_id, service_id, staff_member=None): ...
    def update_outcome(self, log_id, outcome): ...
```

**Baseline Rule Definitions:**

| Rule ID | Rule Name | Condition | Action | Weight |
|---|---|---|---|---|
| R1 | Loyalty Upgrade | total_visits ≥ 3 AND room not top-tier | Recommend room upgrade | 0.9 |
| R2 | Service Repeat | previously used service X | Recommend X or similar | 0.8 |
| R3 | Business Traveler | booking_pattern = 'business' | Meeting room, fast Wi-Fi, airport transfer | 0.7 |
| R4 | High Spender | average_spend > $200/night | Premium dining, exclusive experiences | 0.8 |
| R5 | VIP Treatment | vip_status = True | Exclusive VIP packages | 0.95 |
| R6 | Long Stay | stay_duration ≥ 5 nights | Spa packages, laundry service | 0.7 |
| R7 | Special Occasion | birthday/anniversary in date range | Celebration packages | 0.85 |
| R8 | Late Checkout | checkout_date = today | Late checkout | 0.6 |

> **⚠ v1.1: the delivered rule set differs from this baseline.** See §13.5.

#### 4.2.6 Alert System Module (C9)

| Attribute | Detail |
|---|---|
| Module Name | `alerts/alert_manager.py` |
| Purpose | Generate, deliver, and manage alert notifications. Supports email (SMTP), SMS / **WhatsApp** (Twilio), and dashboard push (WebSocket). |
| Location | Laptop AI Server |
| Dependencies | smtplib, email.message, Twilio SDK, Database Module (C7), Connection Manager (C4) |
| Design Pattern | Observer (alert subscribers), Template Method (alert types) |
| As-built note | Implemented as `alerts/alert_notifier.py`. Per-incident bodies are rendered by `alerts/notification_templates.py` (`render_alert_email` → subject + branded HTML + text; `render_whatsapp` → compact WhatsApp/SMS body) — one `_INCIDENTS` table per `AlertType`. **Email recipients are blind-copied (Bcc)** so they cannot see one another. The Twilio channel is selectable via `TWILIO_CHANNEL` (`sms` \| `whatsapp`, incl. the WhatsApp Sandbox). |

```python
class AlertManager:
    def __init__(self, db_manager, ws_manager, config): ...
    def generate_alert(self, alert_type, severity, description, person_id=None, image_frame=None) -> Alert: ...
    def _check_cooldown(self, alert_type, person_id) -> bool: ...   # 15 min
    def deliver_alert(self, alert): ...   # dashboard always; email/SMS if configured
    def send_email(self, alert, recipients) -> bool: ...   # SMTP+TLS, 3 retries
    def send_sms(self, alert, phone_numbers) -> bool: ...   # Twilio, 3 retries
    def push_to_dashboard(self, alert): ...
    def acknowledge_alert(self, alert_id, acknowledged_by) -> bool: ...
    def resolve_alert(self, alert_id, resolution_note) -> bool: ...
    def log_alert(self, alert, channel, success, error=None): ...
```

#### 4.2.7 Lobby Monitor Module (C10)

| Attribute | Detail |
|---|---|
| Module Name | `monitoring/lobby_monitor.py` |
| Purpose | Orchestrate lobby surveillance by combining person detection, face recognition, tracking, and dwell-time monitoring. |
| Location | Laptop AI Server |
| Dependencies | C5, C6, C9, C7 |
| Design Pattern | Mediator, State |

```python
class TrackedPerson:
    person_id: int; guest_id: Optional[int]; status: str
    first_seen: datetime; last_seen: datetime; dwell_time: float
    position: Tuple[int,int]; bbox: List[int]
    recognition_attempts: int; flagged: bool; alert_generated: bool

class LobbyMonitor:
    def __init__(self, person_detector, face_recognizer, alert_manager, db_manager, config): ...
    def process_frame(self, frame, timestamp) -> dict: ...   # detect→track→recognize→dwell→alert
    def _update_tracking(self, detections) -> List[TrackedPerson]: ...  # centroid match; evict >30s
    def _classify_person(self, tracked, recognition_result) -> str: ...
    def _check_alert_conditions(self, tracked): ...   # security 10min / assistance 5min / VIP
    def get_lobby_status(self) -> dict: ...
    def get_occupancy_count(self) -> int: ...
```

#### 4.2.8 Dashboard Backend Module (C11)

| Attribute | Detail |
|---|---|
| Module Name | `routes/dashboard_routes.py` |
| Purpose | Serve all dashboard API endpoints for guest lookup, alert management, recommendation interaction, enrollment, and system status. |
| Location | Laptop AI Server |
| Dependencies | Flask/FastAPI, Database Module (C7), all business logic modules |

Route groups: Guests (`/api/v1/guests`), Enrollment (`/api/v1/enrollment`), Alerts (`/api/v1/alerts`), Recommendations (`/api/v1/recommendations`), Monitoring (`/api/v1/monitoring`), System (`/api/v1/system`), Authentication (`/api/v1/auth`). See §6.1 for the full API reference.

### 4.3 Frontend (Dashboard) Components

The dashboard is built with React 18.x as a single-page application (SPA), compiled to static files and served by the Flask/FastAPI server. It communicates with the backend via REST API and WebSocket.

**Application structure (baseline):** `App.jsx` (routing), `components/` (Layout, LiveFeed C12, GuestInfo C13, Alerts C14, Recommendations C15, Search C16, Enrollment C17, Monitoring, Common), `pages/` (Dashboard, GuestLookup, Alerts, Reports, Settings, Login), `services/` (api.js, websocket.js, auth.js), `hooks/` (useWebSocket, useAlerts, useGuestData), `styles/global.css`.

| Component | File | Purpose | Data Source |
|---|---|---|---|
| Live Feed (C12) | LiveFeedPanel.jsx | Live camera feed with detection overlays | WS `/ws/live_feed` |
| Guest Info (C13) | GuestInfoPanel.jsx | Identified guest profile, reservation, history | REST `GET /api/v1/guests/{id}` |
| Alert Panel (C14) | AlertPanel.jsx | Active/acknowledged/resolved alerts | REST `/api/v1/alerts` + WS `/ws/alerts` |
| Recommendation Panel (C15) | RecommendationPanel.jsx | Upselling recommendations | REST `/api/v1/recommendations/{guest_id}` |
| Search (C16) | SearchBar.jsx + SearchResults.jsx | Guest search by name/email/phone/reservation | REST `/api/v1/guests/search?q=...` |
| Enrollment (C17) | EnrollmentForm.jsx + FaceCapture.jsx | New guest enrollment with face capture | REST `/api/v1/enrollment/capture` + `/complete` |

---

## 5. Data Design

### 5.1 Database Schema

#### 5.1.1 Entity-Relationship Model

`GUESTS` is the central entity, with 1:N relationships to `FACE_EMBEDDINGS`, `RESERVATIONS`, `VISITS`, and `ALERTS`; `RECOMMENDATION_LOGS` relates N:1 to `SERVICES`.

```python
# database/models.py — SQLAlchemy ORM Models (baseline)
class Guest(Base):
    __tablename__ = 'guests'
    id, first_name, last_name, email(unique), phone, nationality,
    preferences(JSON), vip_status(bool), notes, consent_given(bool),
    created_at, updated_at
    # relationships: embeddings, reservations, visits

class FaceEmbedding(Base):
    __tablename__ = 'face_embeddings'
    id, guest_id(FK), embedding_data(LargeBinary), captured_at, quality_score

class Reservation(Base):
    __tablename__ = 'reservations'
    id, guest_id(FK), room_number, room_type, check_in_date, check_out_date,
    rate_per_night, total_amount, special_requests, status, created_at

class Visit(Base):
    __tablename__ = 'visits'
    id, guest_id(FK), check_in_at, check_out_at, room_number, total_spend,
    services_used(JSON), feedback_score, notes

class Alert(Base):
    __tablename__ = 'alerts'
    id, timestamp, alert_type, severity, description, person_id(FK),
    image_path, status, acknowledged_by, resolution_note, resolved_at

class Service(Base):
    __tablename__ = 'services'
    id, name, category, description, price, is_active

class RecommendationLog(Base):
    __tablename__ = 'recommendation_logs'
    id, guest_id(FK), service_id(FK), recommended_at, outcome, staff_member
```

#### 5.1.2 Indexes

| Table | Index | Columns | Purpose |
|---|---|---|---|
| guests | idx_guests_email | email | Fast lookup by email |
| guests | idx_guests_phone | phone | Fast lookup by phone |
| guests | idx_guests_name | last_name, first_name | Fast name search |
| face_embeddings | idx_embeddings_guest | guest_id | Fast embedding retrieval per guest |
| reservations | idx_reservations_guest | guest_id | Fast reservation lookup |
| reservations | idx_reservations_status | status | Filter active reservations |
| reservations | idx_reservations_dates | check_in_date, check_out_date | Date range queries |
| alerts | idx_alerts_status | status | Filter active/unresolved alerts |
| alerts | idx_alerts_timestamp | timestamp | Chronological alert listing |
| recommendation_logs | idx_reclogs_guest | guest_id | Guest recommendation history |

#### 5.1.3 Constraints

| Constraint | Table | Type | Description |
|---|---|---|---|
| PK auto-increment | All tables | Primary Key | Auto-incrementing integer IDs |
| FK cascade delete | face_embeddings.guest_id | Foreign Key | Delete embeddings when guest deleted |
| FK cascade delete | reservations.guest_id | Foreign Key | Delete reservations when guest deleted |
| FK cascade delete | visits.guest_id | Foreign Key | Delete visits when guest deleted |
| FK set null | alerts.person_id | Foreign Key | Set NULL when guest deleted |
| Unique email | guests.email | Unique | No duplicate email addresses |
| Check status | reservations.status | Check | confirmed/checked_in/checked_out/cancelled |
| Check severity | alerts.severity | Check | low/medium/high |
| Max embeddings | face_embeddings | Application | Maximum 5 embeddings per guest |

### 5.2 Data Structures

#### 5.2.1 In-Memory Data Structures

| Structure | Type | Purpose | Location |
|---|---|---|---|
| Frame Queue | `queue.Queue(maxsize=30)` | Buffer captured frames between camera and network client | RPi |
| Frame Buffer | `collections.deque(maxlen=100)` | Buffer frames when network unavailable | RPi |
| Embedding Cache | `Dict[int, List[np.ndarray]]` | In-memory cache of all facial embeddings keyed by guest_id | Laptop |
| Tracked Persons | `Dict[int, TrackedPerson]` | Currently tracked persons keyed by tracking ID | Laptop |
| Active Reservations Cache | `Set[int]` | guest_ids with active reservations (refreshed every 5 min) | Laptop |
| WebSocket Connections | `List[WebSocket]` | Active dashboard WebSocket connections | Laptop |

#### 5.2.2 Data Formats

| Data | Format | Size (typical) |
|---|---|---|
| Video frame (raw) | NumPy array (1080,1920,3) uint8 | ~6 MB |
| Video frame (encoded) | JPEG bytes, quality 80% | ~100–200 KB |
| Facial embedding (FaceNet) | NumPy (128,) float32 | 512 bytes |
| Facial embedding (DeepFace/VGGFace) | NumPy (4096,) float32 | 16 KB |
| Detection result | JSON `{bbox, confidence, class, track_id}` | ~200 bytes |
| Alert payload | JSON `{id, type, severity, description, image_b64, timestamp}` | ~50–100 KB |
| Guest profile | JSON `{id, name, email, phone, preferences, vip, ...}` | ~1 KB |

### 5.3 Data Flow

#### 5.3.1 Video Processing Data Flow
```
Webcam(1080p) ─USB,Raw BGR─► Camera Module (C1) ─JPEG ~150KB─► Network Client (C3)
  ─HTTP/WS,LAN─► Network Server (C4) ─Decoded frame─► Person Detection (C5)
  ─Detections─► Face Recognition (C6) ─Recognition─► Lobby Monitor (C10)
Annotated frame ─► Dashboard Backend (C11) ◄─REST/WS─ Alert Manager (C9)
  ─WS/HTTP─► Dashboard Frontend (Browser)
```

#### 5.3.2 Alert Data Flow
```
Trigger Event (dwell exceeded, VIP) ─► Lobby Monitor (C10) ─Save─► Database (C7)
  ─generate_alert()─► Alert Manager (C9) ─┬─► WebSocket Push ─► Dashboard (C14)
                                          ├─► SMTP Email ─► Duty Manager Inbox
                                          └─► Twilio SMS ─► Duty Manager Phone
```

#### 5.3.3 Guest Identification Data Flow
```
Camera Frame ─► Person Detection (C5) ─[Person Crop]─► Face Detection (C6)
  ─[Aligned 160×160]─► Embedding Extraction (C6) ─[Vector]─► Database Match (C7)
  ├─ Match Found ─► Get Profile ─► Get Reservation ─► Get Recommendations ─► Dashboard
  └─ No Match ─► "Unknown Guest" ─► Offer Enrollment
```

---

## 6. Interface Design

### 6.1 API Endpoints

| Method | Endpoint | Description | Request Body | Response |
|---|---|---|---|---|
| POST | /api/v1/auth/login | User login | `{username, password}` | `{token, expires_at}` |
| POST | /api/v1/auth/logout | User logout | — | `{message}` |
| POST | /api/v1/frames/upload | Upload frame from RPi | multipart: file, timestamp, metadata | `{detections, recognitions}` |
| GET | /api/v1/guests | List all guests (paginated) | query: page, per_page | `{guests, total}` |
| GET | /api/v1/guests/{id} | Get guest details | — | guest profile + reservation + history |
| GET | /api/v1/guests/search | Search guests | query: q | `[guest summaries]` |
| POST | /api/v1/guests | Create guest | `{first_name, last_name, email, ...}` | created guest |
| PUT | /api/v1/guests/{id} | Update guest | fields to update | updated guest |
| DELETE | /api/v1/guests/{id} | Delete guest | — | `{message}` |
| POST | /api/v1/enrollment/capture | Capture face | — | `{face_image, quality}` |
| POST | /api/v1/enrollment/complete | Complete enrollment | `{guest_data, face_images}` | created guest + embeddings |
| GET | /api/v1/reservations/{guest_id} | Get guest reservations | — | `[reservations]` |
| POST | /api/v1/reservations | Create reservation | `{guest_id, room_number, dates, ...}` | created reservation |
| PUT | /api/v1/reservations/{id} | Update reservation | fields | updated reservation |
| GET | /api/v1/alerts | Get alerts | query: status, severity, page | `{alerts, total}` |
| PUT | /api/v1/alerts/{id}/acknowledge | Acknowledge alert | `{acknowledged_by}` | updated alert |
| PUT | /api/v1/alerts/{id}/resolve | Resolve alert | `{resolution_note}` | updated alert |
| GET | /api/v1/recommendations/{guest_id} | Get recommendations | — | `[{service, price, relevance_score, reason}]` |
| PUT | /api/v1/recommendations/{log_id}/outcome | Update outcome | `{outcome}` | `{message}` |
| GET | /api/v1/monitoring/status | Get lobby status | — | `{total_persons, in_house, unknown, flagged}` |
| GET | /api/v1/services | List services | — | `[services]` |
| POST | /api/v1/services | Create service | `{name, category, description, price}` | created service |
| PUT | /api/v1/services/{id} | Update service | fields | updated service |
| DELETE | /api/v1/services/{id} | Delete service | — | `{message}` |
| GET | /api/v1/system/status | System health | — | `{rpi_connected, camera_ok, models_loaded, uptime}` |
| GET | /api/v1/system/stats | Summary statistics | — | `{guests_today, alerts_today, recommendations_today}` |
| GET | /api/v1/health | Health check | — | `{status, timestamp}` |

**WebSocket Endpoints:**

| Endpoint | Direction | Message Format | Description |
|---|---|---|---|
| /ws/live_feed | Server → Client | Binary (JPEG) + JSON (detections) | Streams annotated video frames and detection data |
| /ws/alerts | Server → Client | JSON `{alert_id, type, severity, description, timestamp}` | Pushes new alerts in real-time |
| /ws/status | Server → Client | JSON `{rpi_connected, camera_ok, lobby_count}` | Periodic system status (every 5s) |

### 6.2 User Interface Design

**6.2.1 Dashboard Layout:** Top navbar (logo, status, user, settings); left sidebar (Live Monitor, Guest Lookup, Alerts, Reports, Settings); main content area with Live Video Feed + Guest Info Panel (top), Lobby Status + Recommendations (middle), Alerts Panel (bottom).

**6.2.2 Navigation Flow:** Login → Dashboard → {Live Monitor → click person → Guest Info; Guest Lookup → Search → Detail → Edit/Delete/Enroll; Alerts → Acknowledge/Resolve; Reports; Settings}.

### 6.3 Hardware Interfaces

**6.3.1 GPIO Pin Assignments:** GPIO 17 (Pin 11) Input Pull-Down ← PIR OUT; 5V (Pin 2) → PIR VCC; GND (Pin 6) → PIR GND.

**6.3.2 USB Camera Configuration:**
```yaml
camera:
  device_id: 0          # /dev/video0
  resolution_width: 1920
  resolution_height: 1080
  fps: 30
  backend: "v4l2"
  jpeg_quality: 80
  auto_exposure: true
  auto_white_balance: true
```

---

## 7. Algorithms and Flowcharts

### 7.1 Person Detection Algorithm
```
ALGORITHM: PersonDetection
INPUT: frame (1920×1080 BGR)
OUTPUT: detections (list of {bbox, confidence, class})
1. RESIZE frame to 640×640 (letterbox padding)
2. NORMALIZE pixels to [0,1]
3. CONVERT to tensor, move to device
4. RUN YOLOv8: CSPDarknet backbone → PANet neck → detection head
5. DECODE predictions: per anchor extract (cx,cy,w,h), objectness, class probs;
   confidence = objectness × class_prob
6. FILTER: class == "person" (COCO 0) AND confidence ≥ 0.5
7. APPLY NMS: sort by confidence desc; drop IoU > 0.4
8. SCALE boxes back to original dimensions
9. RETURN detections
```

### 7.2 Face Recognition Algorithm
```
ALGORITHM: FaceRecognition
INPUT: person_crop
OUTPUT: {matched, guest_id, confidence}
1. DETECT faces with MTCNN (P-Net → R-Net → O-Net → 5 landmarks)
2. IF no face: RETURN {matched:False, guest_id:None, confidence:0}
3. SELECT largest face (closest to camera)
4. ALIGN: eye midpoint + angle → affine → crop 160×160
5. NORMALIZE: RGB, scale [-1,1]
6. EXTRACT embedding via FaceNet (InceptionResnetV1); L2-normalize
7. LOAD all stored embeddings from cache
8. FOR each guest, each stored_emb: similarity = cosine(query, stored); track max per guest
9. SORT guests by max similarity desc
10. IF top ≥ THRESHOLD (0.70): RETURN {matched:True, guest_id, confidence, top_matches}
11. ELSE: RETURN {matched:False, guest_id:None, confidence:top_similarity}
```

### 7.3 Alert Generation Algorithm
```
ALGORITHM: AlertGeneration
INPUT: tracked_person
OUTPUT: alert | None
1. dwell_time = now - first_seen
2. SECURITY: IF unknown AND dwell > 600s AND not fired AND not cooldown:
   severity=medium; capture frame; create+deliver alert; RETURN
3. ASSISTANCE: IF dwell > 300s AND stationary AND not approaching AND not fired:
   severity=low (medium if not in-house); create+deliver; RETURN
4. VIP: IF guest_id AND vip_status AND not vip_sent_today:
   severity=low; create+deliver; RETURN
5. RETURN None
```

### 7.4 Upselling Recommendation Algorithm
```
ALGORITHM: UpsellRecommendation
INPUT: guest, reservation
OUTPUT: up to 5 ranked recommendations
1. LOAD visit history
2. ANALYZE profile: total_visits, avg_spend, services_used, preferred_room,
   loyalty_tier (new/regular/frequent/vip), booking_pattern (business/leisure/mixed)
3. LOAD active services
4. FOR each service: relevance_score=0, reasons=[]
   apply R1..R8 (loyalty/repeat/business/spender/VIP/longstay/occasion/latecheckout)
   IF relevance_score > 0: append {service, score, reasons}
5. SORT by relevance_score desc
6. RETURN top 5
```

---

## 8. Sequence Diagrams

### 8.1 Guest Identification Sequence
Reception Staff · PIR · Camera (RPi) · Network Client · AI Server · Face Recog · Database · Dashboard:
Motion → activate → capture frame → JPEG → HTTP POST `/frames/upload` → detect persons → detections → crop face → extract embedding → get all embeddings → match (cosine) → match result → get guest → profile + reservation → generate recommendations → WebSocket push `{guest_info, recommendations, frame}` → display.

### 8.2 Lobby Monitoring Sequence
Camera → frame → Person Detector → detections → Lobby Monitor `process()` → update tracking → recognize new persons → (DB query/result) → classify → check dwell times → IF threshold exceeded → Alert Mgr generate → push/email/sms → return `{occupancy, tracked_persons, alerts}`.

### 8.3 Alert Generation and Resolution Sequence
Lobby Monitor → trigger → Alert Manager → check cooldown (DB) → save alert (DB) → push alert (WebSocket broadcast JSON → Dashboard) → send email (SMTP) → send SMS (Twilio) → … → acknowledge (PUT `/alerts/{id}/ack` → update status) → resolve (PUT `/alerts/{id}/resolve` → update resolved).

---

## 9. Error Handling

### 9.1 Error Types and Categories

| Category | Error Type | Severity | Example |
|---|---|---|---|
| Hardware | Camera disconnection | High | USB webcam unplugged or /dev/video0 inaccessible |
| Hardware | PIR sensor failure | Medium | GPIO pin unresponsive, sensor malfunction |
| Network | RPi-Laptop connection loss | High | Cable unplugged, Wi-Fi lost, server unreachable |
| Network | WebSocket disconnection | Medium | Dashboard client loses WebSocket connection |
| Network | Email delivery failure | Low | SMTP unreachable, auth failed |
| Network | SMS delivery failure | Low | Twilio API error, invalid number |
| AI/ML | Model loading failure | Critical | Weight file missing, incompatible format, OOM |
| AI/ML | Inference timeout | Medium | Frame processing exceeds 5s |
| AI/ML | No face detected | Low | Face not visible/obstructed/extreme angle |
| Database | Connection failure | Critical | DB file corrupted, disk full |
| Database | Query timeout | Medium | Complex query exceeds timeout |
| Database | Integrity violation | Medium | Duplicate email, FK constraint violation |
| Application | Authentication failure | Medium | Invalid credentials, expired token |
| Application | Configuration error | High | Missing/invalid config.yaml parameters |
| System | Out of memory | Critical | RAM exhaustion |
| System | Disk full | High | No space for DB writes, logs, backups |

### 9.2 Error Handling Strategies

**9.2.1 Retry Mechanisms**

| Operation | Max Retries | Backoff | Fallback |
|---|---|---|---|
| Network frame upload | 3 | Exponential (1s,2s,4s) | Buffer frames locally |
| WebSocket connection | 5 | Exponential (1s,2s,4s,8s,16s) | Switch to HTTP polling |
| Email delivery | 3 | Fixed (5s) | Log error, continue other channels |
| SMS delivery | 3 | Fixed (5s) | Log error, continue other channels |
| Camera reconnection | Infinite | Fixed (5s) | Display error on dashboard, continue other functions |
| Database connection | 5 | Exponential (1s,2s,4s,8s,16s) | Shutdown with critical error log |

**9.2.2 Fallback Procedures:** Camera unavailable → "Camera Offline", DB/search still work. PIR unavailable → always-on mode. AI model fails → "AI Offline", live feed without overlays. Network lost → RPi buffers up to 100 frames, "Edge Disconnected". Email/SMS unavailable → other channels + dashboard; error logged. DB unavailable → critical error, maintenance message, auto-restart.

**9.2.3 Logging Strategy:** Python `logging` with `RotatingFileHandler` (10 MB × 30 files), format `%(asctime)s | %(name)s | %(levelname)s | %(module)s:%(lineno)d | %(message)s`. Levels: DEBUG (diagnostics), INFO (significant events), WARNING (non-critical), ERROR (operation-affecting), CRITICAL (system-level).

---

## 10. Security Design

### 10.1 Data Encryption

**10.1.1 Data at Rest**

| Data | Encryption Method | Implementation |
|---|---|---|
| Facial embeddings (in SQLite) | AES-256-CBC | Embeddings encrypted before storage using Python `cryptography`; key in environment variable. |
| SQLite database file | File-system permissions (chmod 600) | Only the application user has read/write access. |
| Backup files | AES-256 encrypted archive | Backups compressed and encrypted. |
| Configuration files (with secrets) | File-system permissions + `.env` | Secrets in `.env`, not committed to VCS. |

> **⚠ v1.1:** at-rest cipher is AES-256-**GCM** (authenticated), not CBC. See §13.6.

**10.1.2 Data in Transit**

| Communication Path | Protocol | Implementation |
|---|---|---|
| RPi → Laptop (frames, data) | HTTPS (TLS 1.2+) | TLS terminated by the Caddy reverse proxy (`Caddyfile`); `tls internal` for LAN or Let's Encrypt for a public domain. |
| Laptop → Dashboard (API, WS) | HTTPS / WSS | Same Caddy front-end; `/ws` upgraded to WSS automatically. |
| Laptop → Email Server | SMTP with STARTTLS | Python `smtplib` with `starttls()`. |
| Laptop → Twilio API | HTTPS | Twilio SDK handles TLS. |

### 10.2 Authentication and Authorization

**10.2.1 Dashboard Authentication:** Username/password with JWT session tokens. Passwords bcrypt-hashed (work factor 12). Session 8 hours (configurable), 30-minute inactivity timeout. JWT stored in browser httpOnly cookie.

**10.2.2 API Authentication:** RPi → Laptop via `X-API-Key` header. Dashboard → Laptop via `Authorization: Bearer <token>`.

**10.2.3 Role-Based Access Control:** `staff` (view live feed, guest info, view/acknowledge alerts, recommendations, search, enroll) and `admin` (all staff + resolve alerts, manage services, manage users, settings, export, delete guests).

### 10.3 Privacy Compliance

Data minimization (store embeddings, not raw images; alert images purged after 30 days), purpose limitation, explicit consent on enrollment (`consent_given` flag), right to erasure (`DELETE /api/v1/guests/{id}`), configurable retention, access logging, transparency via README/manual.

---

## 11. Testing Strategy

### 11.1 Unit Testing
pytest (Python) and Jest (React). Per-module test files: `test_camera.py`, `test_pir.py`, `test_network_client.py`, `test_person_detector.py`, `test_face_recognizer.py`, `test_database.py`, `test_recommendations.py`, `test_alerts.py`, `test_lobby_monitor.py`, `test_api.py`. **Coverage target: ≥ 80%.**

### 11.2 Integration Testing
RPi → Laptop communication; Detection → Recognition pipeline; Recognition → Database; Alert → Email/SMS; Dashboard → API; Camera → Dashboard (end-to-end).

### 11.3 System Testing

**11.3.1 End-to-End Scenarios:** SYS-01 enrolled guest identification ≤3s; SYS-02 unknown-person security alert at 12 min; SYS-03 assistance alert at 6 min; SYS-04 VIP arrival; SYS-05 multi-person; SYS-06 camera disconnect; SYS-07 network disconnect + buffer flush; SYS-08 guest search; SYS-09 enrollment; SYS-10 4-hour stability.

**11.3.2 Performance Testing:**

| Metric | Target |
|---|---|
| Frame streaming FPS | ≥ 15 FPS |
| Person detection latency | ≤ 200 ms/frame |
| Face recognition latency | ≤ 2 s |
| Dashboard update latency | ≤ 500 ms |
| Database query performance | ≤ 100 ms |
| Memory usage (RPi) | ≤ 80% of 4GB |
| Memory usage (Laptop) | ≤ 90% of available RAM |
| API response time | p95 ≤ 200 ms |

---

## 12. Deployment Design

### 12.1 Installation Procedure

**12.1.1 Raspberry Pi Setup:** Flash Raspberry Pi OS 64-bit; connect webcam + PIR (VCC→Pin2, GND→Pin6, OUT→Pin11) + network; install `python3-pip python3-venv python3-opencv libatlas-base-dev`; venv + `pip install opencv-python-headless numpy requests websocket-client RPi.GPIO pyyaml`; copy edge code + config; install as systemd service `smart-reception-edge`.

**12.1.2 Laptop AI Server Setup:** install Python 3.9+, Node.js 18+, Git; clone repo; venv + `pip install -r requirements.txt`; YOLO/FaceNet weights auto-download; `cd frontend && npm install && npm run build`; copy `.env.example`→`.env` and fill secrets; init DB; seed demo data; `uvicorn server_app:app --host 0.0.0.0 --port 5000 --workers 1`; access at `http://192.168.1.200:5000`.

### 12.2 Configuration

**12.2.1 `config.yaml`** (baseline): server, edge, camera, pir (`gpio_pin:17, always_on:false`), detection (`model:yolov8n, confidence:0.5, nms_iou:0.4`), recognition (`detection_model:mtcnn, recognition_model:facenet, similarity_threshold:0.70, max_embeddings_per_guest:5`), monitoring (`security_dwell:600, assistance_dwell:300, tracking_timeout:30`), alerts (`cooldown:900, email_enabled, sms_enabled`), database, security (`session_timeout:1800, max_login_attempts:5`).

**12.2.2 `.env`** (secrets): `API_KEY`, `JWT_SECRET_KEY`, SMTP_*, TWILIO_*, `ENCRYPTION_KEY`, default admin credentials.

### 12.3 Maintenance

**12.3.1 Backups:** DB daily 02:00 (7-day retention), config on change (Git), logs rotated daily (30-day), alert images purged after 30 days.

**12.3.2 Updates:** `git pull`; `pip install -r requirements.txt --upgrade`; `npm install && npm run build`; migrations; restart services.

**12.3.3 Monitoring:** uptime (heartbeat, 30s), camera status (10s), memory/disk (psutil, >90%), API response (p95>500ms), error rate (>10/hour).

---

## 13. Design Deviations (v1.1 As-Built)

> **Status:** This section is **new in v1.1**. It maps the April 2026 design baseline (Sections 1–12) to the system delivered on the `master` branch (June 2026). It is the design companion to `docs/SDD_COMPLIANCE.md` (which carries the full file-by-file mapping) and to the SysRS v1.1 deviations section. Baseline design text above is intentionally **unchanged**.

### 13.1 As-built environment summary

- **ML stack — GPU-active:** torch (CUDA 12.4) + facenet-pytorch (MTCNN + FaceNet on CUDA) + ultralytics YOLOv8n (`device='0'`, `imgsz=960`) + faster-whisper `small` (CUDA). A single laptop carries all three models in VRAM.
- **Hardware:** Pi 4 (8 GB) + USB webcam over a direct Cat-6 cable on an isolated `192.168.99.0/24` subnet. Measured **16.03 fps** end-to-end.
- **Repository:** post-cleanup — document-generation scripts removed; only files implementing FRs/NFRs retained (see `docs/PROJECT_STRUCTURE.md`).

### 13.2 Layered architecture (vs §3.1) — all five layers MET

| Layer | Implementation |
|---|---|
| L1 Infrastructure | `edge/edge_client.py`, `database/connection.py`, OS-level |
| L2 Data Access | `database/models.py` + 8 repositories under `database/repositories/` |
| L3 Business Logic | `modules/recognition`, `modules/monitoring`, `modules/upselling`, `modules/alerts`, `detection/person_detector.py` |
| L4 Application | FastAPI `api/app.py` + 14 routers under `api/routes/` |
| L5 Presentation | React SPA `frontend/src/` — pages + components + services |

### 13.3 Component map (vs §3.2, §4) — as-built

| ID | Baseline name | Implementation file | Status | Notes |
|---|---|---|---|---|
| C1 | Camera Interface | `edge/edge_client.py` | **MET** | OpenCV V4L2. **Latest-frame thread pattern** added: a `capture_loop` grabs at FPS and keeps only the freshest frame; main loop drops stale frames. `BUFFERSIZE=1`. This change lifted sustained throughput from <1 fps to the 15 fps target. |
| C2 | PIR Sensor | `edge/edge_client.py` | **REMOVED** | HC-SR505 unreliable (stuck-HIGH; second sensor burned). Per FR-7.8 always-on override, class commented out; always-on is the only mode. |
| C3 | Frame Streamer | `edge/edge_client.py` | **MET** | JPEG + bounded queue. Default quality **70%** (down from 80 after Stage-C found the difference imperceptible). |
| C4 | Edge Network Client | `edge/edge_client.py` | **MET** | HTTP POST + retry/backoff (1,2,4,8s), NFR-3.5 buffering (200), heartbeat. `SERVER_URL = http://192.168.99.1:5000`. |
| C5 | Person Detector | `detection/person_detector.py` | **MET** | YOLOv8n on **CUDA** (`device='0'`, `imgsz=960`), conf=0.5, FP16. `CentroidTracker` tuned (`max_distance 80→250`, `max_disappeared 30→8`) — eliminated ghost-track inflation. |
| C6 | Face Recognition | `modules/recognition/face_recognizer.py` | **MET** | MTCNN + InceptionResnetV1 (**512-D**) on CUDA. Threshold **0.80**. **Vectorised (N,512) matrix** matcher for ~8 ms p95 at N=1000. Runtime monkey-patch `_facenet_patch.py` fixes upstream MTCNN stage-2/3 IndexError + degenerate-bbox crash. |
| C7 | Database Module | `database/connection.py` + `models.py` + `repositories/` | **MET** | Schema additions to `Guest`: `id_type, id_number, is_watched, watch_reason, is_staff_badge, staff_badge_label`. `_utcnow()` switched to local-time `datetime.now()` to fix dashboard timestamp drift. |
| C8 | Recommendation Engine | `modules/upselling/recommendation_engine.py` | **MET** | New rule set (see §13.5) — popularity / VIP / dietary / room-type / Arabic-dining / winback / business-pattern. |
| C9 | Alert Manager | `modules/alerts/alert_notifier.py` | **MET** | Subscribes to `watchlist_match` topic too; persists `AlertType.WANTED` with audit trail; per-(kind,id) cooldown; console-fallback outbox for email/SMS. |
| C10 | Lobby Monitor | `modules/monitoring/person_monitor.py` | **MET** | `TrackedPerson.is_staff_badge`; `check_thresholds()` short-circuits badged tracks; `tracking_timeout` 30s→8s. |
| C11 | Network Server | `api/app.py` + **15 routers** (added `audio`) | **MET** | FastAPI, CORS, lifespan with **embedding-cache hydration on startup** (fixed empty-cache-on-restart bug), SPA fallback. |
| C12 | Live Feed (frontend) | `LiveFeedPanel.tsx` | **MET** | Canvas overlay **4-tier color scheme** (blue staff / red watched / green known / gold unknown) + pulsing "WATCHLIST MATCH" banner. |
| C13 | Guest Info Panel | `GuestInfoPanel.tsx` | **MET** | **Multi-person stack** (`Map<guest_id,…>`, 10s TTL, max 6 cards). |
| C14 | Alert Panel | `AlertPanel.tsx` | **MET** | Renders WANTED in addition to security/assistance/VIP. |
| C15 | Recommendation Panel | `RecommendationPanel.tsx` | **MET** | Shows name + category + price + reasoning. |
| C16 | Search Component | `GuestLookupPage.tsx` | **MET** | Multi-field (name/first/last/email/phone/id_number) + "Open full profile". |
| C17 | Enrollment Component | `EnrollmentPage.tsx` | **MET** | Tab strip: Live capture + Upload photo (passport/ID). |
| **C18** (new) | Reservations Page | `ReservationsPage.tsx` | **MET** | 3 tabs (In-House/Arrivals/Departures), 5 derived status badges. |
| **C19** (new) | Guest Profile Page | `GuestProfilePage.tsx` | **MET** | `/guests/:id` — stat strip, ID-document panel, reservation/recommendation history, inline face-enrollment, admin staff-badge toggle. |
| **C20** (new) | Watchlist Page | `WatchlistPage.tsx` | **MET** | Flagged guests + search-to-add; per-guest watch reason shown in WANTED alert. |
| **C21** (new) | Live Translation Page | `LiveTranslationPage.tsx` | **MET** | `/ws/translation` socket; subscriber-count gates Whisper. |
| **C22** (new) | Speech Translator | `modules/speech/translator.py` | **MET** | faster-whisper `small` on CUDA, beam=5, initial_prompt biased to Lebanese Arabic/French/English, `task="translate"` → English, lazy load. |
| **C23** (new) | Audio Edge Client | `edge/audio_client.py` | **MET** | PyAudio 8s WAV chunks → `/api/audio/chunk`; separate systemd service. |
| **C24** (new) | Audio ingest route | `api/routes/audio.py` | **MET** | `/api/audio/chunk` (Pi-key) + `/api/audio/status`; bounded ring buffer; subscriber-gated Whisper dispatch. |
| **C25** (new) | PMS CSV Importer | `scripts/import_pms.py` | **MET** | `--generate-sample`, `--dry-run`, idempotent upsert by email/reservation_code. |

### 13.4 Module-naming note

The baseline §4 used illustrative module filenames (`camera_module.py`, `pir_module.py`, `network_client.py`, `db_manager.py`, `business/recommendation_engine.py`, `alerts/alert_manager.py`, `monitoring/lobby_monitor.py`). The delivered repository consolidates the edge components into a single `edge/edge_client.py` and uses the `modules/` + `detection/` + `database/` + `api/` package layout shown in §13.2/§13.3. Behaviour is unchanged; only file organisation differs. The authoritative file map is `docs/SDD_COMPLIANCE.md`.

### 13.5 Recommendation engine — as-built rule set (vs §4.2.5 / §7.4)

The baseline R1–R8 (loyalty upgrade, service repeat, business, high spender, VIP, long stay, special occasion, late checkout) were replaced by a **seven-rule additive engine** that better fits the actual `Service`/`Guest` schema and the explainability requirement:

| Rule | Trigger | Boost | Rationale string |
|---|---|---|---|
| R1 | always | popularity_score | Popularity baseline (**statistics-driven** — see §13.6) |
| R2 | VIP + category ∈ {spa, dining, room_service} | +0.30 | VIP boost ({category}) |
| R3 | guest dietary preference ⊂ service description | +0.20 | Matches dietary preference |
| R4 | guest room-type preference ⊂ service description | +0.10 | Matches room-type preference |
| R5 | language == "ar" AND category == dining | +0.15 | Curated for Arabic-speaking guests |
| R6 | returning guest, no active reservation, past-accepted service | +0.30 | Winback bundle |
| R7 | business pattern (≥2 short Mon–Thu stays) | ±0.20 | Business-traveller pattern |

Scores cap at 1.0, sorted descending, top-5 persisted with the rationale string. FR-2 intent (rank, explain, accept/decline/defer, log) is fully met.

### 13.6 Algorithm / interface deltas

- **Face recognition (§7.2):** embedding **512-D** (not 128-D); threshold **0.80** (not 0.70); matcher is a single `(N,512)·(512,)` matrix-vector product (the per-pair loop is kept only for unit tests).
- **Person detection (§7.1):** inference at **`imgsz=960` on CUDA** (FP16), not 640×640 CPU; class restricted to person at the call (`classes=[0]`).
- **Recommendation R1 popularity baseline (§7.4):** `Service.popularity_score` is now **statistics-driven** rather than a static constant. `ServiceRepository.recompute_popularity()` derives it from recommendation outcomes using a Laplace-smoothed acceptance rate — `(accepted + 1) / (accepted + declined + 2)` — so it is the neutral 0.5 with no history and converges to the true acceptance ratio with volume. It refreshes live when a recommendation is accepted/declined and on-demand via `POST /api/services/recompute-popularity`.
- **Alert dispatch (§4.2.6):** per-incident templates (`notification_templates.py`) for email (branded HTML + text) and WhatsApp/SMS; email recipients **blind-copied (Bcc)**; Twilio channel selectable (`TWILIO_CHANNEL=sms|whatsapp`, incl. WhatsApp Sandbox).
- **At-rest encryption (§10.1.1):** **AES-256-GCM** authenticated framing (`version byte ∥ 12-byte nonce ∥ ciphertext ∥ 16-byte tag`, base64) in `utils/crypto_utils.py`, not AES-256-CBC. Key from `ENCRYPTION_KEY`. A legacy Fernet reader is retained for back-compat.
- **Transport (§10.1.2):** HTTPS/WSS provided by a **Caddy reverse proxy** (`Caddyfile` in repo root) that terminates TLS in front of the app on `127.0.0.1:5000` and upgrades `/ws` to WSS automatically. The app itself still speaks plain HTTP/WS on localhost; no application code changes were needed. Site blocks for `localhost` (auto-trusted), LAN IP (`tls internal`), and public domain (Let's Encrypt) are included.
- **Ports/topology (§3.3, §12):** a single FastAPI process serves API + WebSocket + SPA on one port; nodes joined by a direct Cat-6 cable on `192.168.99.0/24` (server `.1`, Pi `.2`), not the baseline `192.168.1.0/24` multi-port layout.
- **Edge framework:** FastAPI (not Flask). 15 routers (added `audio`). Lifespan hydrates the face-engine embedding cache before serving.
- **New subsystem (C21–C24):** live speech translation (faster-whisper), audio edge client, audio ingest route, Live Translation page — not in the baseline; addresses the trilingual reception use case.

### 13.7 Cross-references

- File-by-file component/algorithm/sequence mapping with status: `docs/SDD_COMPLIANCE.md`.
- Requirements-level deviations: `SysRS_System_Requirements_Specification.md` §9.
- Quantitative benchmarks and engineering-issue narrative: project report, Chapter V.

---

*End of Software Design Document — Version 1.1*
*Document prepared by Youssef Kassar — CCE Department, AUL — June 2026*
