"""Snippe (https://snippe.sh) mobile-money collections: a USSD push asks the payer to
approve with their mobile-money PIN; Snippe reports the outcome by signed webhook and
by GET /payments/{reference}. Request shapes follow the official Python SDK
(Neurotech-HQ/snippe-python-sdk). Amounts are whole TZS, minimum 500."""

import hashlib
import hmac
import logging
import time

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)
MIN_AMOUNT_TZS = 500
WEBHOOK_TOLERANCE_SECONDS = 300


class SnippeError(Exception):
    def __init__(self, message: str, status_code: int | None = None, error_code: str = ""):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


def local_phone(phone: str) -> str:
    """Snippe's examples use the local format: +255712345678 -> 0712345678."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    if digits.startswith("255") and len(digits) == 12:
        return "0" + digits[3:]
    return digits if digits.startswith("0") else phone


def _request(method: str, path: str, **kwargs) -> dict:
    settings = get_settings()
    if not settings.snippe_api_key:
        raise SnippeError("SNIPPE_API_KEY is not set", error_code="not_configured")
    headers = {"Authorization": f"Bearer {settings.snippe_api_key}", "Accept": "application/json", **kwargs.pop("headers", {})}
    try:
        resp = httpx.request(method, f"{settings.snippe_base_url.rstrip('/')}{path}", headers=headers, timeout=20, **kwargs)
    except httpx.HTTPError as err:
        raise SnippeError(f"Could not reach Snippe: {err}", error_code="network") from err
    try:
        body = resp.json()
    except ValueError:
        body = {"message": resp.text[:300]}
    if resp.status_code not in (200, 201):
        raise SnippeError(body.get("message") or f"HTTP {resp.status_code}", resp.status_code, body.get("error_code", ""))
    return body.get("data", body)


def create_mobile_payment(
    *, amount_tzs: int, phone: str, firstname: str, lastname: str, email: str, webhook_url: str, metadata: dict, idempotency_key: str
) -> dict:
    payload: dict = {
        "payment_type": "mobile",
        "details": {"amount": amount_tzs, "currency": "TZS"},
        "phone_number": local_phone(phone),
        # The live API requires customer.email and webhook_url (the SDK marks them optional).
        "customer": {"firstname": firstname, "lastname": lastname, "email": email},
        "webhook_url": webhook_url,
        "metadata": metadata,
    }
    return _request("POST", "/payments", json=payload, headers={"Idempotency-Key": idempotency_key[:30]})


def get_payment(reference: str) -> dict:
    return _request("GET", f"/payments/{reference}")


def verify_webhook(raw_body: bytes, signature: str | None, timestamp: str | None, now: float | None = None) -> bool:
    """HMAC-SHA256 over "{timestamp}.{raw body}" with the webhook signing key; rejects
    anything older than 5 minutes (replay protection)."""
    secret = get_settings().snippe_webhook_secret
    if not (secret and signature and timestamp):
        return False
    try:
        age = abs((now or time.time()) - int(timestamp))
    except ValueError:
        return False
    if age > WEBHOOK_TOLERANCE_SECONDS:
        return False
    expected = hmac.new(secret.encode(), timestamp.encode() + b"." + raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip())
