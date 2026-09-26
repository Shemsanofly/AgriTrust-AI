from sqlmodel import Session

from .integrations.sms import send_sms
from .models import Alert, User


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
        send_sms(session, user, message)
    return alert
