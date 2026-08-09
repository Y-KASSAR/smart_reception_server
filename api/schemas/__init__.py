"""
Pydantic Schemas
================
Request/response models for all API endpoints.
"""
from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ============================================================
# Enums
# ============================================================

class GuestStatusSchema(str, Enum):
    ACTIVE = "active"
    CHECKED_OUT = "checked_out"
    BLACKLISTED = "blacklisted"
    DUE_IN = "due_in"               #added not in generated code to be noted later
    DUE_OUT = "due_out"             #added not in generated code to be noted later      


class StaffRoleSchema(str, Enum):
    ADMIN = "admin"
    RECEPTIONIST = "receptionist"
    SECURITY = "security"
    MANAGER = "manager"
    ROOM_SERVICE = "room_service"   #added not in generated code to be noted later
    HOUSEKEEPING = "housekeeping"   #added not in generated code to be noted later
    MAINTENANCE = "maintenance"     #added not in generated code to be noted later


class AlertTypeSchema(str, Enum):
    SECURITY= "security"
    ASSISTANCE = "assistance"
    ARRIVAL = "arrival"             #added not in generated code to be noted later
    DUE_OUT = "due_out"             #added not in generated code to be noted later
    VIP_ARRIVAL = "vip_arrival"
    WANTED = "wanted"               #added not in generated code to be noted later

class AlertStatusSchema(str, Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class ReservationStatusSchema(str, Enum):
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CANCELLED  = "cancelled"
    DUE_IN ="due_in"
    DUE_OUT = "due_out"
    NO_SHOW = "noshow"


# ============================================================
# Guest Schemas
# ============================================================

class GuestCreate(BaseModel):
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    nationality: Optional[str] = None
    company: Optional[str] = None
    source: Optional[str] = None
    language_preference: str = "en"
    vip_status: bool = False
    preferences: Optional[str] = None
    notes: Optional[str] = None

class GuestUpdate(BaseModel):
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    nationality: Optional[str] = None
    company: Optional[str] = None
    source: Optional[str] = None
    language_preference: Optional[str] = None
    vip_status: Optional[bool] = None
    preferences: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[GuestStatusSchema] = None

class GuestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str]
    phone: Optional[str]
    nationality: Optional[str]
    company: Optional[str] = None
    source: Optional[str] = None
    id_type: Optional[str] = None
    id_number: Optional[str] = None
    language_preference: str
    vip_status: bool
    status: str
    preferences: Optional[str]
    notes: Optional[str]
    is_watched: bool = False
    watch_reason: Optional[str] = None
    is_staff_badge: bool = False
    staff_badge_label: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class WatchlistUpdate(BaseModel):
    """Payload for PUT /api/guests/{id}/watch."""
    is_watched: bool
    watch_reason: Optional[str] = None


class StaffBadgeUpdate(BaseModel):
    """Payload for PUT /api/guests/{id}/staff-badge. Admin-only."""
    is_staff_badge: bool
    staff_badge_label: Optional[str] = None


# ============================================================
# Staff Schemas
# ============================================================

class StaffCreate(BaseModel):
    username: str
    password: str
    full_name: str
    email: str
    role: StaffRoleSchema

class StaffUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[StaffRoleSchema] = None
    is_active: Optional[bool] = None

class StaffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str
    email: str
    role: str
    is_active: bool
    last_login: Optional[datetime]
    created_at: datetime

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    staff: StaffResponse


# ============================================================
# Alert Schemas
# ============================================================

class AlertCreate(BaseModel):
    alert_type: AlertTypeSchema
    title: str
    description: Optional[str] = None
    severity: int = 1
    location: Optional[str] = None
    person_description: Optional[str] = None
    image_path: Optional[str] = None
    guest_id: Optional[int] = None
    created_by_id: Optional[int] = None

class AlertUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[int] = None
    location: Optional[str] = None
    assigned_to_id: Optional[int] = None
    resolution_note: Optional[str] = None

class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_type: str
    status: str
    title: str
    description: Optional[str]
    severity: int
    location: Optional[str]
    person_description: Optional[str]
    image_path: Optional[str]
    guest_id: Optional[int] = None
    created_by_id: Optional[int]
    assigned_to_id: Optional[int]
    acknowledged_by: Optional[str] = None
    created_at: datetime
    acknowledged_at: Optional[datetime]
    resolved_at: Optional[datetime]
    resolution_note: Optional[str] = None


# ============================================================
# Visit Schemas
# ============================================================

