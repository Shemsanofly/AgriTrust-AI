"""Explainable farmer profile: a transparent weighted scorecard with reason codes,
a rule-based seasonal cash-flow estimate and eligibility-rule product suggestions.

This is decision support, not a credit score. No protected attributes (gender,
ethnicity, religion, ...) are used as inputs."""

from datetime import date, timedelta
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

MODEL_VERSION = "credit-5-criteria-v0.3 + credit-lr-v1"
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


# The five credit criteria and their weights in the overall score (sum 100).
CRITERIA_WEIGHTS = {"transactions": 25, "farm": 15, "production": 25, "offtake": 15, "condition": 20}
MOISTURE_OK = (25.0, 55.0)
PH_OK = (5.5, 7.5)
SOIL_TEMP_OK = (15.0, 35.0)


MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    "sw": ["Januari", "Februari", "Machi", "Aprili", "Mei", "Juni", "Julai", "Agosti", "Septemba", "Oktoba", "Novemba", "Desemba"],
}


def _month_name(ym: str) -> dict[str, str]:
    """"2027-03" -> {"en": "March 2027", "sw": "Machi 2027"}."""
    year, month = ym.split("-")
    return {lang: f"{names[int(month) - 1]} {year}" for lang, names in MONTHS.items()}


def _gather(session: Session, farmer: Farmer) -> dict[str, Any]:
    """Everything the farmer has done on the platform that the assessment looks at."""
    farm_rows = list(session.exec(select(Farm).where(Farm.farmer_id == farmer.id)))
    ids = [f.id for f in farm_rows]
    advice_rows = list(session.exec(select(IrrigationAdvice).where(IrrigationAdvice.farm_id.in_(ids)))) if ids else []  # type: ignore[union-attr]
    actionable_rows = [a for a in advice_rows if a.action in ("IRRIGATE", "SKIP_RAIN") and a.followed is not None]
    batch_rows = list(session.exec(select(CropBatch).where(CropBatch.farmer_id == farmer.id)))
    harvest_ids = [b.harvest_id for b in batch_rows]
    return {
        "farms": farm_rows,
        "crops": list(session.exec(select(Crop).where(Crop.farm_id.in_(ids)))) if ids else [],  # type: ignore[union-attr]
        "actionable": actionable_rows,
        "followed": sum(1 for a in actionable_rows if a.followed),
        "sales": list(session.exec(select(Sale).where(Sale.farmer_id == farmer.id, Sale.completed_at.is_not(None)))),  # type: ignore[union-attr]
        "receipts": list(session.exec(select(WarehouseReceipt).where(WarehouseReceipt.owner_farmer_id == farmer.id))),
        "harvests": list(session.exec(select(Harvest).where(Harvest.id.in_(harvest_ids)))) if harvest_ids else [],  # type: ignore[union-attr]
        "storage_alerts": list(
            session.exec(
                select(Alert).where(
                    Alert.user_id == farmer.user_id,
                    Alert.kind == "SPOILAGE_RISK",
                    Alert.severity == "CRITICAL",
                    Alert.resolved_at.is_(None),  # type: ignore[union-attr]
                )
            )
        ),
    }


