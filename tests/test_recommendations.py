"""
Tests for the upselling/recommendation engine.

Covers all scoring rules used by RecommendationEngine:
- R1: Service popularity baseline
- R2: VIP guest premium boost (spa/dining/room_service)
- R3: Dietary preference match
- R4: Room-type preference match
- R5: Arabic-speaker dining boost
- R6: Score capped at 1.0
- R7: Inactive services excluded
- R8: Persistence (save_recommendations) deduplicates pending entries
"""
import json
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import (
    Base,
    Guest,
    Service,
    Recommendation,
    RecommendationStatus,
    Reservation,
    ReservationStatus,
    ServicePosting,
)
from modules.upselling import RecommendationEngine


@pytest.fixture(scope="function")
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def engine():
    return RecommendationEngine()


def _make_guest(db, **kwargs):
    defaults = dict(full_name="Test Guest", language_preference="en", vip_status=False)
    defaults.update(kwargs)
    g = Guest(**defaults)
    db.add(g)
    db.commit()
    db.refresh(g)
    return g


def _make_service(db, **kwargs):
    defaults = dict(name="Service", category="dining", description="A nice service", popularity_score=0.5, is_active=True)
    defaults.update(kwargs)
    s = Service(**defaults)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _make_reservation(db, guest_id, check_in_offset_days=-10, **kwargs):
    defaults = dict(
        reservation_code=f"RES-{guest_id}-{id(kwargs)}",
        check_in_date=datetime.now() + timedelta(days=check_in_offset_days),
        check_out_date=datetime.now() + timedelta(days=check_in_offset_days + 2),
        status=ReservationStatus.CHECKED_OUT,
    )
    defaults.update(kwargs)
    r = Reservation(guest_id=guest_id, **defaults)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _make_posting(db, guest_id, service_id, reservation_id=None, **kwargs):
    defaults = dict(quantity=1, unit_price=10.0, amount=10.0, source_system="manual")
    defaults.update(kwargs)
    p = ServicePosting(guest_id=guest_id, service_id=service_id, reservation_id=reservation_id, **defaults)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


# ----------------------------------------------------------------------
# R1: popularity baseline
# ----------------------------------------------------------------------
class TestPopularityBaseline:
    def test_uses_popularity_as_base_score(self, db, engine):
        _make_guest(db)
        _make_service(db, popularity_score=0.42, name="Popular")
        recs = engine.recommend_for_guest(db, guest_id=1, limit=5)
        assert len(recs) == 1
        assert recs[0]["score"] == pytest.approx(0.42, abs=0.001)

    def test_popularity_zero_default(self, db, engine):
        _make_guest(db)
        _make_service(db, popularity_score=0.0, description=None)
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == 0.0

    def test_recommendations_sorted_by_score(self, db, engine):
        _make_guest(db)
        _make_service(db, name="Low", popularity_score=0.1)
        _make_service(db, name="High", popularity_score=0.9)
        _make_service(db, name="Mid", popularity_score=0.5)
        recs = engine.recommend_for_guest(db, guest_id=1, limit=5)
        scores = [r["score"] for r in recs]
        assert scores == sorted(scores, reverse=True)
        assert recs[0]["service_name"] == "High"

    def test_limit_truncates_results(self, db, engine):
        _make_guest(db)
        for i in range(5):
            _make_service(db, name=f"S{i}", popularity_score=0.1 * i)
        recs = engine.recommend_for_guest(db, guest_id=1, limit=2)
        assert len(recs) == 2


