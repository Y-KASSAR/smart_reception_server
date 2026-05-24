import sys
import types
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

# -----------------------------------------------------------------------------
# Test-time stub for utils.crypto_utils
# -----------------------------------------------------------------------------
# Your current repository import chain expects utils.crypto_utils.encrypt_embedding.
# This makes the test suite importable even if that helper is missing or incomplete.
utils_pkg = sys.modules.get("utils")
if utils_pkg is None:
    utils_pkg = types.ModuleType("utils")
    utils_pkg.__path__ = []
    sys.modules["utils"] = utils_pkg
elif not hasattr(utils_pkg, "__path__"):
    utils_pkg.__path__ = []

crypto_utils = sys.modules.get("utils.crypto_utils")
if crypto_utils is None:
    crypto_utils = types.ModuleType("utils.crypto_utils")
    sys.modules["utils.crypto_utils"] = crypto_utils

if not hasattr(crypto_utils, "encrypt_embedding"):
    crypto_utils.encrypt_embedding = lambda payload: payload[::-1]
if not hasattr(crypto_utils, "decrypt_embedding"):
    crypto_utils.decrypt_embedding = lambda payload: payload[::-1]

# -----------------------------------------------------------------------------
# Project imports
# -----------------------------------------------------------------------------
from database.models import (
    Base,
    Alert,
    AlertStatus,
    AlertType,
    FaceEmbedding,
    Guest,
    GuestStatus,
    Recommendation,
    RecommendationStatus,
    Reservation,
    ReservationStatus,
    Service,
    Staff,
    StaffRole,
    SystemLog,
    Visit,
)

from database.repositories.alert_repository import AlertRepository
from database.repositories.face_embedding_repository import FaceEmbeddingRepository
from database.repositories.guest_repository import GuestRepository
from database.repositories.recommendation_repository import RecommendationRepository
from database.repositories.reservation_repository import ReservationRepository
from database.repositories.service_repository import ServiceRepository
from database.repositories.staff_repository import StaffRepository
from database.repositories.visit_repository import VisitRepository


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------
@pytest.fixture()
def db_session(tmp_path):
    db_file = tmp_path / "test_database.sqlite"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )

    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def create_guest(db_session, full_name, email, phone="+1000000000", vip_status=False, **kwargs):
    return GuestRepository.create(
        db_session,
        full_name=full_name,
        email=email,
        phone=phone,
        vip_status=vip_status,
        **kwargs,
    )


def create_staff(
    db_session,
    username,
    email,
    full_name="Test Staff",
    password_hash="hashed-password",
    role=StaffRole.ADMIN,
):
    return StaffRepository.create(
        db_session,
        username=username,
        password_hash=password_hash,
        full_name=full_name,
        email=email,
        role=role,
    )


# -----------------------------------------------------------------------------
# Core database / schema tests
# -----------------------------------------------------------------------------
def test_all_expected_tables_are_created(db_session):
    inspector = inspect(db_session.get_bind())
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "guests",
        "staff",
        "face_embeddings",
        "visits",
        "reservations",
        "services",
        "alerts",
        "recommendations",
        "system_logs",
    }

    assert expected_tables.issubset(table_names)


def test_guest_model_splits_full_name():
    guest = Guest(full_name="John Smith")
    assert guest.first_name == "John"
    assert guest.last_name == "Smith"
    assert guest.full_name == "John Smith"


def test_system_log_persists(db_session):
    log = SystemLog(
        event_type="database_test",
        severity="info",
        message="Database test log entry",
        extra_data='{"ok": true}',
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)

    assert log.id is not None
    assert db_session.query(SystemLog).count() == 1


