"""Offline / sandbox provider: no external HTTP calls."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from .base import SMSProvider, SMSResult, USSDProvider, USSDRequest, USSDResponse

log = logging.getLogger(__name__)


class ConsoleUSSDProvider(USSDProvider):
    name = "console"

    def parse_request(self, form: dict[str, Any]) -> USSDRequest:
        return USSDRequest(
            session_id=str(form.get("sessionId") or form.get("session_id") or uuid.uuid4()),
            phone_number=str(form.get("phoneNumber") or form.get("phone_number") or ""),
            text=str(form.get("text") or ""),
            service_code=str(form.get("serviceCode") or ""),
            network_code=str(form.get("networkCode") or ""),
            raw=dict(form),
        )


class ConsoleSMSProvider(SMSProvider):
    name = "console"

    def send(self, phone_number: str, message: str, sender_id: str | None = None) -> SMSResult:
        msg_id = f"console-{uuid.uuid4().hex[:12]}"
        log.info("SMS[console] to=%s from=%s body=%s", phone_number, sender_id, message)
        return SMSResult(status="LOGGED", provider_message_id=msg_id)
