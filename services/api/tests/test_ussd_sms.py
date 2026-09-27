"""USSD + SMS channel tests (same backend / DB as the web app)."""

from datetime import timedelta

from sqlmodel import Session, select

from app.communication.phone import mask_phone, normalize_phone
from app.communication.providers.console import ConsoleSMSProvider
from app.communication.sms import send_sms
from app.config import get_settings
from app.db import engine
from app.i18n import bi
from app.models import SmsLog, UssdSession, utcnow
from app.seed import seed


def _ussd(client, phone="+255700000001", text="", session_id="sess-demo-1"):
    # JSON works without python-multipart; Africa's Talking uses urlencoded forms in production.
    return client.post(
        "/api/ussd/callback/",
        json={
            "sessionId": session_id,
            "phoneNumber": phone,
            "serviceCode": "*384*123#",
            "text": text,
            "networkCode": "63902",
        },
    )


def test_normalize_phone():
    assert normalize_phone("0700000001") == "+255700000001"
    assert normalize_phone("255700000001") == "+255700000001"
    assert normalize_phone("+255700000001") == "+255700000001"
    assert normalize_phone("700000001") == "+255700000001"
    assert "******" in mask_phone("+255700000001")


def test_ussd_main_menu_existing_farmer(client):
    r = _ussd(client, text="")
    assert r.status_code == 200
    assert r.text.startswith("CON ")
    assert "Karibu Shambani Kifedha" in r.text or "Shamba Langu" in r.text
    assert "1." in r.text and "3." in r.text


def test_ussd_farm_info(client):
    sid = "sess-farm-1"
    assert _ussd(client, text="", session_id=sid).status_code == 200
    r = _ussd(client, text="1", session_id=sid)
    assert r.status_code == 200
    assert r.text.startswith("CON ")
    r2 = _ussd(client, text="1*1", session_id=sid)
    assert r2.status_code == 200
    assert r2.text.startswith("END ")
    assert "Dodoma" in r2.text or "acres" in r2.text


def test_ussd_main_menu_mirrors_web(client):
    r = _ussd(client, text="", session_id="sess-main-web")
    assert "1. Shamba Langu" in r.text and "2. Ghala" in r.text and "3. Soko" in r.text and "4. Fedha" in r.text


def test_ussd_finance_profile(client):
    sid = "sess-fin-1"
    _ussd(client, text="", session_id=sid)
    _ussd(client, text="4", session_id=sid)
    r = _ussd(client, text="4*4", session_id=sid)
    assert r.status_code == 200
    assert r.text.startswith("CON ")
    assert "HALI" in r.text or "STATUS" in r.text or "WASTANI" in r.text or "NZURI" in r.text or "Mauzo" in r.text
    r2 = _ussd(client, text="4*4*1", session_id=sid)
    assert r2.status_code == 200
    assert r2.text.startswith("END ")


def test_ussd_invalid_input(client):
    sid = "sess-bad-1"
    _ussd(client, text="", session_id=sid)
    r = _ussd(client, text="9", session_id=sid)
    assert r.status_code == 200
    assert r.text.startswith("CON ")
    assert "si sahihi" in r.text or "Invalid" in r.text


def test_ussd_exit(client):
    sid = "sess-exit-1"
    _ussd(client, text="", session_id=sid)
    r = _ussd(client, text="0", session_id=sid)
    assert r.status_code == 200
    assert r.text.startswith("END ")


def test_ussd_unknown_phone_offers_registration(client):
    r = _ussd(client, phone="+255799999999", text="", session_id="sess-new-1")
    assert r.status_code == 200
    assert "haijasajiliwa" in r.text or "not registered" in r.text
    assert "1." in r.text


def _register(client, phone, sid, crop="1", crop_acres="1.5"):
    """Morogoro is on the second region page: 9 (more) then 6; 2-acre farm."""
    path = "1*Asha Juma*9*6*2"
    for text in ("", "1", "1*Asha Juma", "1*Asha Juma*9", "1*Asha Juma*9*6", path):
        assert _ussd(client, phone=phone, text=text, session_id=sid).status_code == 200
    r = _ussd(client, phone=phone, text=f"{path}*{crop}", session_id=sid)
    if crop == "6":
        return r
    assert r.text.startswith("CON ") and "ekari ngapi" in r.text
    return _ussd(client, phone=phone, text=f"{path}*{crop}*{crop_acres}", session_id=sid)


