"""API additions used by the redesigned UI: sessions/devices, biometric step-up,
soil profile, storage duration, explainable-profile evidence, demo rain."""

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
    farm = next(f for f in client.get("/farms", headers=farmer).json() if f["name"] == "Shamba la Juu")
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
    farm = next(f for f in client.get("/farms", headers=farmer).json() if f["name"] == "Shamba la Juu")
    client.post("/demo/scenario/soil-drying", headers=farmer)
    try:
        client.post("/demo/weather/rain", headers=farmer)
        advice = client.get(f"/farms/{farm['id']}/irrigation-advice", headers=farmer).json()
        assert advice["action"] == "SKIP_RAIN"
        assert advice["headline"]["en"].endswith("Delay irrigation.")
        assert "leo" in advice["headline"]["sw"]
    finally:
        client.post("/demo/weather/live", headers=farmer)
