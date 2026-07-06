"""
JWT authentication for Maayan operator dashboard access.

Credentials are configured via environment variables (AUTH_USERNAME,
AUTH_PASSWORD). IoT telemetry ingest uses a separate API key and is
not gated by this module.
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from loguru import logger

# ── Configuration ─────────────────────────────────────────────────────────────

AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "")
JWT_SECRET = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY", "change-me-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))  # 8 hours

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


# ── Models ────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str


class UserInfo(BaseModel):
    username: str
    authenticated: bool


# ── Token helpers ─────────────────────────────────────────────────────────────

def create_access_token(username: str) -> tuple[str, int]:
    """Return (jwt, expires_in_seconds)."""
    expires_in = JWT_EXPIRE_MINUTES * 60
    expire = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    payload = {"sub": username, "exp": expire}
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires_in


def verify_token(token: str) -> Optional[str]:
    """Return username if token is valid, else None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        return username if isinstance(username, str) else None
    except JWTError:
        return None


def _credentials_valid(username: str, password: str) -> bool:
    if not AUTH_PASSWORD:
        logger.warning("AUTH_PASSWORD is not set — login disabled")
        return False
    user_ok = secrets.compare_digest(username, AUTH_USERNAME)
    pass_ok = secrets.compare_digest(password, AUTH_PASSWORD)
    return user_ok and pass_ok


# ── FastAPI dependency ──────────────────────────────────────────────────────

async def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> UserInfo:
    """Protect dashboard API routes. Skipped when AUTH_ENABLED=false."""
    if not AUTH_ENABLED:
        return UserInfo(username="dev", authenticated=False)

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = verify_token(credentials.credentials)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserInfo(username=username, authenticated=True)


def verify_ws_token(token: Optional[str]) -> bool:
    """Validate a WebSocket connection token."""
    if not AUTH_ENABLED:
        return True
    if not token:
        return False
    return verify_token(token) is not None


# ── Routes ────────────────────────────────────────────────────────────────────

@auth_router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Exchange username/password for a JWT access token."""
    if not AUTH_ENABLED:
        token, expires_in = create_access_token(request.username or "dev")
        return LoginResponse(
            access_token=token,
            expires_in=expires_in,
            username=request.username or "dev",
        )

    if not _credentials_valid(request.username, request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token, expires_in = create_access_token(request.username)
    logger.info(f"User '{request.username}' logged in")
    return LoginResponse(
        access_token=token,
        expires_in=expires_in,
        username=request.username,
    )


@auth_router.get("/me", response_model=UserInfo)
async def me(user: UserInfo = Depends(require_auth)):
    """Return the currently authenticated user."""
    return user
