from sqlalchemy.orm import Session
from database.models import Alert, AlertType, AlertStatus
from typing import List, Optional
from datetime import datetime, timezone

class AlertRepository:

    @staticmethod
    def create(db:Session,
                alert_type: AlertType,
                title:str, 
                description : Optional[str] =None, 
                **kwargs)-> Alert:
        alert = Alert( alert_type= alert_type, title=title, description=description,**kwargs) 
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert
    @staticmethod
    def get_by_id(db: Session, alert_id: int) ->Optional[Alert]:
        return db.query(Alert).filter(Alert.id == alert_id).first()
    
    @staticmethod
    def get_all(db: Session, skip: int = 0, limit : int= 100)-> List[Alert]:
        return db.query(Alert).order_by(Alert.created_at.desc()).offset(skip).limit(limit).all()
    
    @staticmethod
    def get_pending_alerts(db : Session)-> List[Alert]:
        return db.query(Alert).filter(Alert.status == AlertStatus.PENDING).order_by(Alert.created_at.desc()).all()
    
    @staticmethod
    def get_by_type(db: Session, alert_type: AlertType)-> List[Alert]:
        return db.query(Alert).filter(Alert.alert_type == alert_type).order_by(Alert.created_at.desc()).all()
    
    @staticmethod
    def acknowledge(
                    db: Session,
                     alert_id: int,
                    staff_id: int,
                    staff_name: Optional[str] = None
                    ) -> Optional[Alert]:

        alert = db.query(Alert).filter(Alert.id == alert_id).first()

        if alert:
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.now(timezone.utc)
            alert.assigned_to_id = staff_id

            if staff_name:
                alert.acknowledged_by = staff_name

            try:
                db.commit()
                db.refresh(alert)
            except Exception:
                db.rollback()
                raise

        return alert
    
    
    @staticmethod
    def resolve(db: Session, alert_id: int) -> Optional[Alert]:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if alert:
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.now(timezone.utc)
            try:  # adjusted
                db.commit()
                db.refresh(alert)
            except Exception:
                db.rollback()  # adjusted
                raise  # adjusted
        return alert

    @staticmethod
    def delete(db: Session, alert_id: int) -> bool:
        alert = db.query(Alert).filter(Alert.id == alert_id).first()
        if alert:
            try:  # adjusted
                db.delete(alert)
                db.commit()
                return True
            except Exception:
                db.rollback()  # adjusted
                raise  # adjusted
        return False