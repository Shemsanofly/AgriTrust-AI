"""Live inputs for the disaster forecast, all from Open-Meteo (free, no key):

- 16-day weather forecast (rain, rain probability, max temperature, min humidity, wind, ET0)
- GloFAS river-discharge forecast (Copernicus Emergency Management Service) and the past year
  of discharge, to judge how unusual the forecast flow is at this spot
- ERA5 reanalysis: rain in the same calendar window over the last 10 years (the local normal)

Results are cached for an hour per location. When a source is unreachable the forecast says
so; nothing is invented to fill the gap."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import httpx

log = logging.getLogger(__name__)
_cache: dict[tuple, tuple[float, dict]] = {}
_TTL = 3600
FORECAST = "https://api.open-meteo.com/v1/forecast"
FLOOD = "https://flood-api.open-meteo.com/v1/flood"
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
DAILY = "precipitation_sum,precipitation_probability_max,temperature_2m_max,relative_humidity_2m_min,wind_speed_10m_max,et0_fao_evapotranspiration"


def _get(url: str, params: dict) -> dict:
    resp = httpx.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _forecast(lat: float, lon: float) -> dict | None:
    try:
        d = _get(FORECAST, {"latitude": lat, "longitude": lon, "daily": DAILY, "forecast_days": 16, "timezone": "Africa/Dar_es_Salaam"})["daily"]
        return {k: [x if x is not None else 0.0 for x in v] if k != "time" else v for k, v in d.items()}
    except (httpx.HTTPError, KeyError, ValueError) as err:
        log.warning("Weather forecast unavailable: %s", err)
        return None


def _flood(lat: float, lon: float) -> dict | None:
    try:
        today = date.today()
        past = _get(FLOOD, {"latitude": lat, "longitude": lon, "daily": "river_discharge", "start_date": (today - timedelta(days=365)).isoformat(), "end_date": (today - timedelta(days=1)).isoformat()})
        # Ensemble statistics: the 75th percentile is the "likely high" flow; the maximum is a
        # single worst-case member and would overstate the risk.
        ahead = _get(FLOOD, {"latitude": lat, "longitude": lon, "daily": "river_discharge_median,river_discharge_p75", "forecast_days": 30})
        history = [x for x in past["daily"]["river_discharge"] if x is not None]
        daily = ahead["daily"]
        return {"history": history, "time": daily["time"], "median": [x or 0.0 for x in daily["river_discharge_median"]], "likely_high": [x or 0.0 for x in daily["river_discharge_p75"]]}
    except (httpx.HTTPError, KeyError, ValueError) as err:
        log.warning("Flood forecast unavailable: %s", err)
        return None


def _normal_rain(lat: float, lon: float, start: date, days: int) -> float | None:
    """Average rain (mm) over the same calendar window in each of the last 10 years."""
    try:
        first_year = start.year - 10
        d = _get(ARCHIVE, {"latitude": lat, "longitude": lon, "daily": "precipitation_sum", "start_date": f"{first_year}-01-01", "end_date": (start - timedelta(days=5)).isoformat()})["daily"]
        window = {(start + timedelta(days=i)).strftime("%m-%d") for i in range(days)}
        totals: dict[int, float] = {}
        for day, rain in zip(d["time"], d["precipitation_sum"]):
            if day[5:] in window and int(day[:4]) < start.year:
                totals[int(day[:4])] = totals.get(int(day[:4]), 0.0) + (rain or 0.0)
        return round(sum(totals.values()) / len(totals), 1) if totals else None
    except (httpx.HTTPError, KeyError, ValueError) as err:
        log.warning("Climate normal unavailable: %s", err)
        return None


def hazard_inputs(lat: float, lon: float) -> dict:
    key = (round(lat, 2), round(lon, 2), date.today().isoformat())
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    # The three sources are independent: fetch them at the same time.
    with ThreadPoolExecutor(max_workers=3) as pool:
        weather_job = pool.submit(_forecast, lat, lon)
        flood_job = pool.submit(_flood, lat, lon)
        normal_job = pool.submit(_normal_rain, lat, lon, date.today(), 16)
        data = {"weather": weather_job.result(), "flood": flood_job.result(), "normal_rain_mm": normal_job.result()}
    _cache[key] = (time.time(), data)
    return data
