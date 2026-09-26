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


@dataclass
class PlantingAdvice:
    headline: dict[str, str]
    soil_summary: dict[str, str]
    tips: list[dict[str, str]] = field(default_factory=list)
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    current_crop: dict[str, Any] | None = None
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


def recommend(soil_type: str, current_crop_type: str | None = None, irrigation_type: str | None = None) -> PlantingAdvice:
    soil_key = soil_type if soil_type in SOIL_CROP_FIT else "loam"
    soil_label = bi(f"planting.soil.{soil_key}")
    fits = SOIL_CROP_FIT[soil_key]
    inputs: dict[str, Any] = {
        "soil_type": soil_key,
        "irrigation_type": irrigation_type,
        "current_crop_type": current_crop_type,
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
        inputs=inputs,
    )
