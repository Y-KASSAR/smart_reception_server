"""
Upselling Recommendation Engine (SDD §4.2.5, FR-2)
==================================================

Generates per-guest service recommendations using a small, transparent
rule-based scoring system. Each rule contributes a boost on top of the
service's intrinsic ``popularity_score`` (R1 baseline), combined via
headroom scaling — ``score = score + boost * (1 - score)`` — rather than
flat addition. This keeps the score mathematically bounded to [0, 1]
without an artificial hard clip, AND keeps services with more/stronger
signals distinguishable from each other even near the top of the range.
(A flat-sum model saturates fast: a VIP guest looking at almost any
already-popular spa/dining service — popularity 0.7-0.9 plus a flat +0.3
VIP boost — blows past 1.0 and every such service reads as an
indistinguishable 100%, silently discarding whatever the other rules
found. Headroom scaling means "5 signals agree" always outranks "2 signals
agree," which a hard clip can't guarantee.) The final min(score, 1.0) is
kept as a defensive safety net (R6), not the primary bound. Penalties
(the business-pattern de-emphasis, R7 inline) scale the score down
proportionally (``score = score * (1 - penalty)``) for the same reason.
Top-N services are returned ranked descending.

Rules (matched to ``tests/test_recommendations.py``):

    R1  Baseline           : score = service.popularity_score
    R2  VIP boost          : guest.vip_status AND category ∈ {spa, dining,
                             room_service}  →  boost 0.3
    R3  Dietary match      : preferences.dietary keyword present
                             (case-insensitive) in service.description  →  boost 0.2
    R4  Room-type match    : preferences.room_type keyword present
                             (case-insensitive) in service.description  →  boost 0.1
    R5  Arabic dining      : language_preference == "ar" AND
                             category == "dining"  →  boost 0.15
    R6  Cap                : final score ≤ 1.0 (defensive; headroom scaling
                             already guarantees this mathematically)
    R7  Active filter      : only services where is_active=True
    R8  Persistence dedupe : save_recommendations() refreshes score/reasoning
                             in place when an existing PENDING recommendation
                             for the same (guest_id, service_id) already
                             exists, rather than inserting a duplicate.

    Usage-rate rules (SDD upselling data source — actual billed service
    postings, not stated preferences or accept/decline history):

    R9  Personal history    : guest used this service in X of their last
                              WINDOW stays  →  boost (rate * 0.35)
    R10 Nationality group    : X% of guests sharing the guest's nationality
                              have used this service (min sample 3)  →  boost (rate * 0.20)
    R11 Company group        : X% of guests billed under the same company
                              have used this service (min sample 3)  →  boost (rate * 0.20)
    R12 Source group         : X% of guests booked via the same channel
                              have used this service (min sample 3)  →  boost (rate * 0.15)

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
from database.repositories.service_posting_repository import ServicePostingRepository

logger = get_logger(__name__)


def _apply_boost(score: float, boost: float) -> float:
    """Combine a boost (roughly a 0-1 signal strength) with `score` via
    headroom scaling instead of flat addition, so stacking many boosts on
    an already-high baseline can't blow past 1.0 and collapse every
    strongly-signalled service into an indistinguishable 100%. See module
    docstring for the full rationale."""
    return score + boost * (1.0 - score)


def _apply_penalty(score: float, penalty: float) -> float:
    """Scale `score` down proportionally by `penalty` (0-1), the symmetric
    counterpart to _apply_boost for de-emphasis rules."""
    return score * (1.0 - penalty)


# R9-R12 — usage-rate boost weights and the personal-history lookback window.
_PERSONAL_USAGE_WINDOW = 5     # "last N stays" for the personal-history rule
_PERSONAL_USAGE_BOOST = 0.35
_NATIONALITY_USAGE_BOOST = 0.20
_COMPANY_USAGE_BOOST = 0.20
_SOURCE_USAGE_BOOST = 0.15


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

        # R9-R12 — usage-rate signals from actual billed service postings
        # (SDD upselling data source). Computed once as batched dicts keyed
        # by service_id, rather than per-service queries in the loop below.
        service_ids = [svc.id for svc in services]
        personal_rates = ServicePostingRepository.personal_usage_rates(
            db, guest_id=guest_id, service_ids=service_ids, window=_PERSONAL_USAGE_WINDOW
        )
        nationality_rates = ServicePostingRepository.group_usage_rates(
            db, field="nationality", value=guest.nationality, service_ids=service_ids
        )
        company_rates = ServicePostingRepository.group_usage_rates(
            db, field="company", value=guest.company, service_ids=service_ids
        )
        source_rates = ServicePostingRepository.group_usage_rates(
            db, field="source", value=guest.source, service_ids=service_ids
        )

        scored: list[dict] = []
        for svc in services:
            score, reasons = self._score_service(guest, svc, prefs)

            # R6 — Winback bundle boost: previously accepted services for a
            # returning, not-in-house guest jump to the top with a bundled
            # premium room-rate teaser in the reasoning.
            if winback and svc.id in accepted_ids:
                score = _apply_boost(score, 0.30)
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
                    score = _apply_boost(score, 0.20)
                    reasons.append(
                        "Business traveller pattern — fast dining + in-room "
                        "service often accepted on short Mon-Thu stays"
                    )
                elif category == "activities":
                    score = _apply_penalty(score, 0.10)
                    reasons.append(
                        "De-emphasised for business pattern (short-stay guest "
                        "typically declines half-day excursions)"
                    )

            # R9 — Personal usage history: how often THIS guest has actually
            # used this service across their recent stays (billed postings,
            # not stated preference).
            personal = personal_rates.get(svc.id)
            if personal and personal["rate"] > 0:
                score = _apply_boost(score, personal["rate"] * _PERSONAL_USAGE_BOOST)
                pct = round(personal["rate"] * 100)
                n = personal["total_stays"]
                reasons.append(
                    f"Guest used this service in {pct}% of their last "
                    f"{n} {'stay' if n == 1 else 'stays'}"
                )

            # R10 — Nationality-group usage rate.
            nat = nationality_rates.get(svc.id)
            if nat and nat["rate"] > 0:
                score = _apply_boost(score, nat["rate"] * _NATIONALITY_USAGE_BOOST)
                pct = round(nat["rate"] * 100)
                reasons.append(
                    f"{pct}% of guests from {guest.nationality} used this service"
                )

            # R11 — Company-group usage rate (corporate account billing pattern).
            comp = company_rates.get(svc.id)
            if comp and comp["rate"] > 0:
                score = _apply_boost(score, comp["rate"] * _COMPANY_USAGE_BOOST)
                pct = round(comp["rate"] * 100)
                reasons.append(
                    f"{pct}% of guests from {guest.company} used this service"
                )

            # R12 — Booking-source-group usage rate.
            src = source_rates.get(svc.id)
            if src and src["rate"] > 0:
                score = _apply_boost(score, src["rate"] * _SOURCE_USAGE_BOOST)
                pct = round(src["rate"] * 100)
                reasons.append(
                    f"{pct}% of guests booked via {guest.source} used this service"
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
        """Persist recommendations for ``guest_id``.

        A (guest_id, service_id) pair that already has a PENDING row (R8)
        is refreshed in place — score and reasoning are overwritten with
        the freshly computed values — rather than skipped outright.
        Without this, a guest recommended a service once would keep
        showing that first-ever score/reasoning forever, even as new
        signals (usage history, updated popularity, etc.) become
        available on later calls. Returns the number of NEW rows inserted
        (refreshed rows don't count, matching the original R8 contract).
        """
        if not recommendations:
            return 0

        existing_pending = {
            r.service_id: r
            for r in db.query(Recommendation)
            .filter(
                Recommendation.guest_id == guest_id,
                Recommendation.status == RecommendationStatus.PENDING,
            )
            .all()
        }

        inserted = 0
        changed = False
        try:
            for rec in recommendations:
                svc_id = rec.get("service_id")
                if svc_id is None:
                    continue
                if svc_id in existing_pending:
                    row = existing_pending[svc_id]
                    new_score = float(rec.get("score", row.score))
                    new_reasoning = rec.get("reasoning")
                    if row.score != new_score or row.reasoning != new_reasoning:
                        row.score = new_score
                        row.reasoning = new_reasoning
                        changed = True
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
                existing_pending[svc_id] = None
                inserted += 1
                changed = True
            if changed:
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
            score = _apply_boost(score, _VIP_BOOST_AMOUNT)
            reasons.append(f"VIP boost ({category})")

        # R3 — Dietary preference match
        dietary = str(prefs.get("dietary", "")).strip().lower()
        if dietary and dietary in description:
            score = _apply_boost(score, _DIETARY_BOOST)
            reasons.append(f"Matches dietary preference: {dietary}")

        # R4 — Room-type preference match
        room_type = str(prefs.get("room_type", "")).strip().lower()
        if room_type and room_type in description:
            score = _apply_boost(score, _ROOM_TYPE_BOOST)
            reasons.append(f"Matches room-type preference: {room_type}")

        # R5 — Arabic speakers get a dining boost
        lang = (guest.language_preference or "").lower()
        if lang == "ar" and category == "dining":
            score = _apply_boost(score, _ARABIC_DINING_BOOST)
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
