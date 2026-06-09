# System Requirements Specification (SysRS)
## Compact AI-Powered Smart Reception Assistant

### Document Information

| Field | Value |
|---|---|
| Document Title | System Requirements Specification (SysRS) |
| Project Name | Compact AI-Powered Smart Reception Assistant |
| Author | Youssef Kassar |
| Institution | Arts, Sciences & Technology University in Lebanon (AUL) |
| Department | Computer & Communications Engineering (CCE) |
| Standard | IEEE 830-1998 (IEEE Recommended Practice for Software Requirements Specifications) |
| Version | 1.1 |
| Date | June 2026 |
| Status | Released for submission |

### Revision History

| Version | Date | Author | Description |
|---|---|---|---|
| 0.1 | March 2026 | Youssef Kassar | Initial draft |
| 0.5 | March 2026 | Youssef Kassar | Added functional requirements |
| 1.0 | April 2026 | Youssef Kassar | Complete SysRS for submission |
| 1.1 | June 2026 | Youssef Kassar | As-built reconciliation. Baseline requirements (v1.0) preserved verbatim; added **Section 9 — Design Deviations (v1.1 As-Built)** recording every divergence between this specification and the delivered system, with rationale. See also `docs/SYSRS_COMPLIANCE.md`. |

> **Reading note (v1.1).** Sections 1–8 below are the **original April 2026 requirements baseline** and are preserved as written, so this document remains the pre-implementation reference the project was built against. Where the delivered system diverged from a requirement (e.g. the PIR motion sensor, the embedding dimensionality, the recognition threshold, the at-rest cipher, the web framework, the budget), the change is **not** silently edited into the baseline — it is recorded in **Section 9 — Design Deviations (v1.1 As-Built)** with the reason and the requirement IDs affected. This preserves the engineering narrative (what was specified → what was built → why).

---

## Table of Contents

1. Introduction
2. Overall Description
3. System Features and Requirements
4. External Interface Requirements
5. Use Cases
6. System Constraints
7. Acceptance Criteria
8. Appendices
9. **Design Deviations (v1.1 As-Built)** — new in v1.1

---

## 1. Introduction

### 1.1 Purpose

The purpose of this System Requirements Specification (SysRS) document is to provide a comprehensive and detailed description of the requirements for the **Compact AI-Powered Smart Reception Assistant** system. This document is intended to serve as the primary reference for the technical and functional requirements governing the design, development, testing, and deployment of the system.

This SysRS is prepared in accordance with the IEEE 830-1998 standard for Software Requirements Specifications and is intended for the following audiences:

- **Project Developer (Youssef Kassar):** To serve as the authoritative requirements baseline for all implementation activities.
- **Academic Supervisors and Jury Members:** To evaluate the completeness, correctness, and feasibility of the proposed system.
- **Future Maintainers:** To understand the full scope of system capabilities and constraints for maintenance and extension purposes.

This document defines what the system shall do (functional requirements), how well it shall perform (non-functional requirements), and the interfaces through which it communicates with external entities.

### 1.2 Scope

The **Compact AI-Powered Smart Reception Assistant** is an intelligent, cost-effective system designed to assist hotel reception staff by automating guest identification, providing personalized service recommendations, and monitoring lobby activity for security and guest-assistance purposes.

The system is architected as a hybrid distributed system comprising:

1. **Edge Device (Raspberry Pi 4):** Responsible for real-time video capture via a USB webcam, motion detection via a PIR (Passive Infrared) sensor, and streaming data to the AI server over a local network.
2. **AI Server (Laptop):** Responsible for computationally intensive tasks including person detection (YOLO/MobileNet), face recognition (FaceNet/DeepFace), recommendation generation, alert management, and serving the web-based dashboard.
3. **Web Dashboard (React):** Provides a real-time graphical user interface for reception staff and duty managers to view live feeds, guest information, alerts, and recommendations.

**In Scope:**

- Real-time video capture and streaming from Raspberry Pi to Laptop server.
- Person detection and tracking within video frames.
- Face detection, embedding extraction, and face matching against a local database.
- Guest profile and reservation retrieval upon successful identification.
- Rule-based upselling and service recommendation engine.
- Lobby monitoring with detection of non-in-house guests and guests requiring assistance.
- Alert generation and delivery via email and SMS to duty managers.
- Web-based dashboard with live feed, detection overlays, guest information panels, and alert management.
- Local SQLite database for guest profiles, facial embeddings, reservations, visit history, and alert logs.
- Motion-triggered camera activation via PIR sensor.

**Out of Scope:**

- Cloud-based deployment or cloud AI inference services.
- Integration with third-party Property Management Systems (PMS) or Channel Managers.
- Voice recognition or natural language processing.
- Mobile application development.
- Multi-property (multi-hotel) deployment.
- Payment processing or billing integration.

> **v1.1 note:** Two in-scope/out-of-scope items moved during implementation. See §9 — the PIR-triggered activation (in scope) was superseded by always-on capture, and a live **speech-translation** capability was added (adjacent to the "voice recognition / NLP" out-of-scope item, but limited to translation-to-English, not command NLP).

### 1.3 Definitions, Acronyms, and Abbreviations

| Term | Definition |
|---|---|
| AI | Artificial Intelligence — the simulation of human intelligence by machines. |
| API | Application Programming Interface — a set of protocols for building software. |
| AUL | Arts, Sciences & Technology University in Lebanon. |
| CCE | Computer & Communications Engineering. |
| CNN | Convolutional Neural Network — a deep learning architecture for image analysis. |
| CRUD | Create, Read, Update, Delete — the four basic database operations. |
| CSS | Cascading Style Sheets — a style sheet language for web documents. |
| CV | Computer Vision — a field of AI enabling machines to interpret visual data. |
| Dashboard | A web-based graphical user interface for system monitoring and interaction. |
| DeepFace | A lightweight Python face recognition and facial attribute analysis framework. |
| Edge Device | A computing device that performs processing at the data source (Raspberry Pi 4). |
| Embedding | A numerical vector representation of a face used for comparison and matching. |
| FaceNet | A face recognition system developed by Google that maps faces to a fixed-length embedding. |
| FastAPI | A modern, high-performance Python web framework for building APIs. |
| Flask | A lightweight Python web framework for building web applications and APIs. |
| FPS | Frames Per Second — a measure of video processing throughput. |
| GPIO | General-Purpose Input/Output — configurable digital signal pins on Raspberry Pi. |
| GUI | Graphical User Interface. |
| HTTP | Hypertext Transfer Protocol — the foundation of data communication on the web. |
| HTTPS | HTTP Secure — HTTP with encryption via TLS/SSL. |
| IEEE | Institute of Electrical and Electronics Engineers. |
| JSON | JavaScript Object Notation — a lightweight data interchange format. |
| MobileNet | A lightweight CNN architecture optimized for mobile and edge devices. |
| NMS | Non-Maximum Suppression — an algorithm to filter overlapping detections. |
| OpenCV | Open Source Computer Vision Library — a library for real-time computer vision. |
| ORM | Object-Relational Mapping — a technique for converting between databases and objects. |
| PIR | Passive Infrared — a sensor that detects infrared radiation from warm bodies. |
| REST | Representational State Transfer — an architectural style for distributed systems. |
| RPi | Raspberry Pi — a small single-board computer. |
| SMTP | Simple Mail Transfer Protocol — a protocol for sending email messages. |
| SQL | Structured Query Language — a language for managing relational databases. |
| SQLAlchemy | A Python SQL toolkit and ORM library. |
| SQLite | A self-contained, serverless relational database engine. |
| SysRS | System Requirements Specification. |
| TCP/IP | Transmission Control Protocol/Internet Protocol — the internet protocol suite. |
| TLS | Transport Layer Security — a cryptographic protocol for secure communications. |
| UI | User Interface. |
| USB | Universal Serial Bus — a standard for connecting peripherals. |
| V4L2 | Video4Linux2 — a Linux API for video capture devices. |
| WebSocket | A communication protocol providing full-duplex channels over TCP. |
| WSS | WebSocket Secure — WebSocket over TLS. |
| YOLO | You Only Look Once — a real-time object detection algorithm. |

### 1.4 References

| Ref. # | Title | Author/Organization | Date |
|---|---|---|---|
| [1] | IEEE 830-1998: IEEE Recommended Practice for Software Requirements Specifications | IEEE | 1998 |
| [2] | IEEE 29148-2018: Systems and Software Engineering — Life Cycle Processes — Requirements Engineering | IEEE | 2018 |
| [3] | YOLO: Real-Time Object Detection | J. Redmon et al. | 2016 |
| [4] | FaceNet: A Unified Embedding for Face Recognition and Clustering | F. Schroff, D. Kalenichenko, J. Philbin (Google) | 2015 |
| [5] | MobileNets: Efficient Convolutional Neural Networks for Mobile Vision Applications | A. G. Howard et al. (Google) | 2017 |
| [6] | DeepFace: Closing the Gap to Human-Level Performance in Face Verification | Y. Taigman et al. (Facebook) | 2014 |
| [7] | Flask Web Development Documentation | Pallets Projects | 2024 |
| [8] | FastAPI Documentation | S. Ramírez | 2024 |
| [9] | React Documentation | Meta (Facebook) | 2024 |
| [10] | OpenCV Documentation | OpenCV Team | 2024 |
| [11] | Raspberry Pi 4 Model B Specifications | Raspberry Pi Foundation | 2019 |
| [12] | General Data Protection Regulation (GDPR) | European Parliament | 2016 |
| [13] | SQLite Documentation | D. R. Hipp | 2024 |