# ----------------------------------------------------------------------
# R2: VIP boost
# ----------------------------------------------------------------------
class TestVipBoost:
    def test_vip_boosts_spa_service(self, db, engine):
        # Headroom-scaled: score + boost*(1-score) = 0.4 + 0.3*0.6 = 0.58
        _make_guest(db, vip_status=True)
        _make_service(db, category="spa", popularity_score=0.4)
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == pytest.approx(0.58, abs=0.001)
        assert recs[0]["score"] > 0.4  # still a genuine boost over the baseline
        assert "VIP" in recs[0]["reasoning"]

    def test_vip_boosts_dining(self, db, engine):
        _make_guest(db, vip_status=True)
        _make_service(db, category="dining", popularity_score=0.2)
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == pytest.approx(0.44, abs=0.001)

    def test_vip_boosts_room_service(self, db, engine):
        _make_guest(db, vip_status=True)
        _make_service(db, category="room_service", popularity_score=0.3)
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == pytest.approx(0.51, abs=0.001)

    def test_vip_no_boost_for_other_categories(self, db, engine):
        _make_guest(db, vip_status=True)
        _make_service(db, category="activities", popularity_score=0.4)
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == pytest.approx(0.4, abs=0.001)

    def test_non_vip_gets_no_boost(self, db, engine):
        _make_guest(db, vip_status=False)
        _make_service(db, category="spa", popularity_score=0.4)
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == pytest.approx(0.4, abs=0.001)


# ----------------------------------------------------------------------
# R3: Dietary preference match
# ----------------------------------------------------------------------
class TestDietaryMatch:
    def test_dietary_match_adds_score(self, db, engine):
        _make_guest(db, preferences=json.dumps({"dietary": "vegan"}))
        _make_service(db, description="Delicious vegan options", popularity_score=0.3, category="activities")
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == pytest.approx(0.44, abs=0.001)
        assert "vegan" in recs[0]["reasoning"].lower()

    def test_dietary_case_insensitive(self, db, engine):
        _make_guest(db, preferences=json.dumps({"dietary": "Vegan"}))
        _make_service(db, description="VEGAN MENU", popularity_score=0.1, category="activities")
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == pytest.approx(0.28, abs=0.001)

    def test_dietary_no_match(self, db, engine):
        _make_guest(db, preferences=json.dumps({"dietary": "vegan"}))
        _make_service(db, description="Steakhouse", popularity_score=0.3, category="activities")
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == pytest.approx(0.3, abs=0.001)


# ----------------------------------------------------------------------
# R4: Room-type preference match
# ----------------------------------------------------------------------
class TestRoomTypeMatch:
    def test_room_type_match_adds_score(self, db, engine):
        _make_guest(db, preferences=json.dumps({"room_type": "suite"}))
        _make_service(db, description="Premium suite cleaning", popularity_score=0.3, category="activities")
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == pytest.approx(0.37, abs=0.001)

    def test_room_type_no_match(self, db, engine):
        _make_guest(db, preferences=json.dumps({"room_type": "suite"}))
        _make_service(db, description="Pool access", popularity_score=0.2, category="activities")
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == pytest.approx(0.2, abs=0.001)


# ----------------------------------------------------------------------
# R5: Arabic speaker dining boost
# ----------------------------------------------------------------------
class TestArabicDiningBoost:
    def test_arabic_speaker_dining_boost(self, db, engine):
        _make_guest(db, language_preference="ar")
        _make_service(db, category="dining", description="X", popularity_score=0.2)
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == pytest.approx(0.32, abs=0.001)
        assert "arabic" in recs[0]["reasoning"].lower()

    def test_arabic_speaker_no_boost_for_non_dining(self, db, engine):
        _make_guest(db, language_preference="ar")
        _make_service(db, category="spa", description="X", popularity_score=0.2)
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == pytest.approx(0.2, abs=0.001)

    def test_english_speaker_no_arabic_boost(self, db, engine):
        _make_guest(db, language_preference="en")
        _make_service(db, category="dining", description="X", popularity_score=0.2)
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == pytest.approx(0.2, abs=0.001)


