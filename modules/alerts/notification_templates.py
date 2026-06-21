"""
Per-incident notification templates (FR-4)
==========================================

Renders a tailored notification for each ``AlertType`` raised by
:class:`~modules.alerts.alert_notifier.AlertNotifier`, across both channels:

* **Email** — :func:`render_alert_email` → ``(subject, text_body, html_body)``.
* **WhatsApp / SMS** — :func:`render_whatsapp` → a single formatted string.

A single ``_INCIDENTS`` table drives both channels, so every incident keeps
one identity (icon, label, accent colour, and a "what to do next" call to
action) no matter where it is delivered. Email gets the full severity-
coloured HTML card; WhatsApp gets a compact message using WhatsApp's own
``*bold*`` / ``_italic_`` markup.

Design notes
------------
* **Zero new dependencies.** Bodies are assembled with ``str.format`` and
  manual ``html.escape`` — no Jinja2 / templating engine is pulled in.
* **Multipart-ready.** :func:`render_alert_email` returns ``(subject,
  text_body, html_body)``. The caller attaches the HTML as an alternative
  so inboxes that block HTML still get the plain-text version.
* **Fail-soft.** Unknown / future alert types fall back to a generic
  template rather than raising — consistent with the notifier's promise
  that a dispatch error can never crash the recognition loop.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Tuple

if TYPE_CHECKING:  # avoid a runtime import cycle with database.models
    from database.models import Alert


# ---------------------------------------------------------------------------
# Per-incident presentation. Keyed by AlertType.value so a missing/renamed
# enum member degrades to the generic block instead of KeyError-ing.
# ---------------------------------------------------------------------------
_INCIDENTS: dict[str, dict] = {
    "security": {
        "icon": "\U0001F6A8",          # 🚨
        "label": "Security",
        "subject": "Security alert",
        "accent": "#c0392b",
        "action": "Dispatch a staff member to the lobby to identify this person.",
    },
    "wanted": {
        "icon": "⛔",              # ⛔
        "label": "Watchlist match",
        "subject": "Watchlist match",
        "accent": "#8e44ad",
        "action": "Notify security immediately. Do not approach — follow your "
                  "watchlist escalation procedure.",
    },
    "assistance": {
        "icon": "\U0001F64B",          # 🙋
        "label": "Assistance",
        "subject": "Guest needs assistance",
        "accent": "#e67e22",
        "action": "Please check in with the waiting guest at reception.",
    },
    "vip_arrival": {
        "icon": "⭐",              # ⭐
        "label": "VIP arrival",
        "subject": "VIP arrival",
        "accent": "#d4af37",
        "action": "Prepare the VIP welcome and notify the duty manager.",
    },
    "arrival": {
        "icon": "\U0001F6CE️",    # 🛎️
        "label": "Guest arrival",
        "subject": "Guest arrival",
        "accent": "#2980b9",
        "action": "Greet the arriving guest and begin check-in.",
    },
    "due_out": {
        "icon": "\U0001F551",          # 🕑
        "label": "Due out",
        "subject": "Guest due out",
        "accent": "#16a085",
        "action": "A dueout guest is standing at the reception.",
    },
}

_GENERIC = {
    "icon": "\U0001F514",              # 🔔
    "label": "Reception alert",
    "subject": "Reception alert",
    "accent": "#34495e",
    "action": "Review this alert in the Smart Reception dashboard.",
}

# Severity (1..3) → human label shown in the body.
_SEVERITY_LABELS = {1: "Low", 2: "Medium", 3: "High"}


def _incident(alert: "Alert") -> dict:
    """Resolve the presentation block for an alert, generic-by-default."""
    try:
        key = alert.alert_type.value
    except Exception:
        key = ""
    return _INCIDENTS.get(key, _GENERIC)


def _severity_label(severity: int | None) -> str:
    return _SEVERITY_LABELS.get(severity or 0, f"Level {severity}")


def _timestamp(alert: "Alert") -> str:
    """ISO-8601 UTC timestamp; prefer the row's created_at, else now()."""
    ts = getattr(alert, "created_at", None) or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.isoformat(timespec="seconds")


def render_subject(alert: "Alert") -> str:
    """Return the e-mail subject line for an alert."""
    inc = _incident(alert)
    # e.g. "[Smart Reception] 🚨 Security alert — Unrecognized person lingering"
    title = (alert.title or inc["subject"]).strip()
    return f"[Smart Reception] {inc['icon']} {inc['subject']} — {title}"


def render_text(alert: "Alert") -> str:
    """Plain-text body (fallback for non-HTML mail clients)."""
    inc = _incident(alert)
    lines = [
        f"{inc['icon']}  {inc['label'].upper()}",
        "=" * 48,
        "",
        (alert.title or "").strip(),
        "",
        (alert.description or "").strip(),
        "",
        f"Type:     {alert.alert_type.value}",
        f"Severity: {_severity_label(alert.severity)} ({alert.severity})",
    ]
    if getattr(alert, "location", None):
        lines.append(f"Location: {alert.location}")
    if getattr(alert, "person_description", None):
        lines.append(f"Person:   {alert.person_description}")
    if getattr(alert, "guest_id", None):
        lines.append(f"Guest ID: {alert.guest_id}")
    lines += [
        f"Alert ID: {getattr(alert, 'id', '—')}",
        f"Time:     {_timestamp(alert)}",
        "",
        "ACTION REQUIRED",
        "-" * 48,
        inc["action"],
        "",
        "— Smart Reception Assistant",
    ]
    return "\n".join(lines)