### 1.5 Overview

The remainder of this document is organized as follows:

- **Section 2 — Overall Description:** Provides a high-level overview of the product, including its context within the broader hotel environment, a summary of its primary functions, user characteristics, constraints, and assumptions.
- **Section 3 — System Features and Requirements:** Contains the detailed functional and non-functional requirements, organized by feature area with unique identifiers for traceability.
- **Section 4 — External Interface Requirements:** Specifies the hardware, software, and communication interfaces required by the system.
- **Section 5 — Use Cases:** Describes the primary use case scenarios, including actors, preconditions, main flows, alternative flows, and postconditions.
- **Section 6 — System Constraints:** Summarizes budget, timeline, hardware, and operational constraints.
- **Section 7 — Acceptance Criteria:** Defines the criteria that must be satisfied for the system to be accepted.
- **Section 8 — Appendices:** Contains supplementary information and diagrams.
- **Section 9 — Design Deviations (v1.1 As-Built):** *(new in v1.1)* Records every divergence between this specification and the delivered system, with rationale and affected requirement IDs.

---

## 2. Overall Description

### 2.1 Product Perspective

The Compact AI-Powered Smart Reception Assistant is a standalone, self-contained system designed for deployment in a hotel reception and lobby environment. It does not replace any existing system but rather augments the capabilities of reception staff through intelligent automation.

#### 2.1.1 System Interfaces

The system operates as a two-node distributed architecture:

- **Node 1 — Edge Device (Raspberry Pi 4):** Interfaces with physical sensors (PIR) and camera hardware (USB webcam). Communicates with the AI server over a local area network via HTTP REST API and WebSocket connections.
- **Node 2 — AI Server (Laptop):** Hosts the AI inference engine, database, alert system, and dashboard backend. Communicates with external email (SMTP) and SMS (Twilio API) services for alert delivery.

The system does not interface with any existing hotel Property Management System (PMS) in the current version. All guest data is managed internally within the SQLite database.

