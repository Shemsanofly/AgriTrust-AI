from __future__ import annotations

from ...config import get_settings
from .africastalking import AfricasTalkingSMSProvider, AfricasTalkingUSSDProvider
from .base import SMSProvider, USSDProvider
from .beem import BeemSMSProvider, BeemUSSDProvider
from .console import ConsoleSMSProvider, ConsoleUSSDProvider

_USSD = {
    "africastalking": AfricasTalkingUSSDProvider,
    "beem": BeemUSSDProvider,
    "console": ConsoleUSSDProvider,
}
_SMS = {
    "africastalking": AfricasTalkingSMSProvider,
    "beem": BeemSMSProvider,
    "console": ConsoleSMSProvider,
}


def get_ussd_provider(name: str | None = None) -> USSDProvider:
    key = (name or get_settings().ussd_provider or "africastalking").strip().lower()
    cls = _USSD.get(key) or ConsoleUSSDProvider
    return cls()


def get_sms_provider(name: str | None = None) -> SMSProvider:
    key = (name or get_settings().sms_provider or "africastalking").strip().lower()
    cls = _SMS.get(key) or ConsoleSMSProvider
    return cls()
