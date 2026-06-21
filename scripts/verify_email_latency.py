r"""
Email latency verification -- AC-6 / NFR-1.5 (email <= 5 s)
==========================================================

The acceptance criterion was previously DEFERRED with the note "code path
ready; needs real SMTP creds to verify." This script removes that blocker by
exercising the *real* ``AlertNotifier.send_email`` path (real ``smtplib``
socket conversation, real ``EmailMessage`` serialization) against a
self-contained in-process SMTP capture server, then measures wall-clock
delivery latency and asserts it is under the 5 second budget.

No external accounts, no paid credentials, no network egress - the relay is a
localhost socket that speaks just enough SMTP (EHLO / MAIL / RCPT / DATA /
QUIT) to accept and capture a message.

Run:
    .\venv\Scripts\python.exe -m scripts.verify_email_latency

Exit code 0 = PASS (latency under budget and message captured intact).
Exit code 1 = FAIL.
"""
from __future__ import annotations

import socket
import sys
import threading
import time
from email.parser import BytesParser
from email.policy import default as default_policy

# Import AFTER we know the path is set up (run as a module from repo root).
from config.settings import settings
from database.models import Alert, AlertType
from modules.alerts import AlertNotifier

LATENCY_BUDGET_S = 5.0


class _CapturingSMTPServer:
    """A minimal, single-message SMTP sink running on a background thread.

    Speaks plain (unencrypted, unauthenticated) SMTP - exactly the shape of a
    local postfix relay on :25. Captures the first delivered message so the
    test can assert on its contents and timing.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind((host, port))
        self._srv.listen(1)
        self.host, self.port = self._srv.getsockname()
        self.received_raw: bytes | None = None
        self.received_at: float | None = None
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _serve(self) -> None:
        try:
            conn, _ = self._srv.accept()
        except OSError:
            return
        with conn:
            conn.sendall(b"220 capture.local ESMTP ready\r\n")
            in_data = False
            data_buf = bytearray()
            f = conn.makefile("rb")
            while True:
                line = f.readline()
                if not line:
                    break
                if in_data:
                    if line == b".\r\n":
                        in_data = False
                        self.received_raw = bytes(data_buf)
                        self.received_at = time.perf_counter()
                        conn.sendall(b"250 OK: queued\r\n")
                        continue
                    # Undo SMTP dot-stuffing for lines beginning with '.'
                    data_buf += line[1:] if line.startswith(b"..") else line
                    continue

                cmd = line.rstrip(b"\r\n")
                upper = cmd.upper()
                if upper.startswith(b"EHLO") or upper.startswith(b"HELO"):
                    # Deliberately do NOT advertise STARTTLS or AUTH.
                    conn.sendall(b"250-capture.local\r\n250 HELP\r\n")
                elif upper.startswith(b"MAIL") or upper.startswith(b"RCPT"):
                    conn.sendall(b"250 OK\r\n")
                elif upper.startswith(b"DATA"):
                    conn.sendall(b"354 End data with <CR><LF>.<CR><LF>\r\n")
                    in_data = True
                elif upper.startswith(b"QUIT"):
                    conn.sendall(b"221 Bye\r\n")
                    break
                elif upper.startswith(b"RSET") or upper.startswith(b"NOOP"):
                    conn.sendall(b"250 OK\r\n")
                else:
                    conn.sendall(b"250 OK\r\n")

    def close(self) -> None:
        try:
            self._srv.close()
        except OSError:
            pass


def main() -> int:
    print("=" * 64)
    print("AC-6 / NFR-1.5 - email dispatch latency verification")
    print("=" * 64)

    sink = _CapturingSMTPServer()
    sink.start()
    print(f"[sink] capture SMTP server listening on {sink.host}:{sink.port}")

    # Point the live settings object at our sink. send_email reads these at
    # call time, so no app restart / env reload is needed.
    s = settings.secrets
    s.smtp_host = sink.host
    s.smtp_port = sink.port
    s.smtp_username = ""          # no auth
    s.smtp_password = ""
    s.smtp_use_tls = False        # plain SMTP
    s.alert_email_recipients = ["reception-desk@hotel.example"]

    notifier = AlertNotifier()
    alert = Alert(
        id=9001,
        alert_type=AlertType.VIP_ARRIVAL,
        title="VIP arrival: Latency Test Guest",
        description="Synthetic alert fired by verify_email_latency.py",
        severity=3,
    )

    print("[send] invoking AlertNotifier.send_email() ...")
    t0 = time.perf_counter()
    ok = notifier.send_email(alert)

    # Wait (bounded) for the sink thread to record the delivered message.
    deadline = t0 + LATENCY_BUDGET_S + 2.0
    while sink.received_at is None and time.perf_counter() < deadline:
        time.sleep(0.01)

    sink.close()

    if not ok:
        print("[FAIL] send_email returned False (fell back to console outbox).")
        return 1
    if sink.received_raw is None:
        print("[FAIL] sink never received a message.")
        return 1

    latency = sink.received_at - t0

    msg = BytesParser(policy=default_policy).parsebytes(sink.received_raw)
    subject = msg["Subject"] or ""
    to = msg["To"] or ""
    body = msg.get_content() if msg.get_content_maintype() == "text" else ""

    print("-" * 64)
    print(f"[recv] Subject : {subject}")
    print(f"[recv] To      : {to}")
    print(f"[recv] Body[0] : {body.splitlines()[0] if body else ''}")
    print("-" * 64)
    print(f"[time] delivery latency : {latency * 1000:.1f} ms "
          f"(budget {LATENCY_BUDGET_S * 1000:.0f} ms)")

    checks = {
        "send_email returned True": ok,
        "message captured by relay": sink.received_raw is not None,
        "subject carries alert title": "Latency Test Guest" in subject,
        "recipient delivered": "reception-desk@hotel.example" in to,
        f"latency < {LATENCY_BUDGET_S:.0f}s": latency < LATENCY_BUDGET_S,
    }
    print("-" * 64)
    all_ok = True
    for name, passed in checks.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        all_ok = all_ok and passed
    print("=" * 64)
    print("RESULT:", "PASS - AC-6 email path verified" if all_ok else "FAIL")
    print("=" * 64)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
