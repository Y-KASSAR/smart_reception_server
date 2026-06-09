"""
System Controller
=================
Central coordinator for all system modules.
Manages module lifecycle and routes events between components.
"""
import threading
import time
from datetime import datetime, timedelta
from typing import Optional
from config.logging_config import get_logger
from config.settings import settings
from core.event_bus import event_bus

logger = get_logger(__name__)


class SystemController:
    """
    Orchestrates all system modules:
    - Starts/stops modules in the correct order
    - Wires up event subscriptions between modules
    - Schedules daily DB backup (NFR-5)
    - Provides a single point of control for the system
    """

    def __init__(self):
        self._running = False
        self._modules = {}
        self._backup_thread: Optional[threading.Thread] = None
        self._backup_stop = threading.Event()

    def start(self) -> None:
        if self._running:
            logger.warning("Controller already running")
            return
        logger.info("Starting Smart Reception System...")
        self._setup_event_subscriptions()
        self._start_backup_scheduler()
        self._running = True
        logger.info("System controller started successfully")

    def stop(self) -> None:
        if not self._running:
            return
        logger.info("Stopping Smart Reception System...")
        self._backup_stop.set()
        if self._backup_thread and self._backup_thread.is_alive():
            self._backup_thread.join(timeout=2)
        event_bus.clear()
        self._running = False
        logger.info("System controller stopped")

    def _setup_event_subscriptions(self) -> None:
        event_bus.subscribe("face_recognized", self._on_face_recognized)
        event_bus.subscribe("unknown_person_detected", self._on_unknown_person)
        event_bus.subscribe("alert_created", self._on_alert_created)
        # Importing alert_notifier instantiates the singleton, which in turn
        # subscribes itself to unknown_person_detected / assistance_needed /
        # vip_arrival on the event_bus (SDD §4.2.6).
        from modules.alerts import alert_notifier  # noqa: F401
        logger.info("AlertNotifier registered with event bus")

    def _on_face_recognized(self, guest_id: int, confidence: float, **kwargs) -> None:
        logger.info(f"Face recognized: guest_id={guest_id}, confidence={confidence:.2f}")

    def _on_unknown_person(self, track_id: int, dwell_time: float, **kwargs) -> None:
        logger.info(f"Unknown person detected: track_id={track_id}, dwell={dwell_time:.1f}s")

    def _on_alert_created(self, alert_id: int = 0, alert_type: str = "", **kwargs) -> None:
        logger.info(f"Alert created: id={alert_id}, type={alert_type}")

    # ------------------------------------------------------------
    # Daily DB backup scheduler (NFR-5)
    # ------------------------------------------------------------
    def _start_backup_scheduler(self) -> None:
        if not settings.database.backup_enabled:
            logger.info("DB backup disabled in config")
            return
        self._backup_stop.clear()
        self._backup_thread = threading.Thread(
            target=self._backup_loop, name="db-backup-scheduler", daemon=True
        )
        self._backup_thread.start()
        logger.info(
            f"DB backup scheduler started (daily at {settings.database.backup_time})"
        )

    def _backup_loop(self) -> None:
        while not self._backup_stop.is_set():
            try:
                wait_s = self._seconds_until_next_backup()
                if self._backup_stop.wait(timeout=wait_s):
                    return
                self._run_backup()
            except Exception as e:
                logger.error(f"Backup scheduler error: {e}", exc_info=True)
                # Avoid tight loop on persistent failure
                if self._backup_stop.wait(timeout=3600):
                    return

    def _seconds_until_next_backup(self) -> float:
        try:
            hh, mm = (int(x) for x in settings.database.backup_time.split(":"))
        except Exception:
            hh, mm = 2, 0
        now = datetime.now()
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        return max(1.0, (target - now).total_seconds())

    def _run_backup(self) -> None:
        try:
            from scripts.backup_database import create_backup, prune_old_backups
            path = create_backup()
            removed = prune_old_backups()
            logger.info(f"Scheduled backup OK: {path.name} (pruned {removed})")
        except Exception as e:
            logger.error(f"Scheduled backup failed: {e}", exc_info=True)

    @property
    def is_running(self) -> bool:
        return self._running


controller = SystemController()
