"""Domain helpers for USSD — the same services the web app uses (farm AI, ghala AI, market, finance)."""

from __future__ import annotations

import secrets
from datetime import date

from sqlmodel import Session, select

from ..ai import soil_map
from ..ai.planting import FIT_RANK, ph_band
from ..ai.profile import build_profile, profile_evidence
from ..i18n import MESSAGES, crop_name, pick_language, t
from ..integrations.open_meteo import get_current_conditions
from ..models import (
    Alert,
    Crop,
    CropBatch,
    Farm,
    Farmer,
    InsuranceClaim,
    InsurancePolicy,
    Language,
    LoanApplication,
    Order,
    Role,
    Sale,
    SavingsGoal,
    User,
    Warehouse,
)
from ..routers.farms import compute_advice, compute_planting, soil_moisture_now
from ..routers.finance import insurance_recs, submit_claim, submit_loan, submit_policy
from ..security.auth import hash_secret, verify_secret
from ..storage import batch_outlook, batch_risk

CROP_CHOICES = {"1": "maize", "2": "rice", "3": "sunflower", "4": "beans", "5": "sorghum"}
NO_CROP_CHOICE = "6"
LOAN_PURPOSES = {"1": "inputs", "2": "storage", "3": "equipment", "4": "other"}
DISASTERS = {"1": "drought", "2": "flood", "3": "pests", "4": "hail_wind", "5": "storage_loss"}
SAVINGS_BUCKETS = {"1": "inputs", "2": "emergency", "3": "household", "4": "goal"}
MAX_LIST = 4
MAX_SCREEN_CHARS = 178  # 182-char USSD page minus the "CON "/"END " prefix


def tzs(amount: float) -> str:
    return f"TZS {amount:,.0f}"


def fit_lines(title: str, lines: list[str], max_chars: int = MAX_SCREEN_CHARS) -> str:
    """Title plus as many lines as fit on one USSD page; the rest become '+N'."""
    text = title
    for i, line in enumerate(lines):
        rest = len(lines) - i - 1
        reserve = len(f"\n+{rest}") if rest else 0
        if len(text) + 1 + len(line) + reserve > max_chars:
            if i == 0:
                room = max_chars - len(text) - 2 - len(f"\n+{rest}")
                return f"{text}\n{line[:room].rstrip()}…" + (f"\n+{rest}" if rest else "")
            return f"{text}\n+{len(lines) - i}"
        text += "\n" + line
    return text


def lang_of(user: User | None) -> str:
    if not user:
        return "sw"
    return pick_language(user.language.value if hasattr(user.language, "value") else str(user.language))


def status_label(status: str, lang: str) -> str:
    key = f"ussd.status.{status}"
    return t(key, lang) if key in MESSAGES else status


def verify_pin(user: User, pin: str) -> bool:
    return pin.isdigit() and 4 <= len(pin) <= 6 and verify_secret(user.pin_hash, pin)


def find_farmer_user(session: Session, phone: str) -> tuple[User | None, Farmer | None]:
    user = session.exec(select(User).where(User.phone == phone)).first()
    if not user or user.role != Role.FARMER:
        return user, None
    farmer = session.exec(select(Farmer).where(Farmer.user_id == user.id)).first()
    return user, farmer


def primary_farm(session: Session, farmer: Farmer) -> Farm | None:
    return session.exec(select(Farm).where(Farm.farmer_id == farmer.id).order_by(Farm.id)).first()  # type: ignore[arg-type]


def band_label(band: str, lang: str) -> str:
    key = {"LOW": "ussd.finance.band_low", "MEDIUM": "ussd.finance.band_medium", "HIGH": "ussd.finance.band_high"}.get(
        band, "ussd.finance.band_medium"
    )
    return t(key, lang)


def moisture_label(pct: float, lang: str) -> str:
    if pct < 30:
        return t("ussd.soil.low", lang)
    if pct < 55:
        return t("ussd.soil.ok", lang)
    return t("ussd.soil.high", lang)


def _crop_label(crop_type: str, lang: str) -> str:
    return crop_name(crop_type)[lang].capitalize()


def _soil_label(soil_type: str, lang: str) -> str:
    key = f"planting.soil.{soil_type}"
    return t(key, lang) if key in MESSAGES else soil_type


