from sqlmodel import Session

from .integrations.sms import send_sms
from .models import Alert, User

# Map alert kinds to SMS event types used by the notification log.
_EVENT_TYPES = {
    "DRY_SOIL": "SOIL_MOISTURE_ALERT",
    "HEAT": "WEATHER_ALERT",
    "WEATHER": "WEATHER_ALERT",
    "SPOILAGE_RISK": "SPOILAGE_RISK_ALERT",
    "ORDER": "BUYER_REQUEST_RECEIVED",
    "LOAN": "FINANCE_READINESS_UPDATED",
    "PROFILE": "FINANCIAL_PROFILE_UPDATED",
    "CLAIM": "SYSTEM_NOTIFICATION",
    "SECURITY": "SYSTEM_NOTIFICATION",
}


def notify(
    session: Session,
    user: User,
    kind: str,
    message: dict[str, str],
    severity: str = "INFO",
    entity_type: str | None = None,
    entity_id: str | None = None,
    sms: bool = False,
) -> Alert:
    alert = Alert(
        user_id=user.id,
        kind=kind,
        severity=severity,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    session.add(alert)
    if sms:
        try:
            send_sms(session, user, message, event_type=_EVENT_TYPES.get(kind, "SYSTEM_NOTIFICATION"))
        except Exception:
            # Never break the main request path because SMS failed or is disabled.
            pass
    return alert