def ai_features(session: Session, farmer: Farmer, g: dict[str, Any], flow: dict[str, Any], offtake: dict, condition: dict) -> dict[str, float]:
    """The farmer's activities and transactions as the model's raw inputs."""
    from ..models import AuditLog, LoanApplication, SavingsGoal, User, utcnow

    loans = list(session.exec(select(LoanApplication).where(LoanApplication.farmer_id == farmer.id)))
    per_season: dict[int, float] = {}
    for h in g["harvests"]:
        per_season[h.harvest_date.year] = per_season.get(h.harvest_date.year, 0) + h.quantity_kg
    amounts = list(per_season.values())
    if len(amounts) >= 2 and sum(amounts):
        mean = sum(amounts) / len(amounts)
        consistency = max(0.0, 1 - (sum((a - mean) ** 2 for a in amounts) / len(amounts)) ** 0.5 / mean)
    else:
        consistency = 0.5  # unknown with fewer than two seasons
    actionable_rows = g["actionable"]
    user = session.get(User, farmer.user_id)
    since = utcnow() - timedelta(days=90)
    activity = session.exec(select(AuditLog.id).where(AuditLog.actor_user_id == farmer.user_id, AuditLog.ts >= since)).all()
    drought = farmer.region.strip().lower() in DROUGHT_PRONE_REGIONS
    return {
        "sales_count": len(g["sales"]),
        "sales_income": sum(x.amount for x in g["sales"]),
        "distinct_buyers": len({x.buyer_id for x in g["sales"]}),
        "selling_months": len({x.completed_at.strftime("%Y-%m") for x in g["sales"] if x.completed_at}),
        "savings": sum(x.saved_amount for x in session.exec(select(SavingsGoal).where(SavingsGoal.farmer_id == farmer.id))),
        "loans_repaid": sum(1 for x in loans if x.status == "CLOSED"),
        "loans_open": sum(1 for x in loans if x.status in ("DISBURSED", "REPAYING")),
        "seasons": len(per_season),
        "harvest_kg": sum(amounts),
        "harvest_consistency": consistency,
        "ghala_receipts": len(g["receipts"]),
        "storage_alerts": len(g["storage_alerts"]),
        "advice_follow_rate": g["followed"] / len(actionable_rows) if len(actionable_rows) >= 3 else 0.5,
        "acres": sum(f.acreage for f in g["farms"]),
        "drought_rainfed": 1.0 if drought and not any(f.irrigation_type != "rainfed" for f in g["farms"]) else 0.0,
        "offtake_coverage": float(offtake["facts"].get("coverage") or (1.0 if offtake["facts"].get("active_contracts") else 0.0)),
        "soil_condition": condition["score"] / 100,
        "account_age": _record_days(user, g),
        "activity_90d": len(activity),
        "coming_harvest": 1.0 if flow.get("expected_income_range_tzs") else 0.0,
    }


def _record_days(user, g: dict[str, Any]) -> int:
    """How long the farmer has a track record: from the earliest of account, farm, harvest or sale."""
    from datetime import datetime

    from ..models import utcnow

    starts = [user.created_at] if user else []
    starts += [f.created_at for f in g["farms"]]
    starts += [datetime.combine(h.harvest_date, datetime.min.time(), tzinfo=utcnow().tzinfo) for h in g["harvests"]]
    starts += [x.completed_at for x in g["sales"] if x.completed_at]
    starts = [d if d.tzinfo else d.replace(tzinfo=utcnow().tzinfo) for d in starts]
    return max(0, (utcnow() - min(starts)).days) if starts else 0


def _feature_label(name: str, raw: dict[str, float]) -> dict[str, str]:
    v = raw[name]
    if name in ("drought_rainfed", "coming_harvest"):
        return bi(f"ai.f.{name}_{int(v)}")
    if name in ("harvest_consistency", "advice_follow_rate", "offtake_coverage"):
        return bi(f"ai.f.{name}", v=f"{round(v * 100)}%")
    if name == "soil_condition":
        return bi("ai.f.soil_condition", v=round(v * 100))
    if name in ("sales_income", "savings"):
        return bi(f"ai.f.{name}", v=round(v, -3))
    if name == "acres":
        return bi("ai.f.acres", v=round(v, 1))
    return bi(f"ai.f.{name}", v=int(round(v)))


def _real_outcomes(session: Session) -> list[tuple[list[float], int]]:
    """Loans repaid on the platform (CLOSED) become real training examples."""
    from ..models import LoanApplication
    from . import credit_model

    out = []
    repaid = {x.farmer_id for x in session.exec(select(LoanApplication).where(LoanApplication.status == "CLOSED"))}
    for farmer_id in sorted(repaid):
        other = session.get(Farmer, farmer_id)
        if not other:
            continue
        g = _gather(session, other)
        flow = cash_flow(session, other, g["sales"])
        offtake = _offtake(session, other, flow.get("expected_yield_kg"))
        condition = _condition(session, g["farms"], g["actionable"], g["followed"])
        out.append((credit_model.to_vector(ai_features(session, other, g, flow, offtake, condition)), 1))
    return out


