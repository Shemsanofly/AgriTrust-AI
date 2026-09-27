"""Face sign-in (FACEIO): the server checks every Facial ID with FACEIO and keeps only a hash."""

import pytest
from sqlmodel import Session, select

from app.config import get_settings
from app.db import engine
from app.models import FaceLogin
from app.routers import face

FID = "fio-3f9c2a17-demo-facial-id"


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


@pytest.fixture()
def faceio(monkeypatch):
    """FACEIO enabled with an API key; `registered` holds the Facial IDs FACEIO knows."""
    settings = get_settings()
    monkeypatch.setattr(settings, "faceio_public_id", "pub-demo")
    monkeypatch.setattr(settings, "faceio_api_key", "key-demo")
    registered = {FID, "fio-second-face"}

    def fake_get(url, params, timeout):
        assert url.endswith("/checkfacialid") and params["key"] == "key-demo"
        return FakeResponse({"status": 200, "valid": params["fid"] in registered})

    monkeypatch.setattr(face.httpx, "get", fake_get)
    return registered


def test_face_disabled_without_public_id(client):
    assert client.get("/auth/face/config").json() == {"enabled": False, "public_id": None}
    assert client.post("/auth/face/login", json={"facial_id": FID}).status_code == 404


def test_enroll_then_sign_in_with_face(client, login, faceio):
    assert client.get("/auth/face/config").json() == {"enabled": True, "public_id": "pub-demo"}
    farmer = login("farmer")
    assert client.post("/auth/face/enroll", json={"facial_id": FID}, headers=farmer).status_code == 201
    assert client.get("/me/security", headers=farmer).json()["face_enrolled"] is True
    with Session(engine) as s:
        row = s.exec(select(FaceLogin)).one()
        assert FID not in row.facial_id_hash  # only a keyed hash is stored

    res = client.post("/auth/face/login", json={"facial_id": FID})
    assert res.status_code == 200, res.text
    assert res.json()["user"]["phone"] == "+255700000001"
    sessions = client.get("/me/sessions", headers={"Authorization": f"Bearer {res.json()['access_token']}"}).json()
    assert any(s["login_method"] == "face" for s in sessions)


def test_unknown_or_revoked_face_is_rejected(client, login, faceio):
    farmer = login("farmer")
    client.post("/auth/face/enroll", json={"facial_id": FID}, headers=farmer)
    # Registered at FACEIO but never linked to an account here.
    assert client.post("/auth/face/login", json={"facial_id": "fio-second-face"}).status_code == 401
    # FACEIO no longer knows the ID (deleted in the console): refused even though we have its hash.
    faceio.discard(FID)
    assert client.post("/auth/face/login", json={"facial_id": FID}).status_code == 401
    assert client.post("/auth/face/enroll", json={"facial_id": "fio-made-up"}, headers=farmer).status_code == 401


def test_one_face_one_account_and_removal(client, login, faceio):
    farmer, buyer = login("farmer"), login("buyer")
    client.post("/auth/face/enroll", json={"facial_id": FID}, headers=farmer)
    assert client.post("/auth/face/enroll", json={"facial_id": FID}, headers=buyer).status_code == 409
    assert client.delete("/auth/face", headers=farmer).status_code == 204
    assert client.get("/me/security", headers=farmer).json()["face_enrolled"] is False
    assert client.post("/auth/face/login", json={"facial_id": FID}).status_code == 401


def test_without_api_key_only_dev_mode_skips_the_check(client, login, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "faceio_public_id", "pub-demo")
    monkeypatch.setattr(settings, "faceio_api_key", "")
    farmer = login("farmer")
    assert client.post("/auth/face/enroll", json={"facial_id": FID}, headers=farmer).status_code == 201
    monkeypatch.setattr(settings, "dev_mode", False)
    assert client.post("/auth/face/login", json={"facial_id": FID}).status_code == 503
