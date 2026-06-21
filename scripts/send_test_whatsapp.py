r"""
Real WhatsApp / SMS send test (manual / one-off)
================================================

Sends an ACTUAL message through Twilio using the credentials in `.env`, via the
application's real `AlertNotifier.send_sms()` path. Use it to confirm the
WhatsApp Sandbox (or an SMS trial number) is wired up correctly.

WhatsApp Sandbox checklist (TWILIO_CHANNEL=whatsapp):
  1. Each recipient must first send the join phrase ("join <code>") from
     WhatsApp to the sandbox number (+14155238886) — found in the Twilio
     console under Messaging → Try it out → WhatsApp Sandbox.
  2. The sandbox session lasts 72h; re-join if messages stop arriving.
  3. On a trial account the recipient must also be a Verified Caller ID.

If the notifier path returns False, this script retries the Twilio call
directly so the precise API error (code 63007, 21608, etc.) is surfaced.
The auth token is never printed.

Usage:
    .\venv\Scripts\python.exe -m scripts.send_test_whatsapp --to +9613XXXXXX
"""
from __future__ import annotations

import argparse
import sys
import time

from config.settings import settings
from database.models import Alert, AlertType
from modules.alerts import AlertNotifier


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Send a real Twilio WhatsApp/SMS test.")
    p.add_argument("--to", default=None, help="Comma-separated recipient list (overrides .env)")
    p.add_argument("--channel", default=None, choices=["sms", "whatsapp"],
                   help="Override TWILIO_CHANNEL for this run")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    s = settings.secrets

    if args.channel:
        s.twilio_channel = args.channel
    if args.to:
        s.alert_sms_recipients = [a.strip() for a in args.to.split(",") if a.strip()]

    print("=" * 64)
    print("Real Twilio send test")
    print("=" * 64)
    print(f"  Channel     : {s.twilio_channel}")
    print(f"  Account SID : {(s.twilio_account_sid[:6] + '…') if s.twilio_account_sid else '(none)'}")
    print(f"  Auth token  : {'set (' + str(len(s.twilio_auth_token)) + ' chars)' if s.twilio_auth_token else '(none)'}")
    print(f"  From        : {s.twilio_from_number or '(none)'}")
    print(f"  Recipients  : {', '.join(s.alert_sms_recipients) or '(none)'}")
    print("-" * 64)

    if not (s.twilio_account_sid and s.twilio_auth_token and s.twilio_from_number and s.alert_sms_recipients):
        print("[ABORT] need SID, auth token, From number and at least one recipient (--to).")
        return 2

    alert = Alert(
        id=8000,
        alert_type=AlertType.VIP_ARRIVAL,
        title="Smart Reception — Twilio delivery test",
        description="Real end-to-end test of the Twilio alert channel.",
        severity=3,
    )

    notifier = AlertNotifier()
    print("[send] AlertNotifier.send_sms() ...")
    t0 = time.perf_counter()
    ok = notifier.send_sms(alert)
    dt = time.perf_counter() - t0

    if ok:
        print("-" * 64)
        print(f"[PASS] send_sms returned True in {dt:.2f} s. Check the device.")
        print("=" * 64)
        return 0

    # send_sms swallows the exception and logs it — reproduce directly so the
    # raw Twilio error is visible.
    print("-" * 64)
    print("[WARN] send_sms returned False — reproducing to capture the error:")
    try:
        from twilio.rest import Client
        from modules.alerts.notification_templates import render_whatsapp
        client = Client(s.twilio_account_sid, s.twilio_auth_token)
        is_wa = s.twilio_channel == "whatsapp"
        sender = AlertNotifier._wa_address(s.twilio_from_number) if is_wa else s.twilio_from_number
        body = render_whatsapp(alert)
        for number in s.alert_sms_recipients:
            to = AlertNotifier._wa_address(number) if is_wa else number
            msg = client.messages.create(body=body, from_=sender, to=to)
            print(f"[ok] queued sid={msg.sid} status={msg.status} to={to}")
        print("[PASS] direct send succeeded — check the device.")
        return 0
    except Exception as e:  # noqa: BLE001 — we want the raw error text
        print(f"[FAIL] {type(e).__name__}: {e}")
        print("=" * 64)
        return 1


if __name__ == "__main__":
    sys.exit(main())