```
┌─────────────────────────────────────────────────────────────────────┐
│ LOCAL AREA NETWORK                                                   │
│  ┌──────────────────────┐         ┌──────────────────────────────┐  │
│  │ EDGE DEVICE (RPi)    │  HTTP/  │ AI SERVER (Laptop)           │  │
│  │  USB Webcam          │   WS    │  Flask/FastAPI Server        │  │
│  │  PIR Sensor (GPIO)   │ ──────► │   YOLO / MobileNet           │  │
│  │  Network Client      │         │   FaceNet/DeepFace           │  │
│  │                      │         │   SQLite DB                  │  │
│  └──────────────────────┘         │   React Dashboard            │  │
│                                   └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

#### 2.1.2 User Interfaces

The system provides a single primary user interface:

- **Web-Based Dashboard (React):** Accessible via a modern web browser (Chrome, Firefox, Edge) from any device on the local network. The dashboard features:
  - A live video feed panel with detection overlays (bounding boxes, labels).
  - A guest information panel displaying identified guest profiles, photos, and reservation details.
  - An upselling recommendations panel with suggested services and acceptance tracking.
  - An alerts panel showing real-time and historical alerts with severity levels.
  - A search interface for querying guest records.
  - A settings panel for system configuration.

The dashboard shall be designed for use on a desktop or laptop screen (minimum resolution 1280×720) and shall not require any client-side installation beyond a web browser.

#### 2.1.3 Hardware Interfaces

| Hardware | Interface Type | Description |
|---|---|---|
| Acer 1080p USB Webcam | USB 2.0/3.0 | Connected to Raspberry Pi 4 via USB port. Provides 1920×1080 video at up to 30 FPS. |
| PIR Motion Sensor (HC-SR501) | GPIO (Digital) | Connected to Raspberry Pi 4 GPIO pin. Outputs HIGH (3.3V) when motion is detected. |
| microSD Card (32GB+) | SD/microSD | Storage medium for Raspberry Pi OS, application code, and local logs. |
| Raspberry Pi 4 Model B (4GB RAM) | Ethernet / Wi-Fi | Connected to the local network for communication with the AI server. |
| Laptop (AI Server) | Ethernet / Wi-Fi | Connected to the local network. Hosts AI models, database, and web server. |

#### 2.1.4 Software Interfaces

| Software | Version | Purpose |
|---|---|---|
| Raspberry Pi OS (Debian-based) | Bullseye or later | Operating system for the edge device. |
| Windows 10/11, macOS, or Ubuntu Linux | Current | Operating system for the AI server laptop. |
| Python | 3.9+ | Primary programming language for all backend components. |
| OpenCV | 4.x | Video capture, frame processing, and image manipulation. |
| YOLO (Ultralytics YOLOv5/v8) | Latest | Person detection in video frames. |
| MobileNet SSD | v2 | Lightweight alternative for person detection. |
| FaceNet (facenet-pytorch) | Latest | Facial embedding extraction for face recognition. |
| DeepFace | Latest | Alternative face recognition and verification framework. |
| Flask or FastAPI | 2.x / 0.100+ | Backend web framework for REST API and WebSocket server. |
| React | 18.x | Frontend JavaScript library for the dashboard UI. |
| SQLite | 3.x | Embedded relational database for all persistent data. |
| SQLAlchemy | 2.x | Python ORM for database operations. |
| NumPy | 1.24+ | Numerical computations, particularly for embedding operations. |
| smtplib (Python stdlib) | — | Email sending for alert notifications. |
| Twilio Python SDK | Latest | SMS sending for alert notifications. |

#### 2.1.5 Communication Interfaces

| Protocol | Usage | Direction |
|---|---|---|
| HTTP/HTTPS (REST) | Frame upload, API requests, responses | RPi → Laptop, Dashboard → Laptop |
| WebSocket / WSS | Real-time live feed streaming, detection updates, alert push | Laptop ↔ Dashboard, RPi → Laptop |
| TCP/IP | Underlying transport for all network communication | Bidirectional |
| SMTP | Email alert delivery to duty managers | Laptop → Email Server |
| HTTPS (Twilio API) | SMS alert delivery to duty managers | Laptop → Twilio Cloud |

### 2.2 Product Functions

At a high level, the Compact AI-Powered Smart Reception Assistant provides the following major functions:

1. **Guest Identification (F1):** Automatically identifies returning guests by capturing and analyzing facial features from the reception-area camera, matching them against a stored database of guest facial embeddings, and retrieving their profile and reservation information for display to reception staff.
2. **Upselling Recommendation (F2):** Analyzes the identified guest's profile, visit history, and preference data to generate personalized recommendations for premium services, room upgrades, and amenities, displayed to reception staff to facilitate targeted upselling.
3. **Lobby Monitoring (F3):** Continuously monitors the hotel lobby area via the camera feed, detecting and tracking all persons present, differentiating between in-house guests and non-in-house visitors, and identifying individuals who may require assistance.
4. **Alert Management (F4):** Generates, delivers, and logs alerts for security-relevant events (e.g., unrecognized persons lingering in the lobby) and guest-assistance events, sending notifications to duty managers via email and SMS.
5. **Dashboard Visualization (F5):** Provides a comprehensive, real-time web-based dashboard for reception staff and duty managers to view the live camera feed with detection overlays, guest information, recommendations, alerts, and historical data.
6. **Data Management (F6):** Maintains a local SQLite database storing guest profiles, facial embeddings, reservation records, visit history, service recommendations, and alert logs, supporting full CRUD operations.
7. **Motion-Triggered Activation (F7):** Uses a PIR sensor to detect physical motion in the reception/lobby area, triggering the camera capture and processing pipeline to optimize resource usage and extend hardware lifespan.

### 2.3 User Characteristics

The system is designed for three categories of users:

#### 2.3.1 Reception Staff (Primary Users)
- **Role:** Hotel front-desk receptionists who interact with guests during check-in, check-out, and general inquiries.
- **Technical Proficiency:** Low to moderate. Familiar with basic computer operations but not expected to have technical or IT background.
- **Interaction Pattern:** Continuous use during shifts. Will monitor the dashboard, view guest identification results, act on upselling recommendations, and respond to alerts.
- **Requirements:** The system must present information in a clear, intuitive manner without requiring technical knowledge. Response times must be fast enough to support real-time guest interactions.

#### 2.3.2 Duty Managers (Secondary Users)
- **Role:** Hotel duty managers responsible for security oversight, guest satisfaction, and operational management.
- **Technical Proficiency:** Low to moderate. Familiar with standard business applications.
- **Interaction Pattern:** Periodic monitoring of the dashboard and responding to alerts received via email/SMS. May not be physically at the reception desk.
- **Requirements:** Alerts must be delivered promptly and contain sufficient context (location, timestamp, description, severity) to enable appropriate action.

#### 2.3.3 System Administrators (Tertiary Users)
- **Role:** IT personnel or the project developer responsible for system installation, configuration, maintenance, and troubleshooting.
- **Technical Proficiency:** High. Comfortable with Linux administration, Python, networking, and database management.
- **Interaction Pattern:** Initial setup, periodic maintenance, software updates, database backup, and troubleshooting.
- **Requirements:** The system must provide comprehensive logs, clear configuration files, and documented setup procedures. Modular architecture shall facilitate component-level debugging and replacement.

### 2.4 Constraints

#### 2.4.1 Regulatory Constraints
- **Data Protection:** The system captures and stores biometric data (facial images and embeddings), classified as sensitive personal data under regulations such as the GDPR. The system must implement appropriate safeguards including encryption, access control, data minimization, and consent mechanisms.
- **Privacy:** Continuous video monitoring of public areas (lobby) must comply with local privacy laws. Signage informing guests of camera surveillance is assumed to be the responsibility of the hotel operator.
- **Consent:** The system shall provide mechanisms for guests to opt out of facial recognition. Guest enrollment shall require explicit consent.

#### 2.4.2 Hardware Constraints
- **Processing Power (Edge):** The Raspberry Pi 4 (4GB RAM, Quad-core ARM Cortex-A72 @ 1.5 GHz) has limited processing power, precluding on-device AI inference for complex models. All heavy computation is offloaded to the laptop server.
- **Processing Power (Server):** The laptop AI server must have sufficient CPU/GPU resources to run YOLO and FaceNet inference in near real-time. A dedicated GPU is recommended but not required.
- **Camera Resolution:** The Acer 1080p webcam provides a fixed resolution of 1920×1080. Face recognition accuracy depends on the subject's distance from the camera and adequate lighting.
- **Storage:** The microSD card on the Raspberry Pi has limited read/write endurance. Persistent data storage is hosted on the laptop's SSD/HDD.
- **Network Bandwidth:** The local network must support continuous streaming of video frames (estimated 2–5 Mbps for compressed 1080p at 15 FPS).

#### 2.4.3 Budget Constraints
- **Total Budget:** $59–$66 USD.
- **Budget Allocation:**
  - Raspberry Pi 4 (4GB): ~$35–$40
  - Acer 1080p USB Webcam: ~$15–$18
  - PIR Sensor (HC-SR501): ~$2–$3
  - microSD Card (32GB): ~$7–$8
  - Miscellaneous (cables, jumper wires): ~$3–$5
- **Software:** All software components are open-source and free of charge.
- **Laptop AI Server:** Assumed to be pre-existing hardware (student's personal laptop); not included in the budget.

#### 2.4.4 Time Constraints
- **Total Duration:** 2 months.
- **Phase 1 (Midterm Delivery — Month 1):** Core infrastructure setup, video capture pipeline, person detection, basic face recognition, and initial dashboard.
- **Phase 2 (Final Delivery — Month 2):** Advanced face recognition, upselling engine, alert system, lobby monitoring, full dashboard, testing, and documentation.

### 2.5 Assumptions and Dependencies

**Assumptions**

| ID | Assumption |
|---|---|
| A-1 | The hotel lobby has adequate lighting for the camera to capture usable facial images at a minimum resolution of 100×100 pixels per face. |
| A-2 | Guests will face the camera at an approximately frontal angle (±30° yaw) during the recognition window. |
| A-3 | The Raspberry Pi 4 and the AI server laptop are connected to the same local area network with stable connectivity. |
| A-4 | The laptop AI server is powered on and running during all operational hours. |
| A-5 | Guest enrollment is performed manually by reception staff during the guest's first visit or check-in. |
| A-6 | The system will operate in a controlled indoor environment. |
| A-7 | The camera is positioned at a fixed location at or near the reception desk, covering the approach path of guests. |
| A-8 | The hotel provides a power supply and network connectivity at the installation location. |
| A-9 | The laptop has Python 3.9+ and Node.js installed, or the system administrator can install them. |
| A-10 | Duty managers have smartphones capable of receiving email and SMS notifications. |

**Dependencies**

| ID | Dependency | Impact if Unavailable |
|---|---|---|
| D-1 | Raspberry Pi 4 hardware availability | Cannot deploy edge device; system inoperable. |
| D-2 | Local network connectivity | RPi cannot communicate with laptop; system inoperable. |
| D-3 | Pre-trained YOLO model weights | Cannot perform person detection; core function unavailable. |
| D-4 | Pre-trained FaceNet/DeepFace model weights | Cannot perform face recognition; guest identification unavailable. |
| D-5 | Internet connectivity (for alerts) | Email and SMS alerts cannot be delivered; dashboard still functional. |
| D-6 | Twilio account and API key (for SMS) | SMS alerts unavailable; email alerts still functional. |
| D-7 | SMTP server credentials (for email) | Email alerts unavailable; SMS and dashboard alerts still functional. |
| D-8 | Adequate lighting in lobby | Face recognition accuracy degrades significantly in low light. |

---

## 3. System Features and Requirements

### 3.1 Functional Requirements

All functional requirements are assigned a unique identifier in the format **FR-X.Y** where X denotes the feature group and Y denotes the specific requirement. Priority levels:

- **P1 (Must Have):** Essential for system operation; required for midterm or final delivery.
- **P2 (Should Have):** Important for full functionality; targeted for final delivery.
- **P3 (Nice to Have):** Desirable but not critical; implemented if time permits.

#### FR-1: Guest Identification System
*The system shall identify returning guests by capturing their facial image, extracting facial embeddings, and matching them against a stored database of known guest embeddings.*

| Req. ID | Requirement | Priority | Phase |
|---|---|---|---|
| FR-1.1 | The system shall capture video frames from the connected USB webcam at a minimum resolution of 1920×1080 pixels. | P1 | 1 |
| FR-1.2 | The system shall detect human faces within captured video frames using a face detection algorithm (e.g., MTCNN, Haar Cascade, or RetinaFace). | P1 | 1 |
| FR-1.3 | The system shall crop and align detected face regions to a standardized size (160×160 pixels for FaceNet) for embedding extraction. | P1 | 1 |
| FR-1.4 | The system shall extract a 128-dimensional (FaceNet) or 4096-dimensional (DeepFace/VGGFace) facial embedding vector from each detected and aligned face. | P1 | 1 |
| FR-1.5 | The system shall compare the extracted embedding against all stored embeddings in the database using cosine similarity or Euclidean distance. | P1 | 1 |
| FR-1.6 | The system shall consider a match positive if the similarity score exceeds a configurable threshold (default: cosine similarity ≥ 0.70). | P1 | 1 |
| FR-1.7 | The system shall retrieve the full guest profile (name, contact, preferences, notes) from the database upon a positive match. | P1 | 1 |
| FR-1.8 | The system shall retrieve all associated reservation details (room number, check-in/out dates, room type, rate, special requests) for the identified guest. | P1 | 2 |
| FR-1.9 | The system shall display the identified guest's name, profile photo, profile summary, and reservation details on the dashboard within 3 seconds of detection. | P1 | 2 |
| FR-1.10 | The system shall flag unrecognized faces and display them as "Unknown Guest" on the dashboard with the captured face image. | P1 | 2 |
| FR-1.11 | The system shall allow reception staff to enroll a new guest by capturing their face and creating a profile entry through the dashboard. | P1 | 2 |
| FR-1.12 | The system shall support storing multiple facial embeddings per guest (up to 5) to improve recognition accuracy across different angles and lighting conditions. | P2 | 2 |
| FR-1.13 | The system shall log all identification events (timestamp, guest ID or "unknown", confidence score, camera source) in the database. | P2 | 2 |
| FR-1.14 | The system shall display the confidence score of each identification alongside the guest information on the dashboard. | P3 | 2 |
| FR-1.15 | The system shall handle multiple simultaneous faces in a single frame, identifying each independently. | P2 | 2 |

#### FR-2: Upselling Recommendation System
*The system shall analyze identified guest profiles and visit histories to generate personalized upselling recommendations for premium services, upgrades, and amenities.*

| Req. ID | Requirement | Priority | Phase |
|---|---|---|---|
| FR-2.1 | The system shall analyze the identified guest's visit history, including number of previous stays, average spend, room types booked, and services used. | P1 | 2 |
| FR-2.2 | The system shall analyze the guest's stored preferences (preferred room type, dietary restrictions, amenity preferences) for recommendation generation. | P2 | 2 |
| FR-2.3 | The system shall maintain a catalog of available upselling services (room upgrades, spa packages, dining packages, late checkout, airport transfers, etc.) with descriptions and prices. | P1 | 2 |
| FR-2.4 | The system shall generate a ranked list of up to 5 personalized upselling recommendations for each identified guest based on their profile and history. | P1 | 2 |
| FR-2.5 | The system shall apply rule-based logic for recommendation generation, including: (a) guests with 3+ stays are eligible for loyalty upgrades, (b) guests who previously purchased spa services are recommended spa packages, (c) guests on business trips are recommended meeting room add-ons. | P1 | 2 |
| FR-2.6 | The system shall display recommendations on the dashboard in a dedicated panel alongside the guest's profile information. | P1 | 2 |
| FR-2.7 | Each recommendation shall include: service name, description, price, and relevance score (percentage match to guest profile). | P2 | 2 |
| FR-2.8 | The system shall allow reception staff to mark a recommendation as "Accepted," "Declined," or "Deferred" via the dashboard. | P2 | 2 |
| FR-2.9 | The system shall log recommendation outcomes to the guest's history for future recommendation improvement. | P2 | 2 |
| FR-2.10 | The system shall display a "No recommendations available" message if no relevant services are found for a guest. | P1 | 2 |
| FR-2.11 | The system shall allow administrators to add, edit, or remove services from the upselling catalog via the dashboard settings. | P3 | 2 |

#### FR-3: Lobby Monitoring System
*The system shall continuously monitor the hotel lobby area through the camera feed, detecting and tracking persons, identifying their status (in-house guest vs. non-in-house visitor), and flagging individuals who may need assistance.*

| Req. ID | Requirement | Priority | Phase |
|---|---|---|---|
| FR-3.1 | The system shall continuously process video frames from the lobby camera to detect all persons present in the field of view. | P1 | 1 |
| FR-3.2 | The system shall detect persons using a pre-trained object detection model (YOLO or MobileNet SSD) with a minimum confidence threshold of 0.5. | P1 | 1 |
| FR-3.3 | The system shall draw bounding boxes around detected persons on the live video feed, with color-coded labels (green for recognized in-house guests, yellow for unrecognized persons, red for flagged individuals). | P1 | 2 |
| FR-3.4 | The system shall track detected persons across consecutive frames using a tracking algorithm (e.g., centroid tracking or SORT) to maintain consistent identity assignments. | P2 | 2 |
| FR-3.5 | The system shall classify each detected person as "In-House Guest" (face matched with active reservation), "Known Non-Guest" (face matched but no active reservation), or "Unknown" (no face match). | P1 | 2 |
| FR-3.6 | The system shall measure the dwell time (duration of presence) of each tracked person in the lobby area. | P2 | 2 |
| FR-3.7 | The system shall flag a person as "Needing Assistance" if they remain stationary in the lobby for more than a configurable duration (default: 5 minutes) without approaching the reception desk. | P2 | 2 |
| FR-3.8 | The system shall maintain a count of the total number of persons currently present in the lobby and display it on the dashboard. | P2 | 2 |
| FR-3.9 | The system shall log all lobby monitoring events (person detected, person left, dwell time exceeded) with timestamps. | P2 | 2 |
| FR-3.10 | The system shall display the current lobby occupancy map on the dashboard, showing approximate positions of detected persons. | P3 | 2 |
| FR-3.11 | The system shall re-attempt face recognition for "Unknown" persons at configurable intervals (default: every 30 seconds). | P3 | 2 |

#### FR-4: Alert System
*The system shall generate, deliver, and log alerts to duty managers and reception staff based on events detected during lobby monitoring and guest identification.*

| Req. ID | Requirement | Priority | Phase |
|---|---|---|---|
| FR-4.1 | The system shall generate an alert when an unrecognized person remains in the lobby beyond a configurable duration threshold (default: 10 minutes). | P1 | 2 |
| FR-4.2 | The system shall generate an alert when a person is flagged as "Needing Assistance". | P1 | 2 |
| FR-4.3 | The system shall generate a VIP alert when a guest with a VIP tag is identified at the reception area. | P2 | 2 |
| FR-4.4 | The system shall assign a severity level to each alert: Low (informational), Medium (attention required), High (immediate action required). | P1 | 2 |
| FR-4.5 | The system shall deliver alerts via email to configured duty manager email addresses using SMTP. | P1 | 2 |
| FR-4.6 | The system shall deliver alerts via SMS to configured duty manager phone numbers using the Twilio API. | P2 | 2 |
| FR-4.7 | The system shall display real-time alerts on the dashboard alert panel with visual and auditory notifications. | P1 | 2 |
| FR-4.8 | Each alert shall contain: alert ID, timestamp, severity level, alert type, description, location, and an associated image. | P1 | 2 |
| FR-4.9 | The system shall allow duty managers or reception staff to acknowledge alerts via the dashboard. | P2 | 2 |
| FR-4.10 | The system shall allow staff to resolve alerts via the dashboard with an optional resolution note. | P2 | 2 |
| FR-4.11 | The system shall log all alerts (generation, delivery, acknowledgment, resolution) in the database with complete audit trails. | P1 | 2 |
| FR-4.12 | The system shall implement a cooldown period (default: 15 minutes) to prevent duplicate alerts for the same person/event. | P2 | 2 |
| FR-4.13 | The system shall allow administrators to configure alert thresholds, recipient lists, and delivery channels via the dashboard settings. | P3 | 2 |

#### FR-5: Dashboard System
*The system shall provide a web-based dashboard as the primary user interface for reception staff and duty managers to interact with all system functions.*

| Req. ID | Requirement | Priority | Phase |
|---|---|---|---|
| FR-5.1 | The system shall serve a web-based dashboard accessible via HTTP/HTTPS on the local network from any modern web browser. | P1 | 1 |
| FR-5.2 | The dashboard shall display a live video feed with real-time detection overlays (bounding boxes, labels, confidence scores). | P1 | 2 |
| FR-5.3 | The dashboard shall display a guest information panel showing the identified guest's name, profile photo, contact information, and key profile details. | P1 | 2 |
| FR-5.4 | The dashboard shall display a reservation details panel (room number, check-in/out dates, room type, rate, special requests, balance). | P1 | 2 |
| FR-5.5 | The dashboard shall display a visit history panel (dates, room types, total spent, feedback scores). | P2 | 2 |
| FR-5.6 | The dashboard shall display an upselling recommendations panel with ranked service suggestions, prices, and accept/decline buttons. | P1 | 2 |
| FR-5.7 | The dashboard shall display an alerts panel showing active, acknowledged, and resolved alerts with filtering and sorting. | P1 | 2 |
| FR-5.8 | The dashboard shall provide guest search by name, email, phone number, or reservation ID. | P1 | 2 |
| FR-5.9 | The dashboard shall provide a guest enrollment form for registering new guests with face capture, name, contact details, and preferences. | P1 | 2 |
| FR-5.10 | The dashboard shall display a lobby overview section showing current person count, classification, and dwell times. | P2 | 2 |
| FR-5.11 | The dashboard shall provide a navigation menu to switch between views: Live Monitor, Guest Lookup, Alerts, Reports, and Settings. | P1 | 2 |
| FR-5.12 | The dashboard shall support responsive design for screens with a minimum resolution of 1280×720 pixels. | P2 | 2 |
| FR-5.13 | The dashboard shall implement auto-refresh for all real-time panels without manual page reloads. | P1 | 2 |
| FR-5.14 | The dashboard shall display a system status indicator showing connectivity to the Raspberry Pi, camera status, and AI model status. | P2 | 2 |
| FR-5.15 | The dashboard shall provide a reports section with summary statistics. | P3 | 2 |

#### FR-6: Database Management
*The system shall maintain a local SQLite database for persistent storage of all guest data, facial embeddings, reservations, visit history, alerts, and system configuration.*

| Req. ID | Requirement | Priority | Phase |
|---|---|---|---|
| FR-6.1 | The system shall store guest profiles (guest ID, first/last name, email, phone, nationality, preferences JSON, VIP status, notes, creation/updated timestamps). | P1 | 1 |
| FR-6.2 | The system shall store facial embeddings as serialized binary blobs or base64-encoded text, associated with a guest ID and capture timestamp. | P1 | 1 |
| FR-6.3 | The system shall support storing multiple embeddings per guest (up to 5) and use the average or best-match strategy during recognition. | P2 | 2 |
| FR-6.4 | The system shall store reservation records (reservation ID, guest ID FK, room number, room type, check-in/out date, rate per night, total amount, special requests, status, timestamps). | P1 | 2 |
| FR-6.5 | The system shall store visit history records (visit ID, guest ID FK, check-in/out timestamps, room number, total spend, services used JSON, feedback score, notes). | P2 | 2 |
| FR-6.6 | The system shall store alert records (alert ID, timestamp, type, severity, description, person/guest ID, image path, status, acknowledged by, resolution note, resolution timestamp). | P1 | 2 |
| FR-6.7 | The system shall store a services catalog (service ID, name, category, description, price, active status). | P1 | 2 |
| FR-6.8 | The system shall store recommendation logs (log ID, guest ID, service ID, recommendation timestamp, outcome, staff member). | P2 | 2 |
| FR-6.9 | The system shall support full CRUD operations for all database entities via the backend API. | P1 | 1 |
| FR-6.10 | The system shall enforce referential integrity via foreign key constraints between related tables. | P1 | 1 |
| FR-6.11 | The system shall implement database indexing on frequently queried columns (guest ID, email, phone, reservation status, alert status). | P2 | 2 |
| FR-6.12 | The system shall support database export to CSV format for reporting purposes. | P3 | 2 |

#### FR-7: Motion Detection
*The system shall use a PIR (Passive Infrared) sensor connected to the Raspberry Pi to detect physical motion in the reception/lobby area, triggering the camera capture and processing pipeline.*

> **⚠ v1.1 status: SUPERSEDED.** FR-7.1–FR-7.7 were superseded by always-on capture after hardware failure of the HC-SR505 sensor; **FR-7.8 (always-on override) was invoked and is the delivered mode.** See §9.2. The requirements below are preserved as the original baseline.

| Req. ID | Requirement | Priority | Phase |
|---|---|---|---|
| FR-7.1 | The system shall interface with a PIR motion sensor (HC-SR501) connected to a designated GPIO pin on the Raspberry Pi 4. | P1 | 1 |
| FR-7.2 | The system shall detect motion events when the PIR sensor output transitions from LOW to HIGH. | P1 | 1 |
| FR-7.3 | Upon detecting a motion event, the system shall activate the camera capture pipeline (if not already active) and begin capturing and streaming frames. | P1 | 1 |
| FR-7.4 | The system shall maintain the camera active for a configurable duration (default: 60 seconds) after the last motion event before entering idle mode. | P2 | 1 |
| FR-7.5 | The system shall log all motion events (timestamp, duration) in a local log file on the Raspberry Pi. | P2 | 1 |
| FR-7.6 | The system shall support a configurable sensitivity setting for the PIR sensor via a software-adjustable timeout parameter. | P3 | 2 |
| FR-7.7 | The system shall debounce PIR sensor signals to prevent false triggers, requiring a minimum interval of 2 seconds between consecutive motion events. | P2 | 1 |
| FR-7.8 | The system shall provide a manual override to keep the camera always active, bypassing the PIR trigger, configurable via the dashboard settings. | P3 | 2 |

### 3.2 Non-Functional Requirements

All non-functional requirements use the format **NFR-X.Y** where X denotes the quality attribute category.

#### NFR-1: Performance Requirements

| Req. ID | Requirement | Priority |
|---|---|---|
| NFR-1.1 | The system shall process and stream video frames from the Raspberry Pi to the AI server at a minimum rate of 15 FPS at 1080p over the local network. | P1 |
| NFR-1.2 | The person detection module shall process each frame and return detection results within 200 ms per frame on the AI server. | P1 |
| NFR-1.3 | The face recognition pipeline shall complete within 2 seconds per detected face. | P1 |
| NFR-1.4 | Alert generation (from trigger event to alert record creation) shall complete within 1 second. | P1 |
| NFR-1.5 | Alert delivery via email shall complete within 5 seconds of alert generation. | P2 |
| NFR-1.6 | Alert delivery via SMS shall complete within 10 seconds of alert generation. | P2 |
| NFR-1.7 | The dashboard shall update all real-time panels with a maximum latency of 500 ms from the server. | P1 |
| NFR-1.8 | Database queries for guest lookup (by ID, email, or phone) shall return results within 100 ms. | P1 |
| NFR-1.9 | The upselling recommendation engine shall generate recommendations within 1 second of guest identification. | P2 |
| NFR-1.10 | The system shall support a minimum database of 1,000 guest facial embeddings without degradation of recognition speed below the 2-second threshold. | P1 |
| NFR-1.11 | The Raspberry Pi shall consume no more than 80% of available CPU during peak operation. | P2 |
| NFR-1.12 | The AI server shall consume no more than 90% of available RAM during peak operation. | P2 |

#### NFR-2: Security Requirements

| Req. ID | Requirement | Priority |
|---|---|---|
| NFR-2.1 | All facial embedding data stored in the SQLite database shall be encrypted at rest using AES-256 encryption. | P1 |
| NFR-2.2 | All communication between the Raspberry Pi and the AI server shall use HTTPS or equivalent encrypted transport. | P2 |
| NFR-2.3 | WebSocket connections for live feed streaming shall use WSS (WebSocket Secure) protocol. | P2 |
| NFR-2.4 | The SQLite database file shall be protected with file-system-level permissions restricting access to the application user only. | P1 |
| NFR-2.5 | The dashboard shall require username/password authentication before granting access. | P1 |
| NFR-2.6 | The system shall support role-based access control (RBAC) with at least two roles: "staff" and "admin". | P2 |
| NFR-2.7 | API endpoints shall require authentication via API keys or session tokens. | P2 |
| NFR-2.8 | The system shall log all authentication attempts (successful and failed) with timestamps and source IP addresses. | P2 |
| NFR-2.9 | Passwords shall be stored using bcrypt hashing with a minimum work factor of 12. | P1 |
| NFR-2.10 | The system shall comply with data protection best practices, including data minimization and purpose limitation. | P1 |
| NFR-2.11 | The system shall provide a mechanism to delete a guest's facial data and profile upon request (right to erasure). | P2 |
| NFR-2.12 | The system shall implement session timeout (default: 30 minutes of inactivity) for dashboard sessions. | P2 |

#### NFR-3: Reliability Requirements

| Req. ID | Requirement | Priority |
|---|---|---|
| NFR-3.1 | The system shall achieve a minimum uptime of 95% during operational hours. | P1 |
| NFR-3.2 | The edge device shall automatically restart the capture service if it crashes, using a watchdog/process supervisor (e.g., systemd). | P1 |
| NFR-3.3 | The AI server shall automatically restart the server process if it crashes, using a process supervisor. | P1 |
| NFR-3.4 | The system shall implement a heartbeat mechanism between the RPi and the AI server, with a heartbeat interval of 10 seconds. | P2 |
| NFR-3.5 | If the network connection is lost, the RPi shall buffer captured frames locally (up to 100 frames) and transmit them when connectivity is restored. | P2 |
| NFR-3.6 | The SQLite database shall be backed up automatically at a configurable interval (default: daily at 02:00). | P2 |
| NFR-3.7 | The system shall maintain the last 7 daily backups, with older backups automatically purged. | P3 |
| NFR-3.8 | The system shall gracefully handle camera disconnection events, displaying a message and attempting reconnection every 5 seconds. | P1 |
| NFR-3.9 | The system shall continue to serve the dashboard and database functions even if the camera or PIR sensor is disconnected. | P1 |
| NFR-3.10 | All critical operations (database writes, alert deliveries) shall implement try-catch exception handling with appropriate error logging. | P1 |

#### NFR-4: Usability Requirements

| Req. ID | Requirement | Priority |
|---|---|---|
| NFR-4.1 | The dashboard UI shall be intuitive and usable by non-technical reception staff with no more than 30 minutes of training. | P1 |
| NFR-4.2 | The dashboard shall use clear labels, icons, and color-coding to convey information without requiring technical knowledge. | P1 |
| NFR-4.3 | The system shall provide clear, user-friendly error messages on the dashboard when errors occur. | P1 |
| NFR-4.4 | The initial system setup shall be completable within 30 minutes by a person with basic Linux administration skills, following the provided setup guide. | P2 |
| NFR-4.5 | The dashboard shall provide tooltip help text for all major UI elements. | P3 |
| NFR-4.6 | The dashboard shall support keyboard navigation for all primary functions. | P3 |
| NFR-4.7 | The dashboard shall use a consistent color scheme and typography throughout all views. | P1 |
| NFR-4.8 | Alerts on the dashboard shall use visual differentiation based on severity: Low (blue/info), Medium (yellow/warning), High (red/danger). | P1 |
| NFR-4.9 | The guest enrollment process shall be completable in under 2 minutes per guest. | P2 |

#### NFR-5: Scalability Requirements

| Req. ID | Requirement | Priority |
|---|---|---|
| NFR-5.1 | The system architecture shall support the addition of multiple camera sources (up to 4) in future versions without fundamental architectural changes. | P3 |
| NFR-5.2 | The database schema shall support at least 10,000 guest profiles with associated embeddings without significant query performance degradation. | P2 |
| NFR-5.3 | The dashboard shall support at least 5 concurrent users without performance degradation. | P2 |
| NFR-5.4 | The system shall be designed with modular components that can be independently scaled or replaced (e.g., swapping SQLite for PostgreSQL, or YOLO for a different model). | P2 |
| NFR-5.5 | The API design shall follow RESTful conventions, facilitating future integration with external systems (PMS, CRM). | P2 |
| NFR-5.6 | The face recognition module shall support a database of up to 50,000 embeddings with appropriate indexing strategies (e.g., approximate nearest neighbor search). | P3 |

#### NFR-6: Maintainability Requirements

| Req. ID | Requirement | Priority |
|---|---|---|
| NFR-6.1 | All source code shall include docstrings and inline comments explaining purpose, inputs, outputs, and logic. | P1 |
| NFR-6.2 | The system shall use a modular architecture with clearly defined interfaces between components. | P1 |
| NFR-6.3 | The system shall maintain structured application logs (timestamps, levels, module names, messages). | P1 |
| NFR-6.4 | Log files shall be rotated daily with a maximum retention of 30 days. | P2 |
| NFR-6.5 | The system shall use a version-controlled configuration file (e.g., `config.yaml` or `.env`) for all configurable parameters, avoiding hard-coded values. | P1 |
| NFR-6.6 | The system shall include a comprehensive README with setup instructions, architecture overview, and troubleshooting guide. | P1 |
| NFR-6.7 | The codebase shall follow PEP 8 coding style guidelines for Python code. | P2 |
| NFR-6.8 | The React frontend code shall follow established conventions and use functional components with hooks. | P2 |
| NFR-6.9 | The system shall use Git for version control with meaningful commit messages. | P1 |

---

## 4. External Interface Requirements

### 4.1 Hardware Interfaces

#### 4.1.1 Raspberry Pi 4 GPIO Interface (PIR Sensor)

| Parameter | Specification |
|---|---|
| GPIO Pin | BCM GPIO 17 (Physical Pin 11) — configurable |
| Signal Type | Digital (HIGH = 3.3V when motion detected, LOW = 0V when idle) |
| Sensor Model | HC-SR501 PIR Motion Sensor |
| Detection Range | Up to 7 meters, 120° detection angle |
| Trigger Mode | Retriggerable (H mode) |
| Delay Time | Adjustable 0.3s – 5 minutes (via hardware potentiometer) |
| Power Supply | 5V–20V DC (powered from Raspberry Pi 5V pin) |
| Connections | VCC → RPi 5V (Pin 2), GND → RPi GND (Pin 6), OUT → RPi GPIO 17 (Pin 11) |

#### 4.1.2 USB Webcam Interface

| Parameter | Specification |
|---|---|
| Device | Acer 1080p USB Webcam |
| Interface | USB 2.0 (connected to Raspberry Pi 4 USB port) |
| Resolution | 1920×1080 (Full HD) |
| Frame Rate | Up to 30 FPS |
| Format | MJPEG / YUV |
| Linux Device | `/dev/video0` (V4L2 compatible) |
| Driver | UVC (USB Video Class) — included in Raspberry Pi OS kernel |

#### 4.1.3 Network Interface

| Parameter | Specification |
|---|---|
| Raspberry Pi | Gigabit Ethernet (RJ45) or Wi-Fi (802.11ac dual-band) |
| Laptop Server | Gigabit Ethernet or Wi-Fi |
| Network Type | Local Area Network (LAN) — wired preferred for reliability |
| IP Addressing | Static IP recommended (RPi: 192.168.1.100, Laptop: 192.168.1.200 — configurable) |
| Bandwidth Requirement | Minimum 5 Mbps (for 1080p MJPEG streaming at 15 FPS) |

### 4.2 Software Interfaces

#### 4.2.1 Operating System Interfaces

| Component | OS | Interface Details |
|---|---|---|
| Raspberry Pi 4 | Raspberry Pi OS (Bullseye+) | Linux kernel 5.15+, Python 3.9+, V4L2 for camera, GPIO sysfs/libgpiod for PIR |
| Laptop AI Server | Windows 10/11, macOS 12+, or Ubuntu 20.04+ | Python 3.9+, Node.js 18+ (for React build), SQLite3 native support |
| Client (Browser) | Any OS | Chrome 90+, Firefox 88+, Edge 90+, Safari 14+ |

#### 4.2.2 Database Interface (SQLite)

| Parameter | Specification |
|---|---|
| Engine | SQLite 3.36+ |
| ORM | SQLAlchemy 2.x (Python) |
| Database File | `smart_reception.db` (located on the laptop AI server) |
| Access Pattern | Single-writer, multiple-reader (WAL mode enabled) |
| Backup | File-level copy to backup directory |

#### 4.2.3 Email Interface (SMTP)

| Parameter | Specification |
|---|---|
| Protocol | SMTP with TLS (port 587) or SMTP with SSL (port 465) |
| Library | Python `smtplib` (standard library) |
| Configuration | SMTP server address, port, username, password (stored in config file) |
| Message Format | HTML email with alert details, embedded image (base64) |

#### 4.2.4 SMS Interface (Twilio)

| Parameter | Specification |
|---|---|
| Service | Twilio Programmable SMS API |
| Library | Twilio Python SDK |
| Configuration | Account SID, Auth Token, From phone number (stored in config file) |
| Message Format | Plain text with alert summary and link to dashboard |

### 4.3 Communication Interfaces

#### 4.3.1 REST API (HTTP/HTTPS)
- **Protocol:** HTTP/1.1 (HTTPS when TLS certificates are configured)
- **Data Format:** JSON (application/json)
- **Authentication:** API key in request header (`X-API-Key`)
- **Base URL:** `http://<laptop_ip>:<port>/api/v1/`

