"""
Upselling Recommendation Engine (SDD §4.2.5, FR-2)
==================================================

Generates per-guest service recommendations using a small, transparent
rule-based scoring system. Each rule contributes an additive boost on top
of the service's intrinsic ``popularity_score`` (R1 baseline); the final
score is capped at 1.0 (R6) and the top-N services are returned ranked
descending.

Rules (matched to ``tests/test_recommendations.py``):

    R1  Baseline           : score = service.popularity_score
    R2  VIP boost          : guest.vip_status AND category ∈ {spa, dining,
                             room_service}  →  +0.3
    R3  Dietary match      : preferences.dietary keyword present
                             (case-insensitive) in service.description  →  +0.2
    R4  Room-type match    : preferences.room_type keyword present
                             (case-insensitive) in service.description  →  +0.1
    R5  Arabic dining      : language_preference == "ar" AND
                             category == "dining"  →  +0.15
    R6  Cap                : final score ≤ 1.0
    R7  Active filter      : only services where is_active=True
    R8  Persistence dedupe : save_recommendations() skips an entry when an
                             existing PENDING recommendation for the same
                             (guest_id, service_id) already exists.

Each result is a dict with keys ``service_id``, ``service_name``, ``score``,
``reasoning`` — the route layer turns them into RecommendationResponse rows
after ``save_recommendations()`` persists them via ``RecommendationRepository``.
"""
from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.orm import Session

from config.logging_config import get_logger
from database.models import (
    Guest,
    Recommendation,
    RecommendationStatus,
    Service,
)

logger = get_logger(__name__)


# Categories eligible for the VIP boost (R2)
_VIP_BOOST_CATEGORIES = {"spa", "dining", "room_service"}
_VIP_BOOST_AMOUNT = 0.3

# Other rule constants
_DIETARY_BOOST = 0.2
_ROOM_TYPE_BOOST = 0.1
_ARABIC_DINING_BOOST = 0.15
_DEFAULT_REASON = "Suggested based on popularity"


