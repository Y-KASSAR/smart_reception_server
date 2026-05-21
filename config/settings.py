import os
import yaml
from pathlib import Path
from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import List, Optional, Any

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

load_dotenv(PROJECT_ROOT / ".env")


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 5000
    debug: bool = False
    workers: int = 1


@dataclass
class EdgeConfig:
    ip: str = "192.168.1.100"
    heartbeat_interval: int = 10
    frame_timeout: int = 30


@dataclass
class CameraConfig:
    device_id: int = 0
    resolution_width: int = 1920
    resolution_height: int = 1080
    fps: int = 30
    jpeg_quality: int = 80
    backend: str = "v4l2"


@dataclass
class PIRConfig:
    gpio_pin: int = 17
    debounce_ms: int = 2000
    idle_timeout_s: int = 60
    always_on: bool = False


@dataclass
class DetectionConfig:
    model: str = "yolov8n"
    confidence_threshold: float = 0.5
    nms_iou_threshold: float = 0.4
    device: str = "auto"


@dataclass
class RecognitionConfig:
    detection_model: str = "mtcnn"
    recognition_model: str = "facenet"
    similarity_threshold: float = 0.70
    max_embeddings_per_guest: int = 5
    re_recognition_interval: int = 30


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
    alert_email_recipients: List[str] = field(default_factory=list)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    alert_sms_recipients: List[str] = field(default_factory=list)
    encryption_key: str = ""
    default_admin_username: str = "admin"
    default_admin_password: str = "change_me_immediately"


class Settings:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = PROJECT_ROOT / "config.yaml"

        self._raw = {}

        if Path(config_path).exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self._raw = yaml.safe_load(f) or {}

        self.server = self._load_section(ServerConfig, "server")
        self.edge = self._load_section(EdgeConfig, "edge")
        self.camera = self._load_section(CameraConfig, "camera")
        self.pir = self._load_section(PIRConfig, "pir")
        self.detection = self._load_section(DetectionConfig, "detection")
        self.recognition = self._load_section(RecognitionConfig, "recognition")
        self.monitoring = self._load_section(MonitoringConfig, "monitoring")
        self.alert = self._load_section(AlertConfig, "alert")
        self.database = self._load_section(DatabaseConfig, "database")
        self.security = self._load_section(SecurityConfig, "security")
        self.secrets = self._load_secrets()

    def _load_section(self, dataclass_type: Any, yaml_key: str):
        section_data = self._raw.get(yaml_key, {})
        if section_data is None:
            section_data = {}

        valid_keys = set(dataclass_type.__dataclass_fields__.keys())
        filtered = {k: v for k, v in section_data.items() if k in valid_keys}
        return dataclass_type(**filtered)

    def _load_secrets(self):
        email_recipients_str = os.getenv("ALERT_EMAIL_RECIPIENTS", "")
        sms_recipients_str = os.getenv("ALERT_SMS_RECIPIENTS", "")

        return SecretsConfig(
            api_key=os.getenv("API_KEY", ""),
            jwt_secret_key=os.getenv("JWT_SECRET_KEY", ""),
            smtp_host=os.getenv("SMTP_HOST", ""),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_username=os.getenv("SMTP_USERNAME", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            alert_email_recipients=[e.strip() for e in email_recipients_str.split(",") if e.strip()],
            twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
            twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
            twilio_from_number=os.getenv("TWILIO_FROM_NUMBER", ""),
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

        if not (0 <= self.recognition.similarity_threshold <= 1):
            errors.append(
                f"Recognition similarity_threshold must be 0-1, got {self.recognition.similarity_threshold}"
            )

        if not (0 <= self.detection.confidence_threshold <= 1):
            errors.append(
                f"Detection confidence_threshold must be 0-1, got {self.detection.confidence_threshold}"
            )

        return errors


settings = Settings()