#### 4.3.2 WebSocket
- **Protocol:** WebSocket (WS) / WebSocket Secure (WSS)
- **Purpose:** Real-time bidirectional communication for live video feed, detection updates, and alert push notifications.
- **Endpoint:** `ws://<laptop_ip>:<port>/ws/`
- **Message Format:** JSON payloads for structured data; binary frames for video data.
- **Heartbeat:** Ping/pong every 30 seconds to maintain connection.

#### 4.3.3 TCP/IP Network
- **Protocol Stack:** TCP/IP over Ethernet or Wi-Fi
- **Subnet:** 192.168.1.0/24 (configurable)
- **DNS:** Not required (direct IP addressing)
- **Firewall:** Ports 5000 (API), 5001 (WebSocket), 3000 (Dashboard) must be open on the laptop

---

## 5. Use Cases

### UC-1: Guest Check-in with Facial Recognition

| Field | Description |
|---|---|
| Use Case ID | UC-1 |
| Title | Guest Check-in with Facial Recognition |
| Primary Actor | Reception Staff |
| Secondary Actors | Guest, System (AI Server) |
| Preconditions | (1) System operational with camera active. (2) Guest previously enrolled with ≥1 facial embedding. (3) Reception staff logged into the dashboard. |
| Trigger | Guest approaches the reception desk and enters the camera's field of view. |