# ---------------------------------------------------------------- registration


def register_farmer(
    session: Session,
    phone: str,
    *,
    full_name: str,
    region: str,
    acreage: float,
    crop_type: str | None,
    crop_acreage: float | None = None,
) -> tuple[User, Farmer, Farm, str]:
    """Create a farmer and farm at the chosen region with its soil profile. Returns (user, farmer, farm, pin)."""
    soil = soil_map.lookup(region) or soil_map.lookup("Dodoma")
    assert soil is not None
    pin = f"{secrets.randbelow(10_000):04d}"
    user = User(
        phone=phone,
        full_name=full_name.strip()[:80],
        role=Role.FARMER,
        pin_hash=hash_secret(pin),
        language=Language.SW,
        status="ACTIVE",
    )
    session.add(user)
    session.flush()
    farmer = Farmer(public_id=f"FMR-{user.id:04d}", user_id=user.id, display_name=full_name.strip()[:80], region=soil.name, district="")
    session.add(farmer)
    session.flush()
    farm = Farm(
        farmer_id=farmer.id,
        name=f"Shamba la {full_name.strip()[:40]}",
        region=soil.name,
        lat=soil.lat,
        lon=soil.lon,
        acreage=max(0.1, acreage),
        soil_type=soil.soil_type,
        irrigation_type="rainfed",
        soil_ph=soil.ph,
        soil_salinity_ec=soil.salinity_ec,
        soil_source="soil_map",
    )
    session.add(farm)
    session.flush()
    if crop_type:
        session.add(Crop(farm_id=farm.id, crop_type=crop_type, acreage=crop_acreage, planting_date=date.today(), growth_stage="initial"))
    soil_moisture_now(session, farm)
    return user, farmer, farm, pin


def registration_summary(session: Session, farm: Farm, lang: str) -> str:
    cur = get_current_conditions(farm.lat, farm.lon)
    result = compute_planting(session, farm)
    moisture = result.inputs.get("moisture_pct")
    return t(
        "ussd.reg.done",
        lang,
        region=farm.region,
        temp=round(cur.temperature_c),
        rh=round(cur.humidity_pct),
        moisture=round(moisture) if moisture is not None else "-",
        ph=f"{farm.soil_ph:g}" if farm.soil_ph is not None else "-",
        crops=_best_crops(result.recommendations, lang),
    )


# ---------------------------------------------------------------- farm


def farmer_crops(session: Session, farmer: Farmer) -> list[Crop]:
    farm_ids = [f.id for f in session.exec(select(Farm).where(Farm.farmer_id == farmer.id))]
    if not farm_ids:
        return []
    return list(
        session.exec(
            select(Crop)
            .where(Crop.farm_id.in_(farm_ids), Crop.growth_stage != "harvested")  # type: ignore[union-attr]
            .order_by(Crop.planting_date.desc())  # type: ignore[attr-defined]
        )
    )


def crops_summary(session: Session, farmer: Farmer, lang: str, limit: int = 3, with_stage: bool = True) -> str:
    crops = farmer_crops(session, farmer)
    if not crops:
        return t("ussd.farm.no_crops", lang)
    labels = []
    for c in crops[:limit]:
        acres = f" {c.acreage:g}ac" if c.acreage else ""
        stage = f" ({t(f'ussd.stage.{c.growth_stage}', lang)})" if with_stage else ""
        labels.append(f"{_crop_label(c.crop_type, lang)}{acres}{stage}")
    if len(crops) > limit:
        labels.append(f"+{len(crops) - limit}")
    return ", ".join(labels)


def farm_info_text(session: Session, farmer: Farmer, lang: str) -> str:
    farm = primary_farm(session, farmer)
    if not farm:
        return t("ussd.farm.none", lang)
    return t(
        "ussd.farm.info",
        lang,
        region=farm.region or farmer.region,
        acres=farm.acreage,
        soil=_soil_label(farm.soil_type, lang),
        crops=crops_summary(session, farmer, lang),
    )


