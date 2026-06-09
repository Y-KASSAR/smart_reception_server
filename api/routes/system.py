"""
System Observability Routes (SDD §3.4.6, §4.3.10)
=================================================
Operational endpoints surfaced on the dashboard "System Status" tile and the
Reports page. Read-only, all behind staff authentication.

    GET /api/system/status   → liveness of every subsystem (camera, models,
                                database, edge heartbeat, server uptime)
    GET /api/system/stats    → today's headline counters (guests identified,
                                alerts created, recommendations made)
"""
import os
import time
from datetime import datetime, time as dtime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config.logging_config import get_logger
from config.settings import settings
from database.connection import get_db
from database.models import (
    Alert,
    AlertStatus,
    FaceEmbedding,
    Guest,
    Recommendation,
    RecommendationStatus,
    SystemLog,
)
from utils.security_utils import get_current_staff, require_role

logger = get_logger(__name__)
router = APIRouter()

# Captured once at module import so we can report uptime relative to server start
_SERVER_START_TS: float = time.time()


# ----------------------------------------------------------------------------
# Response models
# ----------------------------------------------------------------------------
class SubsystemStatus(BaseModel):
    name: str
    ok: bool
    detail: str = ""


class SystemStatusResponse(BaseModel):
    server_uptime_seconds: int
    timestamp: str
    database: SubsystemStatus
    recognition: SubsystemStatus
    person_detection: SubsystemStatus
    monitoring: SubsystemStatus
    alert_pipeline: SubsystemStatus


class SystemStatsResponse(BaseModel):
    date: str                       # ISO date the stats apply to (UTC "today")
    guests_total: int               # all-time total
    guests_identified_today: int    # alerts of type VIP_ARRIVAL or arrival logs today
    alerts_today: int
    alerts_open: int
    alerts_by_severity: dict        # {severity_int: count}
    recommendations_today: int
    recommendations_accepted_today: int
    embeddings_total: int


# ----------------------------------------------------------------------------
# /status — subsystem liveness
# ----------------------------------------------------------------------------
@router.get("/status", response_model=SystemStatusResponse)
def get_system_status(
    db: Session = Depends(get_db),
    _=Depends(get_current_staff),
):
    """High-level liveness of every backend subsystem.

    Imports are local + try/except so a missing optional package never breaks
    this endpoint — the dashboard's "subsystem ok?" tile must always render.
    """
    # --- Database ----------------------------------------------------------
    db_ok = True
    db_detail = ""
    db_path: Path = settings.database.full_path
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        size_mb = (
            round(db_path.stat().st_size / (1024 * 1024), 2)
            if db_path.is_file()
            else 0.0
        )
        db_detail = f"SQLite {db_path.name} ({size_mb} MB)"
    except Exception as e:
        db_ok = False
        db_detail = f"DB check failed: {e}"

    # --- Recognition -------------------------------------------------------
    recog_ok = False
    recog_detail = "not initialized"
    try:
        from modules.recognition import face_engine
        recog_ok = face_engine.backend != "none"
        recog_detail = (
            f"backend={face_engine.backend}, embeddings_loaded="
            f"{face_engine.guest_count}"
        )
    except Exception as e:
        recog_detail = f"import failed: {e}"

    # --- Person detection --------------------------------------------------
    det_ok = False
    det_detail = "not initialized"
    try:
        from detection import person_detector
        det_ok = getattr(person_detector, "backend", "none") != "none"
        det_detail = f"backend={getattr(person_detector, 'backend', '?')}"
    except Exception as e:
        det_detail = f"import failed: {e}"

    # --- Monitoring --------------------------------------------------------
    mon_ok = False
    mon_detail = "not initialized"
    try:
        from modules.monitoring import person_monitor
        mon_ok = True
        mon_detail = f"active_tracks={person_monitor.active_count}"
    except Exception as e:
        mon_detail = f"import failed: {e}"

    # --- Alert pipeline ----------------------------------------------------
    alert_ok = False
    alert_detail = "not subscribed"
    try:
        from modules.alerts import alert_notifier
        alert_ok = alert_notifier._subscribed
        alert_detail = (
            f"email={'on' if settings.alert.email_enabled else 'off'}, "
            f"sms={'on' if settings.alert.sms_enabled else 'off'}"
        )
    except Exception as e:
        alert_detail = f"import failed: {e}"

    uptime = int(time.time() - _SERVER_START_TS)

    return SystemStatusResponse(
        server_uptime_seconds=uptime,
        timestamp=datetime.now(timezone.utc).isoformat(),
        database=SubsystemStatus(name="database", ok=db_ok, detail=db_detail),
        recognition=SubsystemStatus(name="recognition", ok=recog_ok, detail=recog_detail),
        person_detection=SubsystemStatus(name="person_detection", ok=det_ok, detail=det_detail),
        monitoring=SubsystemStatus(name="monitoring", ok=mon_ok, detail=mon_detail),
        alert_pipeline=SubsystemStatus(name="alert_pipeline", ok=alert_ok, detail=alert_detail),
    )


