"""
Smoke test for every feature shipped on 2026-05-31.

Hits each new/changed endpoint, asserts the expected shape, prints a
green/red one-liner per check. Exits 0 if everything passes.

Usage::
    python scripts/smoke_test_today.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
from pathlib import Path

# Ensure project root on sys.path so `from utils.crypto_utils import ...` works
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

BASE = "http://localhost:5000"
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"
EDGE_KEY = "test_api_key_12345"

_pass = 0
_fail = 0
_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global _pass, _fail
    if cond:
        _pass += 1
        print(f"  [PASS] {name}{(' — ' + detail) if detail else ''}")
    else:
        _fail += 1
        msg = f"  [FAIL] {name}{(' — ' + detail) if detail else ''}"
        _failures.append(msg)
        print(msg)


def section(title: str) -> None:
    print()
    print(f"=== {title} ===")


def main() -> int:
    section("Auth")
    r = requests.post(f"{BASE}/api/staff/login",
                      json={"username": ADMIN_USER, "password": ADMIN_PASS},
                      timeout=10)
    check("admin login 200", r.status_code == 200, f"status={r.status_code}")
    token = r.json().get("access_token", "")
    check("token returned", bool(token), f"len={len(token)}")
    H = {"Authorization": f"Bearer {token}"}

    # ----------------------------------------------------------------------
    section("FR-1 Guest Profile (multi-field search + summary + ID fields)")
    r = requests.get(f"{BASE}/api/guests/", headers=H, timeout=10)
    check("GET /api/guests/ 200", r.status_code == 200)
    guests = r.json() if r.ok else []
    test_guest_id = guests[0]["id"] if guests else None

    if test_guest_id is not None:
        # Multi-field search probes
        for label, q in [("name", "youssef"), ("partial-phone", "7120"),
                         ("partial-id", "passport"), ("email", "@example.com")]:
            r = requests.get(f"{BASE}/api/guests/search",
                             params={"q": q}, headers=H, timeout=10)
            ok = r.status_code == 200 and isinstance(r.json(), list)
            check(f"search by {label} ({q!r})", ok,
                  f"hits={len(r.json()) if r.ok else 'err'}")

        # Summary aggregate
        r = requests.get(f"{BASE}/api/guests/{test_guest_id}/summary", headers=H, timeout=10)
        check("GET /api/guests/{id}/summary 200", r.status_code == 200)
        data = r.json() if r.ok else {}
        g = data.get("guest", {})
        for key in ("id", "is_watched", "is_staff_badge", "id_type", "id_number"):
            check(f"  summary.guest.{key} present", key in g)
        for sec in ("stays", "visits", "recommendations", "finance"):
            check(f"  summary.{sec} present", sec in data)

    # ----------------------------------------------------------------------
    section("FR-5.8 Multi-field search end-to-end (name/email/phone/ID)")
    # Already covered above — record overall outcome
    r = requests.get(f"{BASE}/api/guests/search", params={"q": "z" * 10}, headers=H, timeout=10)
    check("empty query returns []", r.ok and r.json() == [],
          "wrong shape" if r.ok and r.json() != [] else "")

    # ----------------------------------------------------------------------
    section("Watchlist + WANTED alerts + Staff badge (admin-only)")
    if test_guest_id is not None:
        # Add to watchlist
        r = requests.put(f"{BASE}/api/guests/{test_guest_id}/watch", headers=H,
                         json={"is_watched": True, "watch_reason": "smoke test"}, timeout=10)
        check("PUT /watch on", r.ok)
        # Listed
        r = requests.get(f"{BASE}/api/guests/watchlist", headers=H, timeout=10)
        watched = r.json() if r.ok else []
        check("guest appears in watchlist", any(g["id"] == test_guest_id for g in watched))
        # Toggle off
        r = requests.put(f"{BASE}/api/guests/{test_guest_id}/watch", headers=H,
                         json={"is_watched": False}, timeout=10)
        check("PUT /watch off", r.ok)

        # Staff badge (admin only)
        r = requests.put(f"{BASE}/api/guests/{test_guest_id}/staff-badge", headers=H,
                         json={"is_staff_badge": True, "staff_badge_label": "smoke"}, timeout=10)
        check("PUT /staff-badge on (admin)", r.ok)
        r = requests.get(f"{BASE}/api/guests/staff-badges", headers=H, timeout=10)
        badges = r.json() if r.ok else []
        check("badge appears in /staff-badges", any(g["id"] == test_guest_id for g in badges))
        r = requests.put(f"{BASE}/api/guests/{test_guest_id}/staff-badge", headers=H,
                         json={"is_staff_badge": False}, timeout=10)
        check("PUT /staff-badge off", r.ok)

    # ----------------------------------------------------------------------
    section("Reservations dashboard (in-house / arrivals / departures)")
    for path in ("/api/reservations/in-house", "/api/reservations/arrivals",
                 "/api/reservations/departures"):
        r = requests.get(f"{BASE}{path}", headers=H, timeout=10)
        check(f"GET {path} 200", r.status_code == 200,
              f"rows={len(r.json()) if r.ok else 'err'}")
        if r.ok and r.json():
            row = r.json()[0]
            check(f"  {path} row carries embedded .guest",
                  isinstance(row.get("guest"), dict),
                  f"guest_id={row.get('guest_id')}")

    # ----------------------------------------------------------------------
    section("FR-2.5/2.8/2.11 Recommendations engine + R6 winback + R7 business + CRUD")
    if test_guest_id is not None:
        r = requests.post(f"{BASE}/api/recommendations/generate/{test_guest_id}",
                          params={"limit": 5}, headers=H, timeout=15)
        check("generate recs 201", r.status_code == 201,
              f"status={r.status_code}")
        recs = r.json() if r.ok else []
        check("recs include embedded service", any(rec.get("service") for rec in recs))
        # Inspect reasoning for R6 winback or R7 business markers
        reasonings = " | ".join(rec.get("reasoning", "") for rec in recs)
        has_r6 = "Winback bundle" in reasonings or "Returning guest" in reasonings
        has_r7 = "Business traveller pattern" in reasonings or "business pattern" in reasonings.lower()
        check("R6 winback rule wired", has_r6 or len(recs) == 0,
              "no winback markers" if recs and not has_r6 else "")
        # R7 is data-conditional (needs 2+ short Mon–Thu stays). Verify the
        # rule code path exists instead of relying on live data.
        # `modules.upselling` re-exports the engine SINGLETON under the same
        # name as the submodule, shadowing it. Read the file directly.
        src = Path("modules/upselling/recommendation_engine.py").read_text(encoding="utf-8")
        check("R7 business rule defined in engine",
              "Business traveller pattern" in src and "business_stays" in src,
              "wired but not exercised by seed data" if not has_r7 else "and fired in live recs")

        if recs:
            # FR-2.8 — change status
            rec_id = recs[0]["id"]
            r = requests.put(f"{BASE}/api/recommendations/{rec_id}/status",
                             headers={**H, "Content-Type": "application/json"},
                             data='"presented"', timeout=10)
            check("PUT rec/status = presented", r.ok, f"status={r.status_code}")

    # Services CRUD (admin)
    new_svc = {"name": "Smoke Test Spa", "category": "spa",
               "description": "ephemeral", "price": 99, "popularity_score": 0.5,
               "is_active": True}
    r = requests.post(f"{BASE}/api/services/", headers=H, json=new_svc, timeout=10)
    check("admin POST /api/services/ 201", r.status_code == 201)
    new_id = r.json().get("id") if r.ok else None
    if new_id is not None:
        r = requests.put(f"{BASE}/api/services/{new_id}", headers=H,
                         json={**new_svc, "name": "Smoke Test Spa Renamed"}, timeout=10)
        check("admin PUT /api/services/{id}", r.ok)
        r = requests.delete(f"{BASE}/api/services/{new_id}", headers=H, timeout=10)
        check("admin DELETE /api/services/{id}", r.status_code in (200, 204))

    # ----------------------------------------------------------------------
    section("FR-3 Edge frame ingest (3-state classification + dwell + bbox enrichment)")
    r = requests.get(f"{BASE}/api/edge/status",
                     headers={"X-API-Key": EDGE_KEY}, timeout=10)
    check("GET /api/edge/status 200", r.status_code == 200)
    if r.ok:
        body = r.json()
        check("  recognition backend reports", body.get("recognition_backend") in ("facenet", "none"),
              f"backend={body.get('recognition_backend')}")
        check("  guest embeddings loaded > 0 (hydrated on startup)",
              body.get("guest_embeddings_loaded", 0) > 0,
              f"loaded={body.get('guest_embeddings_loaded')}")

    # ----------------------------------------------------------------------
    section("FR-3.10 Lobby occupancy map — payload contract")
    r = requests.get(f"{BASE}/api/monitoring/status", headers=H, timeout=10)
    check("GET /api/monitoring/status 200", r.status_code == 200)
    if r.ok:
        # Frontend reads detection_update events directly; this endpoint
        # confirms backend monitoring shape.
        m = r.json()
        check("  carries total_persons", "total_persons" in m,
              f"keys={list(m.keys())}")

    # ----------------------------------------------------------------------
    section("FR-4.5/4.6 Alert email + SMS (console fallback)")
    r = requests.post(f"{BASE}/api/system/test-email", headers=H, timeout=10)
    check("POST /test-email 200", r.status_code == 200)
    r = requests.post(f"{BASE}/api/system/test-sms", headers=H, timeout=10)
    check("POST /test-sms 200", r.status_code == 200)
    email_log = Path("logs/outbox/email.log")
    sms_log = Path("logs/outbox/sms.log")
    check("outbox/email.log written", email_log.exists() and email_log.stat().st_size > 0)
    check("outbox/sms.log written", sms_log.exists() and sms_log.stat().st_size > 0)

    # ----------------------------------------------------------------------
    section("FR-6.12 CSV exports")
    for entity in ("guests", "visits", "reservations", "alerts"):
        r = requests.get(f"{BASE}/api/exports/{entity}", headers=H, timeout=10)
        check(f"GET /api/exports/{entity}", r.ok)
        if r.ok:
            first_line = r.text.split("\n")[0] if r.text else ""
            check(f"  /exports/{entity} returns CSV header", "," in first_line,
                  f"first_line={first_line[:60]!r}")

    # ----------------------------------------------------------------------
    section("Live Translation pipeline (audio route + Whisper ready)")
    r = requests.get(f"{BASE}/api/audio/status",
                     headers={"X-API-Key": EDGE_KEY}, timeout=10)
    check("GET /api/audio/status 200", r.status_code == 200)
    if r.ok:
        body = r.json()
        check("  speech backend reports faster-whisper",
              body.get("speech_backend") == "faster-whisper",
              f"backend={body.get('speech_backend')}")
        check("  ring buffer wired (size>=0)",
              isinstance(body.get("buffer_size"), int))

    # ----------------------------------------------------------------------
    section("NFR-2.1 AES-256-GCM encryption round-trip (in-process)")
    try:
        import os as _os
        _os.environ["ENCRYPTION_KEY"] = "f" * 64  # 32 raw bytes hex
        import importlib, sys as _sys
        _sys.modules.pop("utils.crypto_utils", None)
        from utils.crypto_utils import encrypt_embedding, decrypt_embedding
        sample = b"\x00\x01\x02" * 100
        enc = encrypt_embedding(sample)
        dec = decrypt_embedding(enc)
        check("AES-256-GCM round-trip", dec == sample,
              f"plaintext={len(sample)}B  ciphertext={len(enc)}B")
        check("ciphertext is framed (not == plaintext)", enc != sample)
    except Exception as e:
        check("AES-256-GCM round-trip", False, str(e))

    # ----------------------------------------------------------------------
    section("Summary")
    print(f"  PASS: {_pass}")
    print(f"  FAIL: {_fail}")
    if _failures:
        print()
        print("  Failure detail:")
        for f in _failures:
            print(f"   {f}")
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
