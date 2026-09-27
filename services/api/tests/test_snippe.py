"""Live payments through Snippe (mocked here: no money moves in tests).

The order becomes PAID only after Snippe confirms, by signed webhook or status check."""

import hashlib
import hmac
import json
import time

import pytest

from app.config import get_settings
from app.integrations import snippe

SECRET = "whsec_test"


class FakeResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data
        self.text = json.dumps(data)

    def json(self):
        return self._data


@pytest.fixture()
def live(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "payments_provider", "snippe")
    monkeypatch.setattr(settings, "snippe_api_key", "snp_test_key")
    monkeypatch.setattr(settings, "snippe_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "public_web_url", "https://example.ngrok-free.dev")
    from app import config

    config.public_web_url.cache_clear()
    calls = []
    state = {"status": "pending", "create_status": 201}

    def fake_request(method, url, headers, timeout, **kwargs):
        calls.append({"method": method, "url": url, "headers": headers, **kwargs})
        if method == "POST":
            if state["create_status"] != 201:
                return FakeResponse(state["create_status"], {"status": "error", "message": "Insufficient balance", "error_code": "payment_failed"})
            amount = kwargs["json"]["details"]["amount"]
            return FakeResponse(201, {"status": "success", "data": {"reference": "pi_test123", "status": "pending", "amount": {"value": amount, "currency": "TZS"}}})
        return FakeResponse(200, {"status": "success", "data": {"reference": "pi_test123", "status": state["status"], "amount": {"value": state.get("paid", 400000), "currency": "TZS"}}})

    monkeypatch.setattr(snippe.httpx, "request", fake_request)
    yield {"calls": calls, "state": state}
    config.public_web_url.cache_clear()


def accepted_order(client, login, kg=100):
    farmer, buyer = login("farmer"), login("buyer")
    batch_id = client.get("/marketplace/listings", headers=buyer).json()[0]["batch_id"]
    res = client.post("/orders", json={"batch_id": batch_id, "quantity_kg": kg, "confirm_pin": "1234"}, headers=buyer)
    assert res.status_code == 201, res.text
    order = res.json()
    client.patch(f"/orders/{order['id']}", json={"action": "accept"}, headers=farmer)
    return order, buyer, farmer


def signed(body: dict, secret=SECRET, ts=None):
    raw = json.dumps(body).encode()
    ts = str(int(ts or time.time()))
    sig = hmac.new(secret.encode(), ts.encode() + b"." + raw, hashlib.sha256).hexdigest()
    return raw, {"X-Webhook-Timestamp": ts, "X-Webhook-Signature": sig, "Content-Type": "application/json"}


def test_pay_sends_ussd_push_and_waits(client, login, live):
    order, buyer, _ = accepted_order(client, login)
    res = client.patch(f"/orders/{order['id']}", json={"action": "pay", "confirm_pin": "1234", "phone": "+255712345678", "email": "buyer@tanzanitefoods.co.tz"}, headers=buyer)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "ACCEPTED"  # not paid until Snippe confirms
    assert body["payment"]["status"] == "PENDING" and body["payment"]["reference"] == "pi_test123"
    call = live["calls"][0]
    assert call["url"] == "https://api.snippe.sh/api/v1/payments"
    assert call["headers"]["Authorization"] == "Bearer snp_test_key" and call["headers"]["Idempotency-Key"]
    sent = call["json"]
    assert sent["payment_type"] == "mobile" and sent["phone_number"] == "0712345678"
    assert sent["customer"]["email"] == "buyer@tanzanitefoods.co.tz"  # Snippe requires it
    assert client.get("/me", headers=buyer).json()["email"] == "buyer@tanzanitefoods.co.tz"  # remembered
    assert sent["details"] == {"amount": round(order["total"]), "currency": "TZS"}
    assert sent["webhook_url"] == "https://example.ngrok-free.dev/api/payments/snippe/webhook"
    assert sent["metadata"]["order_id"] == str(order["id"])
    # A second tap while waiting does not charge twice.
    again = client.patch(f"/orders/{order['id']}", json={"action": "pay", "confirm_pin": "1234", "email": "buyer@tanzanitefoods.co.tz"}, headers=buyer)
    assert again.status_code == 409 and again.json()["detail"] == "payment_pending"


def test_signed_webhook_marks_the_order_paid_once(client, login, live):
    order, buyer, farmer = accepted_order(client, login)
    client.patch(f"/orders/{order['id']}", json={"action": "pay", "confirm_pin": "1234", "email": "buyer@tanzanitefoods.co.tz"}, headers=buyer)
    event = {"type": "payment.completed", "data": {"reference": "pi_test123", "status": "completed", "amount": {"value": round(order["total"]), "currency": "TZS"}}}

    raw, headers = signed(event, secret="wrong")
    assert client.post("/payments/snippe/webhook", content=raw, headers=headers).status_code == 401
    raw, headers = signed(event, ts=time.time() - 3600)
    assert client.post("/payments/snippe/webhook", content=raw, headers=headers).status_code == 401  # replay
    assert client.get(f"/orders/{order['id']}", headers=buyer).json()["status"] == "ACCEPTED"

    raw, headers = signed(event)
    assert client.post("/payments/snippe/webhook", content=raw, headers=headers).json() == {"received": True, "matched": True}
    paid = client.get(f"/orders/{order['id']}", headers=buyer).json()
    assert paid["status"] == "PAID" and paid["payment_ref"] == "pi_test123"
    assert client.post("/payments/snippe/webhook", content=raw, headers=headers).status_code == 200  # retry: no change
    alerts = client.get("/alerts", headers=farmer).json()
    assert any(a["kind"] == "ORDER" and "PAID" in a["message"]["en"] for a in alerts)


def test_status_check_confirms_without_webhook(client, login, live):
    order, buyer, _ = accepted_order(client, login)
    client.patch(f"/orders/{order['id']}", json={"action": "pay", "confirm_pin": "1234", "email": "buyer@tanzanitefoods.co.tz"}, headers=buyer)
    assert client.get(f"/orders/{order['id']}/payment", headers=buyer).json()["payment"]["status"] == "PENDING"
    live["state"].update(status="completed", paid=round(order["total"]))
    result = client.get(f"/orders/{order['id']}/payment", headers=buyer).json()
    assert result["payment"]["status"] == "COMPLETED" and result["order"]["status"] == "PAID"


def test_underpayment_and_failure_leave_order_unpaid_and_retryable(client, login, live):
    order, buyer, _ = accepted_order(client, login)
    client.patch(f"/orders/{order['id']}", json={"action": "pay", "confirm_pin": "1234", "email": "buyer@tanzanitefoods.co.tz"}, headers=buyer)
    live["state"].update(status="completed", paid=1000)  # less than the order total
    result = client.get(f"/orders/{order['id']}/payment", headers=buyer).json()
    assert result["payment"]["status"] == "FAILED" and "amount_mismatch" in result["payment"]["failure_reason"]
    assert result["order"]["status"] == "ACCEPTED"

    live["state"]["create_status"] = 400
    res = client.patch(f"/orders/{order['id']}", json={"action": "pay", "confirm_pin": "1234", "email": "buyer@tanzanitefoods.co.tz"}, headers=buyer)
    assert res.status_code == 502 and res.json() == {"detail": "payment_provider_error", "reason": "Insufficient balance"}
    assert client.get(f"/orders/{order['id']}/payment", headers=buyer).json()["payment"]["failure_reason"] == "Insufficient balance"


def test_amount_below_snippe_minimum_is_refused(client, login, live):
    order, buyer, _ = accepted_order(client, login, kg=0.5)  # 0.5 kg x 780 = 390 TZS
    res = client.patch(f"/orders/{order['id']}", json={"action": "pay", "email": "buyer@tanzanitefoods.co.tz"}, headers=buyer)
    assert res.status_code == 422 and res.json()["detail"] == "amount_too_small"


def test_simulated_mode_is_unchanged(client, login):
    order, buyer, _ = accepted_order(client, login)
    paid = client.patch(f"/orders/{order['id']}", json={"action": "pay", "confirm_pin": "1234", "email": "buyer@tanzanitefoods.co.tz"}, headers=buyer).json()
    assert paid["status"] == "PAID" and paid["payment_mode"] == "simulated" and paid["payment"]["provider"] == "simulated"


def test_tiny_leftovers_are_not_shown_to_buyers(client, login):
    from sqlmodel import Session

    from app.db import engine
    from app.models import CropBatch

    buyer = login("buyer")
    batch_id = client.get("/marketplace/listings", headers=buyer).json()[0]["batch_id"]
    with Session(engine) as s:
        batch = s.get(CropBatch, batch_id)
        batch.available_kg = 1
        s.add(batch)
        s.commit()
    assert batch_id not in [x["batch_id"] for x in client.get("/marketplace/listings", headers=buyer).json()]


def test_email_and_public_address_are_required(client, login, live, monkeypatch):
    order, buyer, _ = accepted_order(client, login)
    res = client.patch(f"/orders/{order['id']}", json={"action": "pay", "confirm_pin": "1234"}, headers=buyer)
    assert res.status_code == 422 and res.json()["detail"] == "email_required"
    assert client.patch(f"/orders/{order['id']}", json={"action": "pay", "email": "not-an-email"}, headers=buyer).status_code == 422
    from app import config

    monkeypatch.setattr(get_settings(), "public_web_url", "http://localhost:5173")
    config.public_web_url.cache_clear()
    monkeypatch.setattr(config, "_lan_ip", lambda: None)
    res = client.patch(f"/orders/{order['id']}", json={"action": "pay", "email": "b@x.co"}, headers=buyer)
    assert res.status_code == 503 and res.json()["detail"] == "payment_setup_incomplete"
    assert live["calls"] == []  # nothing was sent to Snippe
