from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..chain.anchor import chain_mode, verify_ledger_chain
from ..db import get_session
from ..models import Alert, AuditLog, Role, SmsLog, User, utcnow
from ..security.auth import get_current_user, require_roles

router = APIRouter(tags=["alerts", "admin"])


@router.get("/alerts")
def my_alerts(unread_only: bool = False, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    query = select(Alert).where(Alert.user_id == user.id)
    if unread_only:
        query = query.where(Alert.read == False)  # noqa: E712
    return list(session.exec(query.order_by(Alert.created_at.desc()).limit(100)))  # type: ignore[attr-defined]


def _own_alert(session: Session, user: User, alert_id: int) -> Alert:
    alert = session.get(Alert, alert_id)
    if not alert or alert.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return alert


@router.post("/alerts/{alert_id}/read")
def mark_read(alert_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    alert = _own_alert(session, user, alert_id)
    alert.read = True
    session.add(alert)
    session.commit()
    session.refresh(alert)
    return alert


@router.post("/alerts/{alert_id}/resolve")
def resolve(alert_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    alert = _own_alert(session, user, alert_id)
    alert.read = True
    alert.resolved_at = utcnow()
    session.add(alert)
    session.commit()
    session.refresh(alert)
    return alert


@router.get("/admin/audit")
def audit_log(limit: int = 200, _: User = Depends(require_roles(Role.ADMIN)), session: Session = Depends(get_session)):
    rows = session.exec(select(AuditLog).order_by(AuditLog.ts.desc()).limit(min(limit, 1000)))  # type: ignore[attr-defined]
    out = []
    for r in rows:
        actor = session.get(User, r.actor_user_id) if r.actor_user_id else None
        out.append({**r.model_dump(mode="json"), "actor_name": actor.full_name if actor else None, "actor_role": actor.role.value if actor else None})
    return out


@router.get("/admin/alerts")
def admin_alerts(user: User = Depends(require_roles(Role.ADMIN)), session: Session = Depends(get_session)):
    return list(session.exec(select(Alert).where(Alert.user_id == user.id).order_by(Alert.created_at.desc()).limit(200)))  # type: ignore[attr-defined]


@router.get("/admin/users")
def users(_: User = Depends(require_roles(Role.ADMIN)), session: Session = Depends(get_session)):
    return [
        {"id": u.id, "phone": u.phone, "full_name": u.full_name, "role": u.role.value, "language": u.language.value, "status": u.status}
        for u in session.exec(select(User).order_by(User.id))  # type: ignore[arg-type]
    ]


@router.get("/admin/sms")
def sms_log(_: User = Depends(require_roles(Role.ADMIN)), session: Session = Depends(get_session)):
    return list(session.exec(select(SmsLog).order_by(SmsLog.created_at.desc()).limit(200)))  # type: ignore[attr-defined]


@router.get("/admin/ledger")
def ledger_status(_: User = Depends(require_roles(Role.ADMIN)), session: Session = Depends(get_session)):
    mode = chain_mode()
    return {"mode": mode, "simulated_ledger_intact": verify_ledger_chain(session) if mode == "SIMULATED" else None}
