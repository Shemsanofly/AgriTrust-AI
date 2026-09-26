import secrets
from datetime import timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..config import get_settings
from ..db import get_session
from ..i18n import bi
from ..integrations.sms import send_sms
from ..models import Buyer, Farmer, Language, RefreshToken, Role, User, WebAuthnCredential, utcnow
from ..notify import notify
from ..security.audit import audit
from ..security.auth import (
    create_access_token,
    find_refresh_token,
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


def device_label(user_agent: str | None) -> str:
    ua = (user_agent or "").lower()
    os_name = next((n for k, n in (("android", "Android"), ("iphone", "iPhone"), ("ipad", "iPad"), ("windows", "Windows"), ("mac os", "Mac"), ("linux", "Linux")) if k in ua), "")
    browser = next((n for k, n in (("edg/", "Edge"), ("chrome", "Chrome"), ("firefox", "Firefox"), ("safari", "Safari")) if k in ua), "")
    return " · ".join(x for x in (browser, os_name) if x) or "Unknown device"


def _tokens(session: Session, user: User, request: Request | None = None, method: str = "pin", started_at=None) -> dict:
    device_id = request.headers.get("x-device-id") if request else None
    user_agent = request.headers.get("user-agent") if request else None
    new_device = False
    if request and method != "refresh":
        known = session.exec(select(RefreshToken).where(RefreshToken.user_id == user.id)).all()
        if known and device_id and not any(t.device_id == device_id for t in known):
            new_device = True
            notify(
                session,
                user,
                "SECURITY",
                bi("alert.new_device", device=device_label(user_agent)),
                severity="WARNING",
                sms=True,
            )
            audit(session, user.id, "NEW_DEVICE_LOGIN", "USER", user.id, reason=device_label(user_agent))
    refresh = issue_refresh_token(session, user, device_id, user_agent, "pin" if method == "refresh" else method, started_at)
    session.commit()
    return {
        "access_token": create_access_token(user),
        "refresh_token": refresh,
        "token_type": "bearer",
        "new_device": new_device,
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
def verify_otp(body: OtpIn, request: Request, session: Session = Depends(get_session)):
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
    return _tokens(session, user, request, "otp")


@router.post("/login")
def login(body: LoginIn, request: Request, session: Session = Depends(get_session)):
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
        left = settings.max_failed_logins - user.failed_logins if user.failed_logins else 0
        if not left:
            return JSONResponse({"detail": "account_locked"}, status_code=status.HTTP_423_LOCKED)
        # Tell the person how many tries remain before the temporary lock.
        return JSONResponse({"detail": "invalid_credentials", "attempts_left": left}, status_code=status.HTTP_401_UNAUTHORIZED)
    if user.status == "PENDING_OTP":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "otp_required")
    if user.status != "ACTIVE":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "inactive_user")
    user.failed_logins = 0
    session.add(user)
    audit(session, user.id, "LOGIN", "USER", user.id)
    return _tokens(session, user, request, "pin")


@router.post("/refresh")
def refresh(body: RefreshIn, request: Request, session: Session = Depends(get_session)):
    old = find_refresh_token(session, body.refresh_token)
    user = rotate_refresh_token(session, body.refresh_token)
    data = _tokens(session, user, None, "refresh", old.session_started_at if old else None)
    # Keep the session's device and sign-in method across refreshes.
    new = find_refresh_token(session, data["refresh_token"])
    if old and new:
        new.device_id, new.user_agent, new.login_method = old.device_id, old.user_agent, old.login_method
        session.add(new)
        session.commit()
    return data


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


# ---------------------------------------------------------------- sessions & devices


@me_router.get("/me/sessions")
def my_sessions(request: Request, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """Active sign-ins, one row per device (refresh-token chains are merged by device)."""
    now = utcnow()
    rows = session.exec(
        select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)).order_by(RefreshToken.created_at.desc())  # type: ignore[union-attr]
    ).all()
    current_device = request.headers.get("x-device-id")
    seen: set[str] = set()
    out = []
    for r in rows:
        if r.expires_at < now:
            continue
        key = r.device_id or f"token-{r.id}"
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "id": r.id,
                "device": device_label(r.user_agent),
                "login_method": r.login_method,
                "started_at": r.session_started_at.isoformat(),
                "last_active_at": r.created_at.isoformat(),
                "current": bool(current_device and r.device_id == current_device),
            }
        )
    return out


@me_router.delete("/me/sessions/{session_id}", status_code=204)
def revoke_session(session_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    target = session.get(RefreshToken, session_id)
    if not target or target.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    for r in session.exec(select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))):  # type: ignore[union-attr]
        if r.id == target.id or (target.device_id and r.device_id == target.device_id):
            r.revoked_at = utcnow()
            session.add(r)
    audit(session, user.id, "REVOKE_SESSION", "USER", user.id, reason=device_label(target.user_agent))
    session.commit()


@me_router.post("/me/sessions/revoke-others", status_code=204)
def revoke_other_sessions(request: Request, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    current_device = request.headers.get("x-device-id")
    for r in session.exec(select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))):  # type: ignore[union-attr]
        if not current_device or r.device_id != current_device:
            r.revoked_at = utcnow()
            session.add(r)
    audit(session, user.id, "REVOKE_OTHER_SESSIONS", "USER", user.id)
    session.commit()


@me_router.get("/me/security")
def my_security(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    creds = session.exec(select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)).all()
    return {
        "passkeys": [
            {"id": c.id, "label": c.label, "created_at": c.created_at.isoformat(), "last_used_at": c.last_used_at.isoformat() if c.last_used_at else None}
            for c in creds
        ],
        "pin_set": True,
        "phone_verified": user.status == "ACTIVE",
    }
