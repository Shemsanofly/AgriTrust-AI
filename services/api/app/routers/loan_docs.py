"""Supporting documents for loan applications.

The farmer uploads a document (PDF or photo) first; applying for a loan on the web then needs
at least one of them, and they are attached to that application. Who can open a document:
the farmer, admins, and the lender of the application it is attached to while the farmer's
data-sharing consent is active. Every lender or admin view is written to the audit log."""

import re
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from .. import files
from ..db import get_session
from ..models import Farmer, LoanApplication, LoanDocument, Role, User
from ..security.audit import audit
from ..security.auth import farmer_for, get_current_user, require_roles
from ..security.consent import require_consent

router = APIRouter(tags=["kifedha"])
KIND = "loan-docs"
MAX_UNATTACHED = 10
DocType = Literal["national_id", "land", "cooperative", "other"]


def document_json(d: LoanDocument) -> dict:
    return {
        "id": d.id,
        "doc_type": d.doc_type,
        "name": d.original_name,
        "content_type": d.content_type,
        "size_bytes": d.size_bytes,
        "url": f"/loan-documents/{d.id}",
        "attached": d.loan_id is not None,
        "created_at": d.created_at.isoformat(),
    }


def documents_for_loan(session: Session, loan_id: int) -> list[dict]:
    return [document_json(d) for d in session.exec(select(LoanDocument).where(LoanDocument.loan_id == loan_id).order_by(LoanDocument.id))]


def attach(session: Session, farmer: Farmer, loan: LoanApplication, document_ids: list[int]) -> None:
    """Attach the farmer's own, not-yet-used documents to a new application."""
    docs = [session.get(LoanDocument, i) for i in dict.fromkeys(document_ids)]
    if not docs or any(d is None or d.farmer_id != farmer.id or d.loan_id is not None for d in docs):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_document")
    for d in docs:
        d.loan_id = loan.id
        session.add(d)


def _safe_name(name: str | None) -> str:
    return re.sub(r"[^\w.\- ]", "_", (name or "document").split("/")[-1].split("\\")[-1])[:80]


@router.post("/loan-documents", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: DocType = Form(...),
    user: User = Depends(require_roles(Role.FARMER)),
    session: Session = Depends(get_session),
):
    farmer = farmer_for(session, user)
    waiting = session.exec(select(LoanDocument.id).where(LoanDocument.farmer_id == farmer.id, LoanDocument.loan_id.is_(None))).all()  # type: ignore[union-attr]
    if len(waiting) >= MAX_UNATTACHED:
        raise HTTPException(status.HTTP_409_CONFLICT, "too_many_documents")
    data = await file.read(files.MAX_BYTES + 1)
    if len(data) > files.MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "document_too_large")
    kind = files.sniff(data[:16])
    if not kind:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "not_a_document")
    doc = LoanDocument(
        farmer_id=farmer.id,
        doc_type=doc_type,
        original_name=_safe_name(file.filename),
        stored_name=files.save(KIND, data, kind),
        content_type=kind,
        size_bytes=len(data),
    )
    session.add(doc)
    session.flush()
    audit(session, user.id, "LOAN_DOCUMENT_ADDED", "LOAN_DOCUMENT", doc.id, subject_farmer_id=farmer.id)
    session.commit()
    return document_json(doc)


@router.get("/loan-documents")
def my_waiting_documents(user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    """Documents uploaded but not yet attached to an application."""
    farmer = farmer_for(session, user)
    rows = session.exec(select(LoanDocument).where(LoanDocument.farmer_id == farmer.id, LoanDocument.loan_id.is_(None)).order_by(LoanDocument.id))  # type: ignore[union-attr]
    return [document_json(d) for d in rows]


def _load_for_viewer(session: Session, doc_id: int, user: User) -> LoanDocument:
    doc = session.get(LoanDocument, doc_id)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    farmer = session.get(Farmer, doc.farmer_id)
    if user.role == Role.FARMER and farmer and farmer.user_id == user.id:
        return doc
    if user.role == Role.ADMIN:
        audit(session, user.id, "READ", "LOAN_DOCUMENT", doc.id, subject_farmer_id=doc.farmer_id, reason="admin_access")
        session.commit()
        return doc
    loan = session.get(LoanApplication, doc.loan_id) if doc.loan_id else None
    if user.role == Role.LENDER and loan and loan.lender_user_id == user.id:
        require_consent(session, doc.farmer_id, user.id, "profile")  # 403 once the farmer revokes
        audit(session, user.id, "READ", "LOAN_DOCUMENT", doc.id, subject_farmer_id=doc.farmer_id, reason=f"loan#{loan.id}")
        session.commit()
        return doc
    raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")


@router.get("/loan-documents/{doc_id}")
def open_document(doc_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    doc = _load_for_viewer(session, doc_id, user)
    path = files.upload_dir(KIND) / doc.stored_name
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return FileResponse(path, media_type=doc.content_type, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.delete("/loan-documents/{doc_id}", status_code=204)
def delete_document(doc_id: int, user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    doc = session.get(LoanDocument, doc_id)
    if not doc or doc.farmer_id != farmer_for(session, user).id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if doc.loan_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "document_in_use")  # part of an application record
    (files.upload_dir(KIND) / doc.stored_name).unlink(missing_ok=True)
    session.delete(doc)
    session.commit()
