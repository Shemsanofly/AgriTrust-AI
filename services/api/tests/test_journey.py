"""One farmer's season, end to end (README §23/§24)."""

from datetime import date, datetime, timezone

from sqlmodel import Session, select

from app.db import engine
from app.models import SmsLog
from app.routers.iot import sign


def test_full_demo_journey(client, login):
    farmer, buyer, wh, lender, admin = (login(x) for x in ("farmer", "buyer", "warehouse", "lender", "admin"))

    # --- Shambani: soil dries out -> irrigation advice in Kiswahili + English
    farms = client.get("/farms", headers=farmer).json()
    farm = next(f for f in farms if f["name"] == "Shamba")
    assert client.post("/demo/scenario/soil-drying", headers=farmer).status_code == 200
    advice = client.get(f"/farms/{farm['id']}/irrigation-advice", headers=farmer).json()
    assert advice["action"] == "IRRIGATE"
    assert advice["headline"]["sw"].startswith("Mwagilia")
    assert advice["headline"]["en"].startswith("Irrigate")
    assert advice["reasons"] and all({"en", "sw"} <= set(r) for r in advice["reasons"])
    assert client.post(f"/advice/{advice['id']}/feedback", json={"followed": True}, headers=farmer).status_code == 200

    # --- Harvest -> batch + on-chain (simulated) proof, stored straight into the ghala
    crop = next(c for c in farm["crops"] if c["growth_stage"] == "maturity")
    warehouse_id = client.get("/me", headers=wh).json()["warehouses"][0]["id"]
    batch = client.post(
        "/harvests",
        json={"crop_id": crop["id"], "harvest_date": date.today().isoformat(), "quantity_kg": 2600, "warehouse_id": warehouse_id, "bay": "A-1"},
        headers=farmer,
    ).json()
    batch_id = batch["id"]
    assert batch_id.startswith("BATCH-") and batch["proofs"][0]["mode"] == "SIMULATED"

    # --- Ghalani: digital warehouse receipt issued on intake
    assert batch["status"] == "IN_STORAGE" and batch["warehouse"]["id"] == warehouse_id
    assert not any(b["id"] == batch_id for b in client.get("/warehouses/pending-batches", headers=wh).json())
    receipt = client.get(f"/receipts/{batch['receipt']['id']}", headers=farmer).json()
    assert receipt["id"].startswith("WR-") and receipt["status"] == "ACTIVE"
    assert receipt["legal_notice"]["sw"]

    # Humidity climbs -> HIGH risk alert (+ SMS in each user's language)
    assert client.post("/demo/scenario/ghala-humid", headers=wh).status_code == 200
    risk = client.get(f"/batches/{batch_id}/storage-risk", headers=farmer).json()
    assert risk["level"] == "HIGH"
    alerts = client.get("/alerts", headers=farmer).json()
    assert any(a["kind"] == "SPOILAGE_RISK" for a in alerts)
    with Session(engine) as s:
        sms = list(s.exec(select(SmsLog).where(SmsLog.phone == "+255700000001")))
        assert any(m.language == "sw" and "Hatari" in m.body for m in sms)
    rec = client.post(f"/batches/{batch_id}/storage-records", headers=wh)
    assert rec.status_code == 201 and rec.json()["verification"]["status"] == "VERIFIED"
    # Back to normal and the farmer resolves the alert
    client.post("/demo/scenario/ghala-normal", headers=wh)
    for a in alerts:
        if a["kind"] == "SPOILAGE_RISK":
            client.post(f"/alerts/{a['id']}/resolve", headers=farmer)

    # --- Sokoni: list, discover, verify by QR
    assert client.patch(f"/batches/{batch_id}/listing", json={"listed": True, "price_per_kg": 800}, headers=farmer).status_code == 200
    listings = client.get("/marketplace/listings?crop=maize", headers=buyer).json()
    assert any(item["batch_id"] == batch_id for item in listings)
    detail = client.get(f"/marketplace/listings/{batch_id}", headers=buyer).json()
    assert detail["storage_history"] and detail["digital_ghala"]
    assert "phone" not in str(detail["farmer"])

    v = client.get(f"/verify/{batch_id}").json()
    assert v["status"] == "VERIFIED" and [s["stage"] for s in v["stages"]] == ["SHAMBANI", "GHALANI"]
    qr = client.get(f"/qr/{batch_id}.svg")
    assert qr.status_code == 200 and qr.headers["content-type"].startswith("image/svg+xml")

    # Tamper demo: silent DB edit -> MISMATCH, restore -> VERIFIED
    client.post(f"/demo/tamper/{batch_id}", headers=admin)
    assert client.get(f"/verify/{batch_id}").json()["status"] == "MISMATCH"
    client.post(f"/demo/restore/{batch_id}", headers=admin)
    assert client.get(f"/verify/{batch_id}").json()["status"] == "VERIFIED"

    # --- Order -> accept -> simulated payment -> release -> deliver -> two-party confirmation
    big = client.post("/orders", json={"batch_id": batch_id, "quantity_kg": 1000}, headers=buyer)
    assert big.status_code == 403 and big.json()["detail"] == "step_up_required"  # 800,000 TZS needs PIN
    order = client.post("/orders", json={"batch_id": batch_id, "quantity_kg": 1000, "confirm_pin": "1234"}, headers=buyer).json()
    assert order["farmer"]["phone"] is None  # contact hidden until accepted
    oid = order["id"]
    assert client.patch(f"/orders/{oid}", json={"action": "pay"}, headers=buyer).status_code == 409
    order = client.patch(f"/orders/{oid}", json={"action": "accept"}, headers=farmer).json()
    assert order["status"] == "ACCEPTED" and order["farmer"]["phone"]
    client.post(f"/orders/{oid}/messages", json={"body": "Tutachukua Jumatatu"}, headers=buyer)
    assert len(client.get(f"/orders/{oid}/messages", headers=farmer).json()) == 1
    order = client.patch(f"/orders/{oid}", json={"action": "pay", "confirm_pin": "1234"}, headers=buyer).json()
    assert order["status"] == "PAID" and order["payment_ref"].startswith("SIM-MM-")
    order = client.patch(f"/orders/{oid}", json={"action": "release"}, headers=wh).json()
    assert order["status"] == "RELEASED"
    order = client.patch(f"/orders/{oid}", json={"action": "deliver"}, headers=buyer).json()
    sale_id = order["sale"]["id"]
    client.post(f"/sales/{sale_id}/confirm", headers=buyer)
    order = client.post(f"/sales/{sale_id}/confirm", headers=farmer).json()
    assert order["status"] == "SALE_CONFIRMED"
    v = client.get(f"/verify/{sale_id}").json()
    assert v["status"] == "VERIFIED" and v["stages"][-1]["stage"] == "SOKONI"

    # --- Kifedha: explainable profile, consent-gated lender view, human decision
    profile = client.get("/farmers/me/profile", headers=farmer).json()
    assert profile["risk_band"] in ("LOW", "MEDIUM", "HIGH")
    assert profile["positive_factors"] and profile["disclaimer"]["sw"]
    assert any(p["type"] == "input_loan" for p in profile["suggested_products"])

    assert client.get("/farmers/FMR-0042/profile", headers=lender).status_code == 403  # no consent yet
    lender_id = client.get("/partners?role=LENDER", headers=farmer).json()[0]["id"]
    # A web application needs a supporting document (uploaded first).
    no_doc = {"lender_user_id": lender_id, "amount": 400000, "purpose": "Seeds and fertiliser", "confirm_pin": "1234"}
    assert client.post("/loans", json=no_doc, headers=farmer).json()["detail"] == "document_required"
    doc = client.post("/loan-documents", files={"file": ("nida.pdf", b"%PDF-1.4 national id", "application/pdf")}, data={"doc_type": "national_id"}, headers=farmer).json()
    assert client.post(
        "/loans", json={**no_doc, "confirm_pin": "0000", "document_ids": [doc["id"]]}, headers=farmer
    ).status_code == 403
    loan = client.post(
        "/loans",
        json={**no_doc, "repayment_month": "2027-03", "document_ids": [doc["id"]]},
        headers=farmer,
    ).json()
    assert [d["doc_type"] for d in loan["documents"]] == ["national_id"]
    seen = client.get(f"/loans/{loan['id']}", headers=lender).json()
    assert seen["profile"]["risk_band"] == profile["risk_band"]
    assert client.patch(f"/loans/{loan['id']}/decision", json={"status": "APPROVED"}, headers=lender).status_code == 422
    decided = client.patch(
        f"/loans/{loan['id']}/decision", json={"status": "APPROVED", "reason": "Verified sales history", "interest_rate_pct": 18, "tenor_months": 6}, headers=lender
    ).json()
    assert decided["status"] == "APPROVED" and decided["decided_by_name"]
    history = client.get("/farmers/me/access-history", headers=farmer).json()
    assert any(h["resource_type"] == "PROFILE" for h in history)

    # Revoke consent -> lender loses access
    consent_id = loan["consent"]["id"]
    client.delete(f"/consents/{consent_id}", headers=farmer)
    assert client.get("/farmers/FMR-0042/profile", headers=lender).status_code == 403

    # --- Insurance: recommendation -> policy -> parametric trigger proposes a claim -> insurer decides
    insurer = login("insurer")
    recs = client.get("/insurance/recommendations", headers=farmer).json()["recommendations"]
    wi = next(r for r in recs if r["product"] == "weather_index")
    insurer_id = client.get("/partners?role=INSURER", headers=farmer).json()[0]["id"]
    policy = client.post(
        "/insurance/policies",
        json={"insurer_user_id": insurer_id, "product": "weather_index", "coverage_tzs": wi["suggested_coverage_tzs"], "farm_id": wi["farm_id"], "confirm_pin": "1234"},
        headers=farmer,
    ).json()
    client.patch(f"/insurance/policies/{policy['id']}", json={"status": "ACTIVE"}, headers=insurer)
    trig = client.post(f"/insurance/policies/{policy['id']}/check-trigger", headers=farmer).json()
    assert trig["triggered"] and trig["simulated"] and trig["claim"]["status"] == "EVIDENCE_ATTACHED"
    claim = client.patch(
        f"/insurance/claims/{trig['claim']['id']}/decision", json={"status": "APPROVED", "reason": "Rainfall index below threshold"}, headers=insurer
    ).json()
    assert claim["status"] == "APPROVED"

    # --- Savings planner from the latest verified sale
    plan = client.get("/savings/plan", headers=farmer).json()
    assert plan["source"] == "latest_verified_sale" and plan["income_tzs"] == 800000
    assert round(sum(b["share"] for b in plan["buckets"]), 6) == 1.0

    # --- Admin sees the audit log; the simulated ledger's hash chain is intact
    assert client.get("/admin/audit", headers=admin).json()
    assert client.get("/admin/ledger", headers=admin).json()["simulated_ledger_intact"] is True
    assert client.get("/admin/audit", headers=farmer).status_code == 403


