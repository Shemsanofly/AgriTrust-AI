from sqlmodel import Session

from ..models import AuditLog


def audit(
    session: Session,
    actor_user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: str | int | None = None,
    subject_farmer_id: int | None = None,
    reason: str | None = None,
) -> None:
    """Append-only record of sensitive reads and writes (who, what, when, why)."""
    session.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=None if resource_id is None else str(resource_id),
            subject_farmer_id=subject_farmer_id,
            reason=reason,
        )
    )
