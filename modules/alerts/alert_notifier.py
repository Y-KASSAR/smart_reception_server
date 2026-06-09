"""
Alert Notifier (SDD §4.2.6, FR-4)
=================================

Subscribes to the detection events published by PersonMonitor and
face recognition, persists them as Alert rows, and dispatches
out-of-band notifications:

    Event subscriptions
    -------------------
    "unknown_person_detected"  →  Alert(type=SECURITY)
    "assistance_needed"        →  Alert(type=ASSISTANCE)
    "vip_arrival"              →  Alert(type=VIP_ARRIVAL)

After persistence, an ``alert_created`` event is published on the bus —
the FastAPI lifespan handler (``api/app.py``) picks that up and fans
it out to every connected dashboard WebSocket.

Email + SMS delivery are *fail-soft*: any backend error is logged and
swallowed so a misconfigured SMTP relay or expired Twilio credential
can never crash the recognition loop.
"""
from __future__ import annotations

import smtplib
import threading
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Optional

from config.logging_config import get_logger
from config.settings import settings
from core.event_bus import event_bus
from database.connection import SessionLocal
from database.models import Alert, AlertType
from database.repositories import AlertRepository

logger = get_logger(__name__)


# Cooldown bookkeeping — one entry per (track_id, event) prevents alert
# storms when PersonMonitor publishes repeatedly for the same person
# (the monitor's own per-track gate already does this, but we double-up
# defensively here in case the dispatch flow is exercised by other
# producers in the future).
_COOLDOWN_SECONDS = float(settings.alert.cooldown_period)


