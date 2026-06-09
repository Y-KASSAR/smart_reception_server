from sqlalchemy.orm import Session
from typing import List, Optional
from database.models import Guest, GuestStatus

class GuestRepository:
    @staticmethod
    def create(db: Session,
               full_name: str,
               email: Optional[str] = None,
               phone: Optional[str] = None,
               **kwargs) -> Guest:
        guest = Guest(
            full_name=full_name,
            email=email,
            phone=phone,
            **kwargs
        )
        try:  # adjusted
            db.add(guest)
            db.commit()
            db.refresh(guest)
            return guest
        except Exception:
            db.rollback()  # adjusted
            raise  # adjusted

    @staticmethod
    def get_by_id(db: Session, guest_id: int) -> Optional[Guest]:
        return db.query(Guest).filter(Guest.id == guest_id).first()

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[Guest]:
        return db.query(Guest).filter(Guest.email == email).first()

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100) -> List[Guest]:
        return db.query(Guest).offset(skip).limit(limit).all()

    @staticmethod
    def get_active_guests(db: Session) -> List[Guest]:
        return db.query(Guest).filter(Guest.status == GuestStatus.ACTIVE).all()

    @staticmethod
    def get_vip_guests(db: Session) -> List[Guest]:
        return db.query(Guest).filter(Guest.vip_status.is_(True)).all()

    @staticmethod
    def update(db: Session, guest_id: int, **kwargs) -> Optional[Guest]:
        guest = db.query(Guest).filter(Guest.id == guest_id).first()
        if guest:
            for key, value in kwargs.items():
                setattr(guest, key, value)
            db.commit()
            db.refresh(guest)
        return guest

    @staticmethod
    def delete(db: Session, guest_id: int) -> bool:
        guest = db.query(Guest).filter(Guest.id == guest_id).first()
        if guest:
            try:  # adjusted
                db.delete(guest)
                db.commit()
                return True
            except Exception:
                db.rollback()  # adjusted
                raise  # adjusted
        return False

    @staticmethod
    def search_by_name(db: Session, name: str) -> List[Guest]:
        return db.query(Guest).filter(Guest.full_name.ilike(f"%{name}%")).all()