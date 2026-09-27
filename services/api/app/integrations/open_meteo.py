"""Open-Meteo weather (free, no API key). Falls back to a deterministic simulated
forecast when offline or when WEATHER_MODE=simulated, and says so in the result."""

import hashlib
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import date, timedelta

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)
_cache: dict[str, tuple[float, "Forecast"]] = {}
# Demo only (DEV_MODE): force a rainy forecast so "delay irrigation" can be shown live.
DEMO_OVERRIDE: dict[str, str | None] = {"weather": None}
_CACHE_SECONDS = 1800


@dataclass
class DayForecast:
    day: date
    rain_mm: float
    et0_mm: float
    tmax_c: float


@dataclass
class Forecast:
    days: list[DayForecast]
    simulated: bool
    source: str
    notes: list[str] = field(default_factory=list)

    def rain_next(self, n_days: int) -> float:
        return round(sum(d.rain_mm for d in self.days[:n_days]), 1)


def _simulated(lat: float, lon: float, start: date, n_days: int, dry: bool = True) -> Forecast:
    seed = int(hashlib.sha256(f"{lat:.2f},{lon:.2f}".encode()).hexdigest()[:6], 16)
    days = []
    for i in range(n_days):
        wave = math.sin((seed % 7 + i) / 2.0)
        rain = 0.0 if dry and i < 3 else max(0.0, round(3 + 4 * wave, 1))
        days.append(DayForecast(start + timedelta(days=i), rain, round(5.2 + 0.6 * wave, 1), round(30.5 + 2 * wave, 1)))
    return Forecast(days=days, simulated=True, source="simulated")


def get_forecast(lat: float, lon: float, n_days: int = 7) -> Forecast:
    settings = get_settings()
    today = date.today()
    if DEMO_OVERRIDE["weather"] == "rain":
        fc = _simulated(lat, lon, today, n_days, dry=False)
        fc.days[0].rain_mm, fc.days[1].rain_mm = 14.0, 10.0
        return fc
    if settings.weather_mode != "live" or DEMO_OVERRIDE["weather"] == "dry":
        return _simulated(lat, lon, today, n_days)
    key = f"{lat:.2f},{lon:.2f},{n_days}"
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < _CACHE_SECONDS:
        return cached[1]
    try:
        resp = httpx.get(
            f"{settings.open_meteo_base}/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "precipitation_sum,et0_fao_evapotranspiration,temperature_2m_max",
                "forecast_days": n_days,
                "timezone": "Africa/Dar_es_Salaam",
            },
            timeout=6,
        )
        resp.raise_for_status()
        daily = resp.json()["daily"]
        days = [
            DayForecast(date.fromisoformat(d), float(r or 0), float(e or 0), float(t or 0))
            for d, r, e, t in zip(
                daily["time"],
                daily["precipitation_sum"],
                daily["et0_fao_evapotranspiration"],
                daily["temperature_2m_max"],
            )
        ]
        forecast = Forecast(days=days, simulated=False, source="open-meteo")
        _cache[key] = (time.time(), forecast)
        return forecast
    except Exception as exc:  # offline demo, rate limit, etc.
        log.warning("Open-Meteo unavailable (%s); using simulated forecast", exc)
        return _simulated(lat, lon, today, n_days)


@dataclass
class CurrentConditions:
    temperature_c: float
    humidity_pct: float
    soil_moisture_pct: float  # volumetric, 3-9 cm
    simulated: bool
    source: str


_current_cache: dict[str, tuple[float, CurrentConditions]] = {}


def _simulated_current(lat: float, lon: float) -> CurrentConditions:
    seed = int(hashlib.sha256(f"current:{lat:.2f},{lon:.2f}".encode()).hexdigest()[:6], 16)
    return CurrentConditions(
        temperature_c=float(22 + seed % 9),
        humidity_pct=float(50 + (seed >> 4) % 35),
        soil_moisture_pct=float(18 + (seed >> 8) % 25),
        simulated=True,
        source="simulated",
    )


def get_current_conditions(lat: float, lon: float) -> CurrentConditions:
    """Air temperature, relative humidity and topsoil moisture at a location right now."""
    settings = get_settings()
    if settings.weather_mode != "live":
        return _simulated_current(lat, lon)
    key = f"{lat:.2f},{lon:.2f}"
    cached = _current_cache.get(key)
    if cached and time.time() - cached[0] < _CACHE_SECONDS:
        return cached[1]
    try:
        resp = httpx.get(
            f"{settings.open_meteo_base}/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,soil_moisture_3_to_9cm",
                "timezone": "Africa/Dar_es_Salaam",
            },
            timeout=4,
        )
        resp.raise_for_status()
        cur = resp.json()["current"]
        result = CurrentConditions(
            temperature_c=round(float(cur["temperature_2m"]), 1),
            humidity_pct=round(float(cur["relative_humidity_2m"]), 1),
            soil_moisture_pct=round(float(cur["soil_moisture_3_to_9cm"]) * 100, 1),
            simulated=False,
            source="open-meteo",
        )
        _current_cache[key] = (time.time(), result)
        return result
    except Exception as exc:
        log.warning("Open-Meteo current conditions unavailable (%s); using simulated values", exc)
        return _simulated_current(lat, lon)


def get_soil_moisture(lat: float, lon: float) -> tuple[float, bool, str]:
    """Current topsoil moisture (3-9 cm) as volumetric %. Returns (pct, simulated, source)."""
    cur = get_current_conditions(lat, lon)
    return cur.soil_moisture_pct, cur.simulated, cur.source


def get_rainfall_total(lat: float, lon: float, start: date, end: date) -> tuple[float, bool, str]:
    """Cumulative rainfall for a past window (used by the parametric insurance demo).
    Returns (mm, simulated, source)."""
    settings = get_settings()
    if settings.weather_mode == "live":
        try:
            resp = httpx.get(
                "https://archive-api.open-meteo.com/v1/archive",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "start_date": start.isoformat(),
                    "end_date": min(end, date.today() - timedelta(days=2)).isoformat(),
                    "daily": "precipitation_sum",
                    "timezone": "Africa/Dar_es_Salaam",
                },
                timeout=6,
            )
            resp.raise_for_status()
            values = resp.json()["daily"]["precipitation_sum"]
            return round(sum(v or 0 for v in values), 1), False, "open-meteo-archive"
        except Exception as exc:
            log.warning("Open-Meteo archive unavailable (%s); using simulated rainfall", exc)
    n_days = max(1, (end - start).days + 1)
    sim = _simulated(lat, lon, start, n_days, dry=False)
    # A drought-like season for the demo: well below a typical threshold.
    return round(sim.rain_next(n_days) * 0.25, 1), True, "simulated"
