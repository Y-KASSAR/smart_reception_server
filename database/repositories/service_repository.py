from sqlalchemy.orm import Session
from database.models import Service
from typing import List, Optional


class ServiceRepository:

    @staticmethod
    def create(db: Session, **kwargs) -> Service:
        service = Service(**kwargs)
        try:  # adjusted
            db.add(service)
            db.commit()
            db.refresh(service)
            return service
        except Exception:
            db.rollback()  # adjusted
            raise

    @staticmethod
    def get_by_id(db: Session, service_id: int) -> Optional[Service]:
        return db.query(Service).filter(Service.id == service_id).first()

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100) -> List[Service]:
        return db.query(Service).offset(skip).limit(limit).all()

    @staticmethod
    def get_active(db: Session) -> List[Service]:
        return db.query(Service).filter(Service.is_active.is_(True)).all()

    @staticmethod
    def get_by_category(db: Session, category: str) -> List[Service]:
        return db.query(Service).filter(Service.category == category, Service.is_active.is_(True)).all()

    @staticmethod
    def update(db: Session, service_id: int, **kwargs) -> Optional[Service]:
        service = db.query(Service).filter(Service.id == service_id).first()
        if service:
            for key, value in kwargs.items():
                setattr(service, key, value)
            try:  # adjusted
                db.commit()
                db.refresh(service)
            except Exception:
                db.rollback()  # adjusted
                raise  # adjusted
        return service

    @staticmethod
    def delete(db: Session, service_id: int) -> bool:
        service = db.query(Service).filter(Service.id == service_id).first()
        if service:
            try:  # adjusted
                db.delete(service)
                db.commit()
                return True
            except Exception:
                db.rollback()  # adjusted
                raise  # adjusted
        return False