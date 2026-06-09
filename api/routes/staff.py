"""
Staff Routes
"""
import time
from collections import defaultdict, deque
from typing import Deque, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import bcrypt
from database.connection import get_db
from database.repositories import StaffRepository
from database.models import StaffRole
from api.schemas import StaffCreate, StaffUpdate, StaffResponse, LoginRequest, LoginResponse
from config.logging_config import get_logger
from config.settings import settings
from utils.security_utils import get_current_staff, require_role

logger = get_logger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Login rate limiter (in-memory, per-IP sliding window)
# ---------------------------------------------------------------------------
_login_attempts: Dict[str, Deque[float]] = defaultdict(deque)
_login_lockouts: Dict[str, float] = {}


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_login_rate_limit(ip: str) -> None:
    now = time.time()
    lockout_until = _login_lockouts.get(ip, 0)
    if lockout_until > now:
        retry_after = int(lockout_until - now)
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed login attempts. Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )
    window = settings.security.lockout_duration
    attempts = _login_attempts[ip]
    while attempts and attempts[0] < now - window:
        attempts.popleft()
    if len(attempts) >= settings.security.max_login_attempts:
        _login_lockouts[ip] = now + settings.security.lockout_duration
        logger.warning(f"Rate-limited login attempts from {ip}; locked for {settings.security.lockout_duration}s")
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts. Account temporarily locked.",
            headers={"Retry-After": str(settings.security.lockout_duration)},
        )


def _record_failed_login(ip: str) -> None:
    _login_attempts[ip].append(time.time())


def _clear_login_attempts(ip: str) -> None:
    _login_attempts.pop(ip, None)
    _login_lockouts.pop(ip, None)


@router.get("/", response_model=List[StaffResponse])
def list_staff(db: Session = Depends(get_db), _=Depends(require_role("admin", "manager"))):
    return StaffRepository.get_all(db)


@router.get("/{staff_id}", response_model=StaffResponse)
def get_staff(staff_id: int, db: Session = Depends(get_db), _=Depends(get_current_staff)):
    staff = StaffRepository.get_by_id(db, staff_id)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return staff


@router.post("/", response_model=StaffResponse, status_code=201)
def create_staff(payload: StaffCreate, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    existing = StaffRepository.get_by_username(db, payload.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken")
    password_hash = bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode()
    return StaffRepository.create(
        db,
        username=payload.username,
        password_hash=password_hash,
        full_name=payload.full_name,
        email=payload.email,
        role=StaffRole(payload.role),
    )


@router.put("/{staff_id}", response_model=StaffResponse)
def update_staff(staff_id: int, payload: StaffUpdate, db: Session = Depends(get_db), _=Depends(require_role("admin", "manager"))):
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "role" in updates:
        updates["role"] = StaffRole(updates["role"])
    staff = StaffRepository.update(db, staff_id, **updates)
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return staff


@router.delete("/{staff_id}", status_code=204)
def delete_staff(staff_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    deleted = StaffRepository.delete(db, staff_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Staff member not found")


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    _check_login_rate_limit(ip)

    staff = StaffRepository.get_by_username(db, payload.username)
    if not staff or not bcrypt.checkpw(payload.password.encode(), staff.password_hash.encode()):
        _record_failed_login(ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not staff.is_active:
        _record_failed_login(ip)
        raise HTTPException(status_code=403, detail="Account is inactive")

    _clear_login_attempts(ip)
    StaffRepository.update_last_login(db, staff.id)
    token = _generate_token(staff.id, staff.username, staff.role.value)
    return LoginResponse(access_token=token, staff=staff)


def _generate_token(staff_id: int, username: str, role: str) -> str:
    from jose import jwt
    from datetime import datetime, timedelta, timezone
    payload = {
        "sub": str(staff_id),
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(seconds=settings.security.session_timeout),
    }
    return jwt.encode(payload, settings.secrets.jwt_secret_key, algorithm="HS256")
