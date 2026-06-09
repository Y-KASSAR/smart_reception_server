from sqlalchemy.orm import Session
from database.models import Recommendation, RecommendationStatus
from typing import List, Optional
from datetime import datetime, timezone


class RecommendationRepository:

    @staticmethod
    def get_by_id(db: Session, rec_id: int) -> Optional[Recommendation]:
        return db.query(Recommendation).filter(Recommendation.id == rec_id).first()

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100) -> List[Recommendation]:
        return db.query(Recommendation).offset(skip).limit(limit).all()

    @staticmethod
    def get_by_guest(db: Session, guest_id: int) -> List[Recommendation]:
        return db.query(Recommendation).filter(Recommendation.guest_id == guest_id).all()

    @staticmethod
    def update_status(db: Session, rec_id: int, status: RecommendationStatus) -> Optional[Recommendation]:
        from datetime import datetime, timezone
        rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
        if rec:
            rec.status = status
            if status == RecommendationStatus.PRESENTED:
                rec.presented_at = datetime.now(timezone.utc)
            elif status in (RecommendationStatus.ACCEPTED, RecommendationStatus.DECLINED):
                rec.responded_at = datetime.now(timezone.utc)
            try:  # adjusted
                db.commit()
                db.refresh(rec)
            except Exception:
                db.rollback()  # adjusted
                raise  # adjusted
        return rec

    @staticmethod
    def delete(db: Session, rec_id: int) -> bool:
        rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
        if rec:
            try:  # adjusted
                db.delete(rec)
                db.commit()
                return True
            except Exception:
                db.rollback()  # adjusted
                raise  # adjusted
        return False