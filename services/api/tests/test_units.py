from datetime import date, datetime, timedelta

from app.ai import ghala, irrigation, planting, soil_map, spoilage
from app.chain.hashing import merkle_root, record_hash
from app.i18n import MESSAGES, bi, pick_language
from app.integrations.open_meteo import CurrentConditions, DayForecast, Forecast


def _forecast(rain: float) -> Forecast:
    today = date.today()
    return Forecast([DayForecast(today + timedelta(days=i), rain, 5.5, 31) for i in range(3)], simulated=False, source="test")


def test_every_message_has_both_languages():
    for key, texts in MESSAGES.items():
        assert set(texts) == {"en", "sw"}, key
        assert texts["en"].count("{") == texts["sw"].count("{"), key


def test_planting_uses_ph_salinity_and_moisture():
    base = planting.recommend("loam")
    assert {r["crop_type"]: r["fit"] for r in base.recommendations}["beans"] == "excellent"
    assert base.timing is None

    salty_alkaline = planting.recommend("loam", ph=8.0, salinity_ec=2.5, moisture_pct=35, rain_next_7d_mm=5)
    fits = {r["crop_type"]: r for r in salty_alkaline.recommendations}
    assert fits["beans"]["fit"] == "fair" and len(fits["beans"]["limits"]) == 2
    assert fits["sorghum"]["fit"] == "good" and fits["sorghum"]["limits"] == []
    assert salty_alkaline.recommendations[0]["crop_type"] == "sorghum"
    assert salty_alkaline.timing["action"] == "plant_now"

    dry = planting.recommend("clay", "rice", "rainfed", ph=6.0, moisture_pct=12, rain_next_7d_mm=3)
    assert {r["crop_type"]: r["fit"] for r in dry.recommendations}["rice"] == "good"
    assert dry.timing["action"] == "wait_for_rains"
    assert planting.recommend("clay", irrigation_type="drip", moisture_pct=12, rain_next_7d_mm=3).timing["action"] == "irrigate_first"


def test_soil_map_regions():
    assert len(soil_map.REGIONS) == 26
    assert soil_map.lookup("manyara").salinity_ec == 2.5
    assert soil_map.salinity_band(1.0) == "low" and soil_map.salinity_band(3) == "moderate" and soil_map.salinity_band(5) == "high"
    assert all(r.soil_type in planting.SOIL_CROP_FIT for r in soil_map.REGIONS)


def test_ghala_outlook_forecast_and_window_actions():
    t0 = datetime(2026, 9, 26, 6, 0)
    rising = [(t0 + timedelta(hours=i), 24.0, 60.0 + 2 * i) for i in range(6)]
    dry_outside = CurrentConditions(24.0, 50.0, None, True, "simulated")
    out = ghala.outlook(rising, dry_outside)
    assert (out.temp_now, out.rh_now, out.temp_pred, out.rh_pred) == (24.0, 70.0, 24.0, 82.0)
    assert out.actions[0] == bi("ghala.act.rising", hours=ghala.HORIZON_HOURS, rh=82)
    assert bi("ghala.act.open_windows", outside=50) in out.actions
    humid_outside = CurrentConditions(24.0, 85.0, None, True, "simulated")
    assert bi("ghala.act.close_windows", outside=85) in ghala.outlook(rising, humid_outside).actions

    safe = [(t0 + timedelta(hours=i), 22.0, 58.0) for i in range(6)]
    assert ghala.outlook(safe, dry_outside).actions == [bi("ghala.act.ok")]
    assert ghala.outlook([], None).temp_now is None


def test_ussd_fit_lines_stays_on_one_page():
    from app.ussd.services import MAX_SCREEN_CHARS, fit_lines

    assert fit_lines("T", ["- a", "- b"]) == "T\n- a\n- b"
    long_lines = [f"- reason number {i} " + "x" * 50 for i in range(5)]
    text = fit_lines("REASONS", long_lines)
    assert len(text) <= MAX_SCREEN_CHARS and text.endswith("+3")
    assert len(fit_lines("T", ["y" * 400, "z"])) <= MAX_SCREEN_CHARS


def test_bilingual_params():
    text = bi("alert.dry_soil", farm="Shamba", moisture=17.5)
    assert text["sw"] == "Udongo mkavu sana shambani Shamba: unyevu 17.5%"
    assert pick_language(None, "en-GB,en;q=0.9") == "en"
    assert pick_language("en", "fr") == "en"
    assert pick_language(None, None) == "sw"


def test_irrigation_rules():
    morning = datetime(2026, 9, 26, 11, 0)
    dry = irrigation.recommend("maize", "vegetative", 22.0, 0.5, _forecast(0), morning)
    assert dry.action == "IRRIGATE" and 5 <= dry.amount_mm <= irrigation.MAX_APPLICATION_MM
    assert dry.when["sw"] == "kesho asubuhi"
    rainy = irrigation.recommend("maize", "vegetative", 22.0, 0.5, _forecast(30), morning)
    assert rainy.action == "SKIP_RAIN"
    assert irrigation.recommend("maize", "vegetative", 35.0, 0.5, _forecast(0), morning).action == "NO_ACTION"
    assert irrigation.recommend("maize", "vegetative", 22.0, 12, _forecast(0), morning).action == "CHECK_SENSOR"


def test_spoilage_levels():
    t0 = datetime(2026, 9, 26)
    safe = [(t0 + timedelta(hours=i), 24.0, 58.0) for i in range(24)]
    humid = [(t0 + timedelta(hours=i), 26 + i * 0.25, 62 + i * 0.9) for i in range(24)]
    assert spoilage.assess(safe).level == "LOW"
    high = spoilage.assess(humid)
    assert high.level == "HIGH" and high.action["sw"]
    assert spoilage.assess([]).level == "UNKNOWN"


def test_hashing_is_canonical_and_salted():
    a = record_hash({"b": 1, "a": 2500}, "00" * 16)
    b = record_hash({"a": 2500.0, "b": 1}, "00" * 16)
    assert a == b
    assert record_hash({"a": 2500}, "11" * 16) != a
    assert merkle_root([b"x", b"y"]) == merkle_root([b"x", b"y"])
    assert merkle_root([b"x", b"y"]) != merkle_root([b"x", b"z"])
