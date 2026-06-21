from sqlalchemy.orm import Session
from database.models import Service, Recommendation, RecommendationStatus
from typing import Dict, List, Optional


# Popularity is derived from recommendation outcomes using a Laplace-smoothed
# acceptance rate (a Beta(1, 1) prior). With no history a service sits at the
# neutral 0.5; as guests accept/decline it, the score converges to the true
# acceptance ratio accepted / (accepted + declined). Smoothing keeps a service
# that was shown once and accepted once (1/1) from outranking one shown 100
# times and accepted 80 — the prior pulls low-volume services toward 0.5.
_POP_PRIOR_ACCEPT = 1.0   # alpha
_POP_PRIOR_TOTAL = 2.0    # alpha + beta


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

    # ------------------------------------------------------------------
    # Statistics-driven popularity
    # ------------------------------------------------------------------
    @staticmethod
    def popularity_from_stats(accepted: int, declined: int) -> float:
        """Laplace-smoothed acceptance rate, rounded to [0, 1]."""
        score = (accepted + _POP_PRIOR_ACCEPT) / (accepted + declined + _POP_PRIOR_TOTAL)
        return round(score, 4)

    @staticmethod
    def recompute_popularity(db: Session, service_id: Optional[int] = None) -> Dict[int, float]:
        """Recompute ``popularity_score`` from recommendation statistics.

        Counts ACCEPTED vs DECLINED recommendations per service and stores the
        smoothed acceptance rate back on the row. Pass ``service_id`` to refresh
        a single service (e.g. right after a guest responds to one of its
        recommendations); omit it to recompute the whole catalogue.

        Returns ``{service_id: new_score}`` for the services touched.
        """
        query = db.query(Service)
        if service_id is not None:
            query = query.filter(Service.id == service_id)
        services = query.all()

        results: Dict[int, float] = {}
        for svc in services:
            accepted = db.query(Recommendation).filter(
                Recommendation.service_id == svc.id,
                Recommendation.status == RecommendationStatus.ACCEPTED,
            ).count()
            declined = db.query(Recommendation).filter(
                Recommendation.service_id == svc.id,
                Recommendation.status == RecommendationStatus.DECLINED,
            ).count()
            svc.popularity_score = ServiceRepository.popularity_from_stats(accepted, declined)
            results[svc.id] = svc.popularity_score

        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        return results

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