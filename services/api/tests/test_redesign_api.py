"""API additions used by the redesigned UI: sessions/devices, biometric step-up,
soil profile, storage duration, explainable-profile evidence, demo rain."""

from datetime import date

from sqlmodel import Session, select

from app.db import engine
from app.models import User, Warehouse
from app.routers.webauthn import _CHALLENGES
from app.security.auth import create_step_up_token


def _login(client, phone="+255700000001", device="device-A", ua="Mozilla/5.0 (Linux; Android 13) Chrome/120"):
    return client.post("/auth/login", json={"phone": phone, "pin": "1234"}, headers={"X-Device-Id": device, "User-Agent": ua})


def test_new_device_warning_and_sessions(client):
    first = _login(client).json()
    assert first["new_device"] is False  # first ever sign-in is not a "new device"
    again = _login(client, device="device-A").json()
    assert again["new_device"] is False
    other = _login(client, device="device-B", ua="Mozilla/5.0 (Windows NT 10.0) Firefox/119").json()
    assert other["new_device"] is True
    headers = {"Authorization": f"Bearer {other['access_token']}", "X-Device-Id": "device-B"}
    alerts = client.get("/alerts", headers=headers).json()
    assert any(a["kind"] == "SECURITY" and "Firefox" in a["message"]["en"] for a in alerts)

    sessions = client.get("/me/sessions", headers=headers).json()
    assert {s["device"] for s in sessions} == {"Chrome · Android", "Firefox · Windows"}
    assert sum(s["current"] for s in sessions) == 1
    assert client.post("/me/sessions/revoke-others", headers=headers).status_code == 204
    # The phone's refresh token no longer works.
    assert client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 401
    assert len(client.get("/me/sessions", headers=headers).json()) == 1


def test_attempts_left_then_lock(client):
    r = client.post("/auth/login", json={"phone": "+255700000002", "pin": "0000"})
    assert r.status_code == 401 and r.json()["attempts_left"] == 4
    for _ in range(3):
        client.post("/auth/login", json={"phone": "+255700000002", "pin": "0000"})
    assert client.post("/auth/login", json={"phone": "+255700000002", "pin": "0000"}).status_code == 423


def test_biometric_step_up_token_replaces_pin(client, login):
    farmer = login("farmer")
    me = client.get("/me", headers=farmer).json()
    lender_id = client.get("/partners?role=LENDER", headers=farmer).json()[0]["id"]
    body = {"grantee_user_id": lender_id, "data_categories": ["profile"], "purpose": "Loan review", "days": 30}

    class U:  # minimal user object for the token helper
        id = me["id"]

    ok = client.post("/consents", json={**body, "confirm_pin": create_step_up_token(U)}, headers=farmer)
    assert ok.status_code == 201
    forged = client.post("/consents", json={**body, "confirm_pin": "webauthn:not-a-token"}, headers=farmer)
    assert forged.status_code == 403


def test_passkey_endpoints_need_a_passkey(client, login):
    farmer = login("farmer")
    assert client.post("/auth/webauthn/login/begin", json={"phone": "+255700000001"}).json()["detail"] == "no_passkey"
    options = client.post("/auth/webauthn/register/begin", headers=farmer)
    assert options.status_code == 200 and '"challenge"' in options.json()
    assert any(k.startswith("reg:") for k in _CHALLENGES)
    assert client.get("/me/security", headers=farmer).json()["passkeys"] == []


def test_soil_profile_listing_duration_and_profile_evidence(client, login):
    farmer, buyer = login("farmer"), login("buyer")
    farm = next(f for f in client.get("/farms", headers=farmer).json() if f["name"] == "Shamba")
    assert farm["soil_ph"] == 6.2
    advice = client.get(f"/farms/{farm['id']}/planting-advice", headers=farmer).json()
    assert advice["soil_profile"]["ph_band"] == "slightly_acidic"
    assert "mahindi" in advice["soil_profile"]["ph_note"]["sw"]
    assert any("Fosforasi" in n["sw"] for n in advice["soil_profile"]["nutrient_notes"])

    listings = client.get("/marketplace/listings", headers=buyer).json()
    assert {item["crop_type"] for item in listings} >= {"maize", "rice", "beans"}
    assert all(item["days_in_storage"] is not None and item["risk"]["headline"] for item in listings)
    assert any(item["farmer"]["cooperative"] for item in listings)

    profile = client.get("/farmers/me/profile", headers=farmer).json()
    evidence = profile["evidence"]
    assert evidence["sales"]["repeat_buyers"] == 1 and len(evidence["sales"]["items"]) == 3
    assert evidence["climate"]["drought_prone"] is True
    assert evidence["production"]["harvests"]


