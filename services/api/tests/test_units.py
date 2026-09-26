from datetime import date, datetime, timedelta

from app.ai import irrigation, spoilage
from app.chain.hashing import merkle_root, record_hash
from app.i18n import MESSAGES, bi, pick_language
from app.integrations.open_meteo import DayForecast, Forecast


def _forecast(rain: float) -> Forecast:
    today = date.today()
    return Forecast([DayForecast(today + timedelta(days=i), rain, 5.5, 31) for i in range(3)], simulated=False, source="test")


def test_every_message_has_both_languages():
    for key, texts in MESSAGES.items():
        assert set(texts) == {"en", "sw"}, key
        assert texts["en"].count("{") == texts["sw"].count("{"), key


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