class AlertNotifier:
    def __init__(self):
        self._lock = threading.RLock()
        self._last_fire: dict[tuple, float] = {}
        self._subscribed = False
        self.subscribe()

    # ------------------------------------------------------------------
    # Subscription wiring
    # ------------------------------------------------------------------
    def subscribe(self) -> None:
        if self._subscribed:
            return
        event_bus.subscribe("unknown_person_detected", self._on_unknown_person)
        event_bus.subscribe("assistance_needed", self._on_assistance_needed)
        event_bus.subscribe("vip_arrival", self._on_vip_arrival)
        event_bus.subscribe("watchlist_match", self._on_watchlist_match)
        self._subscribed = True
        logger.info(
            "AlertNotifier subscribed to event_bus "
            "(unknown_person_detected, assistance_needed, vip_arrival, watchlist_match)"
        )

    # ------------------------------------------------------------------
    # Watchlist (WANTED) — persists alert + dispatches when a flagged
    # guest is recognized. Per-guest cooldown shared with other handlers.
    # ------------------------------------------------------------------
    def _on_watchlist_match(
        self,
        guest_id: int,
        guest_name: str = "",
        watch_reason: str = "",
        track_id: Optional[int] = None,
        confidence: float = 0.0,
        **_,
    ) -> None:
        if not self._cooldown_check(("wanted", guest_id)):
            return
        self._create_and_dispatch(
            alert_type=AlertType.WANTED,
            title=f"Watchlist match: {guest_name or f'Guest #{guest_id}'}",
            description=(
                (watch_reason or "Guest flagged for staff attention.")
                + f" (match {confidence * 100:.0f}%)"
            ),
            severity=3,
            guest_id=guest_id,
        )

    # ------------------------------------------------------------------
    # Event handlers — each turns a detection event into an Alert + dispatch
    # ------------------------------------------------------------------
    def _on_unknown_person(self, track_id: int, dwell_time: float = 0.0, **_) -> None:
        if not self._cooldown_check(("unknown", track_id)):
            return
        self._create_and_dispatch(
            alert_type=AlertType.SECURITY,
            title="Unrecognized person lingering in the lobby",
            description=(
                f"Track #{track_id} has been present for "
                f"{int(dwell_time)} seconds without identification."
            ),
            severity=2,
            person_description=f"Unknown track {track_id}",
        )

    def _on_assistance_needed(
        self,
        track_id: int,
        guest_id: Optional[int] = None,
        dwell_time: float = 0.0,
        **_,
    ) -> None:
        if not self._cooldown_check(("assistance", track_id)):
            return
        self._create_and_dispatch(
            alert_type=AlertType.ASSISTANCE,
            title="Guest may need assistance",
            description=(
                f"Guest (track #{track_id}) has been waiting "
                f"~{int(dwell_time)} seconds. Please check in with them."
            ),
            severity=1,
            guest_id=guest_id,
        )

    def _on_vip_arrival(
        self,
        guest_id: int,
        guest_name: str = "",
        confidence: float = 0.0,
        **_,
    ) -> None:
        if not self._cooldown_check(("vip", guest_id)):
            return
        self._create_and_dispatch(
            alert_type=AlertType.VIP_ARRIVAL,
            title=f"VIP arrival: {guest_name or f'Guest #{guest_id}'}",
            description=(
                f"VIP guest detected at reception "
                f"(match confidence {confidence:.2f})."
            ),
            severity=3,
            guest_id=guest_id,
        )

    # ------------------------------------------------------------------
    # Persist + dispatch helpers
    # ------------------------------------------------------------------
    def _create_and_dispatch(
        self,
        alert_type: AlertType,
        title: str,
        description: str,
        severity: int = 1,
        **alert_kwargs,
    ) -> None:
        alert: Optional[Alert] = None
        db = SessionLocal()
        try:
            alert = AlertRepository.create(
                db,
                alert_type=alert_type,
                title=title,
                description=description,
                severity=severity,
                **alert_kwargs,
            )
        except Exception as e:
            logger.error(f"AlertRepository.create failed: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()

        if alert is None:
            return

        # Re-broadcast so the WebSocket handler in api/app.py picks it up
        event_bus.publish(
            "alert_created",
            alert_id=alert.id,
            alert_type=alert_type.value,
            title=title,
            description=description,
            severity=severity,
        )

        # Out-of-band channels (fail-soft)
        if settings.alert.email_enabled:
            self.send_email(alert)
        if settings.alert.sms_enabled:
            self.send_sms(alert)

    def _cooldown_check(self, key: tuple) -> bool:
        """Return True if enough time has elapsed since the last firing."""
        from time import monotonic
        now = monotonic()
        with self._lock:
            last = self._last_fire.get(key, 0.0)
            if now - last < _COOLDOWN_SECONDS:
                return False
            self._last_fire[key] = now
        return True

    # ------------------------------------------------------------------
    # Channel implementations (both fail-soft)
    #
    # Console-fallback mode: when real SMTP / Twilio credentials are
    # not configured but the corresponding `alert.*_enabled` flag is True,
    # we WRITE the dispatch contents to logs/outbox/{email,sms}.log so
    # operators can verify the trigger path works end-to-end without paying
    # for real credentials. Switching to real creds is then a config-only
    # change.
    # ------------------------------------------------------------------
    def _write_outbox(self, channel: str, payload: dict) -> None:
        """Append a JSON line to logs/outbox/{channel}.log."""
        import json, os
        try:
            d = "logs/outbox"
            os.makedirs(d, exist_ok=True)
            with open(f"{d}/{channel}.log", "a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.debug(f"outbox write failed ({channel}): {e}")

    def send_email(self, alert: Alert) -> bool:
        s = settings.secrets
        recipients = s.alert_email_recipients
        if not (s.smtp_host and s.smtp_username and recipients):
            # Console fallback so the dispatch path is still observable
            # during demos / before SMTP is provisioned.
            self._write_outbox("email", {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "alert_id": alert.id,
                "type": alert.alert_type.value,
                "severity": alert.severity,
                "title": alert.title,
                "description": alert.description,
                "recipients": recipients or [],
                "smtp_configured": False,
            })
            logger.info(f"Email console-fallback for alert_id={alert.id} (SMTP not configured)")
            return False
        try:
            msg = EmailMessage()
            msg["Subject"] = f"[Smart Reception] {alert.title}"
            msg["From"] = s.smtp_username
            msg["To"] = ", ".join(recipients)
            body = (
                f"{alert.description or ''}\n\n"
                f"Type: {alert.alert_type.value}\n"
                f"Severity: {alert.severity}\n"
                f"Time: {datetime.now(timezone.utc).isoformat()}"
            )
            msg.set_content(body)

            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as smtp:
                smtp.starttls()
                smtp.login(s.smtp_username, s.smtp_password)
                smtp.send_message(msg)
            logger.info(f"Email alert sent for alert_id={alert.id}")
            return True
        except Exception as e:
            logger.error(f"Email send failed for alert_id={alert.id}: {e}")
            return False

    def send_sms(self, alert: Alert) -> bool:
        s = settings.secrets
        recipients = s.alert_sms_recipients
        if not (s.twilio_account_sid and s.twilio_auth_token and s.twilio_from_number and recipients):
            # Console fallback
            self._write_outbox("sms", {
                "ts": datetime.now().isoformat(timespec="seconds"),
                "alert_id": alert.id,
                "type": alert.alert_type.value,
                "severity": alert.severity,
                "body": f"[Smart Reception] {alert.title}",
                "recipients": recipients or [],
                "twilio_configured": False,
            })
            logger.info(f"SMS console-fallback for alert_id={alert.id} (Twilio not configured)")
            return False
        try:
            # Lazy import: twilio is optional at install time
            from twilio.rest import Client  # type: ignore
            client = Client(s.twilio_account_sid, s.twilio_auth_token)
            body = f"[Smart Reception] {alert.title}"
            for number in recipients:
                client.messages.create(
                    body=body, from_=s.twilio_from_number, to=number
                )
            logger.info(f"SMS alert sent for alert_id={alert.id}")
            return True
        except ImportError:
            logger.warning("twilio package not installed; SMS disabled")
            return False
        except Exception as e:
            logger.error(f"SMS send failed for alert_id={alert.id}: {e}")
            return False


# Module-level singleton — auto-subscribes when first imported (typically
# from core.controller during app startup).
alert_notifier = AlertNotifier()
