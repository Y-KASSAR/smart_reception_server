"""
Seed sample reservations + companion guests so the new dashboard tabs
(In-House / Arrivals / Departures) have demo content.

Idempotent:
  * Each guest is upserted by email
  * Each reservation is upserted by reservation_code

Scenario:
  * Guest #1 (Youssef Kassar) — already enrolled; mark CHECKED_IN with
    a 3-night reservation ending tomorrow.
  * 2 future arrivals (Sara Aoun, Marwan Saliba) — CONFIRMED.
  * 2 departures (Layla Hoss, John Pham) — CHECKED_IN with check-out
    in the next 36 hours.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import SessionLocal
from database.models import Guest, Reservation, ReservationStatus, Title

NOW = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _upsert_guest(db, *, email: str, full_name: str, title: Title, phone: str | None,
                  nationality: str | None, vip: bool) -> Guest:
    existing = db.query(Guest).filter(Guest.email == email).first()
    if existing:
        return existing
    g = Guest(
        title=title,
        full_name=full_name,
        email=email,
        phone=phone,
        nationality=nationality,
        vip_status=vip,
    )
    db.add(g)
    db.flush()
    return g


def _upsert_reservation(db, *, code: str, guest_id: int, check_in: datetime,
                        check_out: datetime, status: ReservationStatus,
                        room: str, rate: float) -> Reservation:
    existing = db.query(Reservation).filter(Reservation.reservation_code == code).first()
    if existing:
        # Refresh dates/status so re-runs reflect "today"
        existing.check_in_date = check_in
        existing.check_out_date = check_out
        existing.status = status
        existing.room_number = room
        existing.rate_per_night = rate
        return existing
    r = Reservation(
        reservation_code=code,
        guest_id=guest_id,
        check_in_date=check_in,
        check_out_date=check_out,
        room_type="Deluxe King",
        room_number=room,
        num_guests=1,
        status=status,
        rate_per_night=rate,
        total_amount=rate * max(1, (check_out - check_in).days),
    )
    db.add(r)
    return r


def main() -> None:
    db = SessionLocal()
    try:
        # The enrolled guest — find by name or create
        youssef = (
            db.query(Guest).filter(Guest.full_name.ilike("youssef kassar")).first()
            or _upsert_guest(db, email="ymk006@hotmail.com", full_name="Youssef Kassar",
                             title=Title.MR if hasattr(Title, "MR") else None,
                             phone="71256807", nationality="LB", vip=True)
        )

        sara = _upsert_guest(db, email="sara.aoun@example.com", full_name="Sara Aoun",
                             title=None, phone="71200001", nationality="LB", vip=False)
        marwan = _upsert_guest(db, email="marwan.saliba@example.com", full_name="Marwan Saliba",
                               title=None, phone="71200002", nationality="LB", vip=False)
        layla = _upsert_guest(db, email="layla.hoss@example.com", full_name="Layla Hoss",
                              title=None, phone="71200003", nationality="LB", vip=True)
        john = _upsert_guest(db, email="john.pham@example.com", full_name="John Pham",
                             title=None, phone="71200004", nationality="US", vip=False)
        db.commit()

        # Youssef — in-house through tomorrow
        _upsert_reservation(db, code="RES-2026-0001", guest_id=youssef.id,
                            check_in=NOW - timedelta(days=2), check_out=NOW + timedelta(days=1),
                            status=ReservationStatus.CHECKED_IN, room="501", rate=240.0)

        # Arrivals
        _upsert_reservation(db, code="RES-2026-0002", guest_id=sara.id,
                            check_in=NOW + timedelta(hours=6), check_out=NOW + timedelta(days=3),
                            status=ReservationStatus.CONFIRMED, room="302", rate=180.0)
        _upsert_reservation(db, code="RES-2026-0003", guest_id=marwan.id,
                            check_in=NOW + timedelta(days=2), check_out=NOW + timedelta(days=5),
                            status=ReservationStatus.CONFIRMED, room="412", rate=220.0)

        # Departures
        _upsert_reservation(db, code="RES-2026-0004", guest_id=layla.id,
                            check_in=NOW - timedelta(days=3), check_out=NOW + timedelta(hours=18),
                            status=ReservationStatus.CHECKED_IN, room="610", rate=310.0)
        _upsert_reservation(db, code="RES-2026-0005", guest_id=john.id,
                            check_in=NOW - timedelta(days=5), check_out=NOW + timedelta(hours=4),
                            status=ReservationStatus.DUE_OUT, room="207", rate=160.0)

        db.commit()

        # Summary
        in_house = db.query(Reservation).filter(Reservation.status == ReservationStatus.CHECKED_IN).count()
        arrivals = db.query(Reservation).filter(Reservation.status.in_(
            [ReservationStatus.CONFIRMED, ReservationStatus.DUE_IN])).count()
        departures = db.query(Reservation).filter(Reservation.status.in_(
            [ReservationStatus.CHECKED_IN, ReservationStatus.DUE_OUT])).count()
        guests = db.query(Guest).count()
        reservations = db.query(Reservation).count()
        print(f"Seeded: guests={guests} reservations={reservations}")
        print(f"  in_house={in_house}  upcoming_arrivals={arrivals}  upcoming_departures={departures}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
