"""Storage (spoilage) risk from ghala temperature and humidity (README §8).

MVP method: transparent rules from safe-storage ranges for dry grain. A classifier
trained on synthetic data is a planned addition; real accuracy needs real outcomes."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..i18n import bi

MODEL_VERSION = "spoilage-rules-v0.1"

LIMITS = {
    # crop: (rh_ideal, rh_unsafe, temp_ideal, temp_unsafe)
    "maize": (65.0, 75.0, 27.0, 32.0),
    "beans": (65.0, 75.0, 25.0, 30.0),
    "rice": (65.0, 75.0, 27.0, 32.0),
}
HUMID_HOURS_LIMIT = 70.0


@dataclass
class SpoilageAssessment:
    level: str  # LOW | MEDIUM | HIGH | UNKNOWN
    score: int
    drivers: list[dict[str, str]]
    action: dict[str, str]
    stats: dict[str, Any] = field(default_factory=dict)
    model_version: str = MODEL_VERSION


def assess(
    readings: list[tuple[datetime, float, float]],
    crop_type: str = "maize",
    days_in_storage: int = 0,
) -> SpoilageAssessment:
    """readings: (timestamp, temperature_c, humidity_pct), oldest first, typically the last 24 h."""
    if not readings:
        return SpoilageAssessment("UNKNOWN", 0, [bi("spoilage.driver.no_data")], bi("spoilage.action.MEDIUM"))
    rh_ideal, rh_unsafe, t_ideal, t_unsafe = LIMITS.get(crop_type, LIMITS["maize"])
    temps = [r[1] for r in readings]
    rhs = [r[2] for r in readings]
    temp_avg, temp_max = sum(temps) / len(temps), max(temps)
    rh_avg, rh_max = sum(rhs) / len(rhs), max(rhs)

    # Hours spent above the humidity limit, from the gaps between consecutive readings.
    humid_hours = 0.0
    for (t0, _, rh0), (t1, _, _) in zip(readings, readings[1:]):
        if rh0 > HUMID_HOURS_LIMIT:
            humid_hours += (t1 - t0).total_seconds() / 3600
    head = rhs[: max(1, len(rhs) // 4)]
    tail = rhs[-max(1, len(rhs) // 4) :]
    rh_trend = sum(tail) / len(tail) - sum(head) / len(head)

    score = 0
    drivers: list[dict[str, str]] = []
    if rh_avg >= rh_unsafe:
        score += 3
        drivers.append(bi("spoilage.driver.rh_high", rh=round(rh_avg, 1), limit=rh_unsafe))
    elif rh_avg >= rh_ideal:
        score += 1
        drivers.append(bi("spoilage.driver.rh_elevated", rh=round(rh_avg, 1), limit=rh_ideal))
    if humid_hours >= 12:
        score += 2
        drivers.append(bi("spoilage.driver.hours_humid", hours=round(humid_hours), limit=HUMID_HOURS_LIMIT))
    elif humid_hours >= 4:
        score += 1
        drivers.append(bi("spoilage.driver.hours_humid", hours=round(humid_hours), limit=HUMID_HOURS_LIMIT))
    if temp_max >= t_unsafe:
        score += 2
        drivers.append(bi("spoilage.driver.temp_high", temp=round(temp_max, 1), limit=t_unsafe))
    elif temp_max >= t_ideal:
        score += 1
        drivers.append(bi("spoilage.driver.temp_high", temp=round(temp_max, 1), limit=t_ideal))
    if rh_trend >= 8:
        score += 1
        drivers.append(bi("spoilage.driver.rising", delta=round(rh_trend)))
    if days_in_storage > 90:
        score += 1
        drivers.append(bi("spoilage.driver.long_storage", days=days_in_storage))

    level = "HIGH" if score >= 4 else "MEDIUM" if score >= 2 else "LOW"
    if not drivers:
        drivers.append(bi("spoilage.driver.safe"))
    return SpoilageAssessment(
        level=level,
        score=score,
        drivers=drivers,
        action=bi(f"spoilage.action.{level}"),
        stats={
            "temp_avg": round(temp_avg, 2),
            "temp_max": round(temp_max, 2),
            "rh_avg": round(rh_avg, 2),
            "rh_max": round(rh_max, 2),
            "hours_above_rh_limit": round(humid_hours, 1),
            "rh_trend": round(rh_trend, 1),
            "reading_count": len(readings),
        },
    )
