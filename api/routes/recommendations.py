"""
Recommendation Routes
"""
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database.connection import get_db
from database.repositories import RecommendationRepository
from database.models import RecommendationStatus
from api.schemas import RecommendationResponse, RecommendationStatusSchema
from modules.upselling import recommendation_engine
from utils.security_utils import get_current_staff, require_role

router = APIRouter()


@router.get("/", response_model=List[RecommendationResponse])
def list_recommendations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    return RecommendationRepository.get_all(db, skip=skip, limit=limit)


@router.get("/guest/{guest_id}", response_model=List[RecommendationResponse])
def list_recommendations_by_guest(guest_id: int, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    return RecommendationRepository.get_by_guest(db, guest_id)


@router.get("/{rec_id}", response_model=RecommendationResponse)
def get_recommendation(rec_id: int, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    rec = RecommendationRepository.get_by_id(db, rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec


@router.post("/generate/{guest_id}", response_model=List[RecommendationResponse], status_code=201)
def generate_recommendations(guest_id: int, limit: int = 5, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    recs = recommendation_engine.recommend_for_guest(db, guest_id=guest_id, limit=limit)
    if not recs:
        raise HTTPException(status_code=404, detail="Guest not found or no active services available")
    recommendation_engine.save_recommendations(db, guest_id=guest_id, recommendations=recs)
    return RecommendationRepository.get_by_guest(db, guest_id)


@router.put("/{rec_id}/status", response_model=RecommendationResponse)
def update_recommendation_status(
    rec_id: int,
    status: RecommendationStatusSchema = Body(..., embed=False),
    db: Session = Depends(get_db),
    _=Depends(get_current_staff),
):
    rec = RecommendationRepository.update_status(db, rec_id, RecommendationStatus(status.value))
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec


@router.delete("/{rec_id}", status_code=204)
def delete_recommendation(rec_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin", "manager"))):
    deleted = RecommendationRepository.delete(db, rec_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Recommendation not found")
