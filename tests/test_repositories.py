"""
Tests for database repositories.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, StaffRole, GuestStatus, AlertType, AlertStatus
from database.repositories import GuestRepository, StaffRepository, AlertRepository
import bcrypt


@pytest.fixture(scope="function")
def db():
    """Create an in-memory SQLite database for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_staff(db):
    """Create a sample staff member."""
    password_hash = bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode()
    return StaffRepository.create(
        db,
        username="testuser",
        password_hash=password_hash,
        full_name="Test User",
        email="test@hotel.com",
        role=StaffRole.RECEPTIONIST,
    )


@pytest.fixture
def sample_guest(db):
    """Create a sample guest."""
    return GuestRepository.create(
        db,
        full_name="Jane Doe",
        email="jane@example.com",
        phone="+1234567890",
        nationality="USA",
        vip_status=False,
    )


# ============================================================
# Staff Repository Tests
# ============================================================

class TestStaffRepository:

    def test_create_staff(self, db):
        password_hash = bcrypt.hashpw(b"pass", bcrypt.gensalt()).decode()
        staff = StaffRepository.create(
            db,
            username="alice",
            password_hash=password_hash,
            full_name="Alice Smith",
            email="alice@hotel.com",
            role=StaffRole.ADMIN,
        )
        assert staff.id is not None
        assert staff.username == "alice"
        assert staff.role == StaffRole.ADMIN
        assert staff.is_active is True

    def test_get_by_username(self, db, sample_staff):
        found = StaffRepository.get_by_username(db, "testuser")
        assert found is not None
        assert found.id == sample_staff.id

    def test_get_by_username_not_found(self, db):
        assert StaffRepository.get_by_username(db, "nobody") is None

    def test_get_by_id(self, db, sample_staff):
        found = StaffRepository.get_by_id(db, sample_staff.id)
        assert found is not None
        assert found.username == "testuser"

    def test_get_all(self, db, sample_staff):
        staff_list = StaffRepository.get_all(db)
        assert len(staff_list) >= 1

    def test_update_staff(self, db, sample_staff):
        updated = StaffRepository.update(db, sample_staff.id, full_name="Updated Name")
        assert updated.full_name == "Updated Name"

    def test_update_last_login(self, db, sample_staff):
        assert sample_staff.last_login is None
        updated = StaffRepository.update_last_login(db, sample_staff.id)
        assert updated.last_login is not None

    def test_delete_staff(self, db, sample_staff):
        result = StaffRepository.delete(db, sample_staff.id)
        assert result is True
        assert StaffRepository.get_by_id(db, sample_staff.id) is None

    def test_delete_nonexistent(self, db):
        assert StaffRepository.delete(db, 9999) is False


# ============================================================
# Guest Repository Tests
# ============================================================

class TestGuestRepository:

    def test_create_guest(self, db):
        guest = GuestRepository.create(
            db,
            full_name="Bob Jones",
            email="bob@example.com",
            vip_status=True,
        )
        assert guest.id is not None
        assert guest.full_name == "Bob Jones"
        assert guest.vip_status is True
        assert guest.status == GuestStatus.ACTIVE

    def test_get_by_email(self, db, sample_guest):
        found = GuestRepository.get_by_email(db, "jane@example.com")
        assert found is not None
        assert found.id == sample_guest.id

    def test_get_by_email_not_found(self, db):
        assert GuestRepository.get_by_email(db, "nobody@example.com") is None

    def test_get_by_id(self, db, sample_guest):
        found = GuestRepository.get_by_id(db, sample_guest.id)
        assert found is not None

    def test_get_all(self, db, sample_guest):
        guests = GuestRepository.get_all(db)
        assert len(guests) >= 1

    def test_get_vip_guests(self, db):
        GuestRepository.create(db, full_name="VIP Person", email="vip@example.com", vip_status=True)
        GuestRepository.create(db, full_name="Regular Person", email="reg@example.com", vip_status=False)
        vips = GuestRepository.get_vip_guests(db)
        assert all(g.vip_status for g in vips)
        assert len(vips) >= 1

    def test_search_by_name(self, db, sample_guest):
        results = GuestRepository.search_by_name(db, "Jane")
        assert len(results) >= 1
        assert any(g.full_name == "Jane Doe" for g in results)

    def test_update_guest(self, db, sample_guest):
        updated = GuestRepository.update(db, sample_guest.id, vip_status=True)
        assert updated.vip_status is True

    def test_delete_guest(self, db, sample_guest):
        result = GuestRepository.delete(db, sample_guest.id)
        assert result is True
        assert GuestRepository.get_by_id(db, sample_guest.id) is None

    def test_delete_nonexistent(self, db):
        assert GuestRepository.delete(db, 9999) is False


# ============================================================
# Alert Repository Tests
# ============================================================

class TestAlertRepository:

    def test_create_alert(self, db):
        alert = AlertRepository.create(
            db,
            alert_type=AlertType.SECURITY,
            title="Test Alert",
            description="Test description",
            severity=2,
        )
        assert alert.id is not None
        assert alert.alert_type == AlertType.SECURITY
        assert alert.status == AlertStatus.PENDING
        assert alert.severity == 2

    def test_get_by_id(self, db):
        alert = AlertRepository.create(db, alert_type=AlertType.ASSISTANCE, title="Help needed")
        found = AlertRepository.get_by_id(db, alert.id)
        assert found is not None
        assert found.title == "Help needed"

    def test_get_all(self, db):
        AlertRepository.create(db, alert_type=AlertType.SECURITY, title="Alert 1")
        AlertRepository.create(db, alert_type=AlertType.ASSISTANCE, title="Alert 2")
        alerts = AlertRepository.get_all(db)
        assert len(alerts) >= 2

    def test_get_pending_alerts(self, db):
        AlertRepository.create(db, alert_type=AlertType.SECURITY, title="Pending Alert")
        pending = AlertRepository.get_pending_alerts(db)
        assert len(pending) >= 1
        assert all(a.status == AlertStatus.PENDING for a in pending)

    def test_acknowledge_alert(self, db, sample_staff):
        alert = AlertRepository.create(db, alert_type=AlertType.SECURITY, title="Ack Test")
        acked = AlertRepository.acknowledge(db, alert.id, sample_staff.id)
        assert acked.status == AlertStatus.ACKNOWLEDGED
        assert acked.acknowledged_at is not None
        assert acked.assigned_to_id == sample_staff.id

    def test_resolve_alert(self, db):
        alert = AlertRepository.create(db, alert_type=AlertType.ASSISTANCE, title="Resolve Test")
        resolved = AlertRepository.resolve(db, alert.id)
        assert resolved.status == AlertStatus.RESOLVED
        assert resolved.resolved_at is not None

    def test_delete_alert(self, db):
        alert = AlertRepository.create(db, alert_type=AlertType.SECURITY, title="Delete Test")
        result = AlertRepository.delete(db, alert.id)
        assert result is True
        assert AlertRepository.get_by_id(db, alert.id) is None