def farm_conditions_text(session: Session, farmer: Farmer, lang: str) -> str:
    """AI view of the farm's location: air temperature/humidity, soil moisture, pH, salinity, best crop."""
    farm = primary_farm(session, farmer)
    if not farm:
        return t("ussd.farm.none", lang)
    cur = get_current_conditions(farm.lat, farm.lon)
    result = compute_planting(session, farm)
    moisture = result.inputs.get("moisture_pct")
    ph = f"{farm.soil_ph:g} ({t(f'ussd.ph.{ph_band(farm.soil_ph)}', lang)})" if farm.soil_ph is not None else "-"
    salinity = t(f"ussd.salinity.{soil_map.salinity_band(farm.soil_salinity_ec)}", lang) if farm.soil_salinity_ec is not None else "-"
    return t(
        "ussd.farm.conditions",
        lang,
        region=farm.region,
        temp=round(cur.temperature_c),
        rh=round(cur.humidity_pct),
        moisture=f"{round(moisture)}% ({moisture_label(moisture, lang)})" if moisture is not None else "-",
        ph=ph,
        salinity=salinity,
        crops=_best_crops(result.recommendations, lang, limit=2),
    )


def planting_text(session: Session, farmer: Farmer, lang: str) -> str:
    farm = primary_farm(session, farmer)
    if not farm:
        return t("ussd.farm.none", lang)
    result = compute_planting(session, farm)
    return t(
        "ussd.plant.advice",
        lang,
        best=_best_crops(result.recommendations, lang),
        avoid=_avoid_line(result.recommendations, lang),
        timing=result.timing["text"][lang] if result.timing else "",
    ).strip()


def _best_crops(recommendations: list[dict], lang: str, limit: int = 3) -> str:
    good = [r for r in recommendations if FIT_RANK[r["fit"]] <= FIT_RANK["good"]] or recommendations[:2]
    return ", ".join(r["name"][lang].capitalize() for r in good[:limit])


def _avoid_line(recommendations: list[dict], lang: str) -> str:
    poor = [r["name"][lang].capitalize() for r in recommendations if r["fit"] == "poor"]
    return t("ussd.plant.avoid", lang, crops=", ".join(poor)) + "\n" if poor else ""


def add_crop(session: Session, farmer: Farmer, crop_type: str, acreage: float) -> Crop | None:
    farm = primary_farm(session, farmer)
    if not farm:
        return None
    crop = Crop(farm_id=farm.id, crop_type=crop_type, acreage=acreage, planting_date=date.today(), growth_stage="initial")
    session.add(crop)
    session.flush()
    return crop


def irrigation_text(session: Session, farmer: Farmer, lang: str) -> str:
    farm = primary_farm(session, farmer)
    if not farm:
        return t("ussd.farm.none", lang)
    advice = compute_advice(session, farm)
    if not advice:
        return t("ussd.advice.none", lang)
    session.flush()
    return t("ussd.advice.current", lang, text=advice.headline.get(lang) or advice.headline.get("sw") or "")


# ---------------------------------------------------------------- ghala


def stored_batches(session: Session, farmer: Farmer) -> list[CropBatch]:
    return list(
        session.exec(
            select(CropBatch).where(CropBatch.farmer_id == farmer.id, CropBatch.status == "IN_STORAGE", CropBatch.warehouse_id.is_not(None))  # type: ignore[union-attr]
        )
    )


def ghala_summary(session: Session, farmer: Farmer, lang: str) -> str:
    batches = stored_batches(session, farmer)
    if not batches:
        return t("ussd.ghala.none_short", lang)
    return t("ussd.ghala.summary", lang, kg=round(sum(b.available_kg for b in batches)), count=len(batches))


def ghala_outlook_text(session: Session, farmer: Farmer, lang: str) -> str:
    """Room conditions now, the AI forecast for the next hours, and what to do (for the riskiest batch)."""
    batches = stored_batches(session, farmer)
    if not batches:
        return t("ussd.ghala.none", lang)
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "UNKNOWN": 3}
    scored = sorted(((batch_risk(session, b), b) for b in batches), key=lambda rb: order.get(rb[0].level, 9))
    risk, batch = scored[0]
    outlook = batch_outlook(session, batch)
    wh = session.get(Warehouse, batch.warehouse_id)
    if outlook.temp_now is None:
        return t("ussd.ghala.no_readings", lang, ghala=wh.name if wh else "-")
    return t(
        "ussd.ghala.outlook",
        lang,
        ghala=wh.name if wh else "-",
        temp=round(outlook.temp_now),
        rh=round(outlook.rh_now),
        hours=outlook.horizon_hours,
        temp_pred=round(outlook.temp_pred),
        rh_pred=round(outlook.rh_pred),
        risk=t(f"ussd.risk.{risk.level}", lang),
        action=" ".join(a[lang] for a in outlook.actions[:2]),
    )


