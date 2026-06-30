"""
Security - JWT Token Verification
Validates JWTs issued by our own auth system (python-jose).
No external HTTP calls needed — everything is verified locally.
"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()
security = HTTPBearer()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Verify JWT token locally using JWT_SECRET.
    Returns the decoded payload dict if valid, raises 401 otherwise.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_user_id(user: dict) -> str:
    """Extract user ID from verified token payload."""
    uid = user.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid user payload")
    return uid