def ai_eligibility(session: Session, raw: dict[str, float]) -> dict[str, Any]:
    """The model's verdict: probability of repaying, eligible or not, and why."""
    from . import credit_model

    model = credit_model.get_model(_real_outcomes(session))
    result = credit_model.predict(model, raw)
    ranked = sorted(result["contributions"].items(), key=lambda kv: kv[1])
    helped = [{"key": k, "label": _feature_label(k, raw), "impact": v} for k, v in reversed(ranked) if v > 0.05][:4]
    held_back = [{"key": k, "label": _feature_label(k, raw), "impact": v, "tip": bi(f"ai.tip.{k}")} for k, v in ranked if v < -0.05][:4]
    return {
        "eligible": result["eligible"],
        "probability": result["probability"],
        "threshold": credit_model.THRESHOLD,
        "helped": helped,
        "held_back": held_back,
        "model": model.card,
    }


def _level(score: float) -> str:
    return "good" if score >= 70 else "fair" if score >= 45 else "weak"


def _criterion(key: str, score: float, findings: list[tuple[bool, dict[str, str]]], facts: dict[str, Any]) -> dict[str, Any]:
    score = max(0.0, min(100.0, score))
    return {
        "key": key,
        "title": bi(f"credit.c.{key}"),
        "weight": CRITERIA_WEIGHTS[key],
        "score": round(score),
        "level": _level(score),
        "findings": [{"good": good, "text": text} for good, text in findings],
        "facts": facts,
    }


def _transactions(session: Session, farmer: Farmer, sales: list[Sale]) -> dict[str, Any]:
    """1. Money earned, repaid and saved: shows the farmer can generate and manage cash."""
    from ..models import LoanApplication, SavingsGoal

    loans = list(session.exec(select(LoanApplication).where(LoanApplication.farmer_id == farmer.id)))
    repaid = sum(1 for loan in loans if loan.status == "CLOSED")
    repaying = sum(1 for loan in loans if loan.status == "REPAYING")
    goals = list(session.exec(select(SavingsGoal).where(SavingsGoal.farmer_id == farmer.id)))
    saved = sum(g.saved_amount for g in goals)
    buyers = {s.buyer_id for s in sales}
    income = sum(s.amount for s in sales)
    score, findings = 20.0, []
    if sales:
        score += min(40, 10 * len(sales)) + (10 if len(buyers) >= 2 else 0)
        findings.append((True, bi("credit.tx.sales", sales=len(sales), amount=round(income), buyers=len(buyers))))
    else:
        findings.append((False, bi("credit.tx.no_sales")))
    if repaid:
        score += min(20, 15 * repaid)
        findings.append((True, bi("credit.tx.repaid", count=repaid)))
    if repaying:
        score += 5
        findings.append((True, bi("credit.tx.repaying", count=repaying)))
    if saved > 0:
        score += 10
        findings.append((True, bi("credit.tx.savings", amount=round(saved), goals=len(goals))))
    else:
        findings.append((False, bi("credit.tx.no_savings")))
    facts = {
        "verified_sales": len(sales),
        "income_tzs": round(income),
        "distinct_buyers": len(buyers),
        "loans_repaid": repaid,
        "loans_repaying": repaying,
        "savings_tzs": round(saved),
    }
    return _criterion("transactions", score, findings, facts)


