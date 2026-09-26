import secrets
from datetime import timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..config import get_settings
from ..db import get_session
from ..i18n import bi
from ..integrations.sms import send_sms
from ..models import Buyer, Farmer, Language, Role, User, utcnow
from ..notify import notify
from ..security.audit import audit
from ..security.auth import (
    create_access_token,
    get_current_user,
    hash_secret,
    issue_refresh_token,
    rotate_refresh_token,
    verify_secret,
    warehouses_for,
)

router = APIRouter(prefix="/auth", tags=["auth"])
me_router = APIRouter(tags=["users"])

PHONE_PATTERN = r"^\+?[0-9]{9,15}$"
PIN_PATTERN = r"^[0-9]{4,6}$"


class RegisterIn(BaseModel):
    phone: str = Field(pattern=PHONE_PATTERN)
    pin: str = Field(pattern=PIN_PATTERN)
    full_name: str = Field(min_length=2, max_length=80)
    role: Literal["FARMER", "BUYER"]
    language: Language = Language.SW
    region: Optional[str] = None
    district: Optional[str] = None
    cooperative: Optional[str] = None
    business_name: Optional[str] = None
    country: str = "TZ"


class OtpIn(BaseModel):
    phone: str
    code: str


class LoginIn(BaseModel):
    phone: str
    pin: str


class RefreshIn(BaseModel):
    refresh_token: str


class MeUpdate(BaseModel):
    language: Optional[Language] = None
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=80)


def user_json(session: Session, user: User) -> dict:
    data = {
        "id": user.id,
        "phone": user.phone,
        "full_name": user.full_name,
        "role": user.role.value,
        "language": user.language.value,
    }
    if user.role == Role.FARMER:
        farmer = session.exec(select(Farmer).where(Farmer.user_id == user.id)).first()
        if farmer:
            data["farmer"] = farmer.model_dump()
    elif user.role == Role.BUYER:
        buyer = session.exec(select(Buyer).where(Buyer.user_id == user.id)).first()
        if buyer:
            data["buyer"] = buyer.model_dump()
    elif user.role == Role.WAREHOUSE_OPERATOR:
        data["warehouses"] = [w.model_dump() for w in warehouses_for(session, user)]
    return data


def _tokens(session: Session, user: User) -> dict:
    refresh = issue_refresh_token(session, user)
    session.commit()
    return {
        "access_token": create_access_token(user),
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": user_json(session, user),
    }


def _send_otp(session: Session, user: User) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    user.otp_code_hash = hash_secret(code)
    user.otp_expires_at = utcnow() + timedelta(minutes=10)
    session.add(user)
    send_sms(session, user, bi("sms.otp", code=code))
    return code


@router.post("/register", status_code=201)
def register(body: RegisterIn, session: Session = Depends(get_session)):
    if session.exec(select(User).where(User.phone == body.phone)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "phone_taken")
    user = User(
        phone=body.phone,
        full_name=body.full_name,
        role=Role(body.role),
        pin_hash=hash_secret(body.pin),
        language=body.language,
        status="PENDING_OTP",
    )
    session.add(user)
    session.flush()
    if user.role == Role.FARMER:
        if not body.region:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "region_required")
        session.add(
            Farmer(
                public_id=f"FMR-{user.id:04d}",
                user_id=user.id,
                display_name=body.full_name,
                region=body.region,
                district=body.district or "",
                cooperative=body.cooperative,
            )
        )
    else:
        session.add(Buyer(user_id=user.id, business_name=body.business_name or body.full_name, country=body.country))
    code = _send_otp(session, user)
    audit(session, user.id, "REGISTER", "USER", user.id)
    session.commit()
    result = {"user_id": user.id, "status": user.status, "otp_sent": True}
    if get_settings().dev_mode:
        result["dev_otp"] = code  # sandbox only: lets the demo run without a real SMS
    return result


@router.post("/otp/verify")
def verify_otp(body: OtpIn, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.phone == body.phone)).first()
    if (
        not user
        or not user.otp_code_hash
        or not user.otp_expires_at
        or user.otp_expires_at < utcnow()
        or not verify_secret(user.otp_code_hash, body.code)
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_otp")
    user.otp_code_hash = None
    user.otp_expires_at = None
    user.status = "ACTIVE"
    session.add(user)
    audit(session, user.id, "OTP_VERIFIED", "USER", user.id)
    return _tokens(session, user)


@router.post("/login")
def login(body: LoginIn, session: Session = Depends(get_session)):
    settings = get_settings()
    user = session.exec(select(User).where(User.phone == body.phone)).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
    if user.locked_until and user.locked_until > utcnow():
        raise HTTPException(status.HTTP_423_LOCKED, "account_locked")
    if not verify_secret(user.pin_hash, body.pin):
        user.failed_logins += 1
        if user.failed_logins >= settings.max_failed_logins:
            user.locked_until = utcnow() + timedelta(minutes=settings.lockout_minutes)
            user.failed_logins = 0
            notify(
                session,
                user,
                "SECURITY",
                bi("alert.locked", minutes=settings.lockout_minutes),
                severity="WARNING",
                sms=True,
            )
            audit(session, user.id, "ACCOUNT_LOCKED", "USER", user.id, reason="failed_pin_attempts")
        session.add(user)
        session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")
    if user.status == "PENDING_OTP":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "otp_required")
    if user.status != "ACTIVE":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "inactive_user")
    user.failed_logins = 0
    session.add(user)
    audit(session, user.id, "LOGIN", "USER", user.id)
    return _tokens(session, user)


@router.post("/refresh")
def refresh(body: RefreshIn, session: Session = Depends(get_session)):
    user = rotate_refresh_token(session, body.refresh_token)
    return _tokens(session, user)


@router.post("/logout", status_code=204)
def logout(body: RefreshIn, session: Session = Depends(get_session)):
    try:
        rotate_refresh_token(session, body.refresh_token)
        session.commit()
    except HTTPException:
        pass


@me_router.get("/me")
def get_me(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return user_json(session, user)


@me_router.patch("/me")
def update_me(body: MeUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """Save the user's preferred language (sw/en). It is used for the UI and for SMS."""
    if body.language is not None:
        user.language = body.language
    if body.full_name is not None:
        user.full_name = body.full_name
    session.add(user)
    session.commit()
    session.refresh(user)
    return user_json(session, user)
