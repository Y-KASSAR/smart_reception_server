from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))  # adjusted

from database.connection import get_db_session, init_db
from database.repositories import GuestRepository, StaffRepository, AlertRepository
from database.models import Staff, Guest, Alert, StaffRole, AlertType
import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def seed_database():
    print("🌱 Seeding database with test data...")

    init_db()

    with get_db_session() as db:
        print("creating staff accounts...")

        if not StaffRepository.get_by_username(db, "admin"):
            admin = StaffRepository.create(
                db,
                username="admin",
                password_hash=hash_password("admin123"),
                full_name="System Administrator",
                email="admin@hotel.com",
                role=StaffRole.ADMIN,
            )
        else:
            admin = StaffRepository.get_by_username(db, "admin")
            print("(admin already exists, skipping.)")

        if not StaffRepository.get_by_username(db, "receptionist"):
            receptionist = StaffRepository.create(
                db,
                username="receptionist",
                password_hash=hash_password("reception123"),
                full_name="Maha Wehbe",
                email="mwehbe@hotel.com",  # adjusted
                role=StaffRole.RECEPTIONIST,
            )
        else:
            receptionist = StaffRepository.get_by_username(db, "receptionist")
            print("  (receptionist already exists, skipping)")

        if not StaffRepository.get_by_username(db, "security"):
            security = StaffRepository.create(
                db,
                username="security",
                password_hash=hash_password("secure123"),
                full_name="Hussien Salemh",
                email="hsalemh@hotel.com",
                role=StaffRole.SECURITY,
            )
        else:
            security = StaffRepository.get_by_username(db, "security")
            print("  (security already exists, skipping)")

        if not StaffRepository.get_by_username(db, "manager"):
            manager = StaffRepository.create(
                db,
                username="manager",
                password_hash=hash_password("manager123"),
                full_name="Kassem Chahin",
                email="kchahin@hotel.com",
                role=StaffRole.MANAGER,
            )
        else:
            manager = StaffRepository.get_by_username(db, "manager")
            print("  (manager already exists, skipping)")

        if not StaffRepository.get_by_username(db, "room_service"):
            room_service = StaffRepository.create(
                db,
                username="room_service",
                password_hash=hash_password("room_service123"),
                full_name="Hussien Ramadan",
                email="hramadan@hotel.com",  # adjusted
                role=StaffRole.ROOM_SERVICE,
            )
        else:
            room_service = StaffRepository.get_by_username(db, "room_service")
            print("  (room_service already exists, skipping)")

        if not StaffRepository.get_by_username(db, "housekeeping"):
            housekeeping = StaffRepository.create(
                db,
                username="housekeeping",
                password_hash=hash_password("housekeeping123"),
                full_name="Abed the syrian",
                email="abed@hotel.com",  # adjusted
                role=StaffRole.HOUSEKEEPING,
            )
        else:
            housekeeping = StaffRepository.get_by_username(db, "housekeeping")
            print("  (housekeeping already exists, skipping)")

        if not StaffRepository.get_by_username(db, "maintenance"):
            maintenance = StaffRepository.create(
                db,
                username="maintenance",
                password_hash=hash_password("maintenance123"),
                full_name="Karem the boldguy",
                email="kboldii@hotel.com",
                role=StaffRole.MAINTENANCE,
            )
        else:
            maintenance = StaffRepository.get_by_username(db, "maintenance")  # adjusted
            print("  (maintenance already exists, skipping)")

        print("Creating guest profiles...")

        if not GuestRepository.get_by_email(db, "john.smith@email.com"):
            guest1 = GuestRepository.create(
                db,
                full_name="John Smith",
                email="john.smith@email.com",
                phone="+1234567890",
                nationality="US",  # adjusted
                vip_status=True,
                preferences='{"room_type": "suite", "floor": "high", "pillow": "soft"}',
                notes="Prefers quiet rooms away from elevator",
            )
        else:
            guest1 = GuestRepository.get_by_email(db, "john.smith@email.com")
            print("  (John Smith already exists, skipping)")

        if not GuestRepository.get_by_email(db, "emma.wilson@email.com"):
            GuestRepository.create(
                db,
                full_name="Emma Wilson",
                email="emma.wilson@email.com",
                phone="+1987654321",
                nationality="GB",  # adjusted
                vip_status=False,
                language_preference="en",
            )
        else:
            print("  (Emma Wilson already exists, skipping)")

        if not GuestRepository.get_by_email(db, "ahmed.hassan@email.com"):
            GuestRepository.create(
                db,
                full_name="Ahmed Hassan",
                email="ahmed.hassan@email.com",
                phone="+9611234567",
                nationality="LB",  # adjusted
                vip_status=True,
                language_preference="ar",
                preferences='{"dietary": "halal", "room_type": "deluxe"}',
            )
        else:
            print("  (Ahmed Hassan already exists, skipping)")

        if not GuestRepository.get_by_email(db, "maria.garcia@email.com"):
            GuestRepository.create(
                db,
                full_name="Maria Garcia",
                email="maria.garcia@email.com",
                phone="+34123456789",
                nationality="ES",  # adjusted
                vip_status=False,
                language_preference="es",
            )
        else:
            print("  (Maria Garcia already exists, skipping)")

        print(f"✓ Guest profiles: {db.query(Guest).count()}")

        print("Creating sample alerts...")

        if db.query(Alert).count() == 0:
            AlertRepository.create(
                db,
                alert_type=AlertType.SECURITY,
                title="Unknown person loitering in lobby",
                description="Unidentified individual has been in lobby for 15 minutes without checking in",
                severity=3,
                location="Main Lobby",
                created_by_id=security.id,
            )

            AlertRepository.create(
                db,
                alert_type=AlertType.ASSISTANCE,
                title="Guest needs assistance",
                description="Guest appears to be waiting at reception desk",
                severity=2,
                location="Reception Area",
                created_by_id=admin.id,
            )

            AlertRepository.create(
                db,
                alert_type=AlertType.VIP_ARRIVAL,
                title="VIP Guest Arrival",
                description=f"VIP guest {guest1.full_name} detected in lobby",
                severity=2,
                location="Main Entrance",
                created_by_id=admin.id,
            )
        else:
            print("  (alerts already exist, skipping)")

        print(f"✓ Alerts: {db.query(Alert).count()}")

        print("\n✅ Database seeding complete!")
        print(f"   - Staff: {db.query(Staff).count()}")
        print(f"   - Guests: {db.query(Guest).count()}")
        print(f"   - Alerts: {db.query(Alert).count()}")
        print("\n📝 Test Credentials:")
        print("   Username: admin | Password: admin123")
        print("   Username: receptionist | Password: reception123")  # adjusted
        print("   Username: security | Password: secure123")


if __name__ == "__main__":
    seed_database()