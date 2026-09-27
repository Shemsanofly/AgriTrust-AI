"""Reusable SMS service. All modules should call this instead of a provider directly."""

from __future__ import annotations

import logging

from sqlmodel import Session

from ..config import get_settings
from ..models import SmsLog, User, utcnow
from .exceptions import InvalidPhoneError, ProviderDisabledError, ProviderRequestError
from .phone import normalize_phone
from .providers import get_sms_provider

log = logging.getLogger(__name__)


def send_sms(
    session: Session,
    user: User | None,
    bilingual: dict[str, str],
    *,
    phone_number: str | None = None,
    event_type: str | None = None,
    language: str | None = None,
) -> SmsLog:
    """Send an SMS in the recipient's language. Without credentials the message is only logged."""
    settings = get_settings()
    if not settings.sms_enabled:
        raise ProviderDisabledError("sms_disabled")

    phone = phone_number or (user.phone if user else None)
    if not phone:
        raise InvalidPhoneError("missing_phone")
    phone = normalize_phone(phone)

    if language:
        lang = language
    elif user is not None:
        lang = user.language.value if hasattr(user.language, "value") else str(user.language)
    else:
        lang = "sw"
    body = bilingual.get(lang) or bilingual.get("sw") or next(iter(bilingual.values()))

    provider = get_sms_provider()
    status = "PENDING"
    provider_message_id = None
    try:
        result = provider.send(phone, body)
        status = result.status
        provider_message_id = result.provider_message_id
    except ProviderRequestError as exc:
        log.warning("SMS send failed: %s", exc)
        status = "FAILED"

    entry = SmsLog(
        phone=phone,
        language=lang,
        body=body,
        status=status,
        provider=provider.name,
        provider_message_id=provider_message_id,
        event_type=event_type,
        user_id=user.id if user else None,
        sent_at=utcnow() if status in ("SENT", "LOGGED") else None,
    )
    session.add(entry)
    log.info("SMS[%s/%s] %s: %s", provider.name, status, phone, body[:80])
    return entry
