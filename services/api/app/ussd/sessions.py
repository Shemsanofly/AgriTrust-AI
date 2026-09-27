from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from ..config import get_settings
from ..models import UssdSession, utcnow
from . import states


def get_or_create_session(
    session: Session,
    *,
    session_id: str,
    phone_number: str,
    provider: str,
    user_id: int | None = None,
) -> UssdSession:
    ttl = get_settings().ussd_session_ttl_minutes
    row = session.exec(select(UssdSession).where(UssdSession.session_id == session_id)).first()
    now = utcnow()
    if row:
        exp = row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=now.tzinfo)
        if exp < now:
            row.state = states.MAIN_MENU if user_id else states.UNREGISTERED
            row.current_menu = row.state
            row.payload = {}
        row.phone_number = phone_number
        row.provider = provider
        if user_id is not None:
            row.user_id = user_id
        row.updated_at = now
        row.expires_at = now + timedelta(minutes=ttl)
        session.add(row)
        return row

    initial = states.MAIN_MENU if user_id else states.UNREGISTERED
    row = UssdSession(
        session_id=session_id,
        phone_number=phone_number,
        current_menu=initial,
        state=initial,
        payload={},
        provider=provider,
        user_id=user_id,
        expires_at=now + timedelta(minutes=ttl),
    )
    session.add(row)
    session.flush()
    return row


def set_state(ussd: UssdSession, state: str, **payload_updates) -> None:
    ussd.state = state
    ussd.current_menu = state
    ussd.updated_at = utcnow()
    ussd.expires_at = utcnow() + timedelta(minutes=get_settings().ussd_session_ttl_minutes)
    if payload_updates:
        data = dict(ussd.payload or {})
        data.update(payload_updates)
        ussd.payload = data
    # SQLAlchemy may not detect in-place JSON mutation; reassign always.
    ussd.payload = dict(ussd.payload or {})
