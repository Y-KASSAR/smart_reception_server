"""
Reservation Routes
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload
from typing import List
from database.connection import get_db
from database.models import Reservation, ReservationStatus
from database.repositories import ReservationRepository
from api.schemas import ReservationCreate, ReservationUpdate, ReservationResponse
from utils.security_utils import get_current_staff, require_role

router = APIRouter()


def _query_with_guest(db: Session):
    """Reservation query with guest eager-loaded for the dashboard tabs."""
    return db.query(Reservation).options(joinedload(Reservation.guest))


@router.get("/", response_model=List[ReservationResponse])
def list_reservations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    return ReservationRepository.get_all(db, skip=skip, limit=limit)


# ---------------------------------------------------------------
# Filtered list endpoints powering the Reservations dashboard tabs
# ---------------------------------------------------------------

@router.get("/in-house", response_model=List[ReservationResponse])
def list_in_house(db: Session = Depends(get_db), _=Depends(get_current_staff)):
    """Guests currently checked in (CHECKED_IN status)."""
    return (
        _query_with_guest(db)
        .filter(Reservation.status == ReservationStatus.CHECKED_IN)
        .order_by(Reservation.check_out_date.asc())
        .all()
    )


@router.get("/arrivals", response_model=List[ReservationResponse])
def list_arrivals(
    days: int = Query(1, ge=1, le=30),
    db: Session = Depends(get_db),
    _=Depends(get_current_staff),
):
    """Reservations arriving today (default) or within the next ``days``
    calendar days. Bounded by today's 00:00 so stale past-dated CONFIRMED
    reservations don't leak in.

    * Still-pending arrivals (CONFIRMED / DUE_IN) in the window
    * Today's already-checked-in arrivals (status=CHECKED_IN, check_in today)
    """
    # Compare against the server's LOCAL date, not UTC. The dashboard's
    # notion of "today's arrivals/departures" is what staff at the reception
    # desk think of as today — i.e. local calendar day. Using UTC here makes
    # everything roll over at the wrong moment for any non-UTC timezone
    # (Lebanon is UTC+3, so 02:00 local 5/31 == 23:00 UTC 5/30 — UTC would
    # treat that as yesterday).
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    horizon = today_start + timedelta(days=days)
    return (
        _query_with_guest(db)
        .filter(
            or_(
                and_(
                    Reservation.status.in_([
                        ReservationStatus.CONFIRMED,
                        ReservationStatus.DUE_IN,
                    ]),
                    Reservation.check_in_date >= today_start,
                    Reservation.check_in_date < horizon,
                ),
                and_(
                    Reservation.status == ReservationStatus.CHECKED_IN,
                    Reservation.check_in_date >= today_start,
                    Reservation.check_in_date < horizon,
                ),
            )
        )
        .order_by(Reservation.check_in_date.asc())
        .all()
    )


@router.get("/departures", response_model=List[ReservationResponse])
def list_departures(
    days: int = Query(1, ge=1, le=30),
    db: Session = Depends(get_db),
    _=Depends(get_current_staff),
):
    """Reservations departing today (default) or within the next ``days``
    calendar days.

    * Still-staying guests (CHECKED_IN / DUE_OUT) leaving in the window
    * Already-departed (CHECKED_OUT) guests who left today
    """
    # Compare against the server's LOCAL date, not UTC. The dashboard's
    # notion of "today's arrivals/departures" is what staff at the reception
    # desk think of as today — i.e. local calendar day. Using UTC here makes
    # everything roll over at the wrong moment for any non-UTC timezone
    # (Lebanon is UTC+3, so 02:00 local 5/31 == 23:00 UTC 5/30 — UTC would
    # treat that as yesterday).
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    horizon = today_start + timedelta(days=days)
    return (
        _query_with_guest(db)
        .filter(
            or_(
                and_(
                    Reservation.status.in_([
                        ReservationStatus.CHECKED_IN,
                        ReservationStatus.DUE_OUT,
                    ]),
                    Reservation.check_out_date >= today_start,
                    Reservation.check_out_date < horizon,
                ),
                and_(
                    Reservation.status == ReservationStatus.CHECKED_OUT,
                    Reservation.check_out_date >= today_start,
                    Reservation.check_out_date < horizon,
                ),
            )
        )
        .order_by(Reservation.check_out_date.asc())
        .all()
    )


@router.get("/guest/{guest_id}", response_model=List[ReservationResponse])
def list_reservations_by_guest(guest_id: int, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    return ReservationRepository.get_by_guest(db, guest_id)


@router.get("/{reservation_id}", response_model=ReservationResponse)
def get_reservation(reservation_id: int, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    reservation = ReservationRepository.get_by_id(db, reservation_id)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return reservation


@router.post("/", response_model=ReservationResponse, status_code=201)
def create_reservation(payload: ReservationCreate, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    existing = ReservationRepository.get_by_code(db, payload.reservation_code)
    if existing:
        raise HTTPException(status_code=409, detail="Reservation code already exists")
    return ReservationRepository.create(db, **payload.model_dump())


@router.put("/{reservation_id}", response_model=ReservationResponse)
def update_reservation(reservation_id: int, payload: ReservationUpdate, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    reservation = ReservationRepository.update(db, reservation_id, **updates)
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return reservation


@router.delete("/{reservation_id}", status_code=204)
def delete_reservation(reservation_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin", "manager"))):
    deleted = ReservationRepository.delete(db, reservation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Reservation not found")
