"""
Tests for FastAPI API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database.models import Base, StaffRole
from database.connection import get_db
from api.app import create_app
from utils.security_utils import get_current_staff, require_role
import bcrypt

MOCK_ADMIN_PAYLOAD = {"sub": "1", "username": "admin", "role": "admin"}
MOCK_STAFF_PAYLOAD = {"sub": "1", "username": "admin", "role": "admin"}


@pytest.fixture(scope="function")
def test_db():
    """In-memory SQLite database for API tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db):
    """FastAPI test client with overridden DB and auth dependencies."""
    app = create_app()

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    def override_get_current_staff():
        return MOCK_ADMIN_PAYLOAD

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_staff] = override_get_current_staff

    return TestClient(app)


@pytest.fixture
def admin_staff(test_db):
    """Create an admin staff member in the test DB."""
    from database.repositories import StaffRepository
    password_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode()
    return StaffRepository.create(
        test_db,
        username="admin",
        password_hash=password_hash,
        full_name="Admin User",
        email="admin@hotel.com",
        role=StaffRole.ADMIN,
    )


# ============================================================
# Health Endpoint Tests
# ============================================================

class TestHealthEndpoint:

    def test_health_check(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


# ============================================================
# Guest Endpoint Tests
# ============================================================

class TestGuestEndpoints:

    def test_list_guests_empty(self, client):
        response = client.get("/api/guests/")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_guest(self, client):
        payload = {
            "full_name": "John Smith",
            "email": "john@example.com",
            "phone": "+1234567890",
            "nationality": "USA",
            "vip_status": True,
        }
        response = client.post("/api/guests/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["full_name"] == "John Smith"
        assert data["vip_status"] is True
        assert data["id"] is not None

    def test_create_guest_duplicate_email(self, client):
        payload = {"full_name": "Alice", "email": "alice@example.com"}
        client.post("/api/guests/", json=payload)
        response = client.post("/api/guests/", json=payload)
        assert response.status_code == 409

    def test_get_guest(self, client):
        create_resp = client.post("/api/guests/", json={"full_name": "Bob", "email": "bob@example.com"})
        guest_id = create_resp.json()["id"]
        response = client.get(f"/api/guests/{guest_id}")
        assert response.status_code == 200
        assert response.json()["full_name"] == "Bob"

    def test_get_guest_not_found(self, client):
        response = client.get("/api/guests/9999")
        assert response.status_code == 404

    def test_update_guest(self, client):
        create_resp = client.post("/api/guests/", json={"full_name": "Carol", "email": "carol@example.com"})
        guest_id = create_resp.json()["id"]
        response = client.put(f"/api/guests/{guest_id}", json={"vip_status": True})
        assert response.status_code == 200
        assert response.json()["vip_status"] is True

    def test_delete_guest(self, client):
        create_resp = client.post("/api/guests/", json={"full_name": "Dave", "email": "dave@example.com"})
        guest_id = create_resp.json()["id"]
        response = client.delete(f"/api/guests/{guest_id}")
        assert response.status_code == 204
        assert client.get(f"/api/guests/{guest_id}").status_code == 404

    def test_search_guests(self, client):
        client.post("/api/guests/", json={"full_name": "Emma Watson", "email": "emma@example.com"})
        response = client.get("/api/guests/search?name=Emma")
        assert response.status_code == 200
        results = response.json()
        assert any(g["full_name"] == "Emma Watson" for g in results)

    def test_list_vip_guests(self, client):
        client.post("/api/guests/", json={"full_name": "VIP Guest", "email": "vip@example.com", "vip_status": True})
        client.post("/api/guests/", json={"full_name": "Regular Guest", "email": "reg@example.com", "vip_status": False})
        response = client.get("/api/guests/vip")
        assert response.status_code == 200
        vips = response.json()
        assert all(g["vip_status"] for g in vips)


# ============================================================
# Staff Endpoint Tests
# ============================================================

class TestStaffEndpoints:

    def test_list_staff_empty(self, client):
        response = client.get("/api/staff/")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_staff(self, client):
        payload = {
            "username": "receptionist1",
            "password": "pass123",
            "full_name": "Sarah Johnson",
            "email": "sarah@hotel.com",
            "role": "receptionist",
        }
        response = client.post("/api/staff/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "receptionist1"
        assert "password_hash" not in data

    def test_create_staff_duplicate_username(self, client):
        payload = {
            "username": "dup_user",
            "password": "pass",
            "full_name": "Dup User",
            "email": "dup@hotel.com",
            "role": "receptionist",
        }
        client.post("/api/staff/", json=payload)
        payload["email"] = "dup2@hotel.com"
        response = client.post("/api/staff/", json=payload)
        assert response.status_code == 409

    def test_login_success(self, client, admin_staff):
        response = client.post("/api/staff/login", json={"username": "admin", "password": "admin123"})
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, admin_staff):
        response = client.post("/api/staff/login", json={"username": "admin", "password": "wrong"})
        assert response.status_code == 401

    def test_login_unknown_user(self, client):
        response = client.post("/api/staff/login", json={"username": "ghost", "password": "pass"})
        assert response.status_code == 401


# ============================================================
# Alert Endpoint Tests
# ============================================================

class TestAlertEndpoints:

    def test_list_alerts_empty(self, client):
        response = client.get("/api/alerts/")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_alert(self, client):
        payload = {
            "alert_type": "security",
            "title": "Unknown person in lobby",
            "severity": 3,
            "location": "Main Lobby",
        }
        response = client.post("/api/alerts/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Unknown person in lobby"
        assert data["status"] == "pending"

    def test_get_alert(self, client):
        create_resp = client.post("/api/alerts/", json={"alert_type": "assistance", "title": "Help"})
        alert_id = create_resp.json()["id"]
        response = client.get(f"/api/alerts/{alert_id}")
        assert response.status_code == 200

    def test_get_alert_not_found(self, client):
        response = client.get("/api/alerts/9999")
        assert response.status_code == 404

    def test_list_pending_alerts(self, client):
        client.post("/api/alerts/", json={"alert_type": "security", "title": "Pending"})
        response = client.get("/api/alerts/pending")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_acknowledge_alert(self, client, admin_staff):
        create_resp = client.post("/api/alerts/", json={"alert_type": "security", "title": "Ack Test"})
        alert_id = create_resp.json()["id"]
        response = client.post(f"/api/alerts/{alert_id}/acknowledge?staff_id={admin_staff.id}")
        assert response.status_code == 200
        assert response.json()["status"] == "acknowledged"

    def test_resolve_alert(self, client):
        create_resp = client.post("/api/alerts/", json={"alert_type": "assistance", "title": "Resolve Test"})
        alert_id = create_resp.json()["id"]
        response = client.post(f"/api/alerts/{alert_id}/resolve")
        assert response.status_code == 200
        assert response.json()["status"] == "resolved"

    def test_delete_alert(self, client):
        create_resp = client.post("/api/alerts/", json={"alert_type": "security", "title": "Delete Test"})
        alert_id = create_resp.json()["id"]
        response = client.delete(f"/api/alerts/{alert_id}")
        assert response.status_code == 204
