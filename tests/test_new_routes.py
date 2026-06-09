"""
Smoke tests for the routes added on Day 3:
    - api.routes.enrollment
    - api.routes.system
    - api.routes.monitoring

They share the same fixture pattern as tests/test_api.py (in-memory SQLite,
mocked staff dependency).
"""
import base64
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.app import create_app
from database.connection import get_db
from database.models import Base
from utils.security_utils import get_current_staff


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

    def override_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_staff] = lambda: MOCK_ADMIN
    return TestClient(app)


# ============================================================
# /api/system
# ============================================================
class TestSystemRoutes:
    def test_status_returns_all_subsystems(self, client):
        r = client.get("/api/system/status")
        assert r.status_code == 200
        data = r.json()
        assert "server_uptime_seconds" in data
        for key in ("database", "recognition", "person_detection", "monitoring", "alert_pipeline"):
            assert key in data, f"missing subsystem: {key}"
            assert "ok" in data[key]
            assert "detail" in data[key]
        # Database must always be ok in the test env
        assert data["database"]["ok"] is True

    def test_stats_returns_zero_counters_on_empty_db(self, client):
        r = client.get("/api/system/stats")
        assert r.status_code == 200
        data = r.json()
        for key in (
            "guests_total",
            "guests_identified_today",
            "alerts_today",
            "alerts_open",
            "recommendations_today",
            "recommendations_accepted_today",
            "embeddings_total",
        ):
            assert key in data
            assert isinstance(data[key], int)
        assert data["guests_total"] == 0


# ============================================================
# /api/monitoring
# ============================================================
class TestMonitoringRoutes:
    def test_status_returns_empty_when_no_tracks(self, client):
        # Ensure clean state — other tests may have left tracks
        from modules.monitoring import person_monitor
        person_monitor.clear()

        r = client.get("/api/monitoring/status")
        assert r.status_code == 200
        data = r.json()
        assert data["total_persons"] == 0
        assert data["in_house_count"] == 0
        assert data["unknown_count"] == 0
        assert data["flagged_count"] == 0
        assert data["tracks"] == []

    def test_status_reflects_added_tracks(self, client):
        from modules.monitoring import person_monitor
        person_monitor.clear()
        person_monitor.update(track_id=10, is_known=False)
        person_monitor.update(track_id=11, is_known=True, guest_id=42)

        r = client.get("/api/monitoring/status")
        assert r.status_code == 200
        data = r.json()
        assert data["total_persons"] == 2
        assert data["in_house_count"] == 1
        assert data["unknown_count"] == 1
        ids = sorted(t["track_id"] for t in data["tracks"])
        assert ids == [10, 11]


# ============================================================
# /api/enrollment
# ============================================================
class TestEnrollmentRoutes:
    def test_complete_requires_consent(self, client):
        payload = {
            "guest": {"full_name": "Test Guest", "email": "t@example.com"},
            "face_images_b64": [base64.b64encode(b"fake").decode("ascii")],
            "consent_given": False,
        }
        r = client.post("/api/enrollment/complete", json=payload)
        assert r.status_code == 400
        assert "consent" in r.json()["detail"].lower()

    def test_complete_requires_at_least_one_image(self, client):
        payload = {
            "guest": {"full_name": "Test", "email": "tt@example.com"},
            "face_images_b64": [],
            "consent_given": True,
        }
        r = client.post("/api/enrollment/complete", json=payload)
        assert r.status_code == 400

    def test_complete_rejects_too_many_images(self, client):
        payload = {
            "guest": {"full_name": "Test", "email": "ttt@example.com"},
            "face_images_b64": ["x"] * 50,
            "consent_given": True,
        }
        r = client.post("/api/enrollment/complete", json=payload)
        assert r.status_code == 400
        assert "Maximum" in r.json()["detail"]

    def test_capture_rejects_invalid_frame(self, client):
        # "not-base64!" is invalid b64 → 400 from _decode_frame
        r = client.post("/api/enrollment/capture", json={"frame_b64": "not-real-base64-data"})
        # Either 400 (invalid frame) or 503 (cv2 not installed) — both are acceptable
        # signals that the endpoint handled bad input without crashing.
        assert r.status_code in (400, 503)