**Main Success Scenario:**
1. The PIR sensor detects motion and activates the camera (if in idle mode).
2. The Raspberry Pi captures video frames and streams them to the AI server.
3. The AI server runs person detection (YOLO/MobileNet) and identifies a person.
4. The AI server extracts the person's face region using face detection.
5. The AI server generates a facial embedding and matches it against the database.
6. A match is found (similarity ≥ threshold). The system retrieves the guest profile and reservation.
7. The dashboard displays name, photo, profile summary, reservation details, and visit history.
8. The dashboard displays personalized upselling recommendations.
9. The reception staff greets the guest by name and proceeds with check-in.
10. The staff optionally acts on upselling recommendations and marks their outcome.
11. The system logs the identification event and any recommendation interactions.

**Alternative Flows:**
- **AF-1.1 (Guest Not Recognized):** No match above threshold. Dashboard displays "Unknown Guest"; staff can enroll them.
- **AF-1.2 (Multiple Matches):** Top 3 matches ranked by confidence shown; staff selects correct guest.
- **AF-1.3 (Camera Unavailable):** Dashboard displays a camera error; staff proceeds with manual check-in.
- **AF-1.4 (Network Error):** RPi buffers frames locally; recognition resumes when connectivity is restored.

**Postconditions:** Guest is identified, profile/reservation displayed, identification logged, recommendation interactions recorded.

