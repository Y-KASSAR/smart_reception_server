"""
Service Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from database.connection import get_db
from database.repositories import ServiceRepository
from api.schemas import ServiceCreate, ServiceUpdate, ServiceResponse
from utils.security_utils import get_current_staff, require_role

router = APIRouter()


@router.get("/", response_model=List[ServiceResponse])
def list_services(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    return ServiceRepository.get_all(db, skip=skip, limit=limit)


@router.get("/active", response_model=List[ServiceResponse])
def list_active_services(db: Session = Depends(get_db), _=Depends(get_current_staff)):
    return ServiceRepository.get_active(db)


@router.get("/category/{category}", response_model=List[ServiceResponse])
def list_services_by_category(category: str, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    return ServiceRepository.get_by_category(db, category)


@router.get("/{service_id}", response_model=ServiceResponse)
def get_service(service_id: int, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    service = ServiceRepository.get_by_id(db, service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.post("/", response_model=ServiceResponse, status_code=201)
def create_service(payload: ServiceCreate, db: Session = Depends(get_db), _=Depends(require_role("admin", "manager"))):
    return ServiceRepository.create(db, **payload.model_dump())


@router.put("/{service_id}", response_model=ServiceResponse)
def update_service(service_id: int, payload: ServiceUpdate, db: Session = Depends(get_db), _=Depends(require_role("admin", "manager"))):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    service = ServiceRepository.update(db, service_id, **updates)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.delete("/{service_id}", status_code=204)
def delete_service(service_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    deleted = ServiceRepository.delete(db, service_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Service not found")