def test_ussd_registration_flow(client):
    phone = "+255711122233"
    r = _register(client, phone, "sess-reg-1")
    assert r.status_code == 200
    assert r.text.startswith("END ")
    assert "umekamilika" in r.text
    assert "Morogoro" in r.text and "pH 6" in r.text and "°C" in r.text and "unyevu" in r.text
    assert len(r.text) <= 186

    # Same phone can now open the main menu
    r2 = _ussd(client, phone=phone, text="", session_id="sess-reg-2")
    assert "Shamba Langu" in r2.text or "My farm" in r2.text


def test_ussd_registration_captures_regional_soil(client):
    phone = "+255711122244"
    _register(client, phone, "sess-soil-1")
    with Session(engine) as s:
        from app.models import Crop, Farm, Farmer, User

        user = s.exec(select(User).where(User.phone == phone)).one()
        farmer = s.exec(select(Farmer).where(Farmer.user_id == user.id)).one()
        farm = s.exec(select(Farm).where(Farm.farmer_id == farmer.id)).one()
        assert farm.region == "Morogoro" and farm.lat == -6.82 and farm.lon == 37.66
        assert farm.soil_type == "clay" and farm.soil_ph == 6.0 and farm.soil_salinity_ec == 0.4
        assert farm.soil_source == "soil_map"
        assert farm.soil_moisture_pct is not None and farm.soil_moisture_source == "simulated"
        crops = s.exec(select(Crop).where(Crop.farm_id == farm.id)).all()
        assert [(c.crop_type, c.acreage) for c in crops] == [("maize", 1.5)]


def test_ussd_registration_rejects_crop_acres_above_farm_size(client):
    phone, sid = "+255711122277", "sess-acres-1"
    r = _register(client, phone, sid, crop_acres="5")
    assert r.text.startswith("CON ") and "si sahihi" in r.text


def test_ussd_region_paging_back_and_invalid(client):
    phone, sid = "+255711122255", "sess-page-1"
    for text in ("", "1", "1*Juma"):
        _ussd(client, phone=phone, text=text, session_id=sid)
    r = _ussd(client, phone=phone, text="1*Juma*9", session_id=sid)
    assert "Kilimanjaro" in r.text and "0. Rudi" in r.text
    r = _ussd(client, phone=phone, text="1*Juma*9*0", session_id=sid)
    assert "Arusha" in r.text
    r = _ussd(client, phone=phone, text="1*Juma*9*0*42", session_id=sid)
    assert r.text.startswith("CON ") and "si sahihi" in r.text


def test_ussd_farm_page_lists_crops_and_add_crop(client):
    phone = "+255711122266"
    _register(client, phone, "sess-crops-1", crop="6")  # not planted yet
    _ussd(client, phone=phone, text="", session_id="sess-crops-2")
    r = _ussd(client, phone=phone, text="1", session_id="sess-crops-2")
    assert r.text.startswith("CON ") and "Mazao: hakuna bado" in r.text

    _ussd(client, phone=phone, text="1*4", session_id="sess-crops-2")
    r = _ussd(client, phone=phone, text="1*4*5", session_id="sess-crops-2")
    assert r.text.startswith("CON ") and "Mtama ni ekari ngapi" in r.text
    r = _ussd(client, phone=phone, text="1*4*5*1.5", session_id="sess-crops-2")
    assert r.text.startswith("END ") and "Mtama" in r.text and "1.5" in r.text

    _ussd(client, phone=phone, text="", session_id="sess-crops-3")
    r = _ussd(client, phone=phone, text="1", session_id="sess-crops-3")
    assert "Mazao: Mtama 1.5ac" in r.text
    r = _ussd(client, phone=phone, text="1*1", session_id="sess-crops-3")
    assert "Mtama 1.5ac (mwanzo)" in r.text


