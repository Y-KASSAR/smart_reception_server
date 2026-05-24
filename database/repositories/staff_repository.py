from sqlalchemy.orm import Session
from database.models import Staff, StaffRole
from typing import List, Optional
from datetime import datetime, timezone

class StaffRepository:

    @staticmethod
    def create(db: Session,
               username: str,
               password_hash: str,
               full_name: str,
               email: str,
               role: StaffRole
               ) -> Staff:
        staff = Staff(
            username=username,
            password_hash=password_hash,
            full_name=full_name,
            email=email,
            role=role
        )
        try:  # adjusted
            db.add(staff)
            db.commit()
            db.refresh(staff)
            return staff
        except Exception:
            db.rollback()  # adjusted
            raise

    @staticmethod
    def get_by_id(db: Session, staff_id: int) -> Optional[Staff]:
        return db.query(Staff).filter(Staff.id == staff_id).first()

    @staticmethod
    def get_by_username(db: Session, username: str) -> Optional[Staff]:
        return db.query(Staff).filter(Staff.username == username).first()

    @staticmethod
    def get_all(db: Session) -> List[Staff]:
        return db.query(Staff).all()

    @staticmethod
    def get_active_staff(db: Session) -> List[Staff]:
        return db.query(Staff).filter(Staff.is_active.is_(True)).all()

    @staticmethod
    def update_last_login(db: Session, staff_id: int) -> Optional[Staff]:
        staff = db.query(Staff).filter(Staff.id == staff_id).first()
        if staff:
            staff.last_login = datetime.now(timezone.utc)
            try:  # adjusted
                db.commit()
                db.refresh(staff)
            except Exception:
                db.rollback()  # adjusted
                raise  # adjusted
        return staff

    @staticmethod
    def update(db: Session, staff_id: int, **kwargs) -> Optional[Staff]:
        staff = db.query(Staff).filter(Staff.id == staff_id).first()
        if staff:
            for key, value in kwargs.items():
                setattr(staff, key, value)
            try:  # adjusted
                db.commit()
                db.refresh(staff)
            except Exception:
                db.rollback()  # adjusted
                raise
        return staff

    @staticmethod
    def delete(db: Session, staff_id: int) -> bool:
        staff = db.query(Staff).filter(Staff.id == staff_id).first()
        if staff:
            try:  # adjusted
                db.delete(staff)
                db.commit()
                return True
            except Exception:
                db.rollback()  # adjusted
                raise  # adjusted
        return False