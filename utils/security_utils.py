"""
Security Utilities
==================
JWT token decoding and role-based access control helpers for FastAPI.
"""
from typing import Optional, Dict, Any
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and validate a JWT token.

    Args:
        token: Raw JWT string

    Returns:
        Decoded payload dict or None if invalid/expired
    """
    try:
        from jose import jwt, JWTError
        payload = jwt.decode(
            token,
            settings.secrets.jwt_secret_key,
            algorithms=["HS256"],
        )
        return payload
    except Exception as e:
        logger.debug(f"JWT decode failed: {e}")
        return None


def get_current_staff(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer_scheme),
) -> Dict[str, Any]:
    """
    FastAPI dependency: extract and validate the current staff member from JWT.

    Usage:
        @router.get("/protected")
        def protected(staff = Depends(get_current_staff)):
            return {"user": staff["username"]}
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_jwt_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return payload


def require_role(*allowed_roles: str):
    """
    FastAPI dependency factory: restrict endpoint to specific staff roles.

    Usage:
        @router.delete("/{id}")
        def delete(staff = Depends(require_role("admin", "manager"))):
            ...
    """
    def _check(staff: Dict[str, Any] = Depends(get_current_staff)) -> Dict[str, Any]:
        if staff.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required roles: {list(allowed_roles)}",
            )
        return staff
    return _check