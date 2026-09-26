"""Irrigation recommendation: rules + a simple soil water balance (README §8).

Not machine learning. Thresholds are agronomic defaults that must be calibrated per
soil and crop with pilot data."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..i18n import bi, crop_name
from ..integrations.open_meteo import Forecast

MODEL_VERSION = "irrigation-rules-v0.1"
MAX_APPLICATION_MM = 30.0
STALE_HOURS = 6

# Volumetric soil moisture (%) thresholds for a loam soil.
CROP_PROFILES: dict[str, dict[str, Any]] = {
    "maize": {
        "field_capacity": 42.0,
        "refill": {"initial": 30.0, "vegetative": 28.0, "flowering": 32.0, "maturity": 22.0},
        "root_depth_mm": {"initial": 200, "vegetative": 400, "flowering": 600, "maturity": 600},
    },
    "beans": {
        "field_capacity": 40.0,
        "refill": {"initial": 30.0, "vegetative": 28.0, "flowering": 31.0, "maturity": 22.0},
        "root_depth_mm": {"initial": 150, "vegetative": 300, "flowering": 450, "maturity": 450},
    },
}
DRY_ALERT_PCT = 18.0
HEAT_ALERT_C = 35.0


@dataclass
class Advice:
    action: str  # IRRIGATE | SKIP_RAIN | NO_ACTION | CHECK_SENSOR
    amount_mm: float
    when: dict[str, str]
    headline: dict[str, str]
    reasons: list[dict[str, str]] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    model_version: str = MODEL_VERSION


def recommend(
    crop_type: str,
    stage: str,
    moisture_pct: float | None,
    reading_age_hours: float | None,
    forecast: Forecast,
    local_now: datetime,
) -> Advice:
    profile = CROP_PROFILES.get(crop_type, CROP_PROFILES["maize"])
    stage = stage if stage in profile["refill"] else "vegetative"
    threshold = profile["refill"][stage]
    rain48 = forecast.rain_next(2)
    today = forecast.days[0] if forecast.days else None
    inputs: dict[str, Any] = {
        "crop_type": crop_type,
        "stage": stage,
        "moisture_pct": moisture_pct,
        "refill_threshold_pct": threshold,
        "rain_next_48h_mm": rain48,
        "et0_today_mm": today.et0_mm if today else None,
        "tmax_today_c": today.tmax_c if today else None,
        "weather_source": forecast.source,
    }
    extra: list[dict[str, str]] = []
    if forecast.simulated:
        extra.append(bi("irrigation.reason.weather_simulated"))

    if moisture_pct is None or reading_age_hours is None or reading_age_hours > STALE_HOURS:
        return Advice(
            action="CHECK_SENSOR",
            amount_mm=0,
            when=bi("irrigation.when.none"),
            headline=bi("irrigation.headline.check_sensor"),
            reasons=[bi("irrigation.reason.no_data", hours=STALE_HOURS), *extra],
            inputs=inputs,
        )

    crop = crop_name(crop_type)
    stage_text = bi(f"stage.{stage}")
    if moisture_pct >= threshold:
        return Advice(
            action="NO_ACTION",
            amount_mm=0,
            when=bi("irrigation.when.none"),
            headline=bi("irrigation.headline.no_action"),
            reasons=[bi("irrigation.reason.moisture_ok", moisture=round(moisture_pct, 1), threshold=threshold), *extra],
            inputs=inputs,
        )

    deficit = round((profile["field_capacity"] - moisture_pct) / 100 * profile["root_depth_mm"][stage], 1)
    inputs["deficit_mm"] = deficit
    reasons = [
        bi(
            "irrigation.reason.moisture_below",
            moisture=round(moisture_pct, 1),
            threshold=threshold,
            crop=crop,
            stage=stage_text,
        )
    ]
    effective_rain = rain48 * 0.8
    if effective_rain >= deficit * 0.5:
        reasons.append(bi("irrigation.reason.rain_expected", rain=rain48, deficit=deficit))
        return Advice(
            action="SKIP_RAIN",
            amount_mm=0,
            when=bi("irrigation.when.none"),
            headline=bi("irrigation.headline.skip_rain"),
            reasons=reasons + extra,
            inputs=inputs,
        )

    amount = round(min(MAX_APPLICATION_MM, max(5.0, deficit - effective_rain)))
    reasons.append(bi("irrigation.reason.no_rain", rain=rain48))
    if today and today.et0_mm >= 5:
        reasons.append(bi("irrigation.reason.high_et", et0=today.et0_mm))
    if today and today.tmax_c >= 30:
        reasons.append(bi("irrigation.reason.hot", tmax=today.tmax_c))

    very_dry = moisture_pct < threshold - 8
    if local_now.hour < 8:
        when_key = "today_morning"
    elif very_dry and local_now.hour < 16:
        when_key = "today_evening"
    else:
        when_key = "tomorrow_morning"
    when = bi(f"irrigation.when.{when_key}")
    return Advice(
        action="IRRIGATE",
        amount_mm=amount,
        when=when,
        headline=bi("irrigation.headline.irrigate", when=when, mm=amount),
        reasons=reasons + extra,
        inputs=inputs,
    )
