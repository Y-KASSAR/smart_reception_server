import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import List, Optional

PROJECT_ROOT =Path(__file__).parent.parent.resolve()

load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 5000
    debug: bool = False
    workers: int =1

@dataclass
class EdgeConfig:
    ip: str = "192.168.1.100"
    heartbeat_interval: int =10
    frame_timeout: int=30
    # Max fps for the dashboard live-video preview (full JPEG over WebSocket).
    # Detection boxes still stream every frame; 0 = no throttle.
    live_feed_fps: int = 12

@dataclass
class CameraConfig:
    device_id: int = 0
    resolution_width: int = 1920
    resolution_height: int = 1080
    fps: int = 30
    jpeg_quality: int = 80
    backend: str = "v4l2"
# PIR module removed — the PIR motion sensor config is no longer used.
# The camera runs always-on at full FPS with no motion gating or downtime.
# @dataclass
# class PIRConfig:
#     gpio_pin: int = 17
#     debounce_ms: int = 2000
#     idle_timeout_s: int = 60
#     always_on: bool = False
@dataclass
class DetectionConfig:
    model: str = "yolov8n"
    confidence_threshold: float = 0.5
    nms_iou_threshold: float = 0.4
    device: str = "auto"          # "auto" -> CUDA if available, else CPU
    inference_width: int = 960    # YOLO imgsz; smaller = faster, lower latency
    # Bounding-box temporal smoothing (anti-jitter for the live overlay).
    # Each track's box is an exponential moving average of its raw detections:
    # smoothing is the weight on the NEW frame. Lower = steadier but laggier;
    # 1.0 disables smoothing entirely. 0.4 is a good steady/responsive balance.
    bbox_smoothing: float = 0.4
    # Deadband (pixels, in frame space): if every corner of the new box moves
    # less than this vs the held box, the box is kept perfectly still — so a
    # stationary person shows zero shimmer. Set 0 to disable the deadband.
    bbox_deadband_px: float = 2.0
    # How many consecutive frames a tracked person can go undetected (brief
    # occlusion, motion blur) before the tracker drops their track_id and
    # mints a new one on their next detection. Too low and PersonMonitor's
    # dwell-time clock (keyed by track_id) silently resets on every minor
    # blip, which can prevent the security/assistance alert thresholds from
    # ever being reached for someone genuinely lingering. Kept roughly in
    # step with monitoring.tracking_timeout (seconds) at the app's typical
    # 10-16fps rather than the previous hardcoded 8-frame (<1s) default.
    track_max_disappeared_frames: int = 24
@dataclass
class RecognitionConfig:
    detection_model: str = "mtcnn"
    recognition_model: str = "facenet"
    similarity_threshold: float = 0.70
    # Same-person gate used when ADDING a face to a guest that already has
    # embeddings: the new face must score at least this cosine similarity
    # against the guest's existing faces, otherwise the add is rejected to
    # avoid mixing two people into one profile. Deliberately LOWER than
    # similarity_threshold — different people score ~0.0–0.4 while the same
    # person at a new angle still scores ~0.5–0.9, so 0.5 separates them
    # without rejecting legitimate new poses.
    enroll_verify_threshold: float = 0.5
    max_embeddings_per_guest: int = 5
    re_recognition_interval: int = 30
    # Real-time tuning: run the expensive FaceNet pass only every Nth frame.
    # Person detection + tracking still runs every frame; identities are
    # carried forward in between. 1 = recognize every frame.
    recognize_every_n_frames: int = 15
    # Downscale width for MTCNN face DETECTION (crops for embedding extraction
    # are still taken at full resolution). 0 = no downscale.
    inference_width: int = 960
    # MTCNN minimum detectable face size (px). Smaller = detects faces further
    # away / smaller in frame (helps recall) at some extra compute cost.
    min_face_size: int = 20
    # MTCNN cascade confidence thresholds [P-Net, R-Net, O-Net]. The library
    # default is [0.6, 0.7, 0.7]; relaxing the later stages lets the detector
    # keep faces at an angle / partially turned (≈30–45° yaw) that the stricter
    # default would discard. Lower = more pose-tolerant detection.
    detection_thresholds: List[float] = field(default_factory=lambda: [0.6, 0.6, 0.6])
@dataclass
class MonitoringConfig:
    security_dwell_threshold: int = 600
    assistance_dwell_threshold: int = 300
    tracking_timeout: int = 30
@dataclass
class AlertConfig:
    cooldown_period: int = 900
    email_enabled: bool = True
    sms_enabled: bool = False
    dashboard_sound_enabled: bool = True
@dataclass
class DatabaseConfig:
    path: str = "data/smart_reception.db"
    backup_enabled: bool = True
    backup_interval: str = "daily"
    backup_time: str = "02:00"
    backup_retention_days: int = 7

    @property
    def full_path(self) -> Path:
        return PROJECT_ROOT / self.path
