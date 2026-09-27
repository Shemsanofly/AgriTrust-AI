"""Crop planting recommendations from soil type (transparent agronomic rules).

Not machine learning. Suitability scores are defaults for common Tanzanian
smallholder crops and should be calibrated with local extension data.
"""

from dataclasses import dataclass, field
from typing import Any

from ..i18n import bi, crop_name

MODEL_VERSION = "planting-soil-rules-v0.1"

# fit: excellent | good | fair | poor
SOIL_CROP_FIT: dict[str, dict[str, str]] = {
    "loam": {
        "maize": "excellent",
        "beans": "excellent",
        "rice": "fair",
        "sorghum": "good",
        "sunflower": "excellent",
    },
    "sandy loam": {
        "maize": "good",
        "beans": "good",
        "rice": "poor",
        "sorghum": "excellent",
        "sunflower": "excellent",
    },
    "sandy": {
        "maize": "fair",
        "beans": "fair",
        "rice": "poor",
        "sorghum": "excellent",
        "sunflower": "good",
    },
    "clay": {
        "maize": "good",
        "beans": "fair",
        "rice": "excellent",
        "sorghum": "good",
        "sunflower": "fair",
    },
}

FIT_RANK = {"excellent": 0, "good": 1, "fair": 2, "poor": 3}
FIT_BY_RANK = {v: k for k, v in FIT_RANK.items()}

# Preferred topsoil pH range, salinity threshold (EC dS/m before yield loss, FAO 29)
# and water need. Each limit the farm breaks lowers the soil-type fit by one step.
CROP_LIMITS: dict[str, dict[str, Any]] = {
    "maize": {"ph": (5.5, 7.5), "ec_max": 1.7, "water": "medium"},
    "beans": {"ph": (6.0, 7.5), "ec_max": 1.0, "water": "medium"},
    "rice": {"ph": (5.0, 7.5), "ec_max": 3.0, "water": "high"},
    "sorghum": {"ph": (5.5, 8.5), "ec_max": 6.8, "water": "low"},
    "sunflower": {"ph": (6.0, 7.5), "ec_max": 4.8, "water": "low"},
}

DRY_MOISTURE_PCT = 30.0  # matches the "initial" refill point in irrigation.CROP_PROFILES
GOOD_RAIN_WEEK_MM = 25.0
SOME_RAIN_WEEK_MM = 10.0
IRRIGATED = ("drip", "sprinkler", "furrow")


@dataclass
class PlantingAdvice:
    headline: dict[str, str]
    soil_summary: dict[str, str]
    tips: list[dict[str, str]] = field(default_factory=list)
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    current_crop: dict[str, Any] | None = None
    timing: dict[str, Any] | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    model_version: str = MODEL_VERSION


def ph_band(ph: float) -> str:
    if ph < 5.5:
        return "acidic"
    if ph < 6.6:
        return "slightly_acidic"
    if ph <= 7.3:
        return "neutral"
    return "alkaline"


def soil_profile_notes(ph: float | None, nutrients: dict[str, str | None]) -> dict[str, Any]:
    """pH band and nutrient notes (rules). Empty when no soil test is recorded."""
    notes = []
    for key, level in nutrients.items():
        if level == "low":
            notes.append(bi("planting.nutrient.low", nutrient=bi(f"nutrient.{key}")))
    return {
        "ph": ph,
        "ph_band": ph_band(ph) if ph is not None else None,
        "ph_note": bi(f"planting.ph.{ph_band(ph)}", ph=ph) if ph is not None else None,
        "nutrients": nutrients,
        "nutrient_notes": notes,
    }


def _limit_notes(
    crop_type: str,
    ph: float | None,
    salinity_ec: float | None,
    moisture_pct: float | None,
    irrigated: bool,
) -> list[dict[str, str]]:
    limits = CROP_LIMITS.get(crop_type)
    if not limits:
        return []
    name = crop_name(crop_type)
    notes: list[dict[str, str]] = []
    lo, hi = limits["ph"]
    if ph is not None and ph < lo:
        notes.append(bi("planting.limit.ph_low", crop=name, lo=lo, hi=hi, ph=ph))
    elif ph is not None and ph > hi:
        notes.append(bi("planting.limit.ph_high", crop=name, lo=lo, hi=hi, ph=ph))
    if salinity_ec is not None and salinity_ec > limits["ec_max"]:
        notes.append(bi("planting.limit.salinity", crop=name, ec=salinity_ec))
    if moisture_pct is not None and moisture_pct < DRY_MOISTURE_PCT and limits["water"] == "high" and not irrigated:
        notes.append(bi("planting.limit.dry", crop=name, moisture=moisture_pct))
    return notes


