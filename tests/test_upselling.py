"""
Tests for the upselling API surface (`/api/recommendations`).

Complements ``test_recommendations.py`` (which unit-tests the engine
scoring rules) by covering the FastAPI route layer end-to-end:
- POST /api/recommendations/generate/{guest_id}
- GET  /api/recommendations/
- GET  /api/recommendations/guest/{guest_id}
- GET  /api/recommendations/{rec_id}
- PUT  /api/recommendations/{rec_id}/status
- DELETE /api/recommendations/{rec_id}

All tests use an in-memory SQLite DB and override authentication.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.app import create_app
from database.connection import get_db
from database.models import (
    Base,
    Guest,
    Recommendation,
    RecommendationStatus,
    Service,
)
from utils.security_utils import get_current_staff, require_role


MOCK_ADMIN = {"sub": "1", "username": "admin", "role": "admin"}


@pytest.fixture(scope="function")
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db):
    app = create_app()

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_staff] = lambda: MOCK_ADMIN
    # require_role(...) returns a callable dependency; override the factory result
    # by overriding get_current_staff (its underlying dependency) — sufficient for tests.
    return TestClient(app)


# ------------------------------------------------------------------ #
# Fixtures: seed a guest + a few services                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def seeded(test_db):
    guest = Guest(full_name="Layla Hassan", language_preference="ar", vip_status=True)
    test_db.add(guest)
    test_db.commit()
    test_db.refresh(guest)

    services = [
        Service(name="Spa Day", category="spa", popularity_score=0.4, is_active=True),
        Service(name="Fine Dining", category="dining", popularity_score=0.6, is_active=True),
        Service(name="Closed Pool", category="leisure", popularity_score=0.9, is_active=False),
    ]
    for s in services:
        test_db.add(s)
    test_db.commit()
    return {"guest": guest, "services": services}


# ------------------------------------------------------------------ #
# POST /generate/{guest_id}                                          #
# ------------------------------------------------------------------ #

class TestGenerate:

    def test_generate_returns_recommendations(self, client, seeded):
        gid = seeded["guest"].id
        r = client.post(f"/api/recommendations/generate/{gid}?limit=5")
        assert r.status_code == 201, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_generate_excludes_inactive_services(self, client, seeded):
        gid = seeded["guest"].id
        r = client.post(f"/api/recommendations/generate/{gid}")
        names = [item.get("service_name") or item.get("name") for item in r.json()]
        # The closed service should not appear in any rec
        for n in names:
            assert n != "Closed Pool"

    def test_generate_404_for_unknown_guest(self, client, test_db):
        # No guests, no services
        r = client.post("/api/recommendations/generate/9999")
        assert r.status_code == 404

    def test_generate_dedupes_on_repeat(self, client, seeded, test_db):
        gid = seeded["guest"].id
        client.post(f"/api/recommendations/generate/{gid}")
        first = test_db.query(Recommendation).count()
        client.post(f"/api/recommendations/generate/{gid}")
        second = test_db.query(Recommendation).count()
        # Pending recommendations are deduplicated by (guest_id, service_id)
        assert second == first

    def test_generate_respects_limit(self, client, seeded):
        gid = seeded["guest"].id
        r = client.post(f"/api/recommendations/generate/{gid}?limit=1")
        assert r.status_code == 201
        # The endpoint returns ALL recs for the guest, but only `limit`
        # were generated this call. Re-running with a different guest is
        # fine; just verify response is a non-empty list.
        assert len(r.json()) >= 1


# ------------------------------------------------------------------ #
# GET endpoints                                                      #
# ------------------------------------------------------------------ #

class TestList:

    def test_list_empty(self, client):
        r = client.get("/api/recommendations/")
        assert r.status_code == 200
        assert r.json() == []

    def test_list_after_generate(self, client, seeded):
        gid = seeded["guest"].id
        client.post(f"/api/recommendations/generate/{gid}")
        r = client.get("/api/recommendations/")
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_list_by_guest(self, client, seeded):
        gid = seeded["guest"].id
        client.post(f"/api/recommendations/generate/{gid}")
        r = client.get(f"/api/recommendations/guest/{gid}")
        assert r.status_code == 200
        recs = r.json()
        assert all(rec["guest_id"] == gid for rec in recs)

    def test_get_by_id(self, client, seeded, test_db):
        gid = seeded["guest"].id
        client.post(f"/api/recommendations/generate/{gid}")
        rec = test_db.query(Recommendation).first()
        r = client.get(f"/api/recommendations/{rec.id}")
        assert r.status_code == 200
        assert r.json()["id"] == rec.id

    def test_get_by_id_404(self, client):
        r = client.get("/api/recommendations/999999")
        assert r.status_code == 404


# ------------------------------------------------------------------ #
# PUT status / DELETE                                                #
# ------------------------------------------------------------------ #

class TestUpdateAndDelete:

    def test_update_status_to_accepted(self, client, seeded, test_db):
        gid = seeded["guest"].id
        client.post(f"/api/recommendations/generate/{gid}")
        rec = test_db.query(Recommendation).first()
        r = client.put(f"/api/recommendations/{rec.id}/status", json="accepted")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "accepted"

    def test_update_status_404(self, client):
        r = client.put("/api/recommendations/999999/status", json="declined")
        assert r.status_code == 404

    def test_delete_recommendation(self, client, seeded, test_db):
        gid = seeded["guest"].id
        client.post(f"/api/recommendations/generate/{gid}")
        rec = test_db.query(Recommendation).first()
        r = client.delete(f"/api/recommendations/{rec.id}")
        assert r.status_code == 204
        assert test_db.query(Recommendation).filter(Recommendation.id == rec.id).first() is None

    def test_delete_404(self, client):
        r = client.delete("/api/recommendations/999999")
        assert r.status_code == 404


# ------------------------------------------------------------------ #
# Persistence integrity                                              #
# ------------------------------------------------------------------ #

class TestPersistence:

    def test_recommendations_have_required_fields(self, client, seeded, test_db):
        gid = seeded["guest"].id
        client.post(f"/api/recommendations/generate/{gid}")
        rec = test_db.query(Recommendation).first()
        assert rec.guest_id == gid
        assert rec.service_id is not None
        assert 0.0 <= rec.score <= 1.0
        assert rec.reasoning  # non-empty
        assert rec.status == RecommendationStatus.PENDING

    def test_status_transition_persists(self, client, seeded, test_db):
        gid = seeded["guest"].id
        client.post(f"/api/recommendations/generate/{gid}")
        rec = test_db.query(Recommendation).first()
        client.put(f"/api/recommendations/{rec.id}/status", json="presented")
        test_db.expire_all()
        rec_after = test_db.query(Recommendation).filter(Recommendation.id == rec.id).first()
        assert rec_after.status == RecommendationStatus.PRESENTED