### UC-2: Upselling Recommendation Interaction

| Field | Description |
|---|---|
| Use Case ID | UC-2 |
| Title | Upselling Recommendation Interaction |
| Primary Actor | Reception Staff |
| Secondary Actors | Guest, System |
| Preconditions | (1) Guest identified via UC-1. (2) Profile/history loaded. (3) Service catalog populated. |
| Trigger | Guest identification completed and profile displayed on the dashboard. |

**Main Success Scenario:**
1. The recommendation engine analyzes the guest's profile, visit history, and preferences.
2. The engine generates a ranked list of up to 5 upselling recommendations.
3. The dashboard displays recommendations with names, descriptions, prices, and relevance scores.
4. The reception staff verbally offers the top recommendation(s).
5. The guest expresses interest.
6. The staff clicks "Accepted" on the relevant recommendation.
7. The system logs the acceptance and updates the guest's history.

**Alternative Flows:**
- **AF-2.1 (Guest Declines All):** Staff clicks "Declined" for each; logged.
- **AF-2.2 (No Recommendations Available):** Dashboard displays "No recommendations available."
- **AF-2.3 (Staff Defers):** Recommendations remain in "Pending" status.

**Postconditions:** Recommendation outcomes logged and associated with the guest's profile.

### UC-3: Lobby Security Alert (Unrecognized Person)

| Field | Description |
|---|---|
| Use Case ID | UC-3 |
| Title | Lobby Security Alert — Unrecognized Person |
| Primary Actor | System (automated) |
| Secondary Actors | Duty Manager, Reception Staff |
| Preconditions | (1) Lobby monitoring active. (2) Alert thresholds configured. (3) Duty manager contact info configured. |
| Trigger | An unrecognized person remains in the lobby beyond the configured dwell threshold (default: 10 minutes). |

**Main Success Scenario:**
1. System detects a person in the lobby.
2. System attempts face recognition but finds no match.
3. System tracks the person and monitors dwell time.
4. Dwell time exceeds the configured threshold.
5. System generates a "Medium" severity alert with image, location, and dwell time.
6. Alert displayed on dashboard with visual/auditory notification.
7. Alert sent via email and SMS to configured duty manager(s).
8. Duty manager views the alert and takes action.
9. Duty manager/staff acknowledges the alert.
10. After resolution, staff resolves the alert with a note.

**Alternative Flows:**
- **AF-3.1 (Person Leaves Before Threshold):** No alert generated; logged as normal activity.
- **AF-3.2 (Person Later Recognized):** Tracking status updated; no security alert generated.
- **AF-3.3 (Alert Delivery Failure):** System logs failure and retries up to 3 times with exponential backoff; dashboard alert remains visible.

**Postconditions:** Alert generated, logged, delivered, and eventually resolved with documentation.

### UC-4: Guest Needs Assistance Alert

| Field | Description |
|---|---|
| Use Case ID | UC-4 |
| Title | Guest Needs Assistance Alert |
| Primary Actor | System (automated) |
| Secondary Actors | Reception Staff, Duty Manager |
| Preconditions | (1) Lobby monitoring active. (2) A person is detected and tracked. |
| Trigger | A tracked person remains stationary for > the configurable assistance threshold (default: 5 minutes) without approaching the desk. |

**Main Success Scenario:**
1. System detects a stationary person.
2. System tracks position and measures dwell time.
3. Dwell time exceeds 5 minutes without movement towards the desk.
4. System generates a "Low" severity alert: "Person may need assistance."
5. Alert displayed on the dashboard.
6. Alert optionally sent via email/SMS.
7. A staff member approaches the person and offers help.
8. Staff acknowledges and resolves the alert.

**Alternative Flows:**
- **AF-4.1 (Person Approaches Desk):** Dwell timer resets; no alert.
- **AF-4.2 (Person is a Known Guest):** Severity adjusted appropriately.

**Postconditions:** Staff notified; alert documented.

### UC-5: Manual Guest Search

