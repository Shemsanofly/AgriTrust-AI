"""Automatic per-role reports: live numbers, a change log, a stamp that moves with the data, and a PDF."""

from datetime import date

import pytest

ROLES = {"farmer": "FARMER", "buyer": "BUYER", "warehouse": "WAREHOUSE_OPERATOR", "lender": "LENDER", "insurer": "INSURER", "admin": "ADMIN"}


@pytest.mark.parametrize("who", list(ROLES))
def test_every_role_gets_its_own_report_and_pdf(client, login, who):
    headers = login(who)
    r = client.get("/reports/me", headers=headers).json()
    assert r["role"] == ROLES[who] and r["title"]["en"] and r["title"]["sw"] and r["stamp"]
    assert r["sections"] and all(s["items"] for s in r["sections"])
    for s in r["sections"]:
        assert all(i["label"]["en"] and i["label"]["sw"] and i["format"] for i in s["items"])
    for lang in ("en", "sw"):
        pdf = client.get(f"/reports/me.pdf?lang={lang}", headers=headers)
        assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
        assert pdf.content.startswith(b"%PDF-") and "attachment" in pdf.headers["content-disposition"]


def test_farmer_report_reflects_live_data(client, login):
    r = client.get("/reports/me", headers=login("farmer")).json()
    values = {i["label"]["en"]: i["value"] for s in r["sections"] for i in s["items"]}
    assert values["Farms"] == 1 and values["Verified sales"] == 3 and values["Income from sales"] == 1_106_000
    sales = next(s for s in r["sections"] if s["key"] == "market")["table"]
    assert len(sales["rows"]) == 3 and sales["formats"] == ["date", "text", "kg", "tzs"]


def test_a_data_change_moves_the_stamp_and_shows_in_the_change_log(client, login):
    farmer = login("farmer")
    before = client.get("/reports/me", headers=farmer).json()
    farm = client.get("/farms", headers=farmer).json()[0]
    crop = {"crop_type": "beans", "planting_date": date.today().isoformat(), "growth_stage": "initial"}
    assert client.post(f"/farms/{farm['id']}/crops", json=crop, headers=farmer).status_code == 201
    after = client.get("/reports/me", headers=farmer).json()
    assert after["stamp"] != before["stamp"]  # the page sees this and says "Updated just now"
    growing = lambda rep: next(i["value"] for s in rep["sections"] for i in s["items"] if i["label"]["en"] == "Crops growing")  # noqa: E731
    assert growing(after) == growing(before) + 1
    # An order to the farmer shows up in their change log.
    buyer = login("buyer")
    batch = client.get("/marketplace/listings", headers=buyer).json()[0]["batch_id"]
    client.post("/orders", json={"batch_id": batch, "quantity_kg": 10}, headers=buyer)
    log = client.get("/reports/me", headers=farmer).json()["changes"]
    assert "New order" in log[0]["text"]["en"] and log[0]["text"]["sw"]


def test_every_change_is_logged(client, login):
    buyer, farmer = login("buyer"), login("farmer")
    batch = client.get("/marketplace/listings", headers=buyer).json()[0]["batch_id"]
    for _ in range(3):
        order = client.post("/orders", json={"batch_id": batch, "quantity_kg": 5}, headers=buyer).json()
        client.patch(f"/orders/{order['id']}", json={"action": "decline"}, headers=farmer)
    log = client.get("/reports/me", headers=buyer).json()["changes"]
    declined = [c for c in log if "DECLINED" in c["text"]["en"]]
    assert sum(c["count"] for c in declined) == 3  # different order numbers, so three separate lines


def test_reports_need_sign_in(client):
    assert client.get("/reports/me").status_code == 401
    assert client.get("/reports/me.pdf").status_code == 401


def test_identical_entries_on_the_same_day_are_grouped(client, login):
    from sqlmodel import Session, select

    from app.db import engine
    from app.models import AuditLog, User

    with Session(engine) as s:
        farmer = s.exec(select(User).where(User.phone == "+255700000001")).one()
        for _ in range(4):
            s.add(AuditLog(actor_user_id=farmer.id, action="CROP_PHOTO_ADDED", resource_type="CROP", resource_id="1"))
        s.commit()
    log = client.get("/reports/me", headers=login("farmer")).json()["changes"]
    photos = [c for c in log if c["text"]["en"] == "You added a crop photo"]
    assert len(photos) == 1 and photos[0]["count"] == 4
