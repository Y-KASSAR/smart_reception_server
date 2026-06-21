r"""
Real email send test (manual / one-off)
========================================

Sends an ACTUAL alert email to real inboxes through a real SMTP relay using
the credentials in `.env`. Unlike `verify_email_latency.py` (which uses a local
capture sink), this leaves the machine and lands in a real mailbox.

It uses the application's real `AlertNotifier.send_email()` path. If that path
reports failure, it then performs a direct `smtplib` attempt purely to surface
the exact server error (auth rejected, TLS, etc.) — the password is never
printed.

Usage:
    .\venv\Scripts\python.exe -m scripts.send_real_test_email \
        --host smtp.office365.com --to a@x.com,b@y.com

Defaults: host from $SMTP_HOST, recipients from --to (required if .env has the
placeholder recipients).
"""
from __future__ import annotations

import argparse
import smtplib
import ssl
import sys
import time
from datetime import datetime, timezone
from email.message import EmailMessage

from config.settings import settings
from database.models import Alert, AlertType
from modules.alerts import AlertNotifier


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Send a real alert test email.")
    p.add_argument("--host", default=None, help="SMTP host (overrides .env SMTP_HOST)")
    p.add_argument("--port", type=int, default=None, help="SMTP port (default 587)")
    p.add_argument("--to", default=None, help="Comma-separated recipient list")
    p.add_argument("--no-tls", action="store_true", help="Disable STARTTLS")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    s = settings.secrets

    if args.host:
        s.smtp_host = args.host
    if args.port:
        s.smtp_port = args.port
    if args.no_tls:
        s.smtp_use_tls = False
    if args.to:
        s.alert_email_recipients = [a.strip() for a in args.to.split(",") if a.strip()]

    print("=" * 64)
    print("Real email send test")
    print("=" * 64)
    print(f"  SMTP host   : {s.smtp_host}:{s.smtp_port}  (STARTTLS={s.smtp_use_tls})")
    print(f"  Username    : {s.smtp_username or '(none)'}")
    print(f"  Password    : {'set (' + str(len(s.smtp_password)) + ' chars)' if s.smtp_password else '(none)'}")
    print(f"  Recipients  : {', '.join(s.alert_email_recipients) or '(none)'}")
    print("-" * 64)

    if not s.smtp_host or not s.alert_email_recipients:
        print("[ABORT] need both SMTP_HOST and at least one recipient (--to).")
        return 2

    alert = Alert(
        id=7000,
        alert_type=AlertType.VIP_ARRIVAL,
        title="Smart Reception — real email delivery test",
        description=(
            "This is a real end-to-end delivery test of the Smart Reception "
            "alert email channel (AC-6 / NFR-1.5). If you are reading this in "
            "your inbox, SMTP dispatch works against a live relay."
        ),
        severity=3,
    )

    notifier = AlertNotifier()
    print("[send] AlertNotifier.send_email() ...")
    t0 = time.perf_counter()
    ok = notifier.send_email(alert)
    dt = time.perf_counter() - t0

    if ok:
        print("-" * 64)
        print(f"[PASS] send_email returned True in {dt:.2f} s.")
        print("       Check the destination inboxes (and spam folder).")
        print("=" * 64)
        return 0

    # send_email failed (it swallows the exception and logs it). Reproduce the
    # SMTP conversation directly so the precise server error is visible.
    print("-" * 64)
    print("[WARN] send_email returned False — reproducing to capture the error:")
    try:
        from email.utils import formataddr
        msg = EmailMessage()
        sender = s.smtp_username or f"smart-reception@{s.smtp_host}"
        msg["Subject"] = f"[Smart Reception] {alert.title}"
        msg["From"] = formataddr((s.smtp_from_name or "Smart Reception", sender))
        msg["To"] = ", ".join(s.alert_email_recipients)
        msg.set_content(
            f"{alert.description}\n\nTime: {datetime.now(timezone.utc).isoformat()}"
        )
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            smtp.ehlo()
            if s.smtp_use_tls:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            if s.smtp_username and s.smtp_password:
                smtp.login(s.smtp_username, s.smtp_password)
            smtp.send_message(msg)
        print("[PASS] direct send succeeded on retry — check your inbox.")
        return 0
    except Exception as e:  # noqa: BLE001 — we want the raw error text
        print(f"[FAIL] {type(e).__name__}: {e}")
        print("=" * 64)
        return 1


if __name__ == "__main__":
    sys.exit(main())
