"""Location-based farm setup suggestions.

This is a transparent rules model for demo and extension-officer review. It
does not claim a lab-grade soil classification; it gives a starting point that
the farmer can override.
"""

from dataclasses import dataclass, field
from typing import Any

MODEL_VERSION = "farm-setup-location-rules-v0.1"


@dataclass(frozen=True)
class FarmSetupSuggestion:
    soil_type: str
    crop_type: str
    irrigation_type: str
    soil_moisture_pct: float
    soil_temperature_c: float
    soil_ph: float
    soil_nitrogen: str
    soil_phosphorus: str
    soil_potassium: str
    confidence: str
    reasons: list[dict[str, str]] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    source: str = "ai_location_rules"
    model_version: str = MODEL_VERSION


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _reason(en: str, sw: str) -> dict[str, str]:
    return {"en": en, "sw": sw}


def predict_setup(lat: float, lon: float, region: str | None = None) -> FarmSetupSuggestion:
    r = _norm(region)
    inputs = {"lat": lat, "lon": lon, "region": region}

    if r in {"dodoma", "singida"} or (-7.9 <= lat <= -3.5 and 33.0 <= lon <= 36.8):
        return FarmSetupSuggestion(
            soil_type="sandy loam",
            crop_type="sorghum",
            irrigation_type="rainfed",
            soil_moisture_pct=18.0,
            soil_temperature_c=31.0,
            soil_ph=7.2,
            soil_nitrogen="low",
            soil_phosphorus="medium",
            soil_potassium="medium",
            confidence="high" if r in {"dodoma", "singida"} else "medium",
            reasons=[
                _reason(
                    "Central semi-arid zone: sandy loam soils and low rainfall favour drought-tolerant crops.",
                    "Ukanda wa kati wenye ukame: udongo wa sandy loam na mvua chache hufaa mazao yanayostahimili ukame.",
                ),
                _reason(
                    "Sorghum is recommended first; sunflower is also a good option for this profile.",
                    "Mtama unapendekezwa kwanza; alizeti pia ni chaguo zuri kwa wasifu huu.",
                ),
            ],
            inputs=inputs,
        )

    if r in {"mbeya", "iringa", "njombe", "rukwa"} or (-10.8 <= lat <= -7.0 and 31.0 <= lon <= 36.5):
        return FarmSetupSuggestion(
            soil_type="loam",
            crop_type="maize",
            irrigation_type="rainfed",
            soil_moisture_pct=32.0,
            soil_temperature_c=22.0,
            soil_ph=6.1,
            soil_nitrogen="medium",
            soil_phosphorus="medium",
            soil_potassium="high",
            confidence="high" if r in {"mbeya", "iringa", "njombe", "rukwa"} else "medium",
            reasons=[
                _reason(
                    "Southern highland conditions commonly support loam soils and reliable seasonal rainfall.",
                    "Nyanda za juu kusini mara nyingi zina udongo wa loam na mvua za msimu zinazoaminika.",
                ),
                _reason(
                    "Maize is recommended first; beans are a strong companion or rotation crop.",
                    "Mahindi yanapendekezwa kwanza; maharage yanafaa kama zao shirikishi au la mzunguko.",
                ),
            ],
            inputs=inputs,
        )

    if r in {"morogoro", "pwani", "dar es salaam", "lindi", "mtwara"} or (-10.8 <= lat <= -5.0 and 37.0 <= lon <= 40.8):
        return FarmSetupSuggestion(
            soil_type="clay",
            crop_type="rice",
            irrigation_type="furrow",
            soil_moisture_pct=38.0,
            soil_temperature_c=28.0,
            soil_ph=6.4,
            soil_nitrogen="medium",
            soil_phosphorus="low",
            soil_potassium="medium",
            confidence="medium",
            reasons=[
                _reason(
                    "Humid lowland and coastal areas often include heavier soils suitable for paddy production.",
                    "Maeneo yenye unyevunyevu na tambarare za pwani mara nyingi yana udongo mzito unaofaa mpunga.",
                )
            ],
            inputs=inputs,
        )

    return FarmSetupSuggestion(
        soil_type="loam",
        crop_type="maize",
        irrigation_type="rainfed",
        soil_moisture_pct=28.0,
        soil_temperature_c=25.0,
        soil_ph=6.5,
        soil_nitrogen="medium",
        soil_phosphorus="medium",
        soil_potassium="medium",
        confidence="low",
        reasons=[
            _reason(
                "No specific local soil rule matched, so the setup starts with a conservative mixed-farming profile.",
                "Hakuna kanuni mahususi ya eneo iliyolingana, hivyo mfumo umeanza na wasifu salama wa kilimo mchanganyiko.",
            )
        ],
        inputs=inputs,
    )
