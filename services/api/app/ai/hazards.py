"""Disaster forecast for a farm: drought, fire and flood, each as a probability with the
numbers behind it and practical recommendations.

Inputs are live forecasts and observations (see integrations/hazard_data.py); the risk model
turns established hazard indicators into a probability with a logistic score:

- Drought (next 16 days): crop water balance (forecast rain vs. evaporation ET0), rain
  compared with the 10-year normal for these dates, soil moisture, the region's drought
  history, and whether crops are in the ground.
- Fire (next 7 days): the Hot-Dry-Windy index (vapour-pressure deficit x wind; Srock et al.,
  2018) at its daily peak, and how many of the days are dry.
- Flood (next 30 days): the GloFAS river-flow forecast (the ensemble's likely-high flow, its
  75th percentile) against the past year's high water at this spot (95th percentile), and
  heavy-rain bursts that cause flash floods.

There is no local record of past disasters to train on, so the weights are set from these
published indicators rather than learned; the response says which sources were used."""

import math
from datetime import date
from typing import Any

from ..i18n import bi

MODEL_VERSION = "hazard-forecast-v1"
LEVELS = ((0.25, "low"), (0.5, "moderate"), (0.75, "high"), (1.01, "severe"))


MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    "sw": ["Januari", "Februari", "Machi", "Aprili", "Mei", "Juni", "Julai", "Agosti", "Septemba", "Oktoba", "Novemba", "Desemba"],
}


def _day(iso: str) -> dict[str, str]:
    """"2026-10-02" -> {"en": "2 October", "sw": "2 Oktoba"}."""
    d = date.fromisoformat(iso)
    return {lang: f"{d.day} {names[d.month - 1]}" for lang, names in MONTHS.items()}


def _sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-z))


def _level(p: float) -> str:
    return next(name for limit, name in LEVELS if p < limit)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _recommendations(hazard: str, level: str) -> list[dict[str, str]]:
    keys = {"low": ["low"], "moderate": ["1", "2"], "high": ["1", "2", "3"], "severe": ["1", "2", "3", "4"]}[level]
    return [bi(f"hazard.rec.{hazard}.{k}") for k in keys]


def drought(weather: dict, normal_rain: float | None, soil_moisture: float | None, drought_prone: bool, crops_growing: bool) -> dict[str, Any]:
    rain = sum(weather["precipitation_sum"])
    et0 = sum(weather["et0_fao_evapotranspiration"])
    deficit = _clamp((et0 - rain) / et0) if et0 else 0.0
    below_normal = _clamp(1 - rain / normal_rain) if normal_rain and normal_rain >= 10 else None
    dry_soil = _clamp((30 - soil_moisture) / 20) if soil_moisture is not None else 0.0
    z = -3.0 + 3.0 * deficit + 1.5 * (below_normal or 0) + 1.2 * dry_soil + (0.6 if drought_prone else 0) + (0.5 if crops_growing else -1.0)
    p = _sigmoid(z)
    drivers = [bi("hazard.why.water_balance", rain=round(rain, 1), et0=round(et0))]
    if normal_rain is not None:
        seasonal = normal_rain < 10
        drivers.append(bi("hazard.why.dry_season" if seasonal else "hazard.why.vs_normal", normal=round(normal_rain, 1), pct=round(100 * rain / normal_rain) if normal_rain else 0))
    if soil_moisture is not None:
        drivers.append(bi("hazard.why.soil", pct=round(soil_moisture)))
    if drought_prone:
        drivers.append(bi("hazard.why.drought_region"))
    return {"hazard": "drought", "probability": round(p, 2), "level": _level(p), "window_days": len(weather["time"]), "start": weather["time"][0], "end": weather["time"][-1], "drivers": drivers, "insurance": "weather_index"}


def _hdw(t_max: float, rh_min: float, wind_kmh: float) -> float:
    """Hot-Dry-Windy index: vapour-pressure deficit (hPa) x wind (m/s)."""
    es = 6.108 * math.exp(17.27 * t_max / (t_max + 237.3))  # saturation vapour pressure, hPa
    return es * (1 - rh_min / 100) * (wind_kmh / 3.6)


