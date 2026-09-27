"""Ghala room outlook: short-range temperature/humidity forecast from the room sensors
and quick actions (open or close windows, lift bags, cool at night).

Method: least-squares trend over the last few hours of readings, projected a few hours
ahead, then transparent rules that compare the room with the outside air."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from ..i18n import bi
from ..integrations.open_meteo import CurrentConditions
from .spoilage import LIMITS

MODEL_VERSION = "ghala-trend-rules-v0.1"
HORIZON_HOURS = 6
TREND_WINDOW_HOURS = 6
DRIER_OUTSIDE_MARGIN = 5.0  # outside RH must be this much lower before opening windows helps
COOLER_OUTSIDE_MARGIN = 2.0


@dataclass
class GhalaOutlook:
    temp_now: float | None
    rh_now: float | None
    temp_pred: float | None
    rh_pred: float | None
    horizon_hours: int
    actions: list[dict[str, str]] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    model_version: str = MODEL_VERSION


def _slope_per_hour(points: list[tuple[float, float]]) -> float:
    if len(points) < 2:
        return 0.0
    n = len(points)
    mx = sum(x for x, _ in points) / n
    my = sum(y for _, y in points) / n
    var = sum((x - mx) ** 2 for x, _ in points)
    if var == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in points) / var


def project(series: list[tuple[datetime, float, float]], horizon_hours: int = HORIZON_HOURS) -> tuple[float, float, float, float] | None:
    """series: (ts, temperature_c, humidity_pct), oldest first. Returns (temp_now, rh_now, temp_pred, rh_pred)."""
    if not series:
        return None
    last_ts = series[-1][0]
    recent = [r for r in series if r[0] >= last_ts - timedelta(hours=TREND_WINDOW_HOURS)]
    hours = [((ts - last_ts).total_seconds() / 3600) for ts, _, _ in recent]
    t_slope = _slope_per_hour([(h, r[1]) for h, r in zip(hours, recent)])
    rh_slope = _slope_per_hour([(h, r[2]) for h, r in zip(hours, recent)])
    temp_now, rh_now = series[-1][1], series[-1][2]
    temp_pred = round(temp_now + t_slope * horizon_hours, 1)
    rh_pred = round(min(100.0, max(0.0, rh_now + rh_slope * horizon_hours)), 1)
    return round(temp_now, 1), round(rh_now, 1), temp_pred, rh_pred


def quick_actions(
    temp_now: float, rh_now: float, temp_pred: float, rh_pred: float, outside: CurrentConditions | None, crop_type: str = "maize"
) -> list[dict[str, str]]:
    rh_ideal, rh_unsafe, t_ideal, _t_unsafe = LIMITS.get(crop_type, LIMITS["maize"])
    actions: list[dict[str, str]] = []
    if rh_now < rh_unsafe <= rh_pred:
        actions.append(bi("ghala.act.rising", hours=HORIZON_HOURS, rh=round(rh_pred)))
    if max(rh_now, rh_pred) >= rh_ideal:
        if outside and outside.humidity_pct < rh_now - DRIER_OUTSIDE_MARGIN:
            actions.append(bi("ghala.act.open_windows", outside=round(outside.humidity_pct)))
        elif outside:
            actions.append(bi("ghala.act.close_windows", outside=round(outside.humidity_pct)))
        else:
            actions.append(bi("ghala.act.ventilate"))
        actions.append(bi("ghala.act.lift_bags"))
    if max(temp_now, temp_pred) >= t_ideal:
        if outside and outside.temperature_c < temp_now - COOLER_OUTSIDE_MARGIN:
            actions.append(bi("ghala.act.cool_air", outside=round(outside.temperature_c)))
        else:
            actions.append(bi("ghala.act.night_air"))
    if not actions:
        actions.append(bi("ghala.act.ok"))
    return actions


def outlook(
    series: list[tuple[datetime, float, float]], outside: CurrentConditions | None, crop_type: str = "maize"
) -> GhalaOutlook:
    projected = project(series)
    inputs: dict[str, Any] = {
        "reading_count": len(series),
        "outside_temperature_c": outside.temperature_c if outside else None,
        "outside_humidity_pct": outside.humidity_pct if outside else None,
        "outside_source": outside.source if outside else None,
        "crop_type": crop_type,
    }
    if not projected:
        return GhalaOutlook(None, None, None, None, HORIZON_HOURS, [bi("spoilage.headline.UNKNOWN")], inputs)
    temp_now, rh_now, temp_pred, rh_pred = projected
    return GhalaOutlook(
        temp_now, rh_now, temp_pred, rh_pred, HORIZON_HOURS, quick_actions(temp_now, rh_now, temp_pred, rh_pred, outside, crop_type), inputs
    )