| Field | Description |
|---|---|
| Use Case ID | UC-5 |
| Title | Manual Guest Search |
| Primary Actor | Reception Staff |
| Preconditions | (1) Staff logged in. (2) Guest database populated. |
| Trigger | Staff needs to look up a guest record without facial recognition. |

**Main Success Scenario:**
1. Staff navigates to "Guest Lookup".
2. Staff enters a query (name, email, phone, or reservation ID).
3. System queries the database and returns matches.
4. Dashboard displays results with names, photos, and key details.
5. Staff selects the desired guest.
6. Dashboard displays the full profile, reservation, visit history, and recommendations.

**Alternative Flows:**
- **AF-5.1 (No Results Found):** Dashboard offers to create a new guest profile.
- **AF-5.2 (Multiple Partial Matches):** Staff reviews and selects the correct record.

**Postconditions:** Guest information displayed; search event logged.

### UC-6: New Guest Enrollment

| Field | Description |
|---|---|
| Use Case ID | UC-6 |
| Title | New Guest Enrollment |
| Primary Actor | Reception Staff |
| Secondary Actors | Guest |
| Preconditions | (1) Staff logged in. (2) Camera active. (3) Guest present at the desk. |
| Trigger | A new guest arrives, or an unrecognized face is detected and staff wishes to enroll them. |

**Main Success Scenario:**
1. Staff navigates to "Guest Enrollment" (or clicks "Enroll" on an unrecognized detection).
2. System activates face capture mode with a live feed and alignment guide.
3. Guest faces the camera; system captures 3 facial images from slightly different angles.
4. System extracts and stores facial embeddings.
5. Staff enters profile information.
6. Staff optionally enters reservation details.
7. Staff clicks "Save"; system creates the profile.
8. Dashboard confirms successful enrollment.

**Alternative Flows:**
- **AF-6.1 (Face Capture Fails):** Guidance message shown.
- **AF-6.2 (Duplicate Detected):** System alerts staff that the guest may already be enrolled.

**Postconditions:** New guest enrolled with facial embeddings and profile data.

### UC-7: VIP Guest Arrival Notification

| Field | Description |
|---|---|
| Use Case ID | UC-7 |
| Title | VIP Guest Arrival Notification |
| Primary Actor | System (automated) |
| Secondary Actors | Reception Staff, Duty Manager |
| Preconditions | (1) Guest enrolled with VIP flag true. (2) System operational. |
| Trigger | The system identifies a VIP-flagged guest. |

**Main Success Scenario:**
1. A guest is detected by the system.
2. System performs face recognition and identifies the guest.
3. System checks the VIP status flag (true).
4. System generates a VIP arrival alert with name, photo, preferences, special instructions.
5. Alert displayed prominently with a distinctive VIP indicator.
6. Alert sent via email and SMS to the duty manager.
7. Staff and duty manager prepare VIP welcome procedures.

**Postconditions:** Staff and management notified; VIP event logged.

---

## 6. System Constraints

### 6.1 Budget Constraints

| Constraint | Detail |
|---|---|
| Total hardware budget | $59–$66 USD |
| Software licensing cost | $0 (all open-source) |
| Cloud service costs | $0 (fully on-premise) |
| Laptop AI server | Not budgeted (assumes pre-existing hardware) |
| Maximum system cost | Not to exceed $200 for any future expansion |

### 6.2 Timeline Constraints

| Phase | Duration | Deliverables |
|---|---|---|
| Phase 1 (Midterm) | Month 1 | Core infrastructure, video pipeline, person detection, basic face recognition, initial dashboard, motion detection |
| Phase 2 (Final) | Month 2 | Advanced face recognition, upselling engine, alert system, full lobby monitoring, complete dashboard, testing, documentation |

### 6.3 Hardware Constraints

| Constraint | Impact |
|---|---|
| Raspberry Pi 4 (4GB RAM) | Limited on-device processing; no AI inference on edge |
| Single camera | Single field of view; limited coverage area |
| PIR sensor range (7m, 120°) | Detection limited to sensor coverage zone |
| No GPU on RPi | All inference must occur on laptop server |
| microSD endurance | Limit write-intensive operations on RPi |

### 6.4 Operational Constraints

| Constraint | Detail |
|---|---|
| Network dependency | System requires stable LAN between RPi and laptop |
| Single-site deployment | System designed for one reception/lobby area |
| Local network only | No cloud dependency; internet needed only for email/SMS alerts |
| Indoor use only | Camera and sensors designed for indoor controlled environments |
| Lighting dependency | Face recognition accuracy depends on adequate lighting |

---

## 7. Acceptance Criteria

### 7.1 Functional Acceptance Criteria

| Criterion ID | Description | Validation Method |
|---|---|---|
| AC-1 | The system correctly detects persons in the camera feed with ≥ 90% accuracy. | Test with 50+ sample frames at various distances. |
| AC-2 | The system correctly identifies enrolled guests via face recognition with ≥ 85% TPR and < 5% FPR. | Test with 20+ enrolled guests under varying conditions. |
| AC-3 | The system retrieves and displays guest profile and reservation info within 3 seconds of identification. | Timed test with 10 sequential identifications. |
| AC-4 | The recommendation engine generates relevant recommendations for identified guests with history. | Verify against 10 test profiles with known histories. |
| AC-5 | The system generates alerts for unrecognized persons exceeding the dwell time threshold. | Simulate unrecognized person presence > threshold. |
| AC-6 | Alerts are delivered via email within 5s and SMS within 10s of generation. | Test alert delivery with timing verification. |
| AC-7 | The dashboard displays live feed, detections, guest info, and alerts correctly. | Manual UI verification across all panels. |
| AC-8 | The PIR sensor triggers camera activation upon motion detection. | Physical test with movement in sensor range. |
| AC-9 | All CRUD operations on guest profiles, reservations, and alerts function correctly. | Automated test suite. |
| AC-10 | The guest enrollment process completes successfully. | Enroll 5 new test guests and verify recognition. |

### 7.2 Non-Functional Acceptance Criteria

| Criterion ID | Description | Validation Method |
|---|---|---|
| AC-11 | Video streaming from RPi to laptop achieves ≥ 15 FPS. | FPS counter during 5-minute streaming test. |
| AC-12 | Face recognition pipeline completes within 2 seconds per face. | Timed test with 20 recognition attempts. |
| AC-13 | Dashboard latency is < 500 ms for real-time updates. | Network latency measurement during operation. |
| AC-14 | System runs continuously for 4+ hours without crash or memory leak. | Extended stability test with monitoring. |
| AC-15 | Dashboard is usable by a non-technical user after brief training. | Usability test with a volunteer user. |

### 7.3 Demonstration Criteria

| Criterion | Description |
|---|---|
| Live Demo | Successful live demonstration to academic jury. |
| End-to-End | Complete flow from guest entry to identification to recommendation display. |
| Alert Demo | Triggered alert with email/SMS delivery during demo. |
| Documentation | Complete SysRS, SDD, and user manual delivered. |
| Source Code | Full source code submitted via Git repository. |

---

## 8. Appendices

### Appendix A: Requirement Traceability Matrix

| Requirement | Use Case | Component | Test Case |
|---|---|---|---|
| FR-1.1 – FR-1.5 | UC-1, UC-6 | Camera Module, Face Recognition Module | AC-1, AC-2 |
| FR-1.7 – FR-1.9 | UC-1 | Database Module, Dashboard | AC-3, AC-7 |
| FR-2.1 – FR-2.6 | UC-2 | Recommendation Engine, Dashboard | AC-4 |
| FR-3.1 – FR-3.5 | UC-3, UC-4 | Person Detection Module, Lobby Monitoring | AC-1, AC-5 |
| FR-4.1 – FR-4.8 | UC-3, UC-4, UC-7 | Alert System Module | AC-5, AC-6 |
| FR-5.1 – FR-5.13 | All UCs | Dashboard Frontend | AC-7 |
| FR-6.1 – FR-6.9 | All UCs | Database Module | AC-9 |
| FR-7.1 – FR-7.7 | UC-1 | PIR Sensor Module | AC-8 |

### Appendix B: Glossary of Hotel Terminology

| Term | Definition |
|---|---|
| Check-in | The process by which a guest registers their arrival and receives their room key. |
| Check-out | The process by which a guest settles their bill and formally departs. |
| In-House Guest | A guest who has an active reservation and is currently checked in. |
| PMS | Property Management System — software used by hotels to manage reservations, billing, and operations. |
| Upselling | The practice of encouraging guests to purchase upgrades, premium services, or additional amenities. |
| VIP | Very Important Person — a guest designated for special treatment. |
| Dwell Time | The duration a person spends in a specific area (e.g., the lobby). |
| Duty Manager | The hotel manager on shift responsible for overall operations and guest satisfaction. |

### Appendix C: System Context Diagram

```
        ┌─────────────────────┐
        │   HOTEL LOBBY       │
        │     ┌──────────┐    │
        │     │  Guest   │    │
        │     └────┬─────┘    │
        │          │ (approaches)
        └──────────┼──────────┘
                   │
   ┌───────────────▼────────────────┐
   │ COMPACT AI-POWERED SMART        │
   │ RECEPTION ASSISTANT             │
   │  ┌─────────┐   ┌───────────┐    │
   │  │  RPi    │───│  Laptop   │    │
   │  │ (Edge)  │   │ (AI Svr)  │    │
   │  └─────────┘   └───────────┘    │
   └────┬───────────────────┬────────┘
        │                   │
  ┌─────▼──────┐    ┌───────▼─────────┐
  │ Reception  │    │  Duty Manager   │
  │   Staff    │    │  (Email/SMS)    │
  │(Dashboard) │    │                 │
  └────────────┘    └─────────────────┘
```

