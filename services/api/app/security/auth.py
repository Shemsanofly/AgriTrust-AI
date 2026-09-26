import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from ..config import get_settings
from ..db import get_session
from ..models import Buyer, Farmer, RefreshToken, Role, User, Warehouse, utcnow

_hasher = PasswordHasher()  # Argon2id
_bearer = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"


def hash_secret(value: str) -> str:
    return _hasher.hash(value)


def verify_secret(hashed: str, value: str) -> bool:
    try:
        return _hasher.verify(hashed, value)
    except (VerifyMismatchError, Exception):
        return False


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def create_access_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "typ": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def issue_refresh_token(session: Session, user: User) -> str:
    token = secrets.token_urlsafe(48)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_sha256(token),
            expires_at=utcnow() + timedelta(days=get_settings().refresh_token_days),
        )
    )
    return token


def rotate_refresh_token(session: Session, token: str) -> User:
    record = session.exec(select(RefreshToken).where(RefreshToken.token_hash == _sha256(token))).first()
    if not record or record.revoked_at or record.expires_at < utcnow():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_refresh_token")
    record.revoked_at = utcnow()
    session.add(record)
    user = session.get(User, record.user_id)
    if not user or user.status != "ACTIVE":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "inactive_user")
    return user


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> User:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not_authenticated")
    try:
        payload = jwt.decode(creds.credentials, get_settings().jwt_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_token")
    if payload.get("typ") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_token")
    user = session.get(User, int(payload["sub"]))
    if not user or user.status != "ACTIVE":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "inactive_user")
    return user


def require_roles(*roles: Role):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden_role")
        return user

    return dependency


def require_pin(user: User, pin: str | None) -> None:
    """Step-up confirmation for sensitive actions (consent grants, large orders)."""
    if not pin or not verify_secret(user.pin_hash, pin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "step_up_required")


def farmer_for(session: Session, user: User) -> Farmer:
    farmer = session.exec(select(Farmer).where(Farmer.user_id == user.id)).first()
    if not farmer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "farmer_profile_missing")
    return farmer


def buyer_for(session: Session, user: User) -> Buyer:
    buyer = session.exec(select(Buyer).where(Buyer.user_id == user.id)).first()
    if not buyer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "buyer_profile_missing")
    return buyer


def warehouses_for(session: Session, user: User) -> list[Warehouse]:
    return list(session.exec(select(Warehouse).where(Warehouse.operator_user_id == user.id)))