@dataclass
class SecurityConfig:
    session_timeout: int = 28800
    inactivity_timeout: int = 1800
    max_login_attempts: int = 5
    lockout_duration: int = 900
@dataclass
class SecretsConfig:
    api_key: str = ""
    jwt_secret_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    # STARTTLS toggle. Most public relays (Gmail/Office365 on :587) require it,
    # but plain relays (a local postfix on :25, or a capture/sink server used
    # for latency verification) speak unencrypted SMTP. Default True.
    smtp_use_tls: bool = True
    # Friendly From display name. The mailbox may be a generic gmail.com
    # address, but recipients see this name in their inbox — keep it branded.
    smtp_from_name: str = "Smart Reception"
    alert_email_recipients: List[str] = field(default_factory=list)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    # Messaging channel: "sms" (default) or "whatsapp". For the WhatsApp
    # Sandbox the from/to numbers must be sent with a "whatsapp:" prefix and
    # the From is Twilio's shared sandbox number (e.g. +14155238886).
    twilio_channel: str = "sms"
    alert_sms_recipients: List[str] = field(default_factory=list)
    encryption_key: str = ""
    default_admin_username: str = "admin"
    default_admin_password: str = "change_me_immediately"

class Settings :

    # Absolute path to the repo root. Referenced by api/app.py (SPA mount)
    # and detection/person_detector.py (model file paths).
    project_root: Path = PROJECT_ROOT

    def __init__(self, config_path:Optional[str] = None):

        if config_path is None:
            config_path = PROJECT_ROOT / "config.yaml"

        self._raw= {}

        if Path(config_path).exists():
            with open(config_path, "r") as f:
                self._raw = yaml.safe_load(f) or {}

        self.server =self._load_section(ServerConfig, "server")
        self.edge = self._load_section(EdgeConfig, "edge")
        self.camera = self._load_section(CameraConfig, "camera")
        # PIR module removed — no longer loading the PIR config section.
        # self.pir = self._load_section(PIRConfig, "pir")
        self.detection =self._load_section(DetectionConfig, "detection")
        self.monitoring = self._load_section(MonitoringConfig, "monitoring")
        self.recognition = self._load_section(RecognitionConfig, "recognition")
        self.alert= self._load_section(AlertConfig, "alert")
        self.database= self._load_section(DatabaseConfig, "database")
        self.security = self._load_section(SecurityConfig, "security")
        self.secrets =self._load_secrets()


    def _load_section(self, dataclass_type, yaml_key : str) : 
        section_data = self._raw.get(yaml_key,{})
        if section_data is None:
            section_data = {}
        
        valid_keys = {f.name for f in dataclass_type.__dataclass_fields__.values()}
        filtered ={k:v for k, v in section_data.items() if k in valid_keys}
        return dataclass_type(**filtered)

    def _load_secrets(self):
        email_recipients_str = os.getenv("ALERT_EMAIL_RECIPIENTS","")
        sms_recipients_str = os.getenv("ALERT_SMS_RECIPIENTS","")
        return SecretsConfig(
            api_key=os.getenv("API_KEY",""),
            jwt_secret_key=os.getenv("JWT_SECRET_KEY", ""),
            smtp_host=os.getenv("SMTP_HOST", ""),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_username=os.getenv("SMTP_USERNAME", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            smtp_use_tls=os.getenv("SMTP_USE_TLS", "true").strip().lower() not in ("0", "false", "no", ""),
            smtp_from_name=os.getenv("SMTP_FROM_NAME", "Smart Reception"),
            alert_email_recipients=[e.strip() for e in email_recipients_str.split(",") if e.strip()],
            twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
            twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
            twilio_from_number=os.getenv("TWILIO_FROM_NUMBER", ""),
            twilio_channel=os.getenv("TWILIO_CHANNEL", "sms").strip().lower(),
            alert_sms_recipients=[p.strip() for p in sms_recipients_str.split(",") if p.strip()],
            encryption_key=os.getenv("ENCRYPTION_KEY", ""),
            default_admin_username=os.getenv("DEFAULT_ADMIN_USERNAME", "admin"),
            default_admin_password=os.getenv("DEFAULT_ADMIN_PASSWORD", "change_me_immediately"),
        )    
    def validate(self) -> List[str]:
        """Validate critical settings. Returns list of error messages."""
        errors = []

        if not self.secrets.api_key:
            errors.append("API_KEY is not set in .env")
        if not self.secrets.jwt_secret_key:
            errors.append("JWT_SECRET_KEY is not set in .env")

        if self.recognition.similarity_threshold < 0 or self.recognition.similarity_threshold > 1:
            errors.append(f"Recognition similarity_threshold must be 0-1, got {self.recognition.similarity_threshold}")

        if self.detection.confidence_threshold < 0 or self.detection.confidence_threshold > 1:
            errors.append(f"Detection confidence_threshold must be 0-1, got {self.detection.confidence_threshold}")

        return errors        

settings = Settings()