# ----------------------------------------------------------------------
# R6: Score capped at 1.0
# ----------------------------------------------------------------------
class TestScoreCap:
    def test_score_never_exceeds_one(self, db, engine):
        # Headroom scaling means 4 stacked boosts (VIP, dietary, room-type,
        # Arabic-dining) on a 0.95 baseline approach 1.0 without an
        # artificial clip: 0.95 -> 0.965 -> 0.972 -> 0.9748 -> ~0.9786.
        # This is the fix for score saturation — previously any 2+ boosts
        # on a popular service all flatly hit exactly 1.0, indistinguishable
        # from each other. Now more signals still means a higher score, and
        # the score genuinely never crosses 1.0 (verified generically below).
        _make_guest(db, vip_status=True, language_preference="ar",
                    preferences=json.dumps({"dietary": "halal", "room_type": "suite"}))
        _make_service(db, category="dining", description="halal suite menu",
                      popularity_score=0.95)
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] <= 1.0
        assert recs[0]["score"] == pytest.approx(0.9786, abs=0.001)
        assert recs[0]["score"] > 0.95  # still a genuine boost over the baseline

    def test_score_stays_under_one_even_at_extreme_baseline(self, db, engine):
        # A near-1.0 baseline plus every boost should still land strictly
        # under 1.0 by construction (headroom scaling), not clip to exactly
        # 1.0 the way flat addition would.
        _make_guest(db, vip_status=True, language_preference="ar",
                    preferences=json.dumps({"dietary": "halal", "room_type": "suite"}))
        _make_service(db, category="dining", description="halal suite menu",
                      popularity_score=0.999)
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] < 1.0


# ----------------------------------------------------------------------
# R7: Active service filter & misc
# ----------------------------------------------------------------------
class TestActiveServiceFilter:
    def test_inactive_service_excluded(self, db, engine):
        _make_guest(db)
        _make_service(db, name="Active", is_active=True, popularity_score=0.1)
        _make_service(db, name="Inactive", is_active=False, popularity_score=0.9)
        recs = engine.recommend_for_guest(db, guest_id=1)
        names = [r["service_name"] for r in recs]
        assert "Active" in names
        assert "Inactive" not in names

    def test_unknown_guest_returns_empty(self, db, engine):
        _make_service(db)
        recs = engine.recommend_for_guest(db, guest_id=9999)
        assert recs == []

    def test_no_active_services_returns_empty(self, db, engine):
        _make_guest(db)
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs == []

    def test_invalid_preferences_json_falls_back_gracefully(self, db, engine):
        _make_guest(db, preferences="not-json{{")
        _make_service(db, popularity_score=0.3)
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == pytest.approx(0.3, abs=0.001)

    def test_default_reasoning_when_no_rules_apply(self, db, engine):
        _make_guest(db)
        _make_service(db, popularity_score=0.2, category="activities")
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert "popularity" in recs[0]["reasoning"].lower()


# ----------------------------------------------------------------------
# R8: Persistence
# ----------------------------------------------------------------------
class TestSaveRecommendations:
    def test_save_persists_recommendations(self, db, engine):
        _make_guest(db)
        s = _make_service(db, popularity_score=0.5)
        recs = engine.recommend_for_guest(db, guest_id=1)
        saved = engine.save_recommendations(db, guest_id=1, recommendations=recs)
        assert saved == 1
        assert db.query(Recommendation).count() == 1
        rec = db.query(Recommendation).first()
        assert rec.service_id == s.id
        assert rec.status == RecommendationStatus.PENDING

    def test_save_dedupes_pending(self, db, engine):
        _make_guest(db)
        _make_service(db, popularity_score=0.5)
        recs = engine.recommend_for_guest(db, guest_id=1)
        engine.save_recommendations(db, guest_id=1, recommendations=recs)
        saved_again = engine.save_recommendations(db, guest_id=1, recommendations=recs)
        assert saved_again == 0
        assert db.query(Recommendation).count() == 1

    def test_save_creates_separate_records_for_distinct_services(self, db, engine):
        _make_guest(db)
        _make_service(db, name="A", popularity_score=0.5)
        _make_service(db, name="B", popularity_score=0.6)
        recs = engine.recommend_for_guest(db, guest_id=1)
        saved = engine.save_recommendations(db, guest_id=1, recommendations=recs)
        assert saved == 2
        assert db.query(Recommendation).count() == 2

    def test_save_refreshes_stale_pending_score_and_reasoning(self, db, engine):
        """A PENDING row from an earlier call must pick up newly-available
        signals (e.g. usage history added after the first recommendation)
        instead of freezing its original score/reasoning forever."""
        guest = _make_guest(db, nationality="LB")
        svc = _make_service(db, popularity_score=0.3, category="activities")
        engine.save_recommendations(db, guest_id=guest.id, recommendations=[
            {"service_id": svc.id, "score": 0.3, "reasoning": "Popularity baseline"},
        ])
        original = db.query(Recommendation).filter(Recommendation.service_id == svc.id).first()
        original_id, original_score = original.id, original.score
        assert original_score == pytest.approx(0.3, abs=0.001)

        # New usage history appears after the first recommendation was saved.
        rsv = _make_reservation(
            db, guest.id, check_in_offset_days=-5,
            check_out_date=datetime.now() + timedelta(days=-1),
        )
        _make_posting(db, guest.id, svc.id, reservation_id=rsv.id)

        fresh = engine.recommend_for_guest(db, guest_id=guest.id)
        saved_again = engine.save_recommendations(db, guest_id=guest.id, recommendations=fresh)

        assert saved_again == 0  # no NEW row — same (guest, service) pair
        assert db.query(Recommendation).count() == 1  # still one row, refreshed in place
        refreshed = db.query(Recommendation).filter(Recommendation.service_id == svc.id).first()
        assert refreshed.id == original_id
        assert refreshed.score > original_score
        assert "used this service in" in refreshed.reasoning


