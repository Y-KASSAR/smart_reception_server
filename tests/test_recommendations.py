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
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import (
    Base,
    Guest,
    Service,
    Recommendation,
    RecommendationStatus,
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
        _make_guest(db, vip_status=True)
        _make_service(db, category="spa", popularity_score=0.4)
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == pytest.approx(0.7, abs=0.001)
        assert "VIP" in recs[0]["reasoning"]

    def test_vip_boosts_dining(self, db, engine):
        _make_guest(db, vip_status=True)
        _make_service(db, category="dining", popularity_score=0.2)
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == pytest.approx(0.5, abs=0.001)

    def test_vip_boosts_room_service(self, db, engine):
        _make_guest(db, vip_status=True)
        _make_service(db, category="room_service", popularity_score=0.3)
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == pytest.approx(0.6, abs=0.001)

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
        assert recs[0]["score"] == pytest.approx(0.5, abs=0.001)
        assert "vegan" in recs[0]["reasoning"].lower()

    def test_dietary_case_insensitive(self, db, engine):
        _make_guest(db, preferences=json.dumps({"dietary": "Vegan"}))
        _make_service(db, description="VEGAN MENU", popularity_score=0.1, category="activities")
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] == pytest.approx(0.3, abs=0.001)

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
        assert recs[0]["score"] == pytest.approx(0.4, abs=0.001)

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
        assert recs[0]["score"] == pytest.approx(0.35, abs=0.001)
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
        _make_guest(db, vip_status=True, language_preference="ar",
                    preferences=json.dumps({"dietary": "halal", "room_type": "suite"}))
        _make_service(db, category="dining", description="halal suite menu",
                      popularity_score=0.95)
        recs = engine.recommend_for_guest(db, guest_id=1)
        assert recs[0]["score"] <= 1.0
        assert recs[0]["score"] == pytest.approx(1.0, abs=0.001)


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
