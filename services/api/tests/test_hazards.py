"""Disaster forecast (drought, fire, flood) from forecast data, with recommendations and alerts."""

import pytest

from app.ai import hazards
from app.integrations import hazard_data

DAYS = [f"2026-10-{d:02d}" for d in range(1, 17)]


def weather(rain=0.0, et0=6.0, t=31.0, rh=25.0, wind=25.0, rain_by_day=None):
    return {
        "time": DAYS,
        "precipitation_sum": rain_by_day or [rain] * 16,
        "precipitation_probability_max": [10] * 16,
        "temperature_2m_max": [t] * 16,
        "relative_humidity_2m_min": [rh] * 16,
        "wind_speed_10m_max": [wind] * 16,
        "et0_fao_evapotranspiration": [et0] * 16,
    }


def river(history_high=10.0, forecast=2.0):
    return {"history": [1.0] * 300 + [history_high] * 65, "time": DAYS * 2, "median": [forecast / 2] * 32, "likely_high": [forecast] * 32}


def by_name(result):
    return {h["hazard"]: h for h in result["hazards"]}


def test_dry_hot_windy_fortnight_means_drought_and_fire_danger():
    r = by_name(hazards.forecast({"weather": weather(), "flood": river(), "normal_rain_mm": 40.0}, soil_moisture=15, drought_prone=True, crops_growing=True))
    assert r["drought"]["level"] in ("high", "severe") and r["fire"]["level"] in ("high", "severe")
    assert r["flood"]["level"] == "low"
    assert "0 mm of rain" in r["drought"]["drivers"][0]["en"] and "normal" in r["drought"]["drivers"][1]["en"]
    assert len(r["drought"]["recommendations"]) >= 3 and all(x["sw"] for x in r["drought"]["recommendations"])
    assert r["drought"]["insurance"] == "weather_index"


def test_wet_mild_weeks_are_low_drought_and_fire():
    wet = weather(rain=8.0, et0=4.0, t=24.0, rh=70.0, wind=8.0)
    r = by_name(hazards.forecast({"weather": wet, "flood": river(), "normal_rain_mm": 60.0}, soil_moisture=40, drought_prone=False, crops_growing=True))
    assert r["drought"]["level"] == "low" and r["fire"]["level"] == "low"
    assert len(r["fire"]["recommendations"]) == 1  # one calm tip when the danger is low


def test_river_in_flood_and_heavy_rain_raise_flood_risk():
    storm = weather(rain_by_day=[2, 5, 60, 70, 40, 5] + [2] * 10, t=26, rh=80, wind=10)
    calm = by_name(hazards.forecast({"weather": weather(rain=1, rh=70), "flood": river(forecast=5.0), "normal_rain_mm": 30.0}, 35, False, True))["flood"]
    wet = by_name(hazards.forecast({"weather": storm, "flood": river(forecast=20.0), "normal_rain_mm": 30.0}, 35, False, True))["flood"]
    assert calm["level"] == "low" and wet["level"] in ("high", "severe") and wet["probability"] > calm["probability"]
    assert any("River flow" in d["en"] for d in wet["drivers"]) and any("Wettest 3 days" in d["en"] for d in wet["drivers"])


def test_nothing_is_invented_when_sources_are_down():
    r = hazards.forecast({"weather": None, "flood": None, "normal_rain_mm": None}, None, True, True)
    assert r["hazards"] == [] and r["available"] == {"weather": False, "river": False, "normals": False}


@pytest.fixture()
def fake_inputs(monkeypatch):
    data = {"weather": weather(), "flood": river(), "normal_rain_mm": 40.0}
    monkeypatch.setattr(hazard_data, "hazard_inputs", lambda lat, lon: data)
    return data


def test_endpoint_forecasts_each_farm_and_alerts_once_a_day(client, login, fake_inputs):
    farmer = login("farmer")
    res = client.get("/insurance/hazards", headers=farmer)
    assert res.status_code == 200, res.text
    farm = res.json()["farms"][0]
    assert {h["hazard"] for h in farm["hazards"]} == {"drought", "fire", "flood"}
    assert res.json()["sources"]
    alerts = [a for a in client.get("/alerts", headers=farmer).json() if a["kind"] == "DISASTER_RISK"]
    assert len(alerts) == 2 and all(a["message"]["sw"] for a in alerts)  # drought + fire
    client.get("/insurance/hazards", headers=farmer)
    assert len([a for a in client.get("/alerts", headers=farmer).json() if a["kind"] == "DISASTER_RISK"]) == 2  # no repeats
    assert client.get("/insurance/hazards", headers=login("buyer")).status_code == 403