---

## 9. Design Deviations (v1.1 As-Built)

> **Status:** This section is **new in v1.1**. It records every divergence between the April 2026 requirements baseline (Sections 1–8) and the system delivered on the `master` branch in June 2026. It is the requirements-level companion to the implementation-level audit in `docs/SYSRS_COMPLIANCE.md` and to the project report's compliance chapter. Baseline requirement text above is intentionally **unchanged**; this section is the authoritative record of what changed and why.

### 9.1 Summary of compliance

| Category | MET | Superseded / Deferred | Notes |
|---|---|---|---|
| Functional FR-1 … FR-6 | All P1 met or exceeded | 2 deferred (formal accuracy run, real SMTP/Twilio), 2 partial | Core identification, recommendation, monitoring, alerting, dashboard, and database all delivered. |
| Functional FR-7 (PIR) | FR-7.8 only | FR-7.1–FR-7.7 superseded | Hardware-driven change to always-on capture. |
| Non-Functional NFR-1 … NFR-6 | Every NFR-1 performance target met or exceeded | HTTPS/WSS (NFR-2.2/2.3) deferred for LAN demo | See §9.5. |
| Acceptance AC-1 … AC-15 | 10 MET | AC-2, AC-6, AC-14, AC-15 deferred; AC-8 N/A | See §9.7. |

### 9.2 FR-7 — PIR motion detection → always-on capture (SUPERSEDED)

- **What the baseline specified:** A HC-SR501 PIR sensor on GPIO 17 gating camera activation (FR-7.1–FR-7.7), with a manual always-on override (FR-7.8).
- **What was delivered:** Always-on continuous capture. The PIR path is removed; the `MotionDetector` class is retained, commented, as a reference implementation in `edge/edge_client.py`.
- **Why:** During Stage-B hardware bring-up the HC-SR505 sensor used in testing proved unreliable (intermittent stuck-HIGH state; a second sensor was destroyed during wiring). FR-7.8 ("always-on override") was invoked as the production mode.
- **Requirements affected:** FR-7.1–FR-7.7 → **SUPERSEDED**; FR-7.8 → **MET (now the only mode)**; AC-8 → **N/A**; F7 (product function) reframed as "continuous capture".
- **Net effect on the system:** None negative — the always-on path was always a permitted mode; removing the motion gate eliminated a fragile hardware dependency and simplified the edge service.

### 9.3 FR-1 — face recognition specifics

| Baseline | As-built | Reason |
|---|---|---|
| FR-1.4: 128-D FaceNet **or** 4096-D DeepFace embeddings | **512-D** embeddings from FaceNet `InceptionResnetV1` pre-trained on VGGFace2 | The chosen `facenet-pytorch` `InceptionResnetV1` produces 512-D vectors; DeepFace was not used. Functionally equivalent (a fixed-length L2-normalised embedding); only the dimensionality figure changed. |
| FR-1.6: default cosine threshold **0.70** | Tuned to **0.80** | Live Stage-C testing showed 0.70 admitted occasional false positives; 0.80 gave the best TPR/FPR balance at this deployment's camera/lighting. Remains configurable (`config.yaml: recognition.similarity_threshold`). |
| FR-1.12: up to 5 embeddings per guest | Met — 5-per-guest cap enforced (oldest evicted) | — |

### 9.4 FR-2 — recommendation engine rule set

- **Baseline FR-2.5** named eight illustrative rules (loyalty upgrade, service repeat, business traveller, high spender, VIP, long stay, special occasion, late checkout).
- **As-built**: a seven-rule additive engine with a different, fully-documented rule set — R1 popularity baseline, R2 VIP boost (+0.30), R3 dietary match (+0.20), R4 room-type match (+0.10), R5 Arabic-speaker dining (+0.15), R6 returning-guest winback bundle (+0.30), R7 business-traveller pattern (±0.20). Scores cap at 1.0; top-5 persisted with human-readable rationale.
- **Requirement intent preserved:** FR-2.1–FR-2.10 (analyse history/preferences, rank top-5, explainable, accept/decline/defer, log outcomes) are all MET. Only the specific rule wording in the FR-2.5 example changed.

### 9.5 NFR-2 — security specifics

| Baseline | As-built | Reason |
|---|---|---|
| NFR-2.1: AES-256 at rest | **AES-256-GCM** (authenticated: version byte + 12-byte nonce + ciphertext + 16-byte tag, base64) | GCM adds integrity/tamper-detection over plain AES; key held outside the DB in `ENCRYPTION_KEY`. Strengthens, does not weaken, the requirement. |
| NFR-2.2 / NFR-2.3: HTTPS / WSS transport | **Deferred** for the LAN-segment demo; documented for production via a Caddy reverse proxy (5-line addition). | On the isolated direct-cable subnet the marginal security gain was low; flagged in the report's Future Works. |
| NFR-2.5 / 2.9: JWT auth, bcrypt cost 12 | MET — JWT (HS256) gates all routes; bcrypt cost factor 12. | — |
| NFR-2.6: RBAC ≥ 2 roles | Exceeded — **7 staff roles** with admin-scoped mutations. | — |
| NFR-2.11: right to erasure | MET — `DELETE /api/guests/{id}` cascades to all child records. | — |

### 9.6 Platform, framework, hardware & network deviations

- **Web framework:** **FastAPI** was selected over Flask (the baseline allowed "Flask or FastAPI"). Reason: native ASGI async + WebSocket broadcast, Pydantic validation, auto-OpenAPI.
- **Edge platform:** **Raspberry Pi 4 Model B 8 GB** (baseline assumed 4 GB). The Pi remains a capture-only node.
- **Network:** the two nodes are joined by a **direct Cat-6 cable on an isolated `192.168.99.0/24` subnet** (server `.1`, Pi `.2`), not the baseline `192.168.1.0/24` shared LAN. Reason: an early Wi-Fi/LAN configuration routed Pi traffic through the campus gateway and collided with internal IP ranges, adding tens of milliseconds; the dedicated cable gives sub-millisecond, contention-free transport.
- **Ports:** the baseline named separate ports 5000/5001/3000; the delivered server runs a single FastAPI process serving the API, the WebSocket endpoints, and the built React SPA together.
- **Budget:** the as-built marginal hardware cost is **≈ $148** (Pi 4 8 GB $100, USB webcam $36, PSU $6, 32 GB microSD $16.5, Cat-6 cable $0.9), above the baseline $59–66 (which assumed a 4 GB Pi and cheaper webcam). Still well under the $200 expansion ceiling (§6.1) and excludes the pre-existing laptop.

### 9.7 New capability beyond the baseline — live speech translation (FR-8 candidate)

A **live speech-translation** subsystem was added during Phase 2, not present in the v1.0 baseline:

- 8-second audio chunks captured on the Pi (`edge/audio_client.py`, separate systemd service) → `faster-whisper` (`small`, CUDA, INT8/FP16) on the server translates Arabic / French / English → English.
- Surfaced on a new **Live Translation** dashboard page; Whisper inference is gated on dashboard-subscriber count to save GPU cycles.
- **Scope note:** this is *translation to English*, adjacent to but narrower than the "voice recognition / natural language processing" item listed Out-of-Scope in §1.2 (no command interpretation/NLP). It directly addresses Lebanon's trilingual reception reality.
- If formalised, this would become **FR-8: Live Speech Translation** with its own acceptance criteria; it is documented here and in the project report rather than retro-fitted into the baseline.

### 9.8 Acceptance criteria — final status

| AC | Status (v1.1) |
|---|---|
| AC-1 person detection ≥90% | **MET** (Stage-C live testing) |
| AC-2 ≥85% TPR / <5% FPR | **DEFERRED** — accuracy harness shipped (`scripts/accuracy_test.py`), formal run not performed |
| AC-3 profile ≤3 s | **MET** |
| AC-4 relevant recommendations | **MET** |
| AC-5 unknown-person security alert | **MET** |
| AC-6 email ≤5 s / SMS ≤10 s | **DEFERRED** — real SMTP/Twilio not configured (console-fallback path verified) |
| AC-7 all dashboard pages render | **MET** |
| AC-8 PIR triggers camera | **N/A** — PIR removed; FR-7 superseded |
| AC-9 all CRUD operations | **MET** |
| AC-10 enroll new guests | **MET** (live + passport-upload paths) |
| AC-11 ≥15 FPS | **MET — 16.03 fps measured** |
| AC-12 face pipeline ≤2 s | **MET — ~100 ms measured** |
| AC-13 dashboard latency <500 ms | **MET** |
| AC-14 4-hour stability | **DEFERRED** |
| AC-15 non-technical usability | **DEFERRED** |

### 9.9 Cross-references

- Implementation-level mapping of every requirement to source files: `docs/SYSRS_COMPLIANCE.md`.
- Component/algorithm mapping and design deviations: `docs/SDD_Software_Design_Document.md` (§ Design Deviations) and `docs/SDD_COMPLIANCE.md`.
- Quantitative results and engineering-issue narrative: project report, Chapter V.

---

*End of System Requirements Specification — Version 1.1*
*Document prepared by Youssef Kassar — CCE Department, AUL — June 2026*
