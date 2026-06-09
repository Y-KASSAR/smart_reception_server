"""
PMS Data Import (CSV)
=====================
Imports guests + reservations from CSV files exported from any external
Property Management System (Opera, Cloudbeds, Mews, etc). Since we don't
have a real PMS to integrate with, this CSV pathway IS the test harness:
ask the front-desk team for any flat-file export they already produce
nightly, drop it in ``data/pms_imports/``, and run this script.

Idempotent: matches existing rows by email (guests) and reservation_code
(reservations). Existing rows get UPDATED, not duplicated.

CSV schemas (both files optional; only the ones present get imported):

    data/pms_imports/guests.csv:
        external_id,full_name,email,phone,nationality,id_type,id_number,vip_status,language_preference,notes

    data/pms_imports/reservations.csv:
        reservation_code,guest_email,room_number,room_type,check_in_date,
        check_out_date,num_guests,rate_per_night,total_amount,status,
        special_requests

Dates may be ISO-8601 (``2026-05-31T14:00``) or ``YYYY-MM-DD``. Status
values map to the ReservationStatus enum case-insensitively.

Usage::

    python scripts/import_pms.py                 # default ./data/pms_imports/
    python scripts/import_pms.py --dir /some/dir
    python scripts/import_pms.py --dry-run       # show what would change

To test without a PMS:
    python scripts/import_pms.py --generate-sample
        → writes a 12-row guests.csv + 10-row reservations.csv full of
          realistic Lebanese-hotel data into data/pms_imports/.
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import SessionLocal
from database.models import Guest, Reservation, ReservationStatus


_DEFAULT_DIR = Path("data") / "pms_imports"


# -----------------------------------------------------------------
# Sample data generator — gives you something to play with even
# without a real PMS feed.
# -----------------------------------------------------------------
SAMPLE_GUESTS = [
    # external_id, full_name, email, phone, nationality, id_type, id_number, vip, lang, notes
    ("PMS001", "Rami Khoury",      "rami.khoury@example.com",     "70300001", "LB", "civil_id", "001-A-1100", True,  "ar", "Prefers high-floor rooms"),
    ("PMS002", "Hana Saade",       "hana.saade@example.com",      "70300002", "LB", "passport", "LB7700321",  False, "fr", "Allergic to peanuts"),
    ("PMS003", "Omar Halabi",      "omar.halabi@example.com",     "70300003", "LB", "civil_id", "001-B-2233", True,  "ar", ""),
    ("PMS004", "Marie Dubois",     "marie.dubois@example.com",    "+33612345678","FR", "passport","FR12CDEFG", False, "fr", "Late check-in usual"),
    ("PMS005", "Klaus Berger",     "klaus.berger@example.com",    "+491511223344","DE","passport","DE998877",  False, "en", ""),
    ("PMS006", "Sofia Russo",      "sofia.russo@example.com",     "+393345566778","IT","passport","IT554433",  False, "it", "Wedding anniversary stay"),
    ("PMS007", "Ahmed Al-Mansoori","ahmed.almansoori@example.com","+971501112233","AE","passport","AE2211009", True,  "ar", "Always requests the spa package"),
    ("PMS008", "Yuki Tanaka",      "yuki.tanaka@example.com",     "+819011223344","JP","passport","JP8877665", False, "en", "Vegetarian"),
    ("PMS009", "Olivia Chen",      "olivia.chen@example.com",     "+14165550199",  "CA","passport","CA4421109", False, "en", ""),
    ("PMS010", "Karim El-Khoury",  "karim.elkhoury@example.com",  "70300010", "LB", "civil_id", "001-C-7788", False, "ar", "Repeat business traveller"),
    ("PMS011", "Lena Schmidt",     "lena.schmidt@example.com",    "+491708812345","DE","passport","DE332211",  True,  "en", "Prefers ground floor"),
    ("PMS012", "Pierre Salameh",   "pierre.salameh@example.com",  "+33611222333", "FR", "passport","FR55ABC",   False, "fr", ""),
]

SAMPLE_RESERVATIONS = [
    # code, guest_email, room, room_type, check_in (rel days from today), check_out (rel days), num, rate, total, status, requests
    ("PMS-RES-0101", "rami.khoury@example.com",      "401", "Deluxe King",       -2, +1,  1, 240.0, 720.0,  "checked_in",  "Extra pillow menu"),
    ("PMS-RES-0102", "hana.saade@example.com",       "302", "Standard Twin",      0, +3,  2, 170.0, 510.0,  "due_in",      "Allergic to peanuts"),
    ("PMS-RES-0103", "omar.halabi@example.com",      "517", "Junior Suite",      +1, +5,  2, 320.0, 1280.0, "confirmed",   ""),
    ("PMS-RES-0104", "marie.dubois@example.com",     "204", "Deluxe King",        0, +2,  1, 240.0, 480.0,  "due_in",      "Late check-in around midnight"),
    ("PMS-RES-0105", "klaus.berger@example.com",     "611", "Executive Suite",   +2, +4,  1, 410.0, 820.0,  "confirmed",   ""),
    ("PMS-RES-0106", "sofia.russo@example.com",      "808", "Honeymoon Suite",   -1, +2,  2, 510.0, 1530.0, "checked_in",  "Anniversary - rose petals + bottle of champagne"),
    ("PMS-RES-0107", "ahmed.almansoori@example.com", "909", "Royal Suite",       -3, 0,   2, 780.0, 2340.0, "due_out",     "Schedule spa package on departure morning"),
    ("PMS-RES-0108", "yuki.tanaka@example.com",      "215", "Standard King",     +3, +6,  1, 190.0, 570.0,  "confirmed",   "Vegetarian breakfast"),
    ("PMS-RES-0109", "olivia.chen@example.com",      "318", "Deluxe Twin",       -1, +1,  2, 250.0, 500.0,  "checked_in",  ""),
    ("PMS-RES-0110", "karim.elkhoury@example.com",   "402", "Business Deluxe",   +5, +7,  1, 220.0, 440.0,  "confirmed",   "Business traveller — quiet room"),
]


def _write_sample(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    g_path = out_dir / "guests.csv"
    r_path = out_dir / "reservations.csv"

    with g_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["external_id", "full_name", "email", "phone", "nationality",
                    "id_type", "id_number", "vip_status", "language_preference", "notes"])
        for row in SAMPLE_GUESTS:
            w.writerow(list(row))

    today_iso_date = datetime.now().strftime("%Y-%m-%d")
    print(f"Sample dates anchored on today = {today_iso_date}")
    from datetime import timedelta
    base = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0)
    with r_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["reservation_code", "guest_email", "room_number", "room_type",
                    "check_in_date", "check_out_date", "num_guests",
                    "rate_per_night", "total_amount", "status", "special_requests"])
        for row in SAMPLE_RESERVATIONS:
            code, email, room, rtype, ci_off, co_off, num, rate, total, status, req = row
            ci = (base + timedelta(days=ci_off)).isoformat(timespec="minutes")
            co = (base + timedelta(days=co_off)).isoformat(timespec="minutes")
            w.writerow([code, email, room, rtype, ci, co, num, rate, total, status, req])

    print(f"Wrote {g_path} ({len(SAMPLE_GUESTS)} rows)")
    print(f"Wrote {r_path} ({len(SAMPLE_RESERVATIONS)} rows)")


# -----------------------------------------------------------------
# Importers
# -----------------------------------------------------------------
def _parse_dt(s: str) -> datetime:
    s = s.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(s)


def _truthy(v: str) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes", "y", "t")


def import_guests(path: Path, db, dry_run: bool) -> tuple[int, int]:
    """Returns (created, updated)."""
    if not path.exists():
        return 0, 0
    created = updated = 0
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = (row.get("email") or "").strip() or None
            full_name = (row.get("full_name") or "").strip()
            if not full_name and not email:
                continue
            guest = None
            if email:
                guest = db.query(Guest).filter(Guest.email == email).first()
            if guest is None:
                guest = Guest(
                    full_name=full_name,
                    email=email,
                    phone=(row.get("phone") or "").strip() or None,
                    nationality=(row.get("nationality") or "").strip()[:2] or None,
                    id_type=(row.get("id_type") or "").strip() or None,
                    id_number=(row.get("id_number") or "").strip() or None,
                    language_preference=(row.get("language_preference") or "en").strip(),
                    vip_status=_truthy(row.get("vip_status", "false")),
                    notes=(row.get("notes") or "").strip() or None,
                )
                if not dry_run:
                    db.add(guest)
                created += 1
            else:
                # Refresh fields from PMS export
                if full_name and guest.full_name != full_name: guest.full_name = full_name
                guest.phone        = (row.get("phone") or guest.phone or "").strip() or guest.phone
                guest.nationality  = (row.get("nationality") or "").strip()[:2] or guest.nationality
                guest.id_type      = (row.get("id_type") or "").strip() or guest.id_type
                guest.id_number    = (row.get("id_number") or "").strip() or guest.id_number
                lang = (row.get("language_preference") or "").strip()
                if lang: guest.language_preference = lang
                vip = (row.get("vip_status") or "").strip()
                if vip: guest.vip_status = _truthy(vip)
                notes = (row.get("notes") or "").strip()
                if notes: guest.notes = notes
                updated += 1
    if not dry_run:
        db.commit()
    return created, updated


def import_reservations(path: Path, db, dry_run: bool) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    created = updated = 0
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = (row.get("reservation_code") or "").strip()
            email = (row.get("guest_email") or "").strip()
            if not code or not email:
                continue
            guest = db.query(Guest).filter(Guest.email == email).first()
            if guest is None:
                print(f"  skip {code}: no matching guest for {email}")
                continue
            try:
                status = ReservationStatus(row.get("status", "confirmed").strip().lower())
            except ValueError:
                status = ReservationStatus.CONFIRMED

            res = db.query(Reservation).filter(Reservation.reservation_code == code).first()
            if res is None:
                res = Reservation(
                    reservation_code=code,
                    guest_id=guest.id,
                    room_number=(row.get("room_number") or "").strip() or None,
                    room_type=(row.get("room_type") or "").strip() or None,
                    check_in_date=_parse_dt(row.get("check_in_date", "")),
                    check_out_date=_parse_dt(row.get("check_out_date", "")),
                    num_guests=int(row.get("num_guests") or 1),
                    rate_per_night=float(row.get("rate_per_night") or 0.0) or None,
                    total_amount=float(row.get("total_amount") or 0.0) or None,
                    status=status,
                    special_requests=(row.get("special_requests") or "").strip() or None,
                )
                if not dry_run:
                    db.add(res)
                created += 1
            else:
                res.room_number     = (row.get("room_number") or res.room_number)
                res.room_type       = (row.get("room_type") or res.room_type)
                res.check_in_date   = _parse_dt(row.get("check_in_date") or res.check_in_date.isoformat())
                res.check_out_date  = _parse_dt(row.get("check_out_date") or res.check_out_date.isoformat())
                res.status          = status
                res.num_guests      = int(row.get("num_guests") or res.num_guests)
                if (row.get("rate_per_night") or "").strip():
                    res.rate_per_night = float(row["rate_per_night"])
                if (row.get("total_amount") or "").strip():
                    res.total_amount = float(row["total_amount"])
                req = (row.get("special_requests") or "").strip()
                if req: res.special_requests = req
                updated += 1
    if not dry_run:
        db.commit()
    return created, updated


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(_DEFAULT_DIR), help="Folder containing guests.csv + reservations.csv")
    ap.add_argument("--dry-run", action="store_true", help="Report what would change without writing")
    ap.add_argument("--generate-sample", action="store_true", help="Write sample CSVs into the folder and exit")
    args = ap.parse_args()

    out_dir = Path(args.dir)
    if args.generate_sample:
        _write_sample(out_dir)
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        g_path = out_dir / "guests.csv"
        r_path = out_dir / "reservations.csv"
        gc, gu = import_guests(g_path, db, args.dry_run)
        rc, ru = import_reservations(r_path, db, args.dry_run)
        verb = "Would" if args.dry_run else "Imported"
        print(f"{verb} guests:       created={gc} updated={gu}  (from {g_path})")
        print(f"{verb} reservations: created={rc} updated={ru}  (from {r_path})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