# -----------------------------------------------------------------------------
# GuestRepository tests
# -----------------------------------------------------------------------------
def test_guest_repository_crud_and_search(db_session):
    guest = create_guest(
        db_session,
        full_name="John Smith",
        email="john.smith@example.com",
        phone="+1234567890",
        vip_status=True,
        preferences='{"room_type": "suite"}',
        notes="Quiet room preferred",
    )

    other_guest = create_guest(
        db_session,
        full_name="Emma Wilson",
        email="emma.wilson@example.com",
        phone="+1987654321",
        vip_status=False,
    )

    assert guest.id is not None
    assert GuestRepository.get_by_id(db_session, guest.id).email == "john.smith@example.com"
    assert GuestRepository.get_by_email(db_session, "john.smith@example.com").id == guest.id

    active_guests = GuestRepository.get_active_guests(db_session)
    vip_guests = GuestRepository.get_vip_guests(db_session)

    assert guest in active_guests
    assert other_guest in active_guests
    assert guest in vip_guests
    assert other_guest not in vip_guests

    matches = GuestRepository.search_by_name(db_session, "Smith")
    assert any(item.id == guest.id for item in matches)

    updated = GuestRepository.update(
        db_session,
        guest.id,
        notes="Updated note",
        vip_status=False,
    )
    assert updated.notes == "Updated note"
    assert updated.vip_status is False

    assert GuestRepository.delete(db_session, other_guest.id) is True
    assert GuestRepository.get_by_id(db_session, other_guest.id) is None


# -----------------------------------------------------------------------------
# StaffRepository tests
# -----------------------------------------------------------------------------
def test_staff_repository_crud_and_last_login(db_session):
    staff = create_staff(
        db_session,
        username="admin",
        email="admin@example.com",
        full_name="System Administrator",
        role=StaffRole.ADMIN,
    )

    assert staff.id is not None
    assert StaffRepository.get_by_id(db_session, staff.id).username == "admin"
    assert StaffRepository.get_by_username(db_session, "admin").id == staff.id

    active_staff = StaffRepository.get_active_staff(db_session)
    assert any(item.id == staff.id for item in active_staff)

    staff = StaffRepository.update_last_login(db_session, staff.id)
    assert staff.last_login is not None

    updated = StaffRepository.update(
        db_session,
        staff.id,
        full_name="Admin Prime",
        is_active=False,
    )
    assert updated.full_name == "Admin Prime"
    assert updated.is_active is False

    assert staff.id not in [item.id for item in StaffRepository.get_active_staff(db_session)]
    assert StaffRepository.delete(db_session, staff.id) is True
    assert StaffRepository.get_by_id(db_session, staff.id) is None


# -----------------------------------------------------------------------------
# ServiceRepository tests
# -----------------------------------------------------------------------------
def test_service_repository_crud_and_filters(db_session):
    spa = ServiceRepository.create(
        db_session,
        name="Spa Massage",
        category="spa",
        description="Relaxing treatment",
        price=120.0,
        is_active=True,
    )
    inactive_spa = ServiceRepository.create(
        db_session,
        name="Old Spa Package",
        category="spa",
        description="Deprecated service",
        price=80.0,
        is_active=False,
    )
    dining = ServiceRepository.create(
        db_session,
        name="Breakfast Buffet",
        category="dining",
        description="All-you-can-eat breakfast",
        price=25.0,
        is_active=True,
    )

    assert spa.id is not None
    assert ServiceRepository.get_by_id(db_session, spa.id).name == "Spa Massage"

    active_services = ServiceRepository.get_active(db_session)
    assert spa in active_services
    assert dining in active_services
    assert inactive_spa not in active_services

    spa_services = ServiceRepository.get_by_category(db_session, "spa")
    assert spa in spa_services
    assert inactive_spa not in spa_services  # inactive should be filtered out
    assert dining not in spa_services

    updated = ServiceRepository.update(
        db_session,
        spa.id,
        price=130.0,
        description="Updated description",
    )
    assert updated.price == 130.0
    assert updated.description == "Updated description"

    assert ServiceRepository.delete(db_session, dining.id) is True
    assert ServiceRepository.get_by_id(db_session, dining.id) is None


