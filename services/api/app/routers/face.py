"""Face sign-in with FACEIO (https://faceio.net).

The browser runs FACEIO's widget (fio.js): it enrolls the face or recognises it and returns
a Facial ID. The server never sees an image. It checks the Facial ID with FACEIO's REST API
(`checkfacialid`, needs FACEIO_API_KEY) and stores only an HMAC of it. PIN + OTP always
remain available, and the farmer can remove face sign-in at any time."""

import hashlib
import hmac
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..config import get_settings
from ..db import get_session
from ..models import FaceLogin, User, utcnow
from ..security.audit import audit
from ..security.auth import get_current_user
from .auth import _tokens

log = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/face", tags=["auth"])
FACEIO_API = "https://api.faceio.net"


class FacialIdIn(BaseModel):
    facial_id: str = Field(min_length=8, max_length=200)


def _hash(facial_id: str) -> str:
    return hmac.new(get_settings().jwt_secret.encode(), facial_id.encode(), hashlib.sha256).hexdigest()


def _require_enabled() -> None:
    if not get_settings().faceio_public_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "face_disabled")


def _check_with_faceio(facial_id: str) -> None:
    """Ask FACEIO whether this Facial ID is real and still registered to our application."""
    settings = get_settings()
    if not settings.faceio_api_key:
        if settings.dev_mode:
            log.warning("FACEIO_API_KEY not set: Facial ID accepted without server check (dev mode only)")
            return
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "face_unavailable")
    try:
        resp = httpx.get(f"{FACEIO_API}/checkfacialid", params={"key": settings.faceio_api_key, "fid": facial_id}, timeout=8)
        data = resp.json()
    except (httpx.HTTPError, ValueError) as err:
        log.warning("FACEIO checkfacialid failed: %s", err)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "face_unavailable")
    if data.get("status") != 200 or data.get("valid") is not True:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "face_not_recognised")


@router.get("/config")
def face_config():
    settings = get_settings()
    return {"enabled": bool(settings.faceio_public_id), "public_id": settings.faceio_public_id or None}


@router.post("/enroll", status_code=201)
def enroll(body: FacialIdIn, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """Link the Facial ID FACEIO returned after enrollment to the signed-in account."""
    _require_enabled()
    _check_with_faceio(body.facial_id)
    digest = _hash(body.facial_id)
    other = session.exec(select(FaceLogin).where(FaceLogin.facial_id_hash == digest)).first()
    if other and other.user_id != user.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "face_in_use")
    row = session.exec(select(FaceLogin).where(FaceLogin.user_id == user.id)).first() or FaceLogin(user_id=user.id, facial_id_hash=digest)
    row.facial_id_hash = digest
    row.created_at = utcnow()
    session.add(row)
    audit(session, user.id, "FACE_ENROLLED", "USER", user.id)
    session.commit()
    return {"enrolled": True}


@router.post("/login")
def face_login(body: FacialIdIn, request: Request, session: Session = Depends(get_session)):
    """Sign in with the Facial ID FACEIO returned after recognising the face."""
    _require_enabled()
    _check_with_faceio(body.facial_id)
    row = session.exec(select(FaceLogin).where(FaceLogin.facial_id_hash == _hash(body.facial_id))).first()
    user = session.get(User, row.user_id) if row else None
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "face_not_recognised")
    if user.locked_until and user.locked_until > utcnow():
        raise HTTPException(status.HTTP_423_LOCKED, "account_locked")
    if user.status != "ACTIVE":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "inactive_user")
    row.last_used_at = utcnow()
    session.add(row)
    audit(session, user.id, "LOGIN", "USER", user.id, reason="face")
    return _tokens(session, user, request, "face")


@router.delete("", status_code=204)
def remove(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    row = session.exec(select(FaceLogin).where(FaceLogin.user_id == user.id)).first()
    if row:
        session.delete(row)
        audit(session, user.id, "FACE_REMOVED", "USER", user.id)
        session.commit()
