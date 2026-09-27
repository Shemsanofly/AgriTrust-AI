from __future__ import annotations

import logging
from typing import Any

import httpx

from ...config import get_settings
from ..exceptions import ProviderRequestError
from .base import SMSProvider, SMSResult, USSDProvider, USSDRequest, USSDResponse

log = logging.getLogger(__name__)


class AfricasTalkingUSSDProvider(USSDProvider):
    name = "africastalking"

    def parse_request(self, form: dict[str, Any]) -> USSDRequest:
        return USSDRequest(
            session_id=str(form.get("sessionId") or form.get("session_id") or ""),
            phone_number=str(form.get("phoneNumber") or form.get("phone_number") or ""),
            text=str(form.get("text") or ""),
            service_code=str(form.get("serviceCode") or form.get("service_code") or ""),
            network_code=str(form.get("networkCode") or form.get("network_code") or ""),
            raw=dict(form),
        )

    def format_response(self, response: USSDResponse) -> str:
        return response.body


class AfricasTalkingSMSProvider(SMSProvider):
    name = "africastalking"

    def send(self, phone_number: str, message: str, sender_id: str | None = None) -> SMSResult:
        settings = get_settings()
        if not settings.africastalking_api_key:
            return SMSResult(status="LOGGED")
        host = (
            "api.sandbox.africastalking.com"
            if settings.africastalking_username == "sandbox"
            else "api.africastalking.com"
        )
        data = {
            "username": settings.africastalking_username,
            "to": phone_number,
            "message": message,
        }
        sid = sender_id or settings.africastalking_sender_id
        if sid:
            data["from"] = sid
        try:
            resp = httpx.post(
                f"https://{host}/version1/messaging",
                data=data,
                headers={"apiKey": settings.africastalking_api_key, "Accept": "application/json"},
                timeout=6,
            )
            resp.raise_for_status()
            payload = resp.json()
            msg_id = None
            try:
                recipients = payload.get("SMSMessageData", {}).get("Recipients") or []
                if recipients:
                    msg_id = str(recipients[0].get("messageId") or "") or None
            except Exception:
                msg_id = None
            return SMSResult(status="SENT", provider_message_id=msg_id, raw=payload)
        except Exception as exc:
            log.warning("Africa's Talking SMS failed: %s", exc)
            raise ProviderRequestError(str(exc)) from exc