def _farm(farmer: Farmer, farms: list[Farm], crops: list[Crop], price_for) -> dict[str, Any]:
    """2. Size and location: production capacity and the climate risk of where it is."""
    if not farms:
        return _criterion("farm", 20, [(False, bi("credit.farm.no_farm"))], {"acres": 0, "farms": 0})
    acres = sum(f.acreage for f in farms)
    growing = {f.id: next((c.crop_type for c in crops if c.farm_id == f.id and c.growth_stage != "harvested"), "maize") for f in farms}
    kg = sum(f.acreage * YIELD_KG_PER_ACRE.get(growing[f.id], 600.0) for f in farms)
    value = sum(f.acreage * YIELD_KG_PER_ACRE.get(growing[f.id], 600.0) * price_for(growing[f.id]) for f in farms)
    score = 35.0 if acres < 1 else 55.0 if acres < 3 else 70.0 if acres < 10 else 80.0
    findings = [(acres >= 1, bi("credit.farm.size", acres=round(acres, 1), farms=len(farms), kg=round(kg), value=round(value, -3)))]
    if acres < 1:
        findings.append((False, bi("credit.farm.small")))
    drought = farmer.region.strip().lower() in DROUGHT_PRONE_REGIONS
    irrigated = any(f.irrigation_type != "rainfed" for f in farms)
    if not drought:
        score += 10
        findings.append((True, bi("credit.farm.good_zone", region=farmer.region)))
    elif irrigated:
        score += 5
        findings.append((True, bi("credit.farm.drought_irrigated", region=farmer.region)))
    else:
        score -= 15
        findings.append((False, bi("credit.farm.drought_rainfed", region=farmer.region)))
    crop_types = {c.crop_type for c in crops}
    if drought and len(crop_types) == 1:
        score -= 5
        findings.append((False, bi("profile.risk.single_crop", crop=crop_name(next(iter(crop_types))))))
    facts = {
        "acres": round(acres, 1),
        "farms": len(farms),
        "region": farmer.region,
        "drought_prone": drought,
        "irrigated": irrigated,
        "estimated_kg_per_season": round(kg),
        "estimated_value_tzs": round(value, -3),
    }
    return _criterion("farm", score, findings, facts)


def _production(harvests: list[Harvest], receipts: list[WarehouseReceipt], storage_alerts: list[Alert]) -> dict[str, Any]:
    """3. Harvest records across seasons and how consistent they are."""
    if not harvests:
        return _criterion("production", 20, [(False, bi("credit.prod.none"))], {"seasons": 0, "total_kg": 0})
    per_season: dict[int, float] = {}
    for h in harvests:
        per_season[h.harvest_date.year] = per_season.get(h.harvest_date.year, 0) + h.quantity_kg
    seasons = len(per_season)
    total = sum(per_season.values())
    findings: list[tuple[bool, dict[str, str]]] = []
    variation = None
    if seasons == 1:
        score = 50.0
        findings.append((False, bi("credit.prod.short", kg=round(total))))
    else:
        findings.append((True, bi("credit.prod.seasons", seasons=seasons, kg=round(total))))
        mean = total / seasons
        variation = (sum((a - mean) ** 2 for a in per_season.values()) / seasons) ** 0.5 / mean if mean else 1.0
        score = 65.0 + (20 if variation < 0.25 else 5 if variation < 0.5 else -10)
        findings.append((variation < 0.5, bi("credit.prod.consistent" if variation < 0.5 else "credit.prod.variable")))
    if receipts:
        if storage_alerts:
            score -= 5 * min(3, len(storage_alerts))
            findings.append((False, bi("profile.risk.storage_alerts", count=len(storage_alerts))))
        else:
            score += 10
            findings.append((True, bi("profile.pos.receipts", count=len(receipts), kg=round(sum(r.quantity_kg for r in receipts)))))
    facts = {
        "seasons": seasons,
        "total_kg": round(total),
        "variation": round(variation, 2) if variation is not None else None,
        "receipts": len(receipts),
        "unresolved_storage_alerts": len(storage_alerts),
    }
    return _criterion("production", score, findings, facts)


