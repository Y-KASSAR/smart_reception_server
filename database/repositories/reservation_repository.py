from sqlalchemy.orm import Session
from database.models import Reservation
from typing import List, Optional


class ReservationRepository:

    @staticmethod
    def create(db: Session, **kwargs) -> Reservation:
        reservation = Reservation(**kwargs)
        try:  # adjusted
            db.add(reservation)
            db.commit()
            db.refresh(reservation)
            return reservation
        except Exception:
            db.rollback()  # adjusted
            raise  # adjusted

    @staticmethod
    def get_by_id(db: Session, reservation_id: int) -> Optional[Reservation]:
        return db.query(Reservation).filter(Reservation.id == reservation_id).first()

    @staticmethod
    def get_by_code(db: Session, code: str) -> Optional[Reservation]:
        return db.query(Reservation).filter(Reservation.reservation_code == code).first()

    @staticmethod
    def get_all(db: Session, skip: int = 0, limit: int = 100) -> List[Reservation]:
        return db.query(Reservation).offset(skip).limit(limit).all()

    @staticmethod
    def get_by_guest(db: Session, guest_id: int) -> List[Reservation]:
        return db.query(Reservation).filter(Reservation.guest_id == guest_id).all()

    @staticmethod
    def update(db: Session, reservation_id: int, **kwargs) -> Optional[Reservation]:
        reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
        if reservation:
            for key, value in kwargs.items():
                setattr(reservation, key, value)
            try:  # adjusted
                db.commit()
                db.refresh(reservation)
            except Exception:
                db.rollback()  # adjusted
                raise  # adjusted
        return reservation

    @staticmethod
    def delete(db: Session, reservation_id: int) -> bool:
        reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
        if reservation:
            try:  # adjusted
                db.delete(reservation)
                db.commit()
                return True
            except Exception:
                db.rollback()  # adjusted
                raise  # adjusted
        return False