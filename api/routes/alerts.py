"""
Alert Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from database.connection import get_db
from database.repositories import AlertRepository
from database.models import AlertType
from api.schemas import AlertCreate, AlertUpdate, AlertResponse
from utils.security_utils import get_current_staff, require_role

router = APIRouter()


@router.get("/", response_model=List[AlertResponse])
def list_alerts(skip: int = 0, limit: int = 100, status: Optional[str] = None,
                db: Session = Depends(get_db), _=Depends(get_current_staff)):
    return AlertRepository.get_all(db, skip=skip, limit=limit, status=status)


@router.get("/pending", response_model=List[AlertResponse])
def list_pending_alerts(db: Session = Depends(get_db), _=Depends(get_current_staff)):
    return AlertRepository.get_pending_alerts(db)


@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert(alert_id: int, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    alert = AlertRepository.get_by_id(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.post("/", response_model=AlertResponse, status_code=201)
def create_alert(payload: AlertCreate, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    data = payload.model_dump()
    data["alert_type"] = AlertType(data["alert_type"])
    return AlertRepository.create(db, **data)


@router.put("/{alert_id}", response_model=AlertResponse)
def update_alert(alert_id: int, payload: AlertUpdate, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    alert = AlertRepository.get_by_id(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    for key, value in updates.items():
        setattr(alert, key, value)
    db.commit()
    db.refresh(alert)
    return alert


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(alert_id: int, staff_id: int, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    alert = AlertRepository.acknowledge(db, alert_id, staff_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
def resolve_alert(alert_id: int, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    alert = AlertRepository.resolve(db, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.delete("/{alert_id}", status_code=204)
def delete_alert(alert_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin", "manager", "security"))):
    deleted = AlertRepository.delete(db, alert_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alert not found")