# ----------------------------------------------------------------------
# R9: Personal usage history (billed service postings)
# ----------------------------------------------------------------------
class TestPersonalUsageHistory:
    def test_personal_usage_boosts_score(self, db, engine):
        guest = _make_guest(db)
        svc = _make_service(db, popularity_score=0.3, category="activities")
        rsv = _make_reservation(db, guest.id, check_in_offset_days=-5)
        _make_posting(db, guest.id, svc.id, reservation_id=rsv.id)

        recs = engine.recommend_for_guest(db, guest_id=guest.id)
        # Headroom-scaled: 0.3 + (1.0 * 0.35) * (1 - 0.3) = 0.545
        assert recs[0]["score"] == pytest.approx(0.545, abs=0.001)
        assert "100%" in recs[0]["reasoning"]
        assert "last 1 stay" in recs[0]["reasoning"]

    def test_no_reservations_no_personal_boost(self, db, engine):
        guest = _make_guest(db)
        _make_service(db, popularity_score=0.3, category="activities")
        recs = engine.recommend_for_guest(db, guest_id=guest.id)
        assert recs[0]["score"] == pytest.approx(0.3, abs=0.001)
        assert "used this service in" not in recs[0]["reasoning"]

    def test_unused_service_across_stays_gets_no_boost(self, db, engine):
        guest = _make_guest(db)
        svc = _make_service(db, popularity_score=0.3, category="activities")
        _make_reservation(db, guest.id, check_in_offset_days=-5)
        # Reservation exists but no posting was ever made for this service.
        recs = engine.recommend_for_guest(db, guest_id=guest.id)
        assert recs[0]["score"] == pytest.approx(0.3, abs=0.001)

    def test_personal_rate_reflects_partial_usage(self, db, engine):
        # 5-night stays so this can't coincidentally trip the unrelated R7
        # business-pattern rule (short Mon-Thu stays), which also biases
        # "activities" scoring independent of usage history.
        guest = _make_guest(db)
        svc = _make_service(db, popularity_score=0.0, category="activities")
        rsv1 = _make_reservation(
            db, guest.id, check_in_offset_days=-30,
            check_out_date=datetime.now() + timedelta(days=-25),
        )
        _make_reservation(
            db, guest.id, check_in_offset_days=-10,
            check_out_date=datetime.now() + timedelta(days=-5),
        )  # no posting
        _make_posting(db, guest.id, svc.id, reservation_id=rsv1.id)

        recs = engine.recommend_for_guest(db, guest_id=guest.id)
        # 1 of 2 stays used the service -> rate 0.5
        assert recs[0]["score"] == pytest.approx(0.5 * 0.35, abs=0.001)
        assert "50%" in recs[0]["reasoning"]
        assert "last 2 stays" in recs[0]["reasoning"]