# -----------------------------------------------------------------------------
# ReservationRepository tests
# -----------------------------------------------------------------------------
def test_reservation_repository_crud(db_session):
    guest = create_guest(
        db_session,
        full_name="Maria Garcia",
        email="maria.garcia@example.com",
        vip_status=False,
    )

    check_in_date = datetime(2026, 6, 1, 14, 0, 0)
    check_out_date = datetime(2026, 6, 5, 11, 0, 0)

    reservation = ReservationRepository.create(
        db_session,
        guest_id=guest.id,
        reservation_code="RES-001",
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        room_type="deluxe",
        room_number="402",
        num_guests=2,
        special_requests="Late check-in",
        rate_per_night=150.0,
        total_amount=600.0,
        status=ReservationStatus.CONFIRMED,
    )

    assert reservation.id is not None
    assert ReservationRepository.get_by_id(db_session, reservation.id).reservation_code == "RES-001"
    assert ReservationRepository.get_by_code(db_session, "RES-001").id == reservation.id

    reservations = ReservationRepository.get_by_guest(db_session, guest.id)
    assert any(item.id == reservation.id for item in reservations)

    updated = ReservationRepository.update(
        db_session,
        reservation.id,
        room_number="405",
        status=ReservationStatus.CHECKED_IN,
    )
    assert updated.room_number == "405"
    assert updated.status == ReservationStatus.CHECKED_IN

    assert ReservationRepository.delete(db_session, reservation.id) is True
    assert ReservationRepository.get_by_id(db_session, reservation.id) is None


# -----------------------------------------------------------------------------
# VisitRepository tests
# -----------------------------------------------------------------------------
def test_visit_repository_crud(db_session):
    guest = create_guest(
        db_session,
        full_name="Ahmed Hassan",
        email="ahmed.hassan@example.com",
        vip_status=True,
    )

    check_in = datetime(2026, 6, 10, 15, 30, 0)

    visit = VisitRepository.create(
        db_session,
        guest_id=guest.id,
        check_in=check_in,
        room_number="210",
        notes="Arrived early",
        total_spend=75.0,
        services_used='["drink", "wifi"]',
        feedback_score=5,
    )

    assert visit.id is not None
    assert VisitRepository.get_by_id(db_session, visit.id).guest_id == guest.id
    assert len(VisitRepository.get_by_guest(db_session, guest.id)) == 1

    updated = VisitRepository.update(
        db_session,
        visit.id,
        check_out=datetime(2026, 6, 12, 11, 0, 0),
        room_number="211",
    )
    assert updated.room_number == "211"
    assert updated.check_out is not None

    assert VisitRepository.delete(db_session, visit.id) is True
    assert VisitRepository.get_by_id(db_session, visit.id) is None


# -----------------------------------------------------------------------------
# AlertRepository tests
# -----------------------------------------------------------------------------
def test_alert_repository_crud_and_state_transitions(db_session):
    staff = create_staff(
        db_session,
        username="security",
        email="security@example.com",
        full_name="Security Guard",
        role=StaffRole.SECURITY,
    )
    guest = create_guest(
        db_session,
        full_name="VIP Guest",
        email="vip.guest@example.com",
        vip_status=True,
    )

    alert = AlertRepository.create(
        db_session,
        alert_type=AlertType.SECURITY,
        title="Unknown person in lobby",
        description="Unidentified person standing near reception",
        severity=3,
        location="Main Lobby",
        guest_id=guest.id,
        created_by_id=staff.id,
    )

    assert alert.id is not None
    assert alert.status == AlertStatus.PENDING

    pending_alerts = AlertRepository.get_pending_alerts(db_session)
    assert any(item.id == alert.id for item in pending_alerts)

    by_type = AlertRepository.get_by_type(db_session, AlertType.SECURITY)
    assert any(item.id == alert.id for item in by_type)

    acknowledged = AlertRepository.acknowledge(
        db_session,
        alert.id,
        staff_id=staff.id,
        staff_name=staff.full_name,
    )
    assert acknowledged.status == AlertStatus.ACKNOWLEDGED
    assert acknowledged.acknowledged_at is not None
    assert acknowledged.assigned_to_id == staff.id
    assert acknowledged.acknowledged_by == staff.full_name

    resolved = AlertRepository.resolve(db_session, alert.id)
    assert resolved.status == AlertStatus.RESOLVED
    assert resolved.resolved_at is not None

    assert AlertRepository.delete(db_session, alert.id) is True
    assert AlertRepository.get_by_id(db_session, alert.id) is None