class VisitCreate(BaseModel):
    guest_id: int
    check_in: datetime
    check_out: Optional[datetime] = None
    room_number: Optional[str] = None
    purpose: Optional[str] = None
    notes: Optional[str] = None
    total_spend: Optional[float] = 0.0
    services_used: Optional[str] = None
    feedback_score: Optional[int] = None

class VisitUpdate(BaseModel):
    check_out: Optional[datetime] = None
    room_number: Optional[str] = None
    purpose: Optional[str] = None
    notes: Optional[str] = None
    total_spend: Optional[float] = None
    services_used: Optional[str] = None
    feedback_score: Optional[int] = None

class VisitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    guest_id: int
    check_in: datetime
    check_out: Optional[datetime]
    room_number: Optional[str]
    purpose: Optional[str]
    notes: Optional[str]
    total_spend: Optional[float] = 0.0
    services_used: Optional[str] = None
    feedback_score: Optional[int] = None


# ============================================================
# Reservation Schemas
# ============================================================

class ReservationCreate(BaseModel):
    guest_id: int
    reservation_code: str
    check_in_date: datetime
    check_out_date: datetime
    room_type: Optional[str] = None
    room_number: Optional[str] = None
    num_guests: int = 1
    special_requests: Optional[str] = None
    rate_per_night: Optional[float] = None
    total_amount: Optional[float] = None
    status: Optional[ReservationStatusSchema] = ReservationStatusSchema.CONFIRMED

class ReservationUpdate(BaseModel):
    check_in_date: Optional[datetime] = None
    check_out_date: Optional[datetime] = None
    room_type: Optional[str] = None
    room_number: Optional[str] = None
    num_guests: Optional[int] = None
    special_requests: Optional[str] = None
    rate_per_night: Optional[float] = None
    total_amount: Optional[float] = None
    status: Optional[ReservationStatusSchema] = None

class ReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    guest_id: int
    reservation_code: str
    check_in_date: datetime
    check_out_date: datetime
    room_type: Optional[str]
    room_number: Optional[str] = None
    num_guests: int
    special_requests: Optional[str]
    rate_per_night: Optional[float] = None
    total_amount: Optional[float] = None
    status: Optional[str] = "confirmed"
    created_at: datetime
    # Eager-serialized guest so the Reservations dashboard tabs can render
    # name + VIP + watchlist state without a per-row follow-up fetch.
    guest: Optional[GuestResponse] = None


# ============================================================
# Service Schemas
# ============================================================

class ServiceCreate(BaseModel):
    name: str
    category: str
    description: Optional[str] = None
    price: Optional[float] = None
    is_active: bool = True
    popularity_score: float = 0.0

class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    is_active: Optional[bool] = None
    popularity_score: Optional[float] = None

class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    description: Optional[str]
    price: Optional[float]
    is_active: bool
    popularity_score: float
    created_at: datetime


# ============================================================
# Service Posting Schemas (a service charge posted to a guest's bill —
# the upselling engine's usage-history data source; see ServicePosting model)
# ============================================================

class ServicePostingCreate(BaseModel):
    service_id: int
    quantity: int = 1
    unit_price: Optional[float] = None    # defaults to the service catalogue price
    amount: Optional[float] = None        # defaults to unit_price * quantity
    reservation_id: Optional[int] = None  # defaults to the guest's currently checked-in stay
    source_system: str = "manual"
    notes: Optional[str] = None

class ServicePostingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    guest_id: int
    reservation_id: Optional[int] = None
    service_id: int
    quantity: int
    unit_price: Optional[float] = None
    amount: Optional[float] = None
    posted_by_id: Optional[int] = None
    source_system: str
    posted_at: datetime
    notes: Optional[str] = None
    service: Optional[ServiceResponse] = None


# ============================================================
# Recommendation Schemas
# ============================================================

class RecommendationStatusSchema(str, Enum):
    PENDING = "pending"
    PRESENTED = "presented"
    ACCEPTED = "accepted"
    DECLINED = "declined"

class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    guest_id: int
    service_id: int
    staff_id: Optional[int] = None
    score: float
    relevance_score: Optional[float] = None
    reasoning: Optional[str]
    status: str
    presented_at: Optional[datetime]
    responded_at: Optional[datetime]
    created_at: datetime
    # Eager-serialized service so the dashboard can render a readable label
    # ("Rooftop Dinner Reservation · $85") instead of "Service #7".
    service: Optional[ServiceResponse] = None

    