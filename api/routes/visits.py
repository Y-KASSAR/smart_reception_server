"""
Visit Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database.connection import get_db
from database.repositories import VisitRepository
from api.schemas import VisitCreate, VisitUpdate, VisitResponse
from utils.security_utils import get_current_staff, require_role

router = APIRouter()


@router.get("/", response_model=List[VisitResponse])
def list_visits(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    return VisitRepository.get_all(db, skip=skip, limit=limit)


@router.get("/guest/{guest_id}", response_model=List[VisitResponse])
def list_visits_by_guest(guest_id: int, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    return VisitRepository.get_by_guest(db, guest_id)


@router.get("/{visit_id}", response_model=VisitResponse)
def get_visit(visit_id: int, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    visit = VisitRepository.get_by_id(db, visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    return visit


@router.post("/", response_model=VisitResponse, status_code=201)
def create_visit(payload: VisitCreate, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    return VisitRepository.create(db, **payload.model_dump())


@router.put("/{visit_id}", response_model=VisitResponse)
def update_visit(visit_id: int, payload: VisitUpdate, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    visit = VisitRepository.update(db, visit_id, **updates)
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    return visit


@router.delete("/{visit_id}", status_code=204)
def delete_visit(visit_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin", "manager"))):
    deleted = VisitRepository.delete(db, visit_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Visit not found")