def test_language_preference_is_saved(client, login):
    buyer = login("buyer")
    assert client.get("/me", headers=buyer).json()["language"] == "en"
    assert client.patch("/me", json={"language": "sw"}, headers=buyer).json()["language"] == "sw"
    assert client.post("/auth/login", json={"phone": "+255700000002", "pin": "1234"}).json()["user"]["language"] == "sw"
    assert client.patch("/me", json={"language": "fr"}, headers=buyer).status_code == 422


def test_register_otp_and_lockout(client):
    r = client.post(
        "/auth/register",
        json={"phone": "+255711000111", "pin": "4321", "full_name": "Asha Juma", "role": "FARMER", "region": "Morogoro", "language": "en"},
    ).json()
    assert client.post("/auth/login", json={"phone": "+255711000111", "pin": "4321"}).status_code == 403
    tokens = client.post("/auth/otp/verify", json={"phone": "+255711000111", "code": r["dev_otp"]}).json()
    assert tokens["user"]["language"] == "en" and tokens["user"]["farmer"]["region"] == "Morogoro"
    refreshed = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401  # rotated
    for _ in range(5):
        client.post("/auth/login", json={"phone": "+255711000111", "pin": "0000"})
    assert client.post("/auth/login", json={"phone": "+255711000111", "pin": "4321"}).status_code == 423