def ghala_stock_text(session: Session, farmer: Farmer, lang: str) -> str:
    batches = stored_batches(session, farmer)
    if not batches:
        return t("ussd.ghala.none", lang)
    lines = []
    for b in batches[:MAX_LIST]:
        risk = batch_risk(session, b)
        lines.append(f"- {_crop_label(b.crop_type, lang)} {b.available_kg:,.0f}kg ({b.grade or '-'}): {t(f'ussd.risk.{risk.level}', lang)}")
    return fit_lines(t("ussd.ghala.stock_title", lang), lines)


def alerts_text(session: Session, user: User, lang: str, kinds: set[str] | None = None) -> str:
    rows = list(
        session.exec(
            select(Alert)
            .where(Alert.user_id == user.id, Alert.resolved_at.is_(None))  # type: ignore[union-attr]
            .order_by(Alert.created_at.desc())  # type: ignore[attr-defined]
        )
    )
    if kinds:
        rows = [a for a in rows if a.kind in kinds]
    if not rows:
        return t("ussd.alerts.none", lang)
    lines = [f"- {(a.message or {}).get(lang) or (a.message or {}).get('sw') or a.kind}" for a in rows[:MAX_LIST]]
    return fit_lines(lines[0], lines[1:])


# ---------------------------------------------------------------- market


def market_listed_text(session: Session, farmer: Farmer, lang: str) -> str:
    batches = list(session.exec(select(CropBatch).where(CropBatch.farmer_id == farmer.id, CropBatch.listed == True)))  # noqa: E712
    if not batches:
        return t("ussd.market.no_stock", lang)
    lines = [
        f"- {_crop_label(b.crop_type, lang)}: {b.available_kg:,.0f}kg @ {tzs(b.price_per_kg or 0)}/kg" for b in batches[:MAX_LIST]
    ]
    return fit_lines(t("ussd.market.stock_title", lang), lines)


def sales_history_text(session: Session, farmer: Farmer, lang: str) -> str:
    sales = list(
        session.exec(
            select(Sale).where(Sale.farmer_id == farmer.id, Sale.completed_at.is_not(None)).order_by(Sale.completed_at.desc())  # type: ignore[union-attr, attr-defined]
        )
    )
    if not sales:
        return t("ussd.finance.no_sales", lang)
    lines = []
    for s in sales[:MAX_LIST]:
        batch = session.get(CropBatch, s.batch_id)
        crop = _crop_label(batch.crop_type, lang) if batch else ""
        lines.append(f"- {s.completed_at:%d/%m/%y} {crop} {s.quantity_kg:,.0f}kg: {tzs(s.amount)}")
    total = sum(s.amount for s in sales)
    return fit_lines(t("ussd.market.sales_title", lang, total=tzs(total), count=len(sales)), lines)


def market_requests_text(session: Session, farmer: Farmer, lang: str) -> str:
    batch_ids = [b.id for b in session.exec(select(CropBatch).where(CropBatch.farmer_id == farmer.id))]
    if not batch_ids:
        return t("ussd.market.no_requests", lang)
    orders = list(
        session.exec(
            select(Order)
            .where(Order.batch_id.in_(batch_ids), Order.status == "REQUESTED")  # type: ignore[union-attr]
            .order_by(Order.created_at.desc())  # type: ignore[attr-defined]
        )
    )
    if not orders:
        return t("ussd.market.no_requests", lang)
    lines = [f"- {o.quantity_kg:,.0f}kg @ {tzs(o.price_per_kg)}/kg" for o in orders[:MAX_LIST]]
    return fit_lines(t("ussd.market.requests_title", lang), lines)


