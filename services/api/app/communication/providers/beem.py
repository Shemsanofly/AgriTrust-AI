from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

from ...config import get_settings
from ..exceptions import ProviderRequestError
from .base import SMSProvider, SMSResult, USSDProvider, USSDRequest, USSDResponse

log = logging.getLogger(__name__)


class BeemUSSDProvider(USSDProvider):
    """Beem Africa USSD callback adapter.

    Field names vary slightly by Beem product version; we accept common aliases.
    """

    name = "beem"

    def parse_request(self, form: dict[str, Any]) -> USSDRequest:
        return USSDRequest(
            session_id=str(form.get("session_id") or form.get("sessionId") or form.get("msisdn") or ""),
            phone_number=str(form.get("msisdn") or form.get("phoneNumber") or form.get("phone") or ""),
            text=str(form.get("input") or form.get("text") or form.get("ussd_string") or ""),
            service_code=str(form.get("service_code") or form.get("serviceCode") or ""),
            network_code=str(form.get("operator") or form.get("networkCode") or ""),
            raw=dict(form),
        )


class BeemSMSProvider(SMSProvider):
    name = "beem"

    def send(self, phone_number: str, message: str, sender_id: str | None = None) -> SMSResult:
        settings = get_settings()
        if not settings.beem_api_key or not settings.beem_secret_key:
            return SMSResult(status="LOGGED")
        auth = base64.b64encode(f"{settings.beem_api_key}:{settings.beem_secret_key}".encode()).decode()
        payload = {
            "source_addr": sender_id or settings.beem_sender_id or "SHAMBANI",
            "encoding": 0,
            "message": message,
            "recipients": [{"recipient_id": 1, "dest_addr": phone_number.lstrip("+")}],
        }
        try:
            resp = httpx.post(
                "https://apisms.beem.africa/v1/send",
                json=payload,
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
                timeout=6,
            )
            resp.raise_for_status()
            data = resp.json()
            request_id = None
            if isinstance(data, dict):
                request_id = str(data.get("request_id") or data.get("message_id") or "") or None
            return SMSResult(status="SENT", provider_message_id=request_id, raw=data if isinstance(data, dict) else None)
        except Exception as exc:
            log.warning("Beem SMS failed: %s", exc)
            raise ProviderRequestError(str(exc)) from exc