def test_iot_hmac_and_replay(client):
    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    readings = {"temperature_c": 25.1, "humidity_pct": 60.2}
    body = {"device_id": "ESP32-GHALA-01", "ts": ts, "readings": readings, "seq": 10_000}
    body["sig"] = sign("dev-ghala-secret", body["device_id"], ts, readings, body["seq"])
    assert client.post("/iot/readings", json=body).status_code == 201
    assert client.post("/iot/readings", json=body).status_code == 409  # replay
    forged = {**body, "seq": 10_001, "sig": sign("wrong", body["device_id"], ts, readings, 10_001)}
    assert client.post("/iot/readings", json=forged).status_code == 401
    weird = {"temperature_c": 25.0, "humidity_pct": 140.0}
    bad = {"device_id": "ESP32-GHALA-01", "ts": ts, "readings": weird, "seq": 10_002}
    bad["sig"] = sign("dev-ghala-secret", bad["device_id"], ts, weird, 10_002)
    assert client.post("/iot/readings", json=bad).json()["flags"]["humidity_pct"] == "SUSPECT"


def test_rbac(client, login):
    buyer, lender = login("buyer"), login("lender")
    assert client.get("/farms", headers=buyer).status_code == 403
    assert client.get("/farmers/FMR-0042/profile", headers=buyer).status_code == 403
    assert client.post("/harvests", json={"crop_id": 1, "harvest_date": "2026-09-01", "quantity_kg": 1}, headers=lender).status_code == 403
    assert client.get("/farms").status_code == 401
