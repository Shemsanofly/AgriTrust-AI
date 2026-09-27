"""USSD provider callback endpoints.

POST /api/ussd/callback/  — Africa's Talking / Beem / console form callbacks
POST /api/ussd/events/    — optional delivery / lifecycle events from the provider
"""

from __future__ import annotations

import logging
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import PlainTextResponse, Response
from sqlmodel import Session

from ..communication.providers import get_ussd_provider
from ..communication.providers.base import USSDResponse
from ..config import Settings, get_settings
from ..db import get_session
from ..i18n import t
from ..ussd.engine import handle_ussd

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ussd", tags=["ussd"])


async def _form_dict(request: Request) -> dict:
    """Parse JSON, urlencoded, or multipart bodies without requiring python-multipart for AT."""
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        data = await request.json()
        return data if isinstance(data, dict) else {}
    raw = await request.body()
    if not raw:
        return {}
    if "multipart/form-data" in content_type:
        try:
            form = await request.form()
            return {k: (v if isinstance(v, str) else str(v)) for k, v in form.items()}
        except AssertionError:
            log.warning("multipart body received but python-multipart is not installed")
            return {}
    # application/x-www-form-urlencoded (Africa's Talking default)
    parsed = parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True)
    return {k: (v[0] if len(v) == 1 else v) for k, v in parsed.items()}


def _normalize_code(code: str) -> str:
    return "".join(str(code or "").split())


def _expected_service_code(settings: Settings, provider_name: str) -> str:
    """Empty means any service code is accepted."""
    codes = {
        "africastalking": settings.africastalking_ussd_code,
        "beem": settings.beem_ussd_code,
    }
    return _normalize_code(codes.get(provider_name, ""))


@router.post("/callback/")
@router.post("/callback")
async def ussd_callback(request: Request, session: Session = Depends(get_session)):
    settings = get_settings()
    if not settings.ussd_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "ussd_disabled")

    provider = get_ussd_provider()
    form = await _form_dict(request)
    if not form.get("sessionId") and not form.get("session_id") and not form.get("msisdn"):
        if not settings.dev_mode:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "malformed_request")

    parsed = provider.parse_request(form)
    if not parsed.session_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "missing_session_id")
    if not parsed.phone_number:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "missing_phone_number")
    if len(parsed.text or "") > 200:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "input_too_long")

    expected = _expected_service_code(settings, provider.name)
    if expected and _normalize_code(parsed.service_code) != expected:
        log.warning("USSD call for unexpected service code %r (expected %r)", parsed.service_code, expected)
        rejected = USSDResponse(message=t("ussd.error.unavailable", "sw"), continue_session=False)
        return PlainTextResponse(provider.format_response(rejected), media_type=provider.media_type())

    response = handle_ussd(session, parsed, provider_name=provider.name)
    session.commit()
    body = provider.format_response(response)
    return PlainTextResponse(body, media_type=provider.media_type())


async def ussd_callback_probe():
    """Providers probe the callback URL with GET/HEAD before sending POSTs."""
    return PlainTextResponse("OK")


router.add_api_route("/callback/", ussd_callback_probe, methods=["GET", "HEAD"], include_in_schema=False)
router.add_api_route("/callback", ussd_callback_probe, methods=["GET", "HEAD"], include_in_schema=False)

alias_router = APIRouter(tags=["ussd"])
alias_router.add_api_route("/ussd", ussd_callback, methods=["POST"])
alias_router.add_api_route("/ussd/", ussd_callback, methods=["POST"], include_in_schema=False)
alias_router.add_api_route("/ussd", ussd_callback_probe, methods=["GET", "HEAD"], include_in_schema=False)
alias_router.add_api_route("/ussd/", ussd_callback_probe, methods=["GET", "HEAD"], include_in_schema=False)


@router.post("/events/")
@router.post("/events")
async def ussd_events(request: Request, session: Session = Depends(get_session)):
    """Accept provider lifecycle events without changing farmer data."""
    form = await _form_dict(request)
    log.info("USSD event keys=%s", sorted(form.keys()))
    session.commit()
    return Response(status_code=204)