# ----------------------------------------------------------------------
# R10: Nationality-group usage rate
# ----------------------------------------------------------------------
class TestNationalityUsageRate:
    def test_nationality_group_boost(self, db, engine):
        svc = _make_service(db, popularity_score=0.3, category="activities")
        g1 = _make_guest(db, nationality="LB")
        g2 = _make_guest(db, nationality="LB")
        g3 = _make_guest(db, nationality="LB")  # the guest we're scoring
        rsv = _make_reservation(db, g1.id, check_in_offset_days=-5)
        _make_posting(db, g1.id, svc.id, reservation_id=rsv.id)

        recs = engine.recommend_for_guest(db, guest_id=g3.id)
        # 1 of 3 LB guests used it -> rate 1/3; headroom-scaled onto 0.3 baseline
        assert recs[0]["score"] == pytest.approx(0.3467, abs=0.001)
        assert "guests from LB used this service" in recs[0]["reasoning"]

    def test_below_min_sample_no_boost(self, db, engine):
        svc = _make_service(db, popularity_score=0.3, category="activities")
        g1 = _make_guest(db, nationality="LB")
        g2 = _make_guest(db, nationality="LB")  # only 2 guests total < MIN_GROUP_SAMPLE
        rsv = _make_reservation(db, g1.id, check_in_offset_days=-5)
        _make_posting(db, g1.id, svc.id, reservation_id=rsv.id)

        recs = engine.recommend_for_guest(db, guest_id=g2.id)
        assert recs[0]["score"] == pytest.approx(0.3, abs=0.001)
        assert "guests from LB" not in recs[0]["reasoning"]

    def test_no_nationality_no_boost(self, db, engine):
        _make_service(db, popularity_score=0.3, category="activities")
        guest = _make_guest(db, nationality=None)
        recs = engine.recommend_for_guest(db, guest_id=guest.id)
        assert recs[0]["score"] == pytest.approx(0.3, abs=0.001)


# ----------------------------------------------------------------------
# R11: Company-group usage rate
# ----------------------------------------------------------------------
class TestCompanyUsageRate:
    def test_company_group_boost(self, db, engine):
        svc = _make_service(db, popularity_score=0.2, category="activities")
        g1 = _make_guest(db, company="Acme Corp")
        g2 = _make_guest(db, company="Acme Corp")
        g3 = _make_guest(db, company="Acme Corp")
        rsv = _make_reservation(db, g1.id, check_in_offset_days=-5)
        _make_posting(db, g1.id, svc.id, reservation_id=rsv.id)
        rsv2 = _make_reservation(db, g2.id, check_in_offset_days=-5)
        _make_posting(db, g2.id, svc.id, reservation_id=rsv2.id)

        recs = engine.recommend_for_guest(db, guest_id=g3.id)
        # 2 of 3 Acme Corp guests used it -> rate 2/3; headroom-scaled onto 0.2 baseline
        assert recs[0]["score"] == pytest.approx(0.3067, abs=0.001)
        assert "guests from Acme Corp used this service" in recs[0]["reasoning"]

    def test_no_company_no_boost(self, db, engine):
        _make_service(db, popularity_score=0.2, category="activities")
        guest = _make_guest(db, company=None)
        recs = engine.recommend_for_guest(db, guest_id=guest.id)
        assert recs[0]["score"] == pytest.approx(0.2, abs=0.001)


# ----------------------------------------------------------------------
# R12: Booking-source-group usage rate
# ----------------------------------------------------------------------
class TestSourceUsageRate:
    def test_source_group_boost(self, db, engine):
        svc = _make_service(db, popularity_score=0.1, category="activities")
        g1 = _make_guest(db, source="booking.com")
        g2 = _make_guest(db, source="booking.com")
        g3 = _make_guest(db, source="booking.com")
        rsv = _make_reservation(db, g1.id, check_in_offset_days=-5)
        _make_posting(db, g1.id, svc.id, reservation_id=rsv.id)

        recs = engine.recommend_for_guest(db, guest_id=g3.id)
        # 1 of 3 booking.com guests used it -> rate 1/3; headroom-scaled onto 0.1 baseline
        assert recs[0]["score"] == pytest.approx(0.145, abs=0.001)
        assert "guests booked via booking.com used this service" in recs[0]["reasoning"]

    def test_no_source_no_boost(self, db, engine):
        _make_service(db, popularity_score=0.1, category="activities")
        guest = _make_guest(db, source=None)
        recs = engine.recommend_for_guest(db, guest_id=guest.id)
        assert recs[0]["score"] == pytest.approx(0.1, abs=0.001)