def market_prices_text(session: Session, farmer: Farmer, lang: str) -> str:
    """Average price per crop across all listed stock on the marketplace."""
    listed = list(session.exec(select(CropBatch).where(CropBatch.listed == True, CropBatch.price_per_kg.is_not(None))))  # noqa: E712  # type: ignore[union-attr]
    by_crop: dict[str, list[float]] = {}
    for b in listed:
        by_crop.setdefault(b.crop_type, []).append(b.price_per_kg or 0)
    if not by_crop:
        return t("ussd.market.prices_none", lang)
    lines = [f"- {_crop_label(c, lang)}: {tzs(sum(p) / len(p))}/kg" for c, p in list(by_crop.items())[:MAX_LIST]]
    return fit_lines(t("ussd.market.prices_title", lang), lines)


# ---------------------------------------------------------------- finance: profile


def finance_profile_text(session: Session, farmer: Farmer, lang: str) -> str:
    profile = build_profile(session, farmer)
    evidence = profile_evidence(session, farmer)
    income = profile.cash_flow.get("expected_income_range_tzs") if isinstance(profile.cash_flow, dict) else None
    return t(
        "ussd.finance.profile",
        lang,
        income=f"TZS {income[0]:,.0f}-{income[1]:,.0f}" if income else "-",
        sales=tzs(evidence["sales"]["total_tzs"]),
        band=band_label(profile.risk_band, lang),
    )


def finance_why_text(session: Session, farmer: Farmer, lang: str) -> str:
    profile = build_profile(session, farmer)
    lines = [f"+ {i.get(lang) or i.get('sw')}" for i in (profile.positive_factors or [])[:3] if i.get(lang) or i.get("sw")]
    lines += [f"- {i.get(lang) or i.get('sw')}" for i in (profile.risk_factors or [])[:3] if i.get(lang) or i.get("sw")]
    if not lines:
        return t("ussd.finance.why_none", lang)
    return fit_lines(t("ussd.finance.why_title", lang), lines)


# ---------------------------------------------------------------- finance: loans


def suggested_loan(session: Session, farmer: Farmer) -> dict | None:
    profile = build_profile(session, farmer)
    products = [p for p in (profile.suggested_products or []) if p.get("type") == "input_loan"]
    return products[0] if products else None


def first_partner(session: Session, role: Role) -> User | None:
    return session.exec(select(User).where(User.role == role, User.status == "ACTIVE").order_by(User.id)).first()  # type: ignore[arg-type]


def apply_loan(session: Session, user: User, farmer: Farmer, amount: float, purpose_key: str) -> tuple[LoanApplication, User] | None:
    lender = first_partner(session, Role.LENDER)
    if not lender:
        return None
    suggestion = suggested_loan(session, farmer)
    purpose = f"{t(f'ussd.loan.purpose.{purpose_key}', 'en')} (USSD)"
    loan = submit_loan(session, user, farmer, lender.id, amount, purpose, (suggestion or {}).get("repayment_month"))
    return loan, lender


def loans_text(session: Session, farmer: Farmer, lang: str) -> str:
    loans = list(
        session.exec(select(LoanApplication).where(LoanApplication.farmer_id == farmer.id).order_by(LoanApplication.created_at.desc()))  # type: ignore[attr-defined]
    )
    if not loans:
        return t("ussd.loan.none", lang)
    lines = [f"- #{ln.id} {tzs(ln.amount)}: {status_label(ln.status, lang)}" for ln in loans[:MAX_LIST]]
    return fit_lines(t("ussd.loan.list_title", lang), lines)


# ---------------------------------------------------------------- finance: savings


def savings_goals(session: Session, farmer: Farmer) -> list[SavingsGoal]:
    return list(session.exec(select(SavingsGoal).where(SavingsGoal.farmer_id == farmer.id).order_by(SavingsGoal.id)))  # type: ignore[arg-type]


def savings_text(session: Session, farmer: Farmer, lang: str) -> str:
    goals = savings_goals(session, farmer)
    if not goals:
        return t("ussd.savings.none", lang)
    lines = []
    for g in goals[:MAX_LIST]:
        pct = round(100 * g.saved_amount / g.target_amount) if g.target_amount else 0
        lines.append(f"- {g.name}: {g.saved_amount:,.0f}/{g.target_amount:,.0f} ({pct}%)")
    total = sum(g.saved_amount for g in goals)
    return fit_lines(t("ussd.savings.title", lang, total=tzs(total)), lines)


