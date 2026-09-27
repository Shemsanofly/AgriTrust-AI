"""SMS via the communication provider layer (Africa's Talking / Beem / console).

Without provider credentials messages are only logged, so the demo works offline.
Each message is sent in the recipient's preferred language.
"""

from sqlmodel import Session

from ..communication.sms import send_sms as _send_sms
from ..models import SmsLog, User

# Re-export for existing imports
__all__ = ["send_sms"]


def send_sms(
    session: Session,
    user: User,
    bilingual: dict[str, str],
    *,
    event_type: str | None = None,
) -> SmsLog:
    return _send_sms(session, user, bilingual, event_type=event_type)