def _offtake(session: Session, farmer: Farmer, expected_kg: float | None) -> dict[str, Any]:
    """4. Buyers who have agreed to buy the coming harvest: market certainty."""
    from ..models import OffTakeContract

    contracts = list(session.exec(select(OffTakeContract).where(OffTakeContract.farmer_id == farmer.id)))
    this_month = _month_label(date.today())
    active = [c for c in contracts if c.status == "ACCEPTED" and c.delivery_month >= this_month]
    fulfilled = sum(1 for c in contracts if c.status == "FULFILLED")
    kg = sum(c.quantity_kg for c in active)
    value = sum(c.quantity_kg * c.price_per_kg for c in active)
    coverage = min(1.0, kg / expected_kg) if expected_kg and kg else None
    findings: list[tuple[bool, dict[str, str]]] = []
    if not active:
        score = 30.0
        findings.append((False, bi("credit.off.none")))
    else:
        findings.append((True, bi("credit.off.active", count=len(active), buyers=len({c.buyer_id for c in active}), kg=round(kg), value=round(value))))
        if coverage is None:
            score = 70.0
        else:
            pct = round(coverage * 100)
            score = 90.0 if coverage >= 0.5 else 75.0 if coverage >= 0.2 else 60.0
            findings.append((coverage >= 0.2, bi("credit.off.coverage" if coverage >= 0.2 else "credit.off.low_coverage", pct=pct)))
    if fulfilled:
        score += min(10, 5 * fulfilled)
        findings.append((True, bi("credit.off.fulfilled", count=fulfilled)))
    facts = {
        "active_contracts": len(active),
        "contracted_kg": round(kg),
        "contracted_value_tzs": round(value),
        "coverage": round(coverage, 2) if coverage is not None else None,
        "fulfilled": fulfilled,
    }
    return _criterion("offtake", score, findings, facts)


def _condition(session: Session, farms: list[Farm], actionable: list[IrrigationAdvice], followed: int) -> dict[str, Any]:
    """5. Soil moisture, pH, temperature and salinity from IoT sensors or AI estimates,
    plus whether the farmer acts on the AI irrigation advice."""
    from ..models import Sensor, SensorReading
    from .farm_setup import estimate_salinity

    if not farms:
        return _criterion("condition", 30, [(False, bi("credit.cond.no_data"))], {})
    farm = max(farms, key=lambda f: f.acreage)
    sensors = {s.id: s for s in session.exec(select(Sensor).where(Sensor.farm_id.in_([f.id for f in farms])))}  # type: ignore[union-attr]

    def latest(metric: str) -> tuple[float, str] | None:
        if not sensors:
            return None
        r = session.exec(
            select(SensorReading)
            .where(SensorReading.sensor_id.in_(list(sensors)), SensorReading.metric == metric)  # type: ignore[union-attr]
            .order_by(SensorReading.ts.desc())  # type: ignore[attr-defined]
        ).first()
        if not r:
            return None
        estimated = r.quality_flag == "ESTIMATE" or sensors[r.sensor_id].device_id.startswith("AI-")
        return r.value, "estimate" if estimated else "sensor"

    def src(kind: str) -> dict[str, str]:
        return bi(f"credit.src.{kind}")

    checks: list[float] = []
    findings: list[tuple[bool, dict[str, str]]] = []
    facts: dict[str, Any] = {}
    if reading := latest("soil_moisture_pct"):
        value, kind = reading
        ok = MOISTURE_OK[0] <= value <= MOISTURE_OK[1]
        checks.append(100 if ok else 50)
        key = "moisture_ok" if ok else "moisture_low" if value < MOISTURE_OK[0] else "moisture_high"
        findings.append((ok, bi(f"credit.cond.{key}", value=round(value, 1), source=src(kind))))
        facts["soil_moisture_pct"] = {"value": round(value, 1), "source": kind}
    if farm.soil_ph is not None:
        ok = PH_OK[0] <= farm.soil_ph <= PH_OK[1]
        checks.append(100 if ok else 40)
        findings.append((ok, bi("credit.cond.ph_ok" if ok else "credit.cond.ph_bad", value=round(farm.soil_ph, 1))))
        facts["soil_ph"] = {"value": farm.soil_ph, "source": farm.soil_source or "farmer"}
    if reading := latest("soil_temperature_c"):
        value, kind = reading
        ok = SOIL_TEMP_OK[0] <= value <= SOIL_TEMP_OK[1]
        checks.append(100 if ok else 50)
        findings.append((ok, bi("credit.cond.temp_ok" if ok else "credit.cond.temp_bad", value=round(value, 1), source=src(kind))))
        facts["soil_temperature_c"] = {"value": round(value, 1), "source": kind}
    # Salinity: a real EC sensor reading wins; otherwise the AI location/soil estimate.
    measured = latest("soil_ec_ds_m")
    if measured:
        ec, kind = measured
    else:
        ec, kind = estimate_salinity(farm.lat, farm.lon, farm.region, farm.soil_type, farm.irrigation_type)["ec_ds_m"], "estimate"
    key = "salinity_ok" if ec < 2 else "salinity_mid" if ec <= 4 else "salinity_high"
    checks.append(100 if ec < 2 else 60 if ec <= 4 else 20)
    findings.append((ec < 2, bi(f"credit.cond.{key}", value=round(ec, 1), source=src(kind))))
    facts["salinity_ec_ds_m"] = {"value": round(ec, 1), "source": kind}
    if len(actionable) >= 3:
        rate = followed / len(actionable)
        checks.append(100 if rate >= 0.8 else 60 if rate >= 0.5 else 20)
        findings.append((rate >= 0.5, bi("profile.pos.adherence" if rate >= 0.5 else "profile.risk.adherence_low", followed=followed, total=len(actionable))))
        facts["advice_followed"] = {"followed": followed, "total": len(actionable)}
    score = sum(checks) / len(checks) if checks else 50.0
    return _criterion("condition", score, findings, facts)