def deposit(session: Session, goal: SavingsGoal, amount: float) -> SavingsGoal:
    goal.saved_amount = round(goal.saved_amount + amount, 2)
    session.add(goal)
    session.flush()
    return goal


def create_goal(session: Session, farmer: Farmer, bucket: str, target: float, lang: str) -> SavingsGoal:
    goal = SavingsGoal(farmer_id=farmer.id, bucket=bucket, name=t(f"savings.{bucket}", lang), target_amount=target)
    session.add(goal)
    session.flush()
    return goal


# ---------------------------------------------------------------- finance: insurance


def active_policies(session: Session, farmer: Farmer) -> list[InsurancePolicy]:
    return list(session.exec(select(InsurancePolicy).where(InsurancePolicy.farmer_id == farmer.id, InsurancePolicy.status == "ACTIVE")))


def policy_for_disaster(session: Session, farmer: Farmer, disaster: str) -> InsurancePolicy | None:
    """Ghala losses are claimed on storage cover; field disasters on the farm (weather index) cover."""
    product = "storage_cover" if disaster == "storage_loss" else "weather_index"
    return next((p for p in active_policies(session, farmer) if p.product == product), None)


def report_disaster(session: Session, user: User, farmer: Farmer, policy: InsurancePolicy, disaster: str) -> InsuranceClaim:
    """A disaster report from the field becomes an insurance claim the insurer reviews (same as a web claim)."""
    farm = primary_farm(session, farmer)
    cur = get_current_conditions(farm.lat, farm.lon) if farm else None
    trigger = "STORAGE_LOSS" if disaster == "storage_loss" else "MANUAL"
    description = f"USSD disaster report: {t(f'ussd.disaster.{disaster}', 'en')} ({t(f'ussd.disaster.{disaster}', 'sw')})"
    evidence = {
        "channel": "ussd",
        "disaster": disaster,
        "farm_id": farm.id if farm else None,
        "region": farm.region if farm else farmer.region,
        "conditions_at_report": {"temperature_c": cur.temperature_c, "humidity_pct": cur.humidity_pct, "source": cur.source} if cur else None,
    }
    return submit_claim(session, user, policy, trigger, description, evidence)


def insurance_options(session: Session, farmer: Farmer) -> list[dict]:
    return insurance_recs(session, farmer)[:3]


def insurance_options_text(options: list[dict], lang: str) -> str:
    lines = [t("ussd.ins.request_title", lang)]
    for i, o in enumerate(options, start=1):
        lines.append(
            t("ussd.ins.option", lang, n=i, product=t(f"ussd.product.{o['product']}", lang), cover=tzs(o["suggested_coverage_tzs"]), premium=tzs(o["indicative_premium_tzs"]))
        )
    return "\n".join(lines)


def request_policy(session: Session, user: User, farmer: Farmer, option: dict) -> tuple[InsurancePolicy, User] | None:
    insurer = first_partner(session, Role.INSURER)
    if not insurer:
        return None
    policy = submit_policy(session, user, farmer, insurer.id, option["product"], option["suggested_coverage_tzs"], option.get("farm_id"))
    return policy, insurer


def policies_text(session: Session, farmer: Farmer, lang: str) -> str:
    policies = list(
        session.exec(select(InsurancePolicy).where(InsurancePolicy.farmer_id == farmer.id).order_by(InsurancePolicy.created_at.desc()))  # type: ignore[attr-defined]
    )
    if not policies:
        return t("ussd.ins.none", lang)
    lines = []
    for p in policies[:3]:
        lines.append(f"- #{p.id} {t(f'ussd.product.{p.product}', lang)}: {status_label(p.status, lang)}")
        claim = session.exec(select(InsuranceClaim).where(InsuranceClaim.policy_id == p.id).order_by(InsuranceClaim.created_at.desc())).first()  # type: ignore[attr-defined]
        if claim:
            lines.append(f"  {t('ussd.ins.claim', lang, id=claim.id)}: {status_label(claim.status, lang)}")
    return fit_lines(t("ussd.ins.list_title", lang), lines)
