# Smart Reception Assistant — Change Log Addendum (v1.2)

**Date:** 2026-06-20
**Scope:** Alerting/notification subsystem (FR-4), upselling popularity model (FR-2),
and test-data tooling. No changes to the face-recognition pipeline.

This addendum documents the changes made after the v1.1 "Compact AI-Powered Smart
Reception Assistant" baseline. It supplements the SDD and SysRS rather than
replacing them.

---

## 1. Per-Incident Notification Templates (FR-4)

**Problem.** Every alert e-mail used a single generic plain-text body
(`description + type + severity + time`). All incident types looked identical and
carried no guidance for staff.

**Change.** Added a dedicated template module,
[`modules/alerts/notification_templates.py`](../modules/alerts/notification_templates.py),
that renders a tailored notification for each `AlertType`. A single `_INCIDENTS`
table drives presentation so every incident has one identity (icon, label, accent
colour, and a "what to do next" call to action) across all channels.

| Incident (`AlertType`) | Subject prefix | Call to action |
|---|---|---|
| `security` | 🚨 Security alert | Dispatch a staff member to the lobby to identify this person. |
| `wanted` | ⛔ Watchlist match | Notify security immediately. Do not approach — follow escalation procedure. |
| `assistance` | 🙋 Guest needs assistance | Check in with the waiting guest at reception. |
| `vip_arrival` | ⭐ VIP arrival | Prepare the VIP welcome and notify the duty manager. |
| `arrival` | 🛎️ Guest arrival | Greet the arriving guest and begin check-in. |
| `due_out` | 🕑 Guest due out | A due-out guest is standing at the reception. |
| *(unknown/future)* | 🔔 Reception alert | Review this alert in the Smart Reception dashboard. |

**Public API**
- `render_alert_email(alert) -> (subject, text_body, html_body)` — branded,
  severity-coloured HTML card plus a plain-text fallback.
- `render_whatsapp(alert) -> str` — compact message using WhatsApp's `*bold*` /
  `_italic_` markup (degrades to plain SMS).

**Design notes:** zero new dependencies (string formatting + `html.escape`, no
templating engine); fail-soft — unknown alert types fall back to a generic block
instead of raising.

**E-mail dispatch** ([`alert_notifier.py`](../modules/alerts/alert_notifier.py))
now builds a multipart message: plain-text + HTML alternative, so clients that
block HTML still render the text body.

---

## 2. WhatsApp / Twilio Alert Channel (FR-4)

**Change.** The SMS path was extended to support Twilio's **WhatsApp Sandbox** in
addition to plain SMS.

- New setting `twilio_channel` (`sms` | `whatsapp`) in
  [`config/settings.py`](../config/settings.py), read from env `TWILIO_CHANNEL`.
- `send_sms()` now normalises addresses with a `whatsapp:` prefix on both the From
  (sandbox number) and each recipient when the channel is `whatsapp`, via the
  helper `AlertNotifier._wa_address()`. SMS behaviour is unchanged.
- The message body is rendered by `render_whatsapp()` (Section 1) — the same
  per-incident identity used for e-mail.
- `twilio==9.3.0` (already in `requirements.txt`) is now installed in the venv.

**Configuration** (`.env` / `.env.example`):

```
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=********
TWILIO_CHANNEL=whatsapp
TWILIO_FROM_NUMBER=+14155238886         # Twilio shared WhatsApp Sandbox number
ALERT_SMS_RECIPIENTS=+96171256807,+96181995046
```

**Operational requirement:** each recipient must first join the sandbox
(`join <code>` to +1 415 523 8886 from WhatsApp); on a trial account they must
also be a Verified Caller ID. The 72-hour sandbox session must be refreshed
periodically.

---

## 3. Recipient Privacy — Blind Copy (BCC)

**Problem.** Alert recipients were listed in the `To` header, so every notified
person could see the others' addresses.

**Change.** In `send_email()`, recipients are now placed in **`Bcc`**. A cosmetic
`To` header (the sending mailbox itself) avoids the "undisclosed-recipients"
display and helps deliverability. The delivery envelope is passed explicitly —
`send_message(msg, from_addr=sender, to_addrs=recipients)` — so the `Bcc` header
is stripped before transmission and only the listed recipients receive the mail
(the sending mailbox is not self-copied). Verified at the wire level: no `Bcc`
header is transmitted and the envelope equals the recipient list.

---

## 4. Statistics-Driven Service Popularity (FR-2)

**Problem.** `Service.popularity_score` was a hand-picked constant in the seed
file and never reflected real guest behaviour.

**Change.** The server now derives popularity from recommendation outcomes.

- [`ServiceRepository.popularity_from_stats(accepted, declined)`](../database/repositories/service_repository.py)
  — a **Laplace-smoothed acceptance rate** (Beta(1,1) prior):
  `score = (accepted + 1) / (accepted + declined + 2)`.
  - No history → neutral **0.5**.
  - Converges to `accepted / (accepted + declined)` as volume grows.
  - Smoothing prevents a service shown once and accepted once (0.667) from
    outranking one shown 100× and accepted 80× (0.794).
- `ServiceRepository.recompute_popularity(db, service_id=None)` — recomputes one
  service or the whole catalogue and stores the result on the row.
