from fastapi import HTTPException, status
from sqlmodel import Session, select

from ..models import ConsentRecord, utcnow

DATA_CATEGORIES = ("profile", "production", "storage", "sales", "receipts")


def active_consent(session: Session, farmer_id: int, grantee_user_id: int, category: str) -> ConsentRecord | None:
    now = utcnow()
    for record in session.exec(
        select(ConsentRecord).where(
            ConsentRecord.farmer_id == farmer_id,
            ConsentRecord.grantee_user_id == grantee_user_id,
            ConsentRecord.revoked_at.is_(None),  # type: ignore[union-attr]
        )
    ):
        if record.expires_at > now and category in record.data_categories:
            return record
    return None


def require_consent(session: Session, farmer_id: int, grantee_user_id: int, category: str) -> ConsentRecord:
    record = active_consent(session, farmer_id, grantee_user_id, category)
    if not record:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "consent_required")
    return record
