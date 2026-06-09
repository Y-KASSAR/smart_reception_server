from sqlalchemy.orm import Session
from database.models import Visit
from typing import List, Optional


class VisitRepository:

    @staticmethod
    def create(db: Session, **kwargs) -> Visit:
        visit = Visit(**kwargs)
        try:  # adjusted
            db.add(visit)
            db.commit()
            db.refresh(visit)
            return visit
        except Exception:
            db.rollback()  # adjusted
            raise

    @staticmethod
    def get_by_id(db: Session, visit_id: int) -> Optional[Visit]:
        return db.query(Visit).filter(Visit.id == visit_id).first()

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100) -> List[Visit]:
        return db.query(Visit).offset(skip).limit(limit).all()

    @staticmethod
    def get_by_guest(db: Session, guest_id: int) -> List[Visit]:
        return db.query(Visit).filter(Visit.guest_id == guest_id).all()

    @staticmethod
    def update(db: Session, visit_id: int, **kwargs) -> Optional[Visit]:
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if visit:
            for key, value in kwargs.items():
                setattr(visit, key, value)
            try:  # adjusted
                db.commit()
                db.refresh(visit)
            except Exception:
                db.rollback()  # adjusted
                raise  # adjusted
        return visit

    @staticmethod
    def delete(db: Session, visit_id: int) -> bool:
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if visit:
            try:  # adjusted
                db.delete(visit)
                db.commit()
                return True
            except Exception:
                db.rollback()  # adjusted
                raise  # adjusted
        return False