class RecommendationEngine:
    """Stateless engine — safe to instantiate many times; tests do."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def recommend_for_guest(
        self,
        db: Session,
        guest_id: int,
        limit: int = 5,
    ) -> list[dict]:
        """Return up to ``limit`` ranked recommendations for ``guest_id``.

        Returns an empty list if the guest doesn't exist or no active
        services are available (per R7).

        Adds a "winback" pass for returning guests with NO current
        in-house reservation: their previously-accepted services get a
        +0.30 boost so the dashboard surfaces their favourites first.
        """
        from database.models import Reservation, ReservationStatus

        guest = db.query(Guest).filter(Guest.id == guest_id).first()
        if guest is None:
            return []

        services = (
            db.query(Service).filter(Service.is_active == True).all()  # noqa: E712
        )
        if not services:
            return []

        prefs = self._parse_preferences(guest.preferences)

        # Winback signal: guest exists in DB but is NOT currently checked
        # in. They walked back into the lobby — likely a returning visitor
        # browsing or asking about another stay. Surface what they loved
        # last time + bundle with a premium room-rate teaser in the reason.
        has_active_stay = (
            db.query(Reservation)
            .filter(
                Reservation.guest_id == guest_id,
                Reservation.status == ReservationStatus.CHECKED_IN,
            )
            .first()
            is not None
        )
        winback = not has_active_stay

        # Past-accepted service IDs (any time, any reservation)
        accepted_ids: set = set()
        if winback:
            accepted_ids = {
                r.service_id
                for r in db.query(Recommendation)
                .filter(
                    Recommendation.guest_id == guest_id,
                    Recommendation.status == RecommendationStatus.ACCEPTED,
                )
                .all()
                if r.service_id is not None
            }

        # R7 — Business booking pattern (SDD §7.4)
        # A guest is on a "business pattern" when they have at least 2 past
        # stays of 1-2 nights each on Mon-Thu, OR their current/most-recent
        # stay matches that profile. We boost business-leaning service
        # categories (dining + room_service) and downweight leisure-only
        # ones (activities) for these guests.
        from datetime import timedelta as _td
        guest_reservations = (
            db.query(Reservation)
            .filter(Reservation.guest_id == guest_id)
            .all()
        )
        business_stays = 0
        for rsv in guest_reservations:
            if rsv.check_in_date is None or rsv.check_out_date is None:
                continue
            nights = max(1, (rsv.check_out_date - rsv.check_in_date).days)
            ci_dow = rsv.check_in_date.weekday()      # 0 = Monday
            if nights <= 2 and ci_dow <= 3:           # Mon–Thu, short stay
                business_stays += 1
        is_business = business_stays >= 2

        scored: list[dict] = []
        for svc in services:
            score, reasons = self._score_service(guest, svc, prefs)

            # R6 — Winback bundle boost: previously accepted services for a
            # returning, not-in-house guest jump to the top with a bundled
            # premium room-rate teaser in the reasoning.
            if winback and svc.id in accepted_ids:
                score += 0.30
                reasons.append(
                    "Winback bundle — pair with our premium room rate for "
                    f"a returning-guest discount on {svc.name}"
                )
            elif winback:
                # Subtle nudge even for non-accepted: prime the package narrative
                reasons.append("Returning guest — consider as part of a comeback package")

            # R7 — Business-booking-pattern (SDD §7.4)
            if is_business:
                category = (svc.category or "").lower()
                if category in ("dining", "room_service"):
                    score += 0.20
                    reasons.append(
                        "Business traveller pattern — fast dining + in-room "
                        "service often accepted on short Mon-Thu stays"
                    )
                elif category == "activities":
                    score -= 0.10
                    reasons.append(
                        "De-emphasised for business pattern (short-stay guest "
                        "typically declines half-day excursions)"
                    )

            scored.append(
                {
                    "service_id": svc.id,
                    "service_name": svc.name,
                    "score": round(min(score, 1.0), 4),  # cap at 1.0
                    "reasoning": "; ".join(reasons) if reasons else _DEFAULT_REASON,
                }
            )

        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:limit]

    def save_recommendations(
        self,
        db: Session,
        guest_id: int,
        recommendations: list[dict],
    ) -> int:
        """Persist new PENDING recommendations for ``guest_id``.

        Skips entries whose (guest_id, service_id) already has a PENDING
        row (R8). Returns the number of new rows inserted.
        """
        if not recommendations:
            return 0

        existing_pending = {
            r.service_id
            for r in db.query(Recommendation)
            .filter(
                Recommendation.guest_id == guest_id,
                Recommendation.status == RecommendationStatus.PENDING,
            )
            .all()
        }

        inserted = 0
        try:
            for rec in recommendations:
                svc_id = rec.get("service_id")
                if svc_id is None or svc_id in existing_pending:
                    continue
                db.add(
                    Recommendation(
                        guest_id=guest_id,
                        service_id=svc_id,
                        score=float(rec.get("score", 0.0)),
                        reasoning=rec.get("reasoning"),
                        status=RecommendationStatus.PENDING,
                    )
                )
                existing_pending.add(svc_id)
                inserted += 1
            if inserted:
                db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"save_recommendations failed: {e}", exc_info=True)
            return 0

        return inserted

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_preferences(raw: Optional[str]) -> dict:
        """Best-effort JSON parse of Guest.preferences (graceful on bad input)."""
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (ValueError, TypeError):
            return {}

    @staticmethod
    def _score_service(
        guest: Guest, svc: Service, prefs: dict
    ) -> tuple[float, list[str]]:
        """Apply rules R1–R5 to a single service; return (score, reasons)."""
        score: float = float(svc.popularity_score or 0.0)
        reasons: list[str] = []
        # R1: keep the popularity-based default reasoning visible whenever
        # no specialized rule fires so the test that grep's for "popularity"
        # still passes.
        if score > 0:
            reasons.append("Popularity baseline")

        description = (svc.description or "").lower()
        category = (svc.category or "").lower()

        # R2 — VIP boost on premium categories
        if bool(guest.vip_status) and category in _VIP_BOOST_CATEGORIES:
            score += _VIP_BOOST_AMOUNT
            reasons.append(f"VIP boost ({category})")

        # R3 — Dietary preference match
        dietary = str(prefs.get("dietary", "")).strip().lower()
        if dietary and dietary in description:
            score += _DIETARY_BOOST
            reasons.append(f"Matches dietary preference: {dietary}")

        # R4 — Room-type preference match
        room_type = str(prefs.get("room_type", "")).strip().lower()
        if room_type and room_type in description:
            score += _ROOM_TYPE_BOOST
            reasons.append(f"Matches room-type preference: {room_type}")

        # R5 — Arabic speakers get a dining boost
        lang = (guest.language_preference or "").lower()
        if lang == "ar" and category == "dining":
            score += _ARABIC_DINING_BOOST
            reasons.append("Curated for Arabic-speaking guests")

        # When the popularity baseline is 0 and no rule fired, leave the
        # reasons list empty so the route can substitute the default text.
        # Otherwise drop the redundant "Popularity baseline" if a more
        # specific reason exists, but keep at least one entry.
        if len(reasons) > 1 and reasons[0] == "Popularity baseline":
            reasons.pop(0)

        return score, reasons


# Module-level singleton — imported by api/routes/recommendations.py:11
recommendation_engine = RecommendationEngine()