def build_profile(session: Session, farmer: Farmer) -> FarmerRiskProfile:
    """Credit assessment on five criteria: transaction history, farm size and location,
    production history, off-take contracts and farm condition (IoT/AI)."""
    g = _gather(session, farmer)
    farms, crops, actionable, followed = g["farms"], g["crops"], g["actionable"], g["followed"]
    sales, receipts, harvests, storage_alerts = g["sales"], g["receipts"], g["harvests"], g["storage_alerts"]

    kg_sold = sum(s.quantity_kg for s in sales)
    sold_price = (sum(s.amount for s in sales) / kg_sold) if kg_sold else None

    def price_for(crop: str) -> float:
        return sold_price or DEFAULT_PRICE_TZS.get(crop, 750.0)

    flow = cash_flow(session, farmer, sales)
    criteria = [
        _transactions(session, farmer, sales),
        _farm(farmer, farms, crops, price_for),
        _production(harvests, receipts, storage_alerts),
        _offtake(session, farmer, flow.get("expected_yield_kg")),
        _condition(session, farms, actionable, followed),
    ]
    score = sum(c["score"] * c["weight"] for c in criteria) / sum(c["weight"] for c in criteria)
    # The AI model decides eligibility from the farmer's activities and transactions; the
    # overall health band follows the same prediction so the page tells one story.
    raw = ai_features(session, farmer, g, flow, criteria[3], criteria[4])
    loan = ai_eligibility(session, raw)
    p = loan["probability"]
    band = "LOW" if p >= 0.7 else "MEDIUM" if p >= loan["threshold"] else "HIGH"
    positive = [f["text"] for c in criteria for f in c["findings"] if f["good"]]
    risks = [f["text"] for c in criteria for f in c["findings"] if not f["good"]]
    drought = bool(criteria[1]["facts"].get("drought_prone"))

    products: list[dict[str, Any]] = []
    # Limit: a share of the coming harvest's income (or, without one, the verified sales so
    # far) that grows with the predicted probability of repaying.
    base = flow["expected_income_range_tzs"][0] if flow.get("expected_income_range_tzs") else raw["sales_income"]
    if loan["eligible"] and base > 0:
        month = flow.get("next_harvest_month")
        products.append(
            {
                "type": "input_loan",
                "max_amount_tzs": round(base * (0.15 + 0.35 * p), -3),
                "repayment_month": month,
                "probability": p,
                "reason": bi("profile.product.input_loan", month=_month_name(month)) if month else bi("profile.product.input_loan_sales"),
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
            "criteria": criteria,
            "eligibility": loan,
            "ai_features": raw,
            "advice_actionable": len(actionable),
            "advice_followed": followed,
            "verified_sales": len(sales),
            "distinct_buyers": len({s.buyer_id for s in sales}),
            "receipts": len(receipts),
            "unresolved_storage_alerts": len(storage_alerts),
            "seasons": criteria[2]["facts"]["seasons"],
            "crop_types": sorted({c.crop_type for c in crops}),
            "drought_prone_region": drought,
        },
    )
    session.add(profile)
    session.flush()
    return profile


