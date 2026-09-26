"""Explainable farmer profile: a transparent weighted scorecard with reason codes,
a rule-based seasonal cash-flow estimate and eligibility-rule product suggestions.

This is decision support, not a credit score. No protected attributes (gender,
ethnicity, religion, ...) are used as inputs."""

from datetime import date
from typing import Any

from sqlmodel import Session, select

from ..i18n import bi, crop_name
from ..models import (
    Alert,
    Crop,
    CropBatch,
    Farm,
    Farmer,
    FarmerRiskProfile,
    Harvest,
    IrrigationAdvice,
    Sale,
    WarehouseReceipt,
)

MODEL_VERSION = "scorecard-v0.1 (hackathon)"
DROUGHT_PRONE_REGIONS = {"dodoma", "singida", "shinyanga", "simiyu", "manyara", "tabora"}
YIELD_KG_PER_ACRE = {"maize": 700.0, "beans": 350.0, "rice": 900.0, "sorghum": 500.0, "sunflower": 400.0}
DEFAULT_PRICE_TZS = {"maize": 750.0, "beans": 2200.0, "rice": 1800.0, "sorghum": 700.0, "sunflower": 1100.0}


def _month_label(d: date) -> str:
    return d.strftime("%Y-%m")


def cash_flow(session: Session, farmer: Farmer, sales: list[Sale]) -> dict[str, Any]:
    farms = list(session.exec(select(Farm).where(Farm.farmer_id == farmer.id)))
    today = date.today()
    upcoming: list[tuple[Farm, Crop]] = []
    for farm in farms:
        for crop in session.exec(select(Crop).where(Crop.farm_id == farm.id)):
            if crop.expected_harvest_date and crop.expected_harvest_date >= today and crop.growth_stage != "harvested":
                upcoming.append((farm, crop))
    if not upcoming:
        return {"next_harvest_month": None, "expected_income_range_tzs": None, "method": "rules"}
    farm, crop = min(upcoming, key=lambda fc: fc[1].expected_harvest_date)
    kg_sold = sum(s.quantity_kg for s in sales)
    price = (sum(s.amount for s in sales) / kg_sold) if kg_sold else DEFAULT_PRICE_TZS.get(crop.crop_type, 750.0)
    expected_kg = farm.acreage * YIELD_KG_PER_ACRE.get(crop.crop_type, 600.0)
    low, high = round(expected_kg * price * 0.7, -3), round(expected_kg * price * 1.1, -3)
    months = []
    cursor = date(today.year, today.month, 1)
    harvest_month = date(crop.expected_harvest_date.year, crop.expected_harvest_date.month, 1)
    while cursor <= harvest_month:
        months.append({"month": _month_label(cursor), "income_tzs": [low, high] if cursor == harvest_month else [0, 0]})
        cursor = date(cursor.year + (cursor.month // 12), cursor.month % 12 + 1, 1)
    return {
        "next_harvest_month": _month_label(crop.expected_harvest_date),
        "crop_type": crop.crop_type,
        "expected_yield_kg": round(expected_kg),
        "price_per_kg_tzs": round(price),
        "price_source": "verified_sales" if kg_sold else "default_market_price",
        "expected_income_range_tzs": [low, high],
        "monthly": months,
        "method": "rules",
    }


def build_profile(session: Session, farmer: Farmer) -> FarmerRiskProfile:
    farms = list(session.exec(select(Farm).where(Farm.farmer_id == farmer.id)))
    farm_ids = [f.id for f in farms]
    crops = list(session.exec(select(Crop).where(Crop.farm_id.in_(farm_ids)))) if farm_ids else []  # type: ignore[union-attr]
    advice = list(session.exec(select(IrrigationAdvice).where(IrrigationAdvice.farm_id.in_(farm_ids)))) if farm_ids else []  # type: ignore[union-attr]
    actionable = [a for a in advice if a.action in ("IRRIGATE", "SKIP_RAIN") and a.followed is not None]
    followed = sum(1 for a in actionable if a.followed)
    sales = list(
        session.exec(select(Sale).where(Sale.farmer_id == farmer.id, Sale.completed_at.is_not(None)))  # type: ignore[union-attr]
    )
    receipts = list(session.exec(select(WarehouseReceipt).where(WarehouseReceipt.owner_farmer_id == farmer.id)))
    batches = list(session.exec(select(CropBatch).where(CropBatch.farmer_id == farmer.id)))
    harvest_ids = [b.harvest_id for b in batches]
    harvests = list(session.exec(select(Harvest).where(Harvest.id.in_(harvest_ids)))) if harvest_ids else []  # type: ignore[union-attr]
    storage_alerts = list(
        session.exec(
            select(Alert).where(
                Alert.user_id == farmer.user_id,
                Alert.kind == "SPOILAGE_RISK",
                Alert.severity == "CRITICAL",
                Alert.resolved_at.is_(None),  # type: ignore[union-attr]
            )
        )
    )

    score = 50.0
    positive: list[dict[str, str]] = []
    risks: list[dict[str, str]] = []

    if len(actionable) >= 3:
        rate = followed / len(actionable)
        if rate >= 0.8:
            score += 15
            positive.append(bi("profile.pos.adherence", followed=followed, total=len(actionable)))
        elif rate < 0.5:
            score -= 10
            risks.append(bi("profile.risk.adherence_low", followed=followed, total=len(actionable)))
        else:
            score += 5
            positive.append(bi("profile.pos.adherence", followed=followed, total=len(actionable)))

    if receipts:
        if storage_alerts:
            score -= 5 * min(3, len(storage_alerts))
            risks.append(bi("profile.risk.storage_alerts", count=len(storage_alerts)))
        else:
            score += 10
            positive.append(bi("profile.pos.storage_ok"))
        score += 5
        positive.append(bi("profile.pos.receipts", count=len(receipts), kg=round(sum(r.quantity_kg for r in receipts))))

    buyers = {s.buyer_id for s in sales}
    if sales:
        score += min(20, 7 * len(sales)) + (5 if len(buyers) >= 2 else 0)
        positive.append(bi("profile.pos.sales", sales=len(sales), buyers=len(buyers)))
    else:
        score -= 5
        risks.append(bi("profile.risk.no_sales"))

    if farmer.cooperative:
        score += 5
        positive.append(bi("profile.pos.cooperative", name=farmer.cooperative))

    drought = farmer.region.strip().lower() in DROUGHT_PRONE_REGIONS
    crop_types = {c.crop_type for c in crops}
    if len(crop_types) == 1 and drought:
        score -= 5
        risks.append(bi("profile.risk.single_crop", crop=crop_name(next(iter(crop_types)))))
    elif drought:
        score -= 5
        risks.append(bi("profile.risk.drought_region", region=farmer.region))

    seasons = len({h.harvest_date.year for h in harvests})
    if seasons <= 1:
        score -= 5
        risks.append(bi("profile.risk.short_history", seasons=max(seasons, 1) if harvests else 0))
    else:
        score += 5 * min(3, seasons - 1)
        positive.append(bi("profile.pos.long_history", seasons=seasons))

    score = max(0.0, min(100.0, score))
    band = "LOW" if score >= 70 else "MEDIUM" if score >= 50 else "HIGH"

    flow = cash_flow(session, farmer, sales)
    products: list[dict[str, Any]] = []
    if flow.get("expected_income_range_tzs"):
        low = flow["expected_income_range_tzs"][0]
        products.append(
            {
                "type": "input_loan",
                "max_amount_tzs": round(low * 0.3, -3),
                "repayment_month": flow["next_harvest_month"],
                "reason": bi("profile.product.input_loan", month=flow["next_harvest_month"]),
            }
        )
    if drought:
        products.append({"type": "weather_index_insurance", "reason": bi("profile.product.weather_index_insurance")})
    active_receipts = [r for r in receipts if r.status in ("ACTIVE", "PARTIALLY_RELEASED")]
    if active_receipts:
        products.append({"type": "storage_cover", "reason": bi("profile.product.storage_cover")})
        products.append(
            {"type": "storage_backed_loan", "status": "FUTURE", "reason": bi("profile.product.storage_backed_loan")}
        )

    profile = FarmerRiskProfile(
        farmer_id=farmer.id,
        model_version=MODEL_VERSION,
        risk_band=band,
        score=round(score, 1),
        positive_factors=positive,
        risk_factors=risks,
        cash_flow=flow,
        suggested_products=products,
        inputs={
            "advice_actionable": len(actionable),
            "advice_followed": followed,
            "verified_sales": len(sales),
            "distinct_buyers": len(buyers),
            "receipts": len(receipts),
            "unresolved_storage_alerts": len(storage_alerts),
            "seasons": seasons,
            "crop_types": sorted(crop_types),
            "drought_prone_region": drought,
        },
    )
    session.add(profile)
    session.flush()
    return profile


def profile_json(p: FarmerRiskProfile, farmer: Farmer) -> dict[str, Any]:
    return {
        "farmer_id": farmer.public_id,
        "display_name": farmer.display_name,
        "region": farmer.region,
        "generated_at": p.generated_at.isoformat(),
        "model_version": p.model_version,
        "risk_band": p.risk_band,
        "score": p.score,
        "positive_factors": p.positive_factors,
        "risk_factors": p.risk_factors,
        "cash_flow_estimate": p.cash_flow,
        "suggested_products": p.suggested_products,
        "inputs": p.inputs,
        "disclaimer": bi("profile.disclaimer"),
    }