def fire(weather: dict) -> dict[str, Any]:
    days = min(7, len(weather["time"]))
    hdw = [_hdw(weather["temperature_2m_max"][i], weather["relative_humidity_2m_min"][i], weather["wind_speed_10m_max"][i]) for i in range(days)]
    dry = sum(1 for i in range(days) if weather["precipitation_sum"][i] < 1) / days
    peak = max(range(days), key=lambda i: hdw[i])
    hot = weather["temperature_2m_max"][peak] >= 32
    z = -3.5 + 3.0 * _clamp(hdw[peak] / 200, 0, 1.5) + 1.5 * dry + (0.5 if hot else 0)
    p = _sigmoid(z)
    drivers = [
        bi("hazard.why.fire_weather", t=round(weather["temperature_2m_max"][peak]), rh=round(weather["relative_humidity_2m_min"][peak]), wind=round(weather["wind_speed_10m_max"][peak]), day=_day(weather["time"][peak])),
        bi("hazard.why.dry_days", n=round(dry * days), total=days),
    ]
    return {"hazard": "fire", "probability": round(p, 2), "level": _level(p), "window_days": days, "start": weather["time"][0], "end": weather["time"][days - 1], "peak_day": weather["time"][peak], "drivers": drivers, "insurance": "storage_cover"}


def flood(weather: dict | None, river: dict | None) -> dict[str, Any]:
    drivers: list[dict[str, str]] = []
    river_part, peak_day = 0.0, None
    if river and river["history"] and river["likely_high"]:
        history = sorted(river["history"])
        p95 = history[int(0.95 * (len(history) - 1))]
        forecast_max = max(river["likely_high"])
        peak_day = river["time"][river["likely_high"].index(forecast_max)]
        if max(history[-1], forecast_max) < 1.0:
            drivers.append(bi("hazard.why.no_river"))
        else:
            ratio = forecast_max / p95 if p95 else 0
            # Starts counting at 60% of the year's high water; 1.8x that level is a strong signal.
            river_part = _clamp((ratio - 0.6) / 0.8, 0, 1.5)
            drivers.append(bi("hazard.why.river", pct=round(100 * ratio), day=_day(peak_day)))
    flash = 0.0
    if weather:
        rain = weather["precipitation_sum"]
        three_day = max(sum(rain[i : i + 3]) for i in range(max(1, len(rain) - 2)))
        flash = _clamp((three_day - 40) / 60, 0, 1.5)
        drivers.append(bi("hazard.why.heavy_rain", mm=round(three_day), day_max=round(max(rain))))
    p = _sigmoid(-3.5 + 3.0 * river_part + 2.5 * flash)
    end = river["time"][-1] if river else (weather["time"][-1] if weather else date.today().isoformat())
    return {"hazard": "flood", "probability": round(p, 2), "level": _level(p), "window_days": 30 if river else 16, "start": date.today().isoformat(), "end": end, "peak_day": peak_day, "drivers": drivers, "insurance": "storage_cover"}


def forecast(inputs: dict, soil_moisture: float | None, drought_prone: bool, crops_growing: bool) -> dict[str, Any]:
    """All three hazards for one farm, each with its recommendations."""
    weather, river = inputs.get("weather"), inputs.get("flood")
    hazards = []
    if weather:
        hazards.append(drought(weather, inputs.get("normal_rain_mm"), soil_moisture, drought_prone, crops_growing))
        hazards.append(fire(weather))
    if weather or river:
        hazards.append(flood(weather, river))
    for h in hazards:
        h["recommendations"] = _recommendations(h["hazard"], h["level"])
    return {
        "hazards": hazards,
        "available": {"weather": weather is not None, "river": river is not None, "normals": inputs.get("normal_rain_mm") is not None},
        "model_version": MODEL_VERSION,
    }
