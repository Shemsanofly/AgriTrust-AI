"""SMS via Africa's Talking (sandbox). Without an API key messages are only logged, so the
demo works offline. Each message is sent in the recipient's preferred language."""

import logging

import httpx
from sqlmodel import Session

from ..config import get_settings
from ..models import SmsLog, User

log = logging.getLogger(__name__)


def send_sms(session: Session, user: User, bilingual: dict[str, str]) -> SmsLog:
    lang = user.language.value if hasattr(user.language, "value") else str(user.language)
    body = bilingual.get(lang) or bilingual.get("sw") or next(iter(bilingual.values()))
    settings = get_settings()
    status = "LOGGED"
    if settings.africastalking_api_key:
        host = "api.sandbox.africastalking.com" if settings.africastalking_username == "sandbox" else "api.africastalking.com"
        try:
            resp = httpx.post(
                f"https://{host}/version1/messaging",
                data={"username": settings.africastalking_username, "to": user.phone, "message": body},
                headers={"apiKey": settings.africastalking_api_key, "Accept": "application/json"},
                timeout=6,
            )
            resp.raise_for_status()
            status = "SENT"
        except Exception as exc:
            log.warning("SMS send failed: %s", exc)
            status = "FAILED"
    entry = SmsLog(phone=user.phone, language=lang, body=body, status=status)
    session.add(entry)
    log.info("SMS[%s] %s: %s", status, user.phone, body)
    return entry