# ----------------------------------------------------------------------------
# /stats — daily counters
# ----------------------------------------------------------------------------
@router.get("/stats", response_model=SystemStatsResponse)
def get_system_stats(
    db: Session = Depends(get_db),
    _=Depends(require_role("admin", "manager")),
):
    """Headline counters for the Reports page (admin / manager only)."""
    now = datetime.now(timezone.utc)
    today_start = datetime.combine(now.date(), dtime.min, tzinfo=timezone.utc)

    guests_total = db.query(Guest).count()
    embeddings_total = db.query(FaceEmbedding).count()

    today_alerts = db.query(Alert).filter(Alert.created_at >= today_start).all()
    alerts_today = len(today_alerts)
    alerts_open = db.query(Alert).filter(Alert.status == AlertStatus.PENDING).count()

    by_severity: dict = {}
    for a in today_alerts:
        sev = a.severity or 0
        by_severity[sev] = by_severity.get(sev, 0) + 1

    # Use VIP_ARRIVAL + ARRIVAL alerts today as a proxy for "guests identified today"
    from database.models import AlertType
    guests_identified_today = sum(
        1
        for a in today_alerts
        if a.alert_type in (AlertType.VIP_ARRIVAL, AlertType.ARRIVAL)
    )

    rec_today_q = db.query(Recommendation).filter(Recommendation.created_at >= today_start)
    recommendations_today = rec_today_q.count()
    recommendations_accepted_today = rec_today_q.filter(
        Recommendation.status == RecommendationStatus.ACCEPTED
    ).count()

    return SystemStatsResponse(
        date=now.date().isoformat(),
        guests_total=guests_total,
        guests_identified_today=guests_identified_today,
        alerts_today=alerts_today,
        alerts_open=alerts_open,
        alerts_by_severity={str(k): v for k, v in by_severity.items()},
        recommendations_today=recommendations_today,
        recommendations_accepted_today=recommendations_accepted_today,
        embeddings_total=embeddings_total,
    )



# ============================================================
# FR-4.5 / FR-4.6 — admin test endpoints for email + SMS
# ============================================================
# These let an admin verify the dispatch path is wired correctly without
# waiting for a real alert to fire. When SMTP/Twilio aren't configured,
# the alert_notifier writes a JSON line into logs/outbox/{email,sms}.log
# so the test still proves the code path executed.
from utils.security_utils import require_role


@router.post("/test-email")
def test_email(_=Depends(require_role("admin"))):
    """Fire a synthetic VIP_ARRIVAL alert and dispatch via email."""
    from modules.alerts import alert_notifier
    from database.models import Alert as _Alert, AlertType as _AT
    synthetic = _Alert(id=-1, alert_type=_AT.VIP_ARRIVAL,
                       title="Email channel test",
                       description="Triggered manually by an admin to verify SMTP wiring.",
                       severity=2)
    ok = alert_notifier.send_email(synthetic)
    return {
        "channel": "email",
        "dispatched": ok,
        "outbox_path": "logs/outbox/email.log",
        "note": ("Real send" if ok else "Console fallback — set SMTP creds in .env to enable real sends."),
    }


@router.post("/test-sms")
def test_sms(_=Depends(require_role("admin"))):
    """Fire a synthetic VIP_ARRIVAL alert and dispatch via SMS."""
    from modules.alerts import alert_notifier
    from database.models import Alert as _Alert, AlertType as _AT
    synthetic = _Alert(id=-1, alert_type=_AT.VIP_ARRIVAL,
                       title="SMS channel test",
                       description="Triggered manually by an admin to verify Twilio wiring.",
                       severity=2)
    ok = alert_notifier.send_sms(synthetic)
    return {
        "channel": "sms",
        "dispatched": ok,
        "outbox_path": "logs/outbox/sms.log",
        "note": ("Real send" if ok else "Console fallback — set Twilio creds in .env to enable real sends."),
    }
