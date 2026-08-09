from datetime import datetime
from typing import Dict, List, Optional, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import Guest, Reservation, ReservationStatus, Service, ServicePosting

# Minimum guests required in a nationality/company/source group before its
# usage rate is trusted enough to influence a recommendation — a "100% of
# guests used this" reasoning line is meaningless with a sample of 1.
MIN_GROUP_SAMPLE = 3

# Guest fields the upselling engine is allowed to group by. Restricts
# group_usage_rates() to known-safe columns instead of taking an arbitrary
# attribute name.
_GROUPABLE_FIELDS = {
    "nationality": Guest.nationality,
    "company": Guest.company,
    "source": Guest.source,
}


class ServicePostingRepository:

    @staticmethod
    def create(
        db: Session,
        guest_id: int,
        service_id: int,
        quantity: int = 1,
        unit_price: Optional[float] = None,
        amount: Optional[float] = None,
        reservation_id: Optional[int] = None,
        posted_by_id: Optional[int] = None,
        source_system: str = "manual",
        posted_at: Optional[datetime] = None,
        notes: Optional[str] = None,
    ) -> ServicePosting:
        """Post one service charge to a guest's bill.

        Auto-resolves `reservation_id` to the guest's currently checked-in
        stay when not given, and snapshots `unit_price` from the service
        catalogue when not given — matching how a real POS/PMS interface
        posts at the price in effect at the time of sale.
        """
        if reservation_id is None:
            current_stay = (
                db.query(Reservation)
                .filter(
                    Reservation.guest_id == guest_id,
                    Reservation.status == ReservationStatus.CHECKED_IN,
                )
                .order_by(Reservation.check_in_date.desc())
                .first()
            )
            reservation_id = current_stay.id if current_stay else None

        if unit_price is None:
            svc = db.query(Service).filter(Service.id == service_id).first()
            unit_price = svc.price if svc is not None else None

        if amount is None and unit_price is not None:
            amount = round(unit_price * quantity, 2)

        posting = ServicePosting(
            guest_id=guest_id,
            reservation_id=reservation_id,
            service_id=service_id,
            quantity=quantity,
            unit_price=unit_price,
            amount=amount,
            posted_by_id=posted_by_id,
            source_system=source_system,
            posted_at=posted_at or datetime.now(),
            notes=notes,
        )
        try:
            db.add(posting)
            db.commit()
            db.refresh(posting)
            return posting
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def get_by_guest(db: Session, guest_id: int, limit: int = 100) -> List[ServicePosting]:
        return (
            db.query(ServicePosting)
            .filter(ServicePosting.guest_id == guest_id)
            .order_by(ServicePosting.posted_at.desc())
            .limit(limit)
            .all()
        )

    # ------------------------------------------------------------------
    # Usage-rate aggregations consumed by RecommendationEngine
    # ------------------------------------------------------------------
    @staticmethod
    def personal_usage_rates(
        db: Session,
        guest_id: int,
        service_ids: Sequence[int],
        window: int = 5,
    ) -> Dict[int, dict]:
        """For each service, how often THIS guest used it across their last
        `window` stays (reservations that have already started, most recent
        first). Returns {service_id: {"rate", "used_in", "total_stays"}} —
        services never used are simply absent from the dict.

        Stays with no postings at all still count toward `total_stays` (a
        guest who stayed 5 times and used spa in 2 of them scores 2/5, not
        2/2), so the denominator always reflects the true stay count.
        """
        if not service_ids:
            return {}

        reservation_ids = [
            r.id
            for r in db.query(Reservation.id)
            .filter(Reservation.guest_id == guest_id, Reservation.check_in_date <= datetime.now())
            .order_by(Reservation.check_in_date.desc())
            .limit(window)
            .all()
        ]
        total_stays = len(reservation_ids)
        if total_stays == 0:
            return {}

        rows = (
            db.query(
                ServicePosting.service_id,
                func.count(func.distinct(ServicePosting.reservation_id)),
            )
            .filter(
                ServicePosting.reservation_id.in_(reservation_ids),
                ServicePosting.service_id.in_(service_ids),
            )
            .group_by(ServicePosting.service_id)
            .all()
        )

        return {
            service_id: {
                "rate": used_in / total_stays,
                "used_in": used_in,
                "total_stays": total_stays,
            }
            for service_id, used_in in rows
        }

    @staticmethod
    def group_usage_rates(
        db: Session,
        field: str,
        value: Optional[str],
        service_ids: Sequence[int],
        min_sample: int = MIN_GROUP_SAMPLE,
    ) -> Dict[int, dict]:
        """For each service, what fraction of guests sharing `field == value`
        (e.g. nationality="LB", company="Acme Corp") have posted at least one
        charge for it, ever. Returns {} if the group is empty/unset or below
        `min_sample` (too small a sample to generalize from).

        Returns {service_id: {"rate", "used_guests", "total_guests"}}.
        """
        if not service_ids or not value:
            return {}
        column = _GROUPABLE_FIELDS.get(field)
        if column is None:
            raise ValueError(f"Unknown groupable field: {field}")

        total_guests = (
            db.query(func.count(Guest.id)).filter(column == value).scalar() or 0
        )
        if total_guests < min_sample:
            return {}

        rows = (
            db.query(
                ServicePosting.service_id,
                func.count(func.distinct(ServicePosting.guest_id)),
            )
            .join(Guest, Guest.id == ServicePosting.guest_id)
            .filter(column == value, ServicePosting.service_id.in_(service_ids))
            .group_by(ServicePosting.service_id)
            .all()
        )

        return {
            service_id: {
                "rate": used_guests / total_guests,
                "used_guests": used_guests,
                "total_guests": total_guests,
            }
            for service_id, used_guests in rows
        }
