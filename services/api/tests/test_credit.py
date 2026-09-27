"""Credit assessment on five criteria, and the off-take contracts that feed criterion 4."""

from datetime import date, timedelta

from sqlmodel import Session, select

from app.db import engine
from app.models import Sensor, SensorReading, utcnow

KEYS = ["transactions", "farm", "production", "offtake", "condition"]


def criteria(client, headers) -> dict:
    profile = client.get("/farmers/me/profile", headers=headers).json()
    return {c["key"]: c for c in profile["criteria"]}, profile


def next_month() -> str:
    return (date.today().replace(day=1) + timedelta(days=32)).strftime("%Y-%m")


def test_profile_is_scored_on_five_weighted_criteria(client, login):
    farmer = login("farmer")
    by_key, profile = criteria(client, farmer)
    assert list(by_key) == KEYS
    assert sum(c["weight"] for c in by_key.values()) == 100
    weighted = sum(c["score"] * c["weight"] for c in by_key.values()) / 100
    assert abs(weighted - profile["score"]) < 0.6
    for c in by_key.values():
        assert c["title"]["en"] and c["title"]["sw"] and c["findings"]
        assert c["level"] in ("good", "fair", "weak")
    # Criterion 5 reads the IoT sensor and falls back to the AI salinity estimate.
    condition = by_key["condition"]["facts"]
    assert condition["soil_moisture_pct"]["source"] == "sensor"
    assert condition["salinity_ec_ds_m"]["source"] == "estimate"
    assert by_key["farm"]["facts"]["acres"] == 5


def test_salinity_sensor_overrides_the_estimate(client, login):
    farmer = login("farmer")
    with Session(engine) as s:
        sensor = s.exec(select(Sensor).where(Sensor.device_id == "ESP32-SOIL-01")).one()
        s.add(SensorReading(sensor_id=sensor.id, ts=utcnow(), metric="soil_ec_ds_m", value=5.1, seq=9999))
        s.commit()
    by_key, _ = criteria(client, farmer)
    salinity = by_key["condition"]["facts"]["salinity_ec_ds_m"]
    assert salinity == {"value": 5.1, "source": "sensor"}
    assert any(not f["good"] and "saline" in f["text"]["en"] for f in by_key["condition"]["findings"])


def test_contract_lifecycle_and_permissions(client, login):
    farmer, buyer, buyer2, lender = login("farmer"), login("buyer"), login("buyer2"), login("lender")
    directory = client.get("/contracts/farmers", headers=buyer).json()
    neema = next(f for f in directory if f["public_id"] == "FMR-0042")
    assert "phone" not in neema and neema["growing"] == ["maize"]
    assert client.get("/contracts/farmers", headers=farmer).status_code == 403

    offer = {"farmer_id": "FMR-0042", "crop_type": "maize", "quantity_kg": 500, "price_per_kg": 820, "delivery_month": next_month()}
    assert client.post("/contracts", json={**offer, "delivery_month": "2020-01"}, headers=buyer).status_code == 422
    c = client.post("/contracts", json=offer, headers=buyer).json()
    assert c["status"] == "OFFERED" and c["total_tzs"] == 410_000 and c["buyer"]["name"] == "Tanzanite Foods Ltd"

    assert any(x["id"] == c["id"] for x in client.get("/contracts", headers=farmer).json())
    assert not any(x["id"] == c["id"] for x in client.get("/contracts", headers=buyer2).json())
    assert client.get("/contracts", headers=lender).status_code == 403

    assert client.patch(f"/contracts/{c['id']}", json={"action": "accept"}, headers=buyer).status_code == 403
    assert client.patch(f"/contracts/{c['id']}", json={"action": "accept"}, headers=buyer2).status_code == 403
    assert client.patch(f"/contracts/{c['id']}", json={"action": "fulfil"}, headers=buyer).status_code == 409
    assert client.patch(f"/contracts/{c['id']}", json={"action": "accept"}, headers=farmer).json()["status"] == "ACCEPTED"
    assert client.patch(f"/contracts/{c['id']}", json={"action": "cancel"}, headers=buyer).status_code == 409
    alerts = client.get("/alerts", headers=buyer).json()
    assert any(a["kind"] == "CONTRACT" and "accepted" in a["message"]["en"] for a in alerts)
    assert client.patch(f"/contracts/{c['id']}", json={"action": "fulfil"}, headers=buyer).json()["status"] == "FULFILLED"

    other = client.post("/contracts", json=offer, headers=buyer2).json()
    assert client.patch(f"/contracts/{other['id']}", json={"action": "decline"}, headers=farmer).json()["status"] == "DECLINED"
    withdrawn = client.post("/contracts", json=offer, headers=buyer2).json()
    assert client.patch(f"/contracts/{withdrawn['id']}", json={"action": "cancel"}, headers=buyer2).json()["status"] == "CANCELLED"


def test_accepted_contracts_raise_market_certainty_and_loan_limit(client, login):
    farmer = login("farmer")
    before, profile_before = criteria(client, farmer)
    offtake = before["offtake"]["facts"]
    assert offtake["active_contracts"] == 1 and offtake["coverage"] < 0.5  # seeded: 1,500 of 3,500 kg
    pending = next(c for c in client.get("/contracts", headers=farmer).json() if c["status"] == "OFFERED")
    client.patch(f"/contracts/{pending['id']}", json={"action": "accept"}, headers=farmer)

    after, profile_after = criteria(client, farmer)
    assert after["offtake"]["facts"]["coverage"] >= 0.5
    assert after["offtake"]["score"] > before["offtake"]["score"]
    loan = lambda p: next(x for x in p["suggested_products"] if x["type"] == "input_loan")["max_amount_tzs"]  # noqa: E731
    assert loan(profile_after) > loan(profile_before)  # 40% instead of 30% of expected income
