import os
import tempfile

# Each test re-seeds; on a disk-backed temp dir SQLite's per-DDL fsync makes that ~10 s instead of ~0.5 s.
_tmp_root = "/dev/shm" if os.path.isdir("/dev/shm") and os.access("/dev/shm", os.W_OK) else None
_db = os.path.join(tempfile.mkdtemp(dir=_tmp_root), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"
os.environ["WEATHER_MODE"] = "simulated"
os.environ["GEOCODE_MODE"] = "offline"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp()  # tests never write into the real uploads folder
os.environ["DEV_MODE"] = "true"
os.environ["RPC_URL"] = ""
os.environ["AFRICASTALKING_API_KEY"] = ""
# Tests must not depend on a developer's .env (real keys, codes, providers).
os.environ["AFRICASTALKING_USSD_CODE"] = ""
os.environ["PAYMENTS_PROVIDER"] = "simulated"
os.environ["SNIPPE_API_KEY"] = ""
os.environ["SNIPPE_WEBHOOK_SECRET"] = ""
os.environ["FACEIO_PUBLIC_ID"] = ""
os.environ["FACEIO_API_KEY"] = ""
os.environ["PUBLIC_WEB_URL"] = "http://localhost:5173"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402

PHONES = {
    "farmer": "+255700000001",
    "buyer": "+255700000002",
    "warehouse": "+255700000003",
    "lender": "+255700000004",
    "insurer": "+255700000005",
    "buyer2": "+255700000006",
    "admin": "+255700000009",
}


@pytest.fixture()
def client():
    seed()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def login(client):
    def _login(who: str) -> dict:
        r = client.post("/auth/login", json={"phone": PHONES[who], "pin": "1234"})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _login