- **Live update:** [`api/routes/recommendations.py`](../api/routes/recommendations.py)
  refreshes a service's popularity immediately when a guest's recommendation is
  marked `ACCEPTED` or `DECLINED`.
- **Admin endpoint:** `POST /api/services/recompute-popularity` (admin/manager)
  recomputes the full catalogue on demand
  ([`api/routes/services.py`](../api/routes/services.py)).

The recommendation engine still reads `service.popularity_score` as its R1
baseline, so no engine logic changed — only the source of the number.

---

## 5. Mock Test Population — 100 Guests

**Change.** Added [`scripts/seed_mock_guests.py`](../scripts/seed_mock_guests.py)
to populate the database for full-system testing.

- Registers **100 realistic guests**: varied titles, 12 nationality/language
  locales (LB, SY, AE, SA, EG, US, GB, FR, DE, ES, IT, JP), VIP flags (~15%),
  dietary/room/pillow preferences, mixed statuses (active / checked-out / due-in /
  due-out / blacklisted), and ~4% watch-listed guests for security testing.
- Seeds ~400 recommendation accept/decline interactions (each service has a hidden
  "appeal") so the popularity statistics in Section 4 are meaningful, then runs the
  real `recompute_popularity` path.
- **Face embeddings are deliberately NOT mocked** — the recognition model is only
  meaningful against real faces; fabricated 512-d vectors would add noise and
  could be mistaken for enrolled identities. These guests are profile-registered
  but not face-enrolled.
- **Idempotent:** guests use the `@mock.example.com` domain and are skipped if a
  matching e-mail exists; re-running tops up to the target count. Flags:
  `--count`, `--reset-interactions`.

---

## 6. HTTPS / WSS Transport via Caddy (NFR-2.2 / NFR-2.3)

**Problem.** The dashboard, REST API and `/ws` WebSocket were served over plain
HTTP/WS; HTTPS/WSS was previously deferred.

**Change.** A [`Caddyfile`](../Caddyfile) in the repository root puts a Caddy
reverse proxy in front of the FastAPI app. Caddy terminates TLS and the app
keeps speaking plain HTTP/WS on `127.0.0.1:5000` — no application code changed.
WebSocket upgrades on `/ws` are proxied transparently (Connection/Upgrade headers
forwarded automatically), so the browser uses **WSS**.

Three ready-to-use site blocks are provided:
- `localhost` — local/demo, Caddy mints a locally-trusted certificate (no warning
  on this machine).
- LAN IP with `tls internal` — run `caddy trust` once per kiosk to install
  Caddy's local CA, then HTTPS works warning-free across the network.
- Public domain — automatic, auto-renewing Let's Encrypt certificate.

Run with `caddy run` from the repo root. `scripts/generate_self_signed_cert.py`
remains as a direct-to-uvicorn alternative. This closes NFR-2.2 (HTTPS) and
NFR-2.3 (WSS).

---

## 7. Configuration Fixes & Additions

- **Latent bug fixed — `config.yaml` alert section ignored.** The file keyed the
  block `alerts:` but the loader reads section `"alert"` (every other section uses
  the singular). The whole alert block was therefore silently discarded and
  dataclass defaults were used. Renamed the key to `alert:` so the configured
  values (cooldown, channel toggles) actually load.
- **`sms_enabled: true`** in `config.yaml` (was `false`).
- **New env var `TWILIO_CHANNEL`** documented in `.env.example`.

---

## 8. New / Modified Files

**New**
| File | Purpose |
|---|---|
| `modules/alerts/notification_templates.py` | Per-incident email + WhatsApp templates |
| `scripts/seed_mock_guests.py` | 100-guest mock population + interaction history |
| `scripts/send_test_whatsapp.py` | Manual Twilio WhatsApp/SMS send test |
| `Caddyfile` | Caddy reverse proxy → HTTPS/WSS (NFR-2.2 / NFR-2.3) |

**Modified**
| File | Change |
|---|---|
| `modules/alerts/alert_notifier.py` | Use templates; WhatsApp channel; BCC privacy |
| `config/settings.py` | `twilio_channel` setting |
| `config.yaml` | `alerts→alert` key fix; `sms_enabled: true` |
| `.env` / `.env.example` | Twilio WhatsApp configuration |
| `database/repositories/service_repository.py` | `popularity_from_stats`, `recompute_popularity` |
| `api/routes/recommendations.py` | Live popularity recompute on accept/decline |
| `api/routes/services.py` | `POST /recompute-popularity` endpoint |

---

## 9. Testing & Verification

- `pytest tests/test_recommendations.py tests/test_upselling.py` — **42 passed**
  after the popularity changes.
- Notification templates render for all incident types (email subject/HTML/text
  and WhatsApp body verified).
- BCC behaviour verified at the SMTP wire level: `Bcc` header absent on
  transmission; envelope recipients equal the configured list.
- `seed_mock_guests.py` executed: 100 guests + 402 interactions created;
  popularity recomputed and differentiated (0.19 – 0.82); re-run is a no-op
  (idempotent).
- HTTPS/WSS: `Caddyfile` validated with `caddy validate` against Caddy v2.11.4
  ("Valid configuration"). Run `caddy run` to serve `https://localhost`; a live
  browser/end-to-end session has not yet been exercised on this machine.