def test_ussd_demo_farm_page_soil_and_planting(client):
    sid = "sess-farm-page"
    _ussd(client, text="", session_id=sid)
    r = _ussd(client, text="1", session_id=sid)
    assert "Mazao: Mahindi 3ac" in r.text
    r = _ussd(client, text="1*2", session_id=sid)
    assert r.text.startswith("END ") and "pH ya udongo: 6.2" in r.text and "Joto" in r.text and "Unyevu wa hewa" in r.text
    assert len(r.text) <= 186

    sid2 = "sess-farm-plant"
    _ussd(client, text="", session_id=sid2)
    _ussd(client, text="1", session_id=sid2)
    r = _ussd(client, text="1*3", session_id=sid2)
    assert r.text.startswith("END ") and "Mazao bora" in r.text


def test_ussd_missing_phone_rejected(client):
    r = client.post("/api/ussd/callback/", json={"sessionId": "x", "text": ""})
    assert r.status_code == 400


def test_ussd_urlencoded_callback(client):
    r = client.post(
        "/api/ussd/callback/",
        content="sessionId=sess-form-1&phoneNumber=%2B255700000001&text=&serviceCode=%2A384%23",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code == 200
    assert r.text.startswith("CON ")


def test_ussd_configured_service_code_accepted(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ussd_provider", "africastalking")
    monkeypatch.setattr(settings, "africastalking_ussd_code", "*384*123#")
    r = _ussd(client, text="", session_id="sess-code-ok")
    assert r.status_code == 200
    assert r.text.startswith("CON ")


def test_ussd_other_service_code_rejected(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ussd_provider", "africastalking")
    monkeypatch.setattr(settings, "africastalking_ussd_code", "*384*999#")
    r = _ussd(client, text="", session_id="sess-code-bad")
    assert r.status_code == 200
    assert r.text.startswith("END ")


def test_ussd_session_expiry_resets(client):
    sid = "sess-expire-1"
    _ussd(client, text="", session_id=sid)
    with Session(engine) as s:
        row = s.exec(select(UssdSession).where(UssdSession.session_id == sid)).first()
        assert row is not None
        row.expires_at = utcnow() - timedelta(minutes=1)
        row.state = "FARM_MENU"
        s.add(row)
        s.commit()
    r = _ussd(client, text="", session_id=sid)
    assert r.status_code == 200
    assert "Karibu" in r.text or "Welcome" in r.text


def test_sms_send_logs_without_provider(client):
    seed()
    with Session(engine) as s:
        from app.models import User

        user = s.exec(select(User).where(User.phone == "+255700000001")).first()
        entry = send_sms(s, user, bi("ussd.reg.pin_sms", pin="1234"), event_type="SYSTEM_NOTIFICATION")
        s.commit()
        assert entry.status in ("LOGGED", "SENT")
        assert entry.event_type == "SYSTEM_NOTIFICATION"
        assert entry.provider in ("africastalking", "console", "beem")


def test_sms_callback_updates_status(client):
    seed()
    with Session(engine) as s:
        row = SmsLog(
            phone="+255700000001",
            language="sw",
            body="test",
            status="SENT",
            provider="console",
            provider_message_id="msg-abc-1",
        )
        s.add(row)
        s.commit()
    r = client.post("/api/sms/callback/", json={"id": "msg-abc-1", "status": "Delivered"})
    assert r.status_code in (200, 204)
    with Session(engine) as s:
        updated = s.exec(select(SmsLog).where(SmsLog.provider_message_id == "msg-abc-1")).first()
        assert updated is not None
        assert updated.status == "DELIVERED"


def test_console_sms_provider():
    result = ConsoleSMSProvider().send("+255700000001", "habari")
    assert result.status == "LOGGED"
    assert result.provider_message_id


def _walk(client, path, sid):
    """Replay a cumulative USSD path (e.g. '2*1') from a fresh session; returns the last response."""
    parts = path.split("*")
    r = _ussd(client, text="", session_id=sid)
    for i in range(1, len(parts) + 1):
        r = _ussd(client, text="*".join(parts[:i]), session_id=sid)
    return r


def test_ussd_ghala_outlook_and_stock(client):
    r = _walk(client, "2", "sess-ghala-0")
    assert r.text.startswith("CON ") and "Ghalani: kg 300" in r.text
    r = _walk(client, "2*1", "sess-ghala-1")
    assert r.text.startswith("END ") and "Sasa:" in r.text and "Baada ya saa 6" in r.text and "Hatari" in r.text
    assert len(r.text) <= 186
    r = _walk(client, "2*2", "sess-ghala-2")
    assert r.text.startswith("END ") and "MAZAO GHALANI" in r.text
    assert _walk(client, "2*3", "sess-ghala-3").text.startswith("END ")


def test_ussd_market_listed_and_sales_history(client):
    r = _walk(client, "3*1", "sess-mkt-1")
    assert r.text.startswith("END ") and "SOKONI" in r.text
    r = _walk(client, "3*2", "sess-mkt-2")
    assert r.text.startswith("END ") and "MAUZO:" in r.text
    for sub in ("3", "4"):
        assert _walk(client, f"3*{sub}", f"sess-mkt-{sub}").text.startswith("END ")


def test_ussd_loan_request_with_pin(client):
    from app.models import LoanApplication

    r = _walk(client, "4*1*1", "sess-loan-1")
    assert r.text.startswith("CON ") and "TZS" in r.text
    r = _walk(client, "4*1*1*500000*1", "sess-loan-2")
    assert r.text.startswith("CON ") and "PIN" in r.text
    r = _walk(client, "4*1*1*500000*1*0000", "sess-loan-3")
    assert r.text.startswith("END ") and "PIN si sahihi" in r.text
    r = _walk(client, "4*1*1*500000*1*1234", "sess-loan-4")
    assert r.text.startswith("END ") and "Ombi la mkopo" in r.text
    with Session(engine) as s:
        loans = s.exec(select(LoanApplication)).all()
        assert len(loans) == 1 and loans[0].amount == 500000 and "USSD" in loans[0].purpose
    r = _walk(client, "4*1*2", "sess-loan-5")
    assert r.text.startswith("END ") and "MIKOPO YANGU" in r.text


def test_ussd_savings_deposit_and_new_goal(client):
    r = _walk(client, "4*2*1", "sess-sav-1")
    assert r.text.startswith("END ") and "AKIBA YANGU" in r.text
    r = _walk(client, "4*2*2*1*10000", "sess-sav-2")
    assert r.text.startswith("END ") and "imewekwa" in r.text
    r = _walk(client, "4*2*3*2*50000", "sess-sav-3")
    assert r.text.startswith("END ") and "Lengo" in r.text


def test_ussd_disaster_report_needs_active_cover(client):
    from app.models import InsuranceClaim, InsurancePolicy

    r = _walk(client, "4*3*1*1", "sess-ins-1")
    assert r.text.startswith("END ") and "Huna bima hai" in r.text

    r = _walk(client, "4*3*3", "sess-ins-2")
    assert r.text.startswith("CON ") and "1." in r.text
    r = _walk(client, "4*3*3*1*1234", "sess-ins-3")
    assert r.text.startswith("END ") and "Ombi la bima" in r.text

    with Session(engine) as s:
        policy = s.exec(select(InsurancePolicy)).one()
        policy.status = "ACTIVE"
        s.add(policy)
        s.commit()
        disaster, uncovered = ("1", "5") if policy.product == "weather_index" else ("5", "1")

    assert "Huna bima hai" in _walk(client, f"4*3*1*{uncovered}", "sess-ins-x").text
    r = _walk(client, f"4*3*1*{disaster}", "sess-ins-4")
    assert r.text.startswith("CON ") and "1. Ndiyo" in r.text
    r = _walk(client, f"4*3*1*{disaster}*1", "sess-ins-5")
    assert r.text.startswith("END ") and "dai #" in r.text
    with Session(engine) as s:
        claim = s.exec(select(InsuranceClaim)).one()
        assert claim.evidence["channel"] == "ussd"
    r = _walk(client, "4*3*2", "sess-ins-6")
    assert "BIMA ZANGU" in r.text and "Dai #" in r.text