def planting_timing(
    moisture_pct: float | None, rain_next_7d_mm: float | None, irrigation_type: str | None
) -> dict[str, Any] | None:
    if moisture_pct is None and rain_next_7d_mm is None:
        return None
    m = moisture_pct if moisture_pct is not None else DRY_MOISTURE_PCT
    rain = rain_next_7d_mm or 0.0
    if m >= DRY_MOISTURE_PCT or rain >= GOOD_RAIN_WEEK_MM:
        action = "plant_now"
    elif irrigation_type in IRRIGATED:
        action = "irrigate_first"
    elif rain >= SOME_RAIN_WEEK_MM:
        action = "plant_after_rain"
    else:
        action = "wait_for_rains"
    return {
        "action": action,
        "moisture_pct": moisture_pct,
        "rain_next_7d_mm": rain_next_7d_mm,
        "text": bi(f"planting.timing.{action}", moisture=round(m), rain=round(rain)),
    }


def recommend(
    soil_type: str,
    current_crop_type: str | None = None,
    irrigation_type: str | None = None,
    *,
    ph: float | None = None,
    salinity_ec: float | None = None,
    moisture_pct: float | None = None,
    rain_next_7d_mm: float | None = None,
) -> PlantingAdvice:
    soil_key = soil_type if soil_type in SOIL_CROP_FIT else "loam"
    soil_label = bi(f"planting.soil.{soil_key}")
    irrigated = irrigation_type in IRRIGATED
    fits: dict[str, str] = {}
    limit_notes: dict[str, list[dict[str, str]]] = {}
    for crop_type, base_fit in SOIL_CROP_FIT[soil_key].items():
        notes = _limit_notes(crop_type, ph, salinity_ec, moisture_pct, irrigated)
        rank = min(FIT_RANK[base_fit] + len(notes), FIT_RANK["poor"])
        fits[crop_type] = FIT_BY_RANK[rank]
        limit_notes[crop_type] = notes
    inputs: dict[str, Any] = {
        "soil_type": soil_key,
        "irrigation_type": irrigation_type,
        "current_crop_type": current_crop_type,
        "ph": ph,
        "salinity_ec": salinity_ec,
        "moisture_pct": moisture_pct,
        "rain_next_7d_mm": rain_next_7d_mm,
    }

    recommendations: list[dict[str, Any]] = []
    for crop_type, fit in sorted(fits.items(), key=lambda kv: (FIT_RANK.get(kv[1], 9), kv[0])):
        name = crop_name(crop_type)
        recommendations.append(
            {
                "crop_type": crop_type,
                "fit": fit,
                "fit_label": bi(f"planting.fit.{fit}"),
                "name": name,
                "reason": bi(f"planting.reason.{fit}", crop=name, soil=soil_label),
                "limits": limit_notes[crop_type],
            }
        )

    top = [r for r in recommendations if r["fit"] in ("excellent", "good")]
    crops = {
        "en": ", ".join(r["name"]["en"] for r in top[:3]),
        "sw": ", ".join(r["name"]["sw"] for r in top[:3]),
    }

    tips = [bi(f"planting.tip.{soil_key}"), bi("planting.tip.general")]
    if irrigation_type == "rainfed":
        tips.append(bi("planting.tip.rainfed"))
    elif irrigation_type in ("drip", "sprinkler", "furrow"):
        tips.append(bi("planting.tip.irrigated", method=bi(f"planting.irrigation.{irrigation_type}")))

    current: dict[str, Any] | None = None
    if current_crop_type and current_crop_type in fits:
        fit = fits[current_crop_type]
        name = crop_name(current_crop_type)
        current = {
            "crop_type": current_crop_type,
            "fit": fit,
            "fit_label": bi(f"planting.fit.{fit}"),
            "name": name,
            "note": bi(f"planting.current.{fit}", crop=name, soil=soil_label),
        }

    return PlantingAdvice(
        headline=bi("planting.headline", soil=soil_label, crops=crops),
        soil_summary=bi(f"planting.summary.{soil_key}"),
        tips=tips,
        recommendations=recommendations,
        current_crop=current,
        timing=planting_timing(moisture_pct, rain_next_7d_mm, irrigation_type),
        inputs=inputs,
    )