def _row(label: str, value) -> str:
    """One <tr> of the details table; skipped by caller when value is empty."""
    return (
        '<tr>'
        f'<td style="padding:6px 12px;color:#7f8c8d;font-size:13px;'
        f'white-space:nowrap;vertical-align:top">{html.escape(label)}</td>'
        f'<td style="padding:6px 12px;color:#2c3e50;font-size:13px;'
        f'font-weight:600">{html.escape(str(value))}</td>'
        '</tr>'
    )


def render_html(alert: "Alert") -> str:
    """Branded, severity-coloured HTML body."""
    inc = _incident(alert)
    accent = inc["accent"]

    rows = [
        _row("Severity", f"{_severity_label(alert.severity)} ({alert.severity})"),
        _row("Type", alert.alert_type.value),
    ]
    if getattr(alert, "location", None):
        rows.append(_row("Location", alert.location))
    if getattr(alert, "person_description", None):
        rows.append(_row("Person", alert.person_description))
    if getattr(alert, "guest_id", None):
        rows.append(_row("Guest ID", alert.guest_id))
    rows.append(_row("Alert ID", getattr(alert, "id", "—")))
    rows.append(_row("Time", _timestamp(alert)))

    title = html.escape((alert.title or inc["subject"]).strip())
    description = html.escape((alert.description or "").strip())
    action = html.escape(inc["action"])

    return f"""\
<!DOCTYPE html>
<html lang="en">
<body style="margin:0;padding:24px;background:#eef1f5;
             font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:10px;
                overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.08)">
    <tr>
      <td style="background:{accent};padding:20px 24px">
        <span style="font-size:22px">{inc['icon']}</span>
        <span style="color:#ffffff;font-size:18px;font-weight:700;
                     vertical-align:middle;margin-left:6px">
          {html.escape(inc['label'])}
        </span>
      </td>
    </tr>
    <tr>
      <td style="padding:24px">
        <h1 style="margin:0 0 8px;font-size:18px;color:#2c3e50">{title}</h1>
        <p style="margin:0 0 20px;font-size:14px;color:#576574;line-height:1.5">
          {description}
        </p>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="background:#f8f9fb;border-radius:8px;margin-bottom:20px">
          {''.join(rows)}
        </table>
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="border-left:4px solid {accent};background:#f8f9fb;border-radius:4px">
          <tr>
            <td style="padding:12px 16px">
              <div style="font-size:11px;font-weight:700;letter-spacing:.05em;
                          text-transform:uppercase;color:{accent};margin-bottom:4px">
                Action required
              </div>
              <div style="font-size:14px;color:#2c3e50;line-height:1.5">{action}</div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    <tr>
      <td style="padding:16px 24px;background:#f8f9fb;border-top:1px solid #eef1f5;
                 font-size:12px;color:#95a5a6;text-align:center">
        Smart Reception Assistant · automated alert · do not reply
      </td>
    </tr>
  </table>
</body>
</html>"""


def render_alert_email(alert: "Alert") -> Tuple[str, str, str]:
    """Return ``(subject, text_body, html_body)`` for the given alert."""
    return render_subject(alert), render_text(alert), render_html(alert)


# ---------------------------------------------------------------------------
# WhatsApp / SMS
# ---------------------------------------------------------------------------
def render_whatsapp(alert: "Alert") -> str:
    """Compact message body for WhatsApp (and plain SMS).

    Uses WhatsApp's own inline markup — ``*bold*`` and ``_italic_`` — which
    degrades gracefully to literal characters on plain SMS. The same incident
    identity (icon, label, action) as the e-mail is reused so an operator
    sees a consistent message regardless of channel.
    """
    inc = _incident(alert)
    lines = [
        f"{inc['icon']} *Smart Reception — {inc['label']}*",
        "",
        f"*{(alert.title or inc['subject']).strip()}*",
    ]
    description = (alert.description or "").strip()
    if description:
        lines.append(description)
    lines += [
        "",
        f"Severity: {_severity_label(alert.severity)} ({alert.severity})",
    ]
    if getattr(alert, "location", None):
        lines.append(f"Location: {alert.location}")
    if getattr(alert, "person_description", None):
        lines.append(f"Person: {alert.person_description}")
    if getattr(alert, "guest_id", None):
        lines.append(f"Guest ID: {alert.guest_id}")
    lines += [
        f"Time: {_timestamp(alert)}",
        "",
        f"⚡ *Action:* {inc['action']}",
    ]
    return "\n".join(lines)
