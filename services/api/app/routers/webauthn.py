"""Passkeys / device biometrics (WebAuthn).

The fingerprint or face check happens on the phone (Android BiometricPrompt, Face ID,
Windows Hello). The server only ever sees a public key and signed challenges: no raw
biometric data is stored here, and nothing biometric goes on chain. PIN + OTP remain
available on every device."""

import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from ..config import get_settings
from ..db import get_session
from ..models import User, WebAuthnCredential, utcnow
from ..security.audit import audit
from ..security.auth import create_step_up_token, get_current_user
from .auth import _tokens, device_label

router = APIRouter(prefix="/auth/webauthn", tags=["auth"])

# Single-process MVP: challenges live in memory for 5 minutes. Use Redis or the DB
# when running more than one API worker.
_CHALLENGES: dict[str, tuple[bytes, float]] = {}
CHALLENGE_TTL = 300


class FinishIn(BaseModel):
    credential: dict[str, Any]
    label: str = Field(default="", max_length=60)


class LoginBeginIn(BaseModel):
    phone: str


class LoginFinishIn(BaseModel):
    phone: str
    credential: dict[str, Any]


def _put(key: str, challenge: bytes) -> None:
    now = time.time()
    for k in [k for k, (_, exp) in _CHALLENGES.items() if exp < now]:
        _CHALLENGES.pop(k, None)
    _CHALLENGES[key] = (challenge, now + CHALLENGE_TTL)


def _take(key: str) -> bytes:
    item = _CHALLENGES.pop(key, None)
    if not item or item[1] < time.time():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "biometric_expired")
    return item[0]


def _origins() -> list[str]:
    return [o.strip() for o in get_settings().webauthn_origins.split(",") if o.strip()]


def _creds(session: Session, user: User) -> list[WebAuthnCredential]:
    return list(session.exec(select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id)))


def _auth_options(session: Session, user: User, key: str) -> Any:
    creds = _creds(session, user)
    if not creds:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_passkey")
    options = generate_authentication_options(
        rp_id=get_settings().webauthn_rp_id,
        allow_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id)) for c in creds],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    _put(key, options.challenge)
    return options_to_json(options)


def _verify_assertion(session: Session, user: User, key: str, credential: dict[str, Any]) -> WebAuthnCredential:
    challenge = _take(key)
    raw_id = credential.get("rawId") or credential.get("id") or ""
    stored = session.exec(
        select(WebAuthnCredential).where(WebAuthnCredential.user_id == user.id, WebAuthnCredential.credential_id == raw_id)
    ).first()
    if not stored:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "biometric_failed")
    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge,
            expected_rp_id=get_settings().webauthn_rp_id,
            expected_origin=_origins(),
            credential_public_key=base64url_to_bytes(stored.public_key),
            credential_current_sign_count=stored.sign_count,
            require_user_verification=True,
        )
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "biometric_failed")
    stored.sign_count = verified.new_sign_count
    stored.last_used_at = utcnow()
    session.add(stored)
    return stored


# ---------------------------------------------------------------- enrol


@router.post("/register/begin")
def register_begin(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    options = generate_registration_options(
        rp_id=get_settings().webauthn_rp_id,
        rp_name="Shambani → Kifedha",
        user_id=str(user.id).encode(),
        user_name=user.phone,
        user_display_name=user.full_name,
        exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id)) for c in _creds(session, user)],
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,  # the phone's own fingerprint / face unlock
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    _put(f"reg:{user.id}", options.challenge)
    return options_to_json(options)


@router.post("/register/finish", status_code=201)
def register_finish(body: FinishIn, request: Request, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    challenge = _take(f"reg:{user.id}")
    try:
        verified = verify_registration_response(
            credential=body.credential,
            expected_challenge=challenge,
            expected_rp_id=get_settings().webauthn_rp_id,
            expected_origin=_origins(),
            require_user_verification=True,
        )
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "biometric_failed")
    cred = WebAuthnCredential(
        user_id=user.id,
        credential_id=bytes_to_base64url(verified.credential_id),
        public_key=bytes_to_base64url(verified.credential_public_key),
        sign_count=verified.sign_count,
        label=body.label or device_label(request.headers.get("user-agent")),
    )
    session.add(cred)
    audit(session, user.id, "PASSKEY_ADDED", "USER", user.id, reason=cred.label)
    session.commit()
    return {"id": cred.id, "label": cred.label}


@router.delete("/credentials/{credential_id}", status_code=204)
def remove_credential(credential_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    cred = session.get(WebAuthnCredential, credential_id)
    if not cred or cred.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    session.delete(cred)
    audit(session, user.id, "PASSKEY_REMOVED", "USER", user.id, reason=cred.label)
    session.commit()


# ---------------------------------------------------------------- sign in


def _user_by_phone(session: Session, phone: str) -> User:
    user = session.exec(select(User).where(User.phone == phone.strip())).first()
    if not user or user.status != "ACTIVE" or (user.locked_until and user.locked_until > utcnow()):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_passkey")
    return user


@router.post("/login/begin")
def login_begin(body: LoginBeginIn, session: Session = Depends(get_session)):
    user = _user_by_phone(session, body.phone)
    return _auth_options(session, user, f"login:{user.id}")


@router.post("/login/finish")
def login_finish(body: LoginFinishIn, request: Request, session: Session = Depends(get_session)):
    user = _user_by_phone(session, body.phone)
    _verify_assertion(session, user, f"login:{user.id}", body.credential)
    audit(session, user.id, "LOGIN", "USER", user.id, reason="biometric")
    return _tokens(session, user, request, "biometric")


# ---------------------------------------------------------------- confirm a sensitive action


@router.post("/stepup/begin")
def stepup_begin(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return _auth_options(session, user, f"stepup:{user.id}")


@router.post("/stepup/finish")
def stepup_finish(body: FinishIn, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    _verify_assertion(session, user, f"stepup:{user.id}", body.credential)
    audit(session, user.id, "STEP_UP", "USER", user.id, reason="biometric")
    session.commit()
    # Send this in place of the PIN (confirm_pin) within 5 minutes.
    return {"confirm_pin": create_step_up_token(user), "expires_in": 300}
