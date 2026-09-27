"""Loan applications on the web need a supporting document that only the right people can open."""

import pytest

from app.config import get_settings

PDF = b"%PDF-1.7\n1 0 obj << >> endobj\n" + b"0" * 200
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 200


@pytest.fixture(autouse=True)
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    return tmp_path


def upload(client, headers, data=PDF, name="id.pdf", doc_type="national_id"):
    return client.post("/loan-documents", files={"file": (name, data, "application/pdf")}, data={"doc_type": doc_type}, headers=headers)


def apply(client, farmer, lender_id, document_ids):
    body = {"lender_user_id": lender_id, "amount": 150000, "purpose": "Seeds", "confirm_pin": "1234", "document_ids": document_ids}
    return client.post("/loans", json=body, headers=farmer)


def test_web_application_requires_a_document_and_attaches_it(client, login, uploads):
    farmer = login("farmer")
    lender_id = client.get("/partners?role=LENDER", headers=farmer).json()[0]["id"]
    assert apply(client, farmer, lender_id, []).json()["detail"] == "document_required"
    doc = upload(client, farmer).json()
    photo = upload(client, farmer, data=JPEG, name="letter.jpg", doc_type="cooperative").json()
    assert doc["content_type"] == "application/pdf" and photo["content_type"] == "image/jpeg"
    assert {d["id"] for d in client.get("/loan-documents", headers=farmer).json()} == {doc["id"], photo["id"]}
    loan = apply(client, farmer, lender_id, [doc["id"], photo["id"]])
    assert loan.status_code == 201
    assert {d["doc_type"] for d in loan.json()["documents"]} == {"national_id", "cooperative"}
    assert client.get("/loan-documents", headers=farmer).json() == []  # attached now
    # A document belongs to one application only, and can't be deleted once it is on record.
    assert apply(client, farmer, lender_id, [doc["id"]]).json()["detail"] == "invalid_document"
    assert client.delete(doc["url"], headers=farmer).status_code == 409


def test_only_real_documents_are_accepted(client, login):
    farmer = login("farmer")
    assert upload(client, farmer, data=b"MZ\x90\x00 program", name="id.pdf").status_code == 415
    assert upload(client, farmer, doc_type="passport_scan").status_code == 422
    other = {"Authorization": "Bearer " + client.post("/auth/login", json={"phone": "+255700000008", "pin": "1234"}).json()["access_token"]}
    theirs = upload(client, other).json()
    lender_id = client.get("/partners?role=LENDER", headers=farmer).json()[0]["id"]
    assert apply(client, farmer, lender_id, [theirs["id"]]).json()["detail"] == "invalid_document"  # not your document


def test_who_can_open_a_loan_document(client, login):
    farmer, lender, buyer, admin = login("farmer"), login("lender"), login("buyer"), login("admin")
    lender_id = client.get("/partners?role=LENDER", headers=farmer).json()[0]["id"]
    doc = upload(client, farmer).json()
    assert client.get(doc["url"], headers=lender).status_code == 403  # not attached to their application yet
    loan = apply(client, farmer, lender_id, [doc["id"]]).json()
    seen = client.get(f"/loans/{loan['id']}", headers=lender).json()
    assert seen["documents"][0]["id"] == doc["id"]
    res = client.get(doc["url"], headers=lender)
    assert res.status_code == 200 and res.content == PDF and res.headers["content-type"] == "application/pdf"
    assert client.get(doc["url"], headers=farmer).status_code == 200
    assert client.get(doc["url"], headers=admin).status_code == 200
    assert client.get(doc["url"], headers=buyer).status_code == 403
    audit = client.get("/admin/audit", headers=admin).json()
    assert any(a.get("action") == "READ" and a.get("resource_type") == "LOAN_DOCUMENT" for a in (audit if isinstance(audit, list) else audit.get("items", [])))
    # Revoking consent cuts the lender off.
    client.delete(f"/consents/{loan['consent']['id']}", headers=farmer)
    assert client.get(doc["url"], headers=lender).status_code == 403


def test_unused_document_can_be_removed(client, login, uploads):
    farmer = login("farmer")
    doc = upload(client, farmer).json()
    assert client.delete(doc["url"], headers=farmer).status_code == 204
    assert client.get(doc["url"], headers=farmer).status_code == 404
    assert list((uploads / "loan-docs").iterdir()) == []
