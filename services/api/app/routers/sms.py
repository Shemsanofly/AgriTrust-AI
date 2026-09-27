"""SMS delivery / status callbacks from the configured provider."""

from __future__ import annotations

import logging
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Request, Response
from sqlmodel import Session, select

from ..db import get_session
from ..models import SmsLog, utcnow

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sms", tags=["sms"])


async def _payload(request: Request) -> dict:
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
            return {}
    parsed = parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True)
    return {k: (v[0] if len(v) == 1 else v) for k, v in parsed.items()}


@router.post("/callback/")
@router.post("/callback")
async def sms_callback(request: Request, session: Session = Depends(get_session)):
    """Update SmsLog status when the provider reports delivery (best-effort)."""
    data = await _payload(request)
    msg_id = (
        data.get("id")
        or data.get("messageId")
        or data.get("message_id")
        or data.get("request_id")
        or data.get("provider_message_id")
    )
    status_raw = str(data.get("status") or data.get("deliveryStatus") or data.get("state") or "").upper()
    mapped = None
    if status_raw in ("SUCCESS", "DELIVERED", "Success"):
        mapped = "DELIVERED"
    elif status_raw in ("FAILED", "REJECTED", "UNDELIVERED", "Failure"):
        mapped = "FAILED"
    elif status_raw in ("SENT", "Submitted", "SUBMITTED"):
        mapped = "SENT"

    if msg_id and mapped:
        row = session.exec(select(SmsLog).where(SmsLog.provider_message_id == str(msg_id))).first()
        if row:
            row.status = mapped
            if mapped in ("SENT", "DELIVERED") and not row.sent_at:
                row.sent_at = utcnow()
            session.add(row)
            session.commit()
            log.info("SMS callback id=%s status=%s", msg_id, mapped)
            return {"ok": True, "updated": True}

    log.info("SMS callback ignored keys=%s", sorted(data.keys()))
    return Response(status_code=204)