def profile_evidence(session: Session, farmer: Farmer) -> dict[str, Any]:
    """The verified records behind the scorecard, so a person can check every factor."""
    from ..models import Buyer, StorageRecord

    batches = list(session.exec(select(CropBatch).where(CropBatch.farmer_id == farmer.id)))
    by_harvest = {b.harvest_id: b for b in batches}
    harvests = (
        list(session.exec(select(Harvest).where(Harvest.id.in_(list(by_harvest))).order_by(Harvest.harvest_date)))  # type: ignore[union-attr, arg-type]
        if by_harvest
        else []
    )
    receipts = list(session.exec(select(WarehouseReceipt).where(WarehouseReceipt.owner_farmer_id == farmer.id)))
    windows = (
        list(session.exec(select(StorageRecord).where(StorageRecord.batch_id.in_([b.id for b in batches]))))  # type: ignore[attr-defined]
        if batches
        else []
    )
    sales = list(
        session.exec(
            select(Sale).where(Sale.farmer_id == farmer.id, Sale.completed_at.is_not(None)).order_by(Sale.completed_at)  # type: ignore[union-attr, arg-type]
        )
    )
    buyer_names = {b.id: b.business_name for b in session.exec(select(Buyer))}
    buyer_counts: dict[int, int] = {}
    for sale in sales:
        buyer_counts[sale.buyer_id] = buyer_counts.get(sale.buyer_id, 0) + 1
    drought = farmer.region.strip().lower() in DROUGHT_PRONE_REGIONS
    safe_windows = sum(1 for w in windows if w.risk_level == "LOW")
    return {
        "production": {
            "harvests": [
                {"date": h.harvest_date.isoformat(), "crop_type": by_harvest[h.id].crop_type, "quantity_kg": h.quantity_kg, "batch_id": by_harvest[h.id].id}
                for h in harvests
            ],
            "total_kg": round(sum(h.quantity_kg for h in harvests)),
        },
        "storage": {
            "receipts": [
                {"id": r.id, "quantity_kg": r.quantity_kg, "grade": r.grade, "date_in": r.date_in.isoformat(), "status": r.status} for r in receipts
            ],
            "windows": len(windows),
            "safe_windows": safe_windows,
            "avg_humidity_pct": round(sum(w.rh_avg for w in windows) / len(windows), 1) if windows else None,
        },
        "sales": {
            "items": [
                {
                    "id": sale.id,
                    "date": sale.completed_at.isoformat() if sale.completed_at else None,
                    "quantity_kg": sale.quantity_kg,
                    "amount": sale.amount,
                    "buyer": buyer_names.get(sale.buyer_id),
                }
                for sale in sales
            ],
            "total_tzs": round(sum(sale.amount for sale in sales)),
            "repeat_buyers": sum(1 for n in buyer_counts.values() if n > 1),
        },
        "climate": {
            "region": farmer.region,
            "drought_prone": drought,
            "main_risk": "drought" if drought else "none",
            "crops": sorted({b.crop_type for b in batches}),
        },
    }


def profile_json(p: FarmerRiskProfile, farmer: Farmer, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "evidence": evidence,
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
        "criteria": p.inputs.get("criteria", []),
        "eligibility": p.inputs.get("eligibility"),
        "inputs": p.inputs,
        "disclaimer": bi("profile.disclaimer"),
    }
