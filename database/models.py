from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, ForeignKey, LargeBinary, Enum, DateTime
from sqlalchemy.orm import relationship, declarative_base
import enum


Base =declarative_base()

_utcnow = lambda: datetime.now(timezone.utc)


class Title(enum.Enum):              # added class 
    MR = "Mr."
    MRS  = "Mrs."
    MS = "Ms."
    MISS= "Miss."
    DR = "Dr."
    ENGR = "Engr."

class GuestStatus(enum.Enum):
    ACTIVE = "active"
    DUE_IN = "due_in"               #added not in generated code to be noted later
    DUE_OUT = "due_out"             #added not in generated code to be noted later      
    CHECKED_OUT = "checked_out"
    BLACKLISTED = "blacklisted"

class StaffRole(enum.Enum):
    ADMIN = "admin"
    RECEPTIONIST = "receptionist"
    SECURITY = "security"
    MANAGER = "manager"
    ROOM_SERVICE = "room_service"   #added not in generated code to be noted later
    HOUSEKEEPING = "housekeeping"   #added not in generated code to be noted later
    MAINTENANCE = "maintenance"     #added not in generated code to be noted later

class AlertType(enum.Enum):
    SECURITY= "security"
    ASSISTANCE = "assistance"
    ARRIVAL = "arrival"             #added not in generated code to be noted later
    DUE_OUT = "due_out"             #added not in generated code to be noted later
    VIP_ARRIVAL = "vip_arrival"
    WANTED = "wanted"               #added not in generated code to be noted later

class AlertStatus(enum.Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"

class RecommendationStatus(enum.Enum):
    PENDING = "pending"
    PRESENTED = "presented"
    ACCEPTED = "accepted"
    DECLINED = "declined"

class ReservationStatus(enum.Enum):
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CANCELLED  = "cancelled"



class Guest(Base):
    __tablename__ = "guests"

    id = Column(Integer, primary_key=True , autoincrement=True) 
    title = Column(Enum(Title), nullable= True)                  #add attribute
    full_name = Column(String(200), nullable=True)
    first_name = Column(String(100), nullable=True)            
    last_name = Column(String(100), nullable=True)             
    email = Column(String(200), unique=True, nullable=True)
    phone = Column(String(15), nullable=True)                   # we adjusted the lenght of the string from 50 to 15 
    nationality = Column(String(2), nullable=True)              # we adjusted the lenght of the string to 2 LB SY DE....
    language_preference = Column(String(50), default="en")
    vip_status = Column(Boolean, nullable= True)
    status = Column(Enum(GuestStatus), nullable=False, default=GuestStatus.ACTIVE)
    preferences = Column(Text, nullable=True)
    notes = Column(Text,  nullable= True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime,  default=_utcnow, onupdate=_utcnow)

    face_embeddings = relationship("FaceEmbedding", back_populates = "guest",cascade="all, delete-orphan")
    visits = relationship("Visit", back_populates="guest", cascade="all, delete-orphan")
    reservations =relationship("Reservation", back_populates="guest",cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="guest", cascade="all, delete-orphan")

    def __init__ (self, *args, **kwargs):
        if "full_name" in kwargs and "first_name" not in kwargs and "last_name" not in kwargs:
            parts = (kwargs["full_name"] or "").strip().split(" ", 1)
            kwargs["first_name"] = parts[0] if parts else None
            kwargs["last_name"] = parts[1] if len(parts) > 1 else None
        elif ("first_name" in kwargs or "last_name" in kwargs) and "full_name" not in kwargs:
            kwargs["full_name"] = (
                f"{kwargs.get('first_name', '') or ''} {kwargs.get('last_name', '') or ''}".strip()
            )
        super().__init__(*args, **kwargs)
    
    def __repr__(self):
        return f"<Guest(id={self.id}, name= {self.title} {self.last_name} ; {self.first_name})>"  # format adjusted
    
class Staff(Base):
    __tablename__ = "staff"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, nullable= False)
    role = Column(Enum(StaffRole), nullable=False)
    is_active = Column(Boolean, default= True, nullable=False)
    last_login = Column(DateTime, nullable=True)
    created_at = Column( DateTime, default=_utcnow)

    alerts_created = relationship("Alert", foreign_keys="Alert.created_by_id", back_populates="created_by")
    alerts_assigned = relationship("Alert", foreign_keys="Alert.assigned_to_id", back_populates="assigned_to")

    def __repr__(self):
        return f"<Staff(id={self.id}, username={self.username}, role= {self.role.value})>"

class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id = Column(Integer, primary_key=True, autoincrement= True)
    guest_id = Column(Integer, ForeignKey("guests.id", ondelete="CASCADE"), nullable=False)
    embedding_vector = Column(LargeBinary,nullable=False)
    source = Column(String(50), default="enrollment")
    quality_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    guest = relationship("Guest",back_populates="face_embeddings")

    def __repr__(self):
        return f"<FaceEmbedding(id={self.id}, guest_id= {self.guest_id}, source= {self.source})>"
    

class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guest_id = Column(Integer, ForeignKey("guests.id", ondelete="CASCADE"), nullable=False)
    check_in = Column(DateTime, nullable=False)
    check_out = Column(DateTime, nullable=True)
    room_number = Column(String(20), nullable=True)
    notes = Column(Text, nullable=True)
    total_spend = Column(Float, default=0.0)
    services_used = Column(Text, nullable=True) 
    feedback_score = Column(Integer, nullable=True)  

    guest = relationship("Guest", back_populates="visits")

    def __repr__(self):
        return f"<​Visit(id={self.id}, guest_id={self.guest_id}, check_in={self.check_in})>"
    
class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guest_id = Column(Integer, ForeignKey("guests.id", ondelete="CASCADE"), nullable=False)
    reservation_code = Column(String(50), unique=True, nullable=False)
    check_in_date = Column(DateTime, nullable=False)
    check_out_date = Column(DateTime, nullable=False)
    room_type = Column(String(100), nullable=True)
    room_number = Column(String(20), nullable=True)
    num_guests = Column(Integer, default=1)
    special_requests = Column(Text, nullable=True)
    rate_per_night = Column(Float, nullable=True)
    total_amount = Column(Float, nullable=True)
    status = Column(Enum(ReservationStatus), default=ReservationStatus.CONFIRMED)
    created_at = Column(DateTime, default=_utcnow)

    # Relationships
    guest = relationship("Guest", back_populates="reservations")

    def __repr__(self):
        return f"<​Reservation(id={self.id}, code='{self.reservation_code}', guest_id={self.guest_id})>"
    
class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False)  # spa, dining, activities, room_service
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    popularity_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=_utcnow)

    # Relationships
    recommendations = relationship("Recommendation", back_populates="service", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<​Service(id={self.id}, name='{self.name}', category='{self.category}')>"

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_type = Column(Enum(AlertType), nullable=False)
    status = Column(Enum(AlertStatus), default=AlertStatus.PENDING)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(Integer, default=1)
    location = Column(String(100), nullable=True)
    person_description = Column(Text, nullable=True)
    image_path = Column(String(500), nullable=True)
    guest_id = Column(Integer, ForeignKey("guests.id", ondelete="SET NULL"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    assigned_to_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    acknowledged_by = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=_utcnow)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)

    # Relationships
    created_by = relationship("Staff", foreign_keys=[created_by_id], back_populates="alerts_created")
    assigned_to = relationship("Staff", foreign_keys=[assigned_to_id], back_populates="alerts_assigned")

    def __repr__(self):
        return f"<​Alert(id={self.id}, type={self.alert_type.value}, status={self.status.value})>"

class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guest_id = Column(Integer, ForeignKey("guests.id", ondelete="CASCADE"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id", ondelete="CASCADE"), nullable=False)
    staff_id = Column(Integer, ForeignKey("staff.id", ondelete="SET NULL"), nullable=True)
    score = Column(Float, nullable=False)  # 0.0 - 1.0
    reasoning = Column(Text, nullable=True)
    status = Column(Enum(RecommendationStatus), default=RecommendationStatus.PENDING)
    presented_at = Column(DateTime, nullable=True)
    responded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    @property
    def relevance_score(self):
        return self.score

    @relevance_score.setter
    def relevance_score(self, value):
        self.score = value

    guest = relationship("Guest", back_populates="recommendations")
    service = relationship("Service", back_populates="recommendations")

    def __repr__(self):
        return f"<​Recommendation(id={self.id}, guest_id={self.guest_id}, service_id={self.service_id}, score={self.score:.2f})>"


class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(100), nullable=False)  
    severity = Column(String(20), default="info") 
    message = Column(Text, nullable=False)
    extra_data = Column(Text, nullable=True)  
    created_at = Column(DateTime, default=_utcnow)

    def __repr__(self):
        return f"<​SystemLog(id={self.id}, type='{self.event_type}', severity='{self.severity}')>"