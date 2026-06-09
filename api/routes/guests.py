"""
Guest Routes
"""
import base64
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from database.connection import get_db
from database.repositories import GuestRepository, FaceEmbeddingRepository
from database.models import GuestStatus
from api.schemas import (
    GuestCreate, GuestUpdate, GuestResponse,
    WatchlistUpdate, StaffBadgeUpdate,
)
from database.models import Guest
from utils.security_utils import get_current_staff, require_role

router = APIRouter()


class EmbedPayload(BaseModel):
    frame_b64: str


@router.get("/", response_model=List[GuestResponse])
def list_guests(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    return GuestRepository.get_all(db, skip=skip, limit=limit)


@router.get("/vip", response_model=List[GuestResponse])
def list_vip_guests(db: Session = Depends(get_db), _=Depends(get_current_staff)):
    return GuestRepository.get_vip_guests(db)


@router.get("/watchlist", response_model=List[GuestResponse])
def list_watchlist(db: Session = Depends(get_db), _=Depends(get_current_staff)):
    """All guests flagged for staff alert on detection (AlertType.WANTED)."""
    return db.query(Guest).filter(Guest.is_watched == True).order_by(Guest.full_name.asc()).all()  # noqa: E712


@router.put("/{guest_id}/watch", response_model=GuestResponse)
def set_watchlist_state(
    guest_id: int,
    payload: WatchlistUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_staff),
):
    """Add or remove a guest from the watchlist."""
    guest = GuestRepository.get_by_id(db, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    guest.is_watched = bool(payload.is_watched)
    guest.watch_reason = payload.watch_reason if payload.is_watched else None
    db.commit()
    db.refresh(guest)
    return guest


@router.put("/{guest_id}/staff-badge", response_model=GuestResponse)
def set_staff_badge(
    guest_id: int,
    payload: StaffBadgeUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),   # admin-only per the spec
):
    """Assign or remove a staff badge. When True, the recognition pipeline
    suppresses ALL automated alerts (security/assistance/VIP/wanted) for
    this person so off-duty managers walking through the lobby don't
    trigger noise. Admin-only."""
    guest = GuestRepository.get_by_id(db, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    guest.is_staff_badge = bool(payload.is_staff_badge)
    guest.staff_badge_label = payload.staff_badge_label if payload.is_staff_badge else None
    db.commit()
    db.refresh(guest)
    return guest


@router.get("/staff-badges", response_model=List[GuestResponse])
def list_staff_badges(db: Session = Depends(get_db), _=Depends(get_current_staff)):
    """All guests carrying a staff badge (alert-suppressed)."""
    return db.query(Guest).filter(Guest.is_staff_badge == True).order_by(Guest.full_name.asc()).all()  # noqa: E712


@router.get("/search", response_model=List[GuestResponse])
def search_guests(
    name: str = "",
    q: str = "",
    db: Session = Depends(get_db),
    _=Depends(get_current_staff),
):
    """Search guests across name, email, phone, and ID number.

    Accepts either ``name`` (legacy parameter — searches name only) or
    ``q`` (preferred — matches against full_name, first_name, last_name,
    email, phone, or id_number). Both are case-insensitive substring
    matches. Empty query returns an empty list.
    """
    from sqlalchemy import or_
    term = (q or name or "").strip()
    if not term:
        return []
    pattern = f"%{term}%"
    return (
        db.query(Guest)
        .filter(
            or_(
                Guest.full_name.ilike(pattern),
                Guest.first_name.ilike(pattern),
                Guest.last_name.ilike(pattern),
                Guest.email.ilike(pattern),
                Guest.phone.ilike(pattern),
                Guest.id_number.ilike(pattern),
            )
        )
        .order_by(Guest.full_name.asc())
        .limit(50)
        .all()
    )


@router.get("/{guest_id}", response_model=GuestResponse)
def get_guest(guest_id: int, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    guest = GuestRepository.get_by_id(db, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    return guest


@router.get("/{guest_id}/summary")
def guest_summary(guest_id: int, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    """Aggregated guest profile data for the dedicated profile page.

    Bundles guest, all reservations, visit count, last-seen, recommendations
    (with embedded service), and financial roll-ups into one response so the
    profile screen renders in a single round-trip.
    """
    from database.models import (
        Guest, Reservation, Visit, Recommendation, Service,
        RecommendationStatus, ReservationStatus,
    )
    from sqlalchemy.orm import joinedload
    from sqlalchemy import func

    g = GuestRepository.get_by_id(db, guest_id)
    if not g:
        raise HTTPException(status_code=404, detail="Guest not found")

    reservations = (
        db.query(Reservation)
        .filter(Reservation.guest_id == guest_id)
        .order_by(Reservation.check_in_date.desc())
        .all()
    )
    visits = (
        db.query(Visit)
        .filter(Visit.guest_id == guest_id)
        .order_by(Visit.entry_time.desc() if hasattr(Visit, "entry_time") else Visit.id.desc())
        .all()
    )
    recommendations = (
        db.query(Recommendation)
        .options(joinedload(Recommendation.service))
        .filter(Recommendation.guest_id == guest_id)
        .order_by(Recommendation.created_at.desc())
        .all()
    )

    # Finance aggregates
    total_billed = sum((r.total_amount or 0.0) for r in reservations)
    completed_stays = [r for r in reservations if r.status == ReservationStatus.CHECKED_OUT]
    avg_per_stay = (
        sum((r.total_amount or 0.0) for r in completed_stays) / len(completed_stays)
        if completed_stays else 0.0
    )
    accepted_services_value = sum(
        ((r.service.price or 0.0) for r in recommendations
         if r.status == RecommendationStatus.ACCEPTED and r.service is not None),
        0.0,
    )

    def _rsv(r):
        return {
            "id": r.id,
            "reservation_code": r.reservation_code,
            "room_number": r.room_number,
            "check_in_date": r.check_in_date.isoformat() if r.check_in_date else None,
            "check_out_date": r.check_out_date.isoformat() if r.check_out_date else None,
            "status": r.status.value if r.status is not None else None,
            "total_amount": r.total_amount,
            "special_requests": r.special_requests,
        }

    def _vis(v):
        return {
            "id": v.id,
            "entry_time": getattr(v, "entry_time", None).isoformat() if getattr(v, "entry_time", None) else None,
            "exit_time": getattr(v, "exit_time", None).isoformat() if getattr(v, "exit_time", None) else None,
            "duration_seconds": getattr(v, "duration_seconds", None),
        }

    def _rec(r):
        svc = r.service
        return {
            "id": r.id,
            "score": r.score,
            "status": r.status.value if r.status is not None else None,
            "reasoning": r.reasoning,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "service": ({
                "id": svc.id, "name": svc.name, "category": svc.category, "price": svc.price,
            } if svc else None),
        }

    return {
        "guest": {
            "id": g.id, "full_name": g.full_name,
            "email": g.email, "phone": g.phone,
            "nationality": g.nationality,
            "id_type": g.id_type, "id_number": g.id_number,
            "language_preference": g.language_preference,
            "vip_status": bool(g.vip_status),
            "status": g.status.value if g.status is not None else None,
            "preferences": g.preferences,
            "notes": g.notes,
            "is_watched": bool(getattr(g, "is_watched", False)),
            "watch_reason": getattr(g, "watch_reason", None),
            "is_staff_badge": bool(getattr(g, "is_staff_badge", False)),
            "staff_badge_label": getattr(g, "staff_badge_label", None),
            "created_at": g.created_at.isoformat() if g.created_at else None,
            "updated_at": g.updated_at.isoformat() if g.updated_at else None,
        },
        "stays": {
            "total": len(reservations),
            "completed": len(completed_stays),
            "active": sum(1 for r in reservations if r.status == ReservationStatus.CHECKED_IN),
            "items": [_rsv(r) for r in reservations],
        },
        "visits": {
            "total": len(visits),
            "items": [_vis(v) for v in visits[:25]],
        },
        "recommendations": {
            "total": len(recommendations),
            "accepted": sum(1 for r in recommendations if r.status == RecommendationStatus.ACCEPTED),
            "declined": sum(1 for r in recommendations if r.status == RecommendationStatus.DECLINED),
            "items": [_rec(r) for r in recommendations[:25]],
        },
        "finance": {
            "total_billed": round(total_billed, 2),
            "avg_per_stay": round(avg_per_stay, 2),
            "accepted_services_value": round(accepted_services_value, 2),
            "currency": "USD",
        },
        "special_requests_history": [r.special_requests for r in reservations if r.special_requests],
    }


@router.post("/", response_model=GuestResponse, status_code=201)
def create_guest(payload: GuestCreate, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    if payload.email:
        existing = GuestRepository.get_by_email(db, payload.email)
        if existing:
            raise HTTPException(status_code=409, detail="Guest with this email already exists")
    return GuestRepository.create(db, **payload.model_dump())


@router.put("/{guest_id}", response_model=GuestResponse)
def update_guest(guest_id: int, payload: GuestUpdate, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "status" in updates:
        updates["status"] = GuestStatus(updates["status"])
    guest = GuestRepository.update(db, guest_id, **updates)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")
    return guest


@router.delete("/{guest_id}", status_code=204)
def delete_guest(guest_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin", "manager"))):
    deleted = GuestRepository.delete(db, guest_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Guest not found")


@router.post("/{guest_id}/embed", status_code=201)
def enroll_guest_face(
    guest_id: int,
    payload: EmbedPayload,
    db: Session = Depends(get_db),
    _=Depends(get_current_staff),
):
    """
    Upload a face image for a guest and persist its embedding (SDD §4.2.2,
    SysRS FR-1.11 / FR-1.12). Body: { frame_b64: <base64 JPEG/PNG> }.
    """
    guest = GuestRepository.get_by_id(db, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    existing = FaceEmbeddingRepository.count_for_guest(db, guest_id)
    if existing >= 5:
        raise HTTPException(status_code=409, detail="Maximum of 5 embeddings per guest (FR-1.12)")

    try:
        import numpy as np
    except ImportError:
        raise HTTPException(status_code=503, detail="numpy not installed")

    try:
        raw = base64.b64decode(payload.frame_b64)
        arr = np.frombuffer(raw, dtype=np.uint8)
        try:
            import cv2
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        except ImportError:
            raise HTTPException(status_code=503, detail="OpenCV not installed")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid frame data: {e}")

    if frame is None:
        raise HTTPException(status_code=400, detail="Could not decode frame image")

    from modules.recognition import face_engine
    success = face_engine.enroll(frame, guest_id=guest_id, db=db)
    if not success:
        raise HTTPException(status_code=422, detail="No face detected or embedding extraction failed")

    return {
        "guest_id": guest_id,
        "embeddings_total": FaceEmbeddingRepository.count_for_guest(db, guest_id),
        "status": "enrolled",
    }