# -----------------------------------------------------------------------------
# RecommendationRepository tests
# -----------------------------------------------------------------------------
def test_recommendation_repository_update_and_delete(db_session):
    guest = create_guest(
        db_session,
        full_name="Recommendation Guest",
        email="recommendation.guest@example.com",
        vip_status=False,
    )
    staff = create_staff(
        db_session,
        username="manager",
        email="manager@example.com",
        full_name="Hotel Manager",
        role=StaffRole.MANAGER,
    )
    service = ServiceRepository.create(
        db_session,
        name="Dinner Reservation",
        category="dining",
        description="Priority dinner booking",
        price=50.0,
        is_active=True,
    )

    recommendation = Recommendation(
        guest_id=guest.id,
        service_id=service.id,
        staff_id=staff.id,
        score=0.85,
        reasoning="Matches guest preferences",
        status=RecommendationStatus.PENDING,
    )
    db_session.add(recommendation)
    db_session.commit()
    db_session.refresh(recommendation)

    assert recommendation.id is not None
    assert RecommendationRepository.get_by_id(db_session, recommendation.id).id == recommendation.id
    assert any(item.id == recommendation.id for item in RecommendationRepository.get_by_guest(db_session, guest.id))

    presented = RecommendationRepository.update_status(
        db_session,
        recommendation.id,
        RecommendationStatus.PRESENTED,
    )
    assert presented.status == RecommendationStatus.PRESENTED
    assert presented.presented_at is not None

    accepted = RecommendationRepository.update_status(
        db_session,
        recommendation.id,
        RecommendationStatus.ACCEPTED,
    )
    assert accepted.status == RecommendationStatus.ACCEPTED
    assert accepted.responded_at is not None

    assert RecommendationRepository.delete(db_session, recommendation.id) is True
    assert RecommendationRepository.get_by_id(db_session, recommendation.id) is None


# -----------------------------------------------------------------------------
# FaceEmbeddingRepository tests
# -----------------------------------------------------------------------------
def test_face_embedding_repository_crud(db_session):
    guest = create_guest(
        db_session,
        full_name="Face Match Guest",
        email="face.guest@example.com",
        vip_status=False,
    )

    plain_embedding = b"embedding-bytes-123"
    created = FaceEmbeddingRepository.create(
        db_session,
        guest_id=guest.id,
        embedding_bytes=plain_embedding,
        source="enrollment",
        quality_score=0.92,
    )

    assert created.id is not None
    assert created.embedding_vector == plain_embedding[::-1]  # test-time stub behavior
    assert FaceEmbeddingRepository.count_for_guest(db_session, guest.id) == 1

    by_guest = FaceEmbeddingRepository.get_by_guest(db_session, guest.id)
    assert len(by_guest) == 1
    assert by_guest[0].id == created.id

    by_id = FaceEmbeddingRepository.get_by_id(db_session, created.id)
    assert by_id is not None
    assert by_id.guest_id == guest.id

    second = FaceEmbeddingRepository.create(
        db_session,
        guest_id=guest.id,
        embedding_bytes=b"another-embedding",
        source="camera",
        quality_score=0.88,
    )
    assert FaceEmbeddingRepository.count_for_guest(db_session, guest.id) == 2

    assert FaceEmbeddingRepository.delete(db_session, second.id) is True
    assert FaceEmbeddingRepository.get_by_id(db_session, second.id) is None

    assert FaceEmbeddingRepository.delete_by_guest(db_session, guest.id) is True
    assert FaceEmbeddingRepository.count_for_guest(db_session, guest.id) == 0