def test_demo_rain_delays_irrigation(client, login):
    farmer = login("farmer")
    farm = next(f for f in client.get("/farms", headers=farmer).json() if f["name"] == "Shamba")
    client.post("/demo/scenario/soil-drying", headers=farmer)
    try:
        client.post("/demo/weather/rain", headers=farmer)
        advice = client.get(f"/farms/{farm['id']}/irrigation-advice", headers=farmer).json()
        assert advice["action"] == "SKIP_RAIN"
        assert advice["headline"]["en"].endswith("Delay irrigation.")
        assert "leo" in advice["headline"]["sw"]
    finally:
        client.post("/demo/weather/live", headers=farmer)


def test_farmer_harvest_can_go_directly_into_ghala_with_simulated_conditions(client, login):
    farmer = login("farmer")
    wh_headers = login("warehouse")
    with Session(engine) as s:
        operator = s.exec(select(User).where(User.phone == "+255700000003")).one()
        wh = Warehouse(
            public_id="WH-DEMO-AUTO",
            name="Demo Auto Ghala",
            operator_user_id=operator.id,
            region="Dodoma",
            verified=True,
        )
        s.add(wh)
        s.commit()
        s.refresh(wh)
        warehouse_id = wh.id

    farms = client.get("/farms", headers=farmer).json()
    farm = next(f for f in farms if f["name"] == "Shamba")
    crop = next(c for c in farm["crops"] if c["growth_stage"] == "maturity")
    res = client.post(
        "/harvests",
        json={
            "crop_id": crop["id"],
            "harvest_date": date.today().isoformat(),
            "quantity_kg": 1800,
            "warehouse_id": warehouse_id,
        },
        headers=farmer,
    )
    assert res.status_code == 201, res.text
    batch = res.json()
    assert batch["status"] == "IN_STORAGE"
    assert batch["warehouse"]["id"] == warehouse_id
    assert batch["receipt"]["id"].startswith("WR-")
    assert batch["risk"]["level"] == "HIGH"
    assert "Ventilate" in batch["risk"]["action"]["en"]
    history = client.get(f"/batches/{batch['id']}/storage-history?hours=24", headers=farmer).json()
    assert history and {"temperature_c", "humidity_pct"} <= set(history[0])
    assert all(b["id"] != batch["id"] for b in client.get("/warehouses/pending-batches", headers=wh_headers).json())
    alerts = client.get("/alerts", headers=farmer).json()
    assert any(a["kind"] == "SPOILAGE_RISK" and a["entity_id"] == batch["id"] for a in alerts)
    qr = client.get(f"/qr/{batch['id']}.svg")
    assert qr.status_code == 200 and qr.headers["content-type"].startswith("image/svg+xml")


def test_farmer_harvest_defaults_into_verified_ghala_for_qr_verification(client, login):
    farmer = login("farmer")
    farms = client.get("/farms", headers=farmer).json()
    farm = next(f for f in farms if f["name"] == "Shamba")
    crop = next(c for c in farm["crops"] if c["growth_stage"] == "maturity")
    res = client.post(
        "/harvests",
        json={
            "crop_id": crop["id"],
            "harvest_date": date.today().isoformat(),
            "quantity_kg": 3,
        },
        headers=farmer,
    )
    assert res.status_code == 201, res.text
    batch = res.json()
    assert batch["status"] == "IN_STORAGE"
    assert batch["warehouse"]
    assert batch["receipt"]

    verification = client.get(f"/verify/{batch['id']}").json()
    ghala = next((stage for stage in verification["stages"] if stage["stage"] == "GHALANI"), None)
    assert ghala
    assert ghala["facts"]["warehouse"] == batch["warehouse"]["name"]
    assert ghala["facts"]["receipt_id"] == batch["receipt"]["id"]
    assert ghala["facts"]["storage_windows"]


def test_farm_setup_prediction_uses_central_dry_location(client, login):
    farmer = login("farmer")
    res = client.post(
        "/farms/predict-setup",
        json={"lat": -6.163, "lon": 35.7516, "region": "Dodoma"},
        headers=farmer,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["soil_type"] == "sandy loam"
    assert data["crop_type"] == "sorghum"
    assert data["irrigation_type"] == "rainfed"
    assert data["soil_moisture_pct"] == 18.0
    assert data["soil_temperature_c"] == 31.0
    assert data["soil_ph"] == 7.2
    assert data["soil_nitrogen"] == "low"
    assert data["soil_phosphorus"] == "medium"
    assert data["soil_potassium"] == "medium"
    assert data["confidence"] in ("medium", "high")
    assert data["source"] == "ai_location_rules"
    assert any("semi-arid" in reason["en"] for reason in data["reasons"])


def test_farm_setup_prediction_uses_highland_location(client, login):
    farmer = login("farmer")
    res = client.post(
        "/farms/predict-setup",
        json={"lat": -8.9094, "lon": 33.4608, "region": "Mbeya"},
        headers=farmer,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["soil_type"] == "loam"
    assert data["crop_type"] == "maize"
    assert data["irrigation_type"] == "rainfed"
    assert data["soil_moisture_pct"] == 32.0
    assert data["soil_temperature_c"] == 22.0
    assert data["soil_ph"] == 6.1
    assert data["soil_nitrogen"] == "medium"
    assert data["soil_phosphorus"] == "medium"
    assert data["soil_potassium"] == "high"
    assert data["confidence"] == "high"


def test_ai_farm_registration_seeds_estimated_soil_readings(client, login):
    farmer = login("farmer")
    res = client.post(
        "/farms",
        json={
            "name": "AI Estimated Farm",
            "region": "Dodoma",
            "lat": -6.163,
            "lon": 35.7516,
            "acreage": 3.5,
            "soil_type": "sandy loam",
            "irrigation_type": "rainfed",
            "soil_source": "soil_map",
            "crop": {"crop_type": "sorghum", "planting_date": "2026-09-26", "growth_stage": "initial"},
        },
        headers=farmer,
    )
    assert res.status_code == 201, res.text
    farm = res.json()
    assert farm["soil_ph"] == 7.2
    assert farm["soil_nitrogen"] == "low"
    assert farm["soil_phosphorus"] == "medium"
    assert farm["soil_potassium"] == "medium"
    assert farm["latest"]["soil_moisture_pct"]["value"] == 18.0
    assert farm["latest"]["soil_temperature_c"]["value"] == 31.0
    assert farm["sensors"][0]["simulated"] is True


def test_ai_environment_estimate_can_coexist_with_manual_soil_test(client, login):
    farmer = login("farmer")
    res = client.post(
        "/farms",
        json={
            "name": "Mixed Source Farm",
            "region": "Mbeya",
            "lat": -8.9094,
            "lon": 33.4608,
            "acreage": 2,
            "soil_type": "loam",
            "irrigation_type": "rainfed",
            "soil_ph": 6.8,
            "soil_source": "farmer",
            "ai_estimated_environment": True,
            "crop": {"crop_type": "maize", "planting_date": "2026-09-26", "growth_stage": "initial"},
        },
        headers=farmer,
    )
    assert res.status_code == 201, res.text
    farm = res.json()
    assert farm["soil_ph"] == 6.8
    assert farm["soil_source"] == "farmer"
    assert farm["latest"]["soil_moisture_pct"]["value"] == 32.0
    assert farm["latest"]["soil_temperature_c"]["quality_flag"] == "ESTIMATE"
