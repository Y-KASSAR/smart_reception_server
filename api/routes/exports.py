"""
CSV Export Routes (FR-6)
=========================
Allow staff to export guests, visits, reservations, and alerts as CSV.
"""
import csv
import io
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Guest, Visit, Reservation, Alert
from utils.security_utils import get_current_staff

router = APIRouter()


def _stream_csv(rows, header):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for r in rows:
        writer.writerow(r)
    buf.seek(0)
    fname = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


def _v(value):
    if value is None:
        return ""
    if hasattr(value, "value"):  # Enum
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


@router.get("/guests")
def export_guests(db: Session = Depends(get_db), _=Depends(get_current_staff)):
    header = ["id", "full_name", "email", "phone", "nationality",
              "language_preference", "vip_status", "status", "created_at"]
    rows = [
        [_v(g.id), _v(g.full_name), _v(g.email), _v(g.phone), _v(g.nationality),
         _v(g.language_preference), _v(g.vip_status), _v(g.status), _v(g.created_at)]
        for g in db.query(Guest).all()
    ]
    return _stream_csv(rows, header)


@router.get("/visits")
def export_visits(db: Session = Depends(get_db), _=Depends(get_current_staff)):
    header = ["id", "guest_id", "check_in", "check_out", "room_number",
              "purpose", "total_spend", "feedback_score", "notes"]
    rows = [
        [_v(v.id), _v(v.guest_id), _v(v.check_in), _v(v.check_out),
         _v(v.room_number), _v(v.purpose), _v(v.total_spend),
         _v(v.feedback_score), _v(v.notes)]
        for v in db.query(Visit).all()
    ]
    return _stream_csv(rows, header)


@router.get("/reservations")
def export_reservations(db: Session = Depends(get_db), _=Depends(get_current_staff)):
    header = ["id", "guest_id", "reservation_code", "check_in_date", "check_out_date",
              "room_type", "num_guests", "rate_per_night", "total_amount", "status",
              "created_at"]
    rows = [
        [_v(r.id), _v(r.guest_id), _v(r.reservation_code), _v(r.check_in_date),
         _v(r.check_out_date), _v(r.room_type), _v(r.num_guests),
         _v(r.rate_per_night), _v(r.total_amount), _v(r.status), _v(r.created_at)]
        for r in db.query(Reservation).all()
    ]
    return _stream_csv(rows, header)


@router.get("/alerts")
def export_alerts(db: Session = Depends(get_db), _=Depends(get_current_staff)):
    header = ["id", "alert_type", "status", "title", "severity", "location",
              "created_at", "acknowledged_at", "resolved_at", "resolution_note"]
    rows = [
        [_v(a.id), _v(a.alert_type), _v(a.status), _v(a.title), _v(a.severity),
         _v(a.location), _v(a.created_at), _v(a.acknowledged_at),
         _v(a.resolved_at), _v(a.resolution_note)]
        for a in db.query(Alert).all()
    ]
    return _stream_csv(rows, header)
