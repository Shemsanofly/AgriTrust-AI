"""Automatic reports: one per role, rebuilt from live data on every request, so a report is
never out of date. Each report has headline numbers per section, an optional table, and a
log of what changed (the user's notifications plus their own recorded actions).

GET /reports/me        -> JSON for the Reports page (which refreshes itself while open)
GET /reports/me.pdf    -> the same report as a PDF (?lang=en|sw)"""

import hashlib
import io
import json
from datetime import date, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlmodel import Session, select

from ..db import get_session
from ..models import (
    Alert,
    AuditLog,
    Buyer,
    Crop,
    CropBatch,
    Farm,
    Farmer,
    FarmerRiskProfile,
    InsuranceClaim,
    InsurancePolicy,
    LoanApplication,
    OffTakeContract,
    Order,
    PaymentIntent,
    Role,
    Sale,
    SavingsGoal,
    Sensor,
    SensorReading,
    SmsLog,
    User,
    WarehouseReceipt,
    utcnow,
)
from ..security.auth import buyer_for, farmer_for, get_current_user, warehouses_for

router = APIRouter(tags=["reports"])
Format = Literal["tzs", "kg", "count", "pct", "date", "acres", "text"]
CHANGE_DAYS = 30
OPEN_ORDER = ("REQUESTED", "ACCEPTED", "PAID", "RELEASED", "DELIVERED")


def L(en: str, sw: str) -> dict[str, str]:
    return {"en": en, "sw": sw}


def item(label: dict[str, str], value: Any, fmt: Format = "count") -> dict[str, Any]:
    return {"label": label, "value": value, "format": fmt}


def section(key: str, title: dict[str, str], items: list[dict], table: dict | None = None) -> dict[str, Any]:
    return {"key": key, "title": title, "items": items, "table": table}


def _count_by_status(rows) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        out[r.status] = out.get(r.status, 0) + 1
    return out


def _latest_reading(session: Session, sensor_ids: list[int], metric: str):
    if not sensor_ids:
        return None
    return session.exec(
        select(SensorReading).where(SensorReading.sensor_id.in_(sensor_ids), SensorReading.metric == metric).order_by(SensorReading.ts.desc())  # type: ignore[union-attr, attr-defined]
    ).first()


# ---------------------------------------------------------------- per-role reports


def farmer_report(session: Session, user: User) -> list[dict]:
    farmer = farmer_for(session, user)
    farms = session.exec(select(Farm).where(Farm.farmer_id == farmer.id)).all()
    farm_ids = [f.id for f in farms]
    crops = session.exec(select(Crop).where(Crop.farm_id.in_(farm_ids), Crop.growth_stage != "harvested")).all() if farm_ids else []  # type: ignore[union-attr]
    upcoming = sorted(c.expected_harvest_date for c in crops if c.expected_harvest_date and c.expected_harvest_date >= date.today())
    sensor_ids = [s.id for s in session.exec(select(Sensor).where(Sensor.farm_id.in_(farm_ids)))] if farm_ids else []  # type: ignore[union-attr]
    moisture = _latest_reading(session, sensor_ids, "soil_moisture_pct")
    batches = session.exec(select(CropBatch).where(CropBatch.farmer_id == farmer.id)).all()
    stored = [b for b in batches if b.status == "IN_STORAGE"]
    sales = session.exec(select(Sale).where(Sale.farmer_id == farmer.id, Sale.completed_at.is_not(None)).order_by(Sale.completed_at.desc())).all()  # type: ignore[union-attr, attr-defined]
    orders = session.exec(select(Order).where(Order.batch_id.in_([b.id for b in batches]))).all() if batches else []  # type: ignore[union-attr]
    contracts = session.exec(select(OffTakeContract).where(OffTakeContract.farmer_id == farmer.id)).all()
    accepted = [c for c in contracts if c.status == "ACCEPTED"]
    loans = session.exec(select(LoanApplication).where(LoanApplication.farmer_id == farmer.id)).all()
    policies = session.exec(select(InsurancePolicy).where(InsurancePolicy.farmer_id == farmer.id, InsurancePolicy.status == "ACTIVE")).all()
    profile = session.exec(select(FarmerRiskProfile).where(FarmerRiskProfile.farmer_id == farmer.id).order_by(FarmerRiskProfile.generated_at.desc())).first()  # type: ignore[attr-defined]
    ai = (profile.inputs or {}).get("eligibility") if profile else None
    buyers = {b.id: b.business_name for b in session.exec(select(Buyer))}
    return [
        section("farm", L("Farm", "Shamba"), [
            item(L("Farms", "Mashamba"), len(farms)),
            item(L("Total area", "Eneo lote"), round(sum(f.acreage for f in farms), 1), "acres"),
            item(L("Crops growing", "Mazao yanayokua"), len(crops)),
            item(L("Next harvest", "Mavuno yajayo"), upcoming[0].isoformat() if upcoming else None, "date"),
            item(L("Soil moisture now", "Unyevu wa udongo sasa"), round(moisture.value) if moisture else None, "pct"),
        ]),
        section("market", L("Ghala and market", "Ghala na soko"), [
            item(L("In the ghala", "Ghalani"), round(sum(b.available_kg for b in stored)), "kg"),
            item(L("Listed for sale", "Imewekwa sokoni"), round(sum(b.available_kg for b in stored if b.listed)), "kg"),
            item(L("Open orders", "Oda zinazoendelea"), sum(1 for o in orders if o.status in OPEN_ORDER)),
            item(L("Verified sales", "Mauzo yaliyothibitishwa"), len(sales)),
            item(L("Income from sales", "Mapato ya mauzo"), round(sum(s.amount for s in sales)), "tzs"),
            item(L("Buyer contracts accepted", "Mikataba iliyokubaliwa"), round(sum(c.quantity_kg * c.price_per_kg for c in accepted)), "tzs"),
        ], {
            "columns": [L("Date", "Tarehe"), L("Buyer", "Mnunuzi"), L("Quantity", "Kiasi"), L("Amount", "Kiasi cha pesa")],
            "formats": ["date", "text", "kg", "tzs"],
            "rows": [[s.completed_at.date().isoformat(), buyers.get(s.buyer_id, "—"), s.quantity_kg, round(s.amount)] for s in sales[:5]],
        }),
        section("finance", L("Finance", "Fedha"), [
            item(L("AI: chance of repaying a loan", "AI: uwezekano wa kulipa mkopo"), round(ai["probability"] * 100) if ai else None, "pct"),
            item(L("Eligible for a loan", "Anastahili mkopo"), (L("Yes", "Ndiyo") if ai["eligible"] else L("Not yet", "Bado")) if ai else None, "text"),
            item(L("Loan applications waiting", "Maombi ya mkopo yanayosubiri"), sum(1 for x in loans if x.status in ("SUBMITTED", "UNDER_REVIEW"))),
            item(L("Loans being repaid", "Mikopo inayolipwa"), round(sum(x.amount for x in loans if x.status in ("DISBURSED", "REPAYING"))), "tzs"),
            item(L("Savings", "Akiba"), round(sum(g.saved_amount for g in session.exec(select(SavingsGoal).where(SavingsGoal.farmer_id == farmer.id)))), "tzs"),
            item(L("Insurance cover", "Kinga ya bima"), round(sum(p.coverage_tzs for p in policies)), "tzs"),
        ]),
    ]


def buyer_report(session: Session, user: User) -> list[dict]:
    buyer = buyer_for(session, user)
    orders = session.exec(select(Order).where(Order.buyer_id == buyer.id).order_by(Order.updated_at.desc())).all()  # type: ignore[attr-defined]
    sales = session.exec(select(Sale).where(Sale.buyer_id == buyer.id, Sale.completed_at.is_not(None))).all()  # type: ignore[union-attr]
    status = _count_by_status(orders)
    contracts = session.exec(select(OffTakeContract).where(OffTakeContract.buyer_id == buyer.id)).all()
    batch_farmer = {b.id: b.farmer_id for b in session.exec(select(CropBatch).where(CropBatch.id.in_([o.batch_id for o in orders])))} if orders else {}  # type: ignore[union-attr]
    return [
        section("orders", L("Orders", "Oda"), [
            item(L("Open orders", "Oda zinazoendelea"), sum(status.get(s, 0) for s in OPEN_ORDER)),
            item(L("Waiting for your payment", "Zinasubiri malipo yako"), status.get("ACCEPTED", 0)),
            item(L("Completed purchases", "Manunuzi yaliyokamilika"), len(sales)),
            item(L("Bought", "Umenunua"), round(sum(s.quantity_kg for s in sales)), "kg"),
            item(L("Spent", "Umetumia"), round(sum(s.amount for s in sales)), "tzs"),
            item(L("Suppliers", "Wauzaji"), len(set(batch_farmer.values()))),
        ], {
            "columns": [L("Order", "Oda"), L("Batch", "Mzigo"), L("Quantity", "Kiasi"), L("Status", "Hali")],
            "formats": ["text", "text", "kg", "text"],
            "rows": [[f"#{o.id}", o.batch_id, o.quantity_kg, o.status] for o in orders[:6]],
        }),
        section("contracts", L("Contracts", "Mikataba"), [
            item(L("Offers waiting for farmers", "Ofa zinazosubiri wakulima"), sum(1 for c in contracts if c.status == "OFFERED")),
            item(L("Accepted contracts", "Mikataba iliyokubaliwa"), sum(1 for c in contracts if c.status == "ACCEPTED")),
            item(L("Contracted value", "Thamani ya mikataba"), round(sum(c.quantity_kg * c.price_per_kg for c in contracts if c.status == "ACCEPTED")), "tzs"),
        ]),
    ]


def warehouse_report(session: Session, user: User) -> list[dict]:
    warehouses = warehouses_for(session, user)
    ids = [w.id for w in warehouses]
    batches = session.exec(select(CropBatch).where(CropBatch.warehouse_id.in_(ids), CropBatch.status == "IN_STORAGE")).all() if ids else []  # type: ignore[union-attr]
    receipts = session.exec(select(WarehouseReceipt).where(WarehouseReceipt.warehouse_id.in_(ids), WarehouseReceipt.status.in_(["ACTIVE", "PARTIALLY_RELEASED"]))).all() if ids else []  # type: ignore[union-attr, attr-defined]
    all_batches = [b.id for b in session.exec(select(CropBatch).where(CropBatch.warehouse_id.in_(ids)))] if ids else []  # type: ignore[union-attr]
    to_release = session.exec(select(Order).where(Order.batch_id.in_(all_batches), Order.status == "PAID")).all() if all_batches else []  # type: ignore[union-attr]
    alerts = session.exec(select(Alert).where(Alert.user_id == user.id, Alert.kind == "SPOILAGE_RISK", Alert.resolved_at.is_(None))).all()  # type: ignore[union-attr]
    rows = []
    for w in warehouses:
        sids = [s.id for s in session.exec(select(Sensor).where(Sensor.warehouse_id == w.id))]
        t, h = _latest_reading(session, sids, "temperature_c"), _latest_reading(session, sids, "humidity_pct")
        rows.append([w.name, round(t.value, 1) if t else None, round(h.value) if h else None, round(sum(b.available_kg for b in batches if b.warehouse_id == w.id))])
    return [
        section("stock", L("Stock", "Mzigo"), [
            item(L("Warehouses", "Maghala"), len(warehouses)),
            item(L("Batches in storage", "Mizigo iliyohifadhiwa"), len(batches)),
            item(L("Stock held", "Mzigo uliopo"), round(sum(b.available_kg for b in batches)), "kg"),
            item(L("Active receipts", "Stakabadhi hai"), len(receipts)),
            item(L("Paid orders to release", "Oda zilizolipwa za kutoa"), len(to_release)),
            item(L("Unresolved spoilage alerts", "Tahadhari za kuharibika zisizoshughulikiwa"), len(alerts)),
        ], {
            "columns": [L("Warehouse", "Ghala"), L("Temperature °C", "Joto °C"), L("Humidity %", "Unyevu %"), L("Stock", "Mzigo")],
            "formats": ["text", "text", "text", "kg"],
            "rows": rows,
        }),
    ]


def lender_report(session: Session, user: User) -> list[dict]:
    loans = session.exec(select(LoanApplication).where(LoanApplication.lender_user_id == user.id).order_by(LoanApplication.created_at.desc())).all()  # type: ignore[attr-defined]
    status = _count_by_status(loans)
    farmers = {f.id: f for f in session.exec(select(Farmer).where(Farmer.id.in_([x.farmer_id for x in loans])))} if loans else {}  # type: ignore[union-attr]

    def ai_pct(farmer_id: int):
        p = session.exec(select(FarmerRiskProfile).where(FarmerRiskProfile.farmer_id == farmer_id).order_by(FarmerRiskProfile.generated_at.desc())).first()  # type: ignore[attr-defined]
        e = (p.inputs or {}).get("eligibility") if p else None
        return round(e["probability"] * 100) if e else None

    probs = [x for x in (ai_pct(fid) for fid in {x.farmer_id for x in loans}) if x is not None]
    return [
        section("portfolio", L("Loan portfolio", "Mikopo"), [
            item(L("Applications waiting", "Maombi yanayosubiri"), status.get("SUBMITTED", 0) + status.get("UNDER_REVIEW", 0)),
            item(L("Approved", "Yaliyoidhinishwa"), status.get("APPROVED", 0)),
            item(L("Declined", "Yaliyokataliwa"), status.get("DECLINED", 0)),
            item(L("Money out (disbursed and repaying)", "Pesa zilizotolewa"), round(sum(x.amount for x in loans if x.status in ("DISBURSED", "REPAYING"))), "tzs"),
            item(L("Repaid loans", "Mikopo iliyolipwa"), status.get("CLOSED", 0)),
            item(L("Average AI chance of repaying (applicants)", "Wastani wa uwezekano wa kulipa (waombaji)"), round(sum(probs) / len(probs)) if probs else None, "pct"),
        ], {
            "columns": [L("Application", "Ombi"), L("Farmer", "Mkulima"), L("Amount", "Kiasi"), L("AI chance", "Uwezekano AI"), L("Status", "Hali")],
            "formats": ["text", "text", "tzs", "pct", "text"],
            "rows": [[f"#{x.id}", farmers[x.farmer_id].display_name if x.farmer_id in farmers else "—", round(x.amount), ai_pct(x.farmer_id), x.status] for x in loans[:6]],
        }),
    ]


def insurer_report(session: Session, user: User) -> list[dict]:
    policies = session.exec(select(InsurancePolicy).where(InsurancePolicy.insurer_user_id == user.id)).all()
    status = _count_by_status(policies)
    claims = session.exec(select(InsuranceClaim).where(InsuranceClaim.policy_id.in_([p.id for p in policies])).order_by(InsuranceClaim.created_at.desc())).all() if policies else []  # type: ignore[union-attr, attr-defined]
    cstatus = _count_by_status(claims)
    return [
        section("policies", L("Policies", "Bima"), [
            item(L("Requests waiting", "Maombi yanayosubiri"), status.get("REQUESTED", 0)),
            item(L("Active policies", "Bima hai"), status.get("ACTIVE", 0)),
            item(L("Cover in force", "Kinga iliyopo"), round(sum(p.coverage_tzs for p in policies if p.status == "ACTIVE")), "tzs"),
            item(L("Premiums (active)", "Ada (hai)"), round(sum(p.premium_tzs for p in policies if p.status == "ACTIVE")), "tzs"),
        ]),
        section("claims", L("Claims", "Madai"), [
            item(L("Claims to decide", "Madai ya kuamua"), sum(n for s, n in cstatus.items() if s in ("FILED", "EVIDENCE_ATTACHED", "UNDER_REVIEW"))),
            item(L("Approved", "Yaliyoidhinishwa"), cstatus.get("APPROVED", 0)),
            item(L("Rejected", "Yaliyokataliwa"), cstatus.get("REJECTED", 0) + cstatus.get("DECLINED", 0)),
        ], {
            "columns": [L("Claim", "Dai"), L("Trigger", "Kichochezi"), L("Status", "Hali"), L("Filed", "Tarehe")],
            "formats": ["text", "text", "text", "date"],
            "rows": [[f"#{c.id}", c.trigger_type, c.status, c.created_at.date().isoformat()] for c in claims[:6]],
        }),
    ]


def admin_report(session: Session, user: User) -> list[dict]:
    since = utcnow() - timedelta(days=1)
    by_role = dict(session.exec(select(User.role, func.count()).group_by(User.role)).all())
    sales = session.exec(select(Sale).where(Sale.completed_at.is_not(None))).all()  # type: ignore[union-attr]
    intents = _count_by_status(session.exec(select(PaymentIntent)).all())
    loans = session.exec(select(LoanApplication)).all()
    return [
        section("platform", L("Platform", "Jukwaa"), [
            item(L("Users", "Watumiaji"), sum(by_role.values())),
            item(L("Farms", "Mashamba"), session.exec(select(func.count()).select_from(Farm)).one()),
            item(L("Batches recorded", "Mizigo iliyorekodiwa"), session.exec(select(func.count()).select_from(CropBatch)).one()),
            item(L("Open orders", "Oda zinazoendelea"), session.exec(select(func.count()).select_from(Order).where(Order.status.in_(OPEN_ORDER))).one()),  # type: ignore[attr-defined]
            item(L("Verified sales value", "Thamani ya mauzo yaliyothibitishwa"), round(sum(s.amount for s in sales)), "tzs"),
            item(L("Loans requested", "Mikopo iliyoombwa"), round(sum(x.amount for x in loans)), "tzs"),
        ], {
            "columns": [L("Role", "Wadhifa"), L("Users", "Watumiaji")],
            "formats": ["text", "count"],
            "rows": [[ROLE_NAMES.get(Role(r), L(str(r), str(r))), n] for r, n in sorted(by_role.items(), key=lambda kv: str(kv[0]))],
        }),
        section("operations", L("Operations (last 24 hours)", "Uendeshaji (saa 24 zilizopita)"), [
            item(L("Live payments completed", "Malipo halisi yaliyokamilika"), intents.get("COMPLETED", 0)),
            item(L("Payments failed or expired", "Malipo yaliyoshindikana"), intents.get("FAILED", 0) + intents.get("EXPIRED", 0)),
            item(L("Unresolved critical alerts", "Tahadhari kubwa zisizoshughulikiwa"), session.exec(select(func.count()).select_from(Alert).where(Alert.severity == "CRITICAL", Alert.resolved_at.is_(None))).one()),  # type: ignore[union-attr]
            item(L("SMS sent", "SMS zilizotumwa"), session.exec(select(func.count()).select_from(SmsLog).where(SmsLog.created_at >= since)).one()),
            item(L("Audited actions", "Vitendo vilivyokaguliwa"), session.exec(select(func.count()).select_from(AuditLog).where(AuditLog.ts >= since)).one()),
        ]),
    ]


BUILDERS = {
    Role.FARMER: farmer_report,
    Role.BUYER: buyer_report,
    Role.WAREHOUSE_OPERATOR: warehouse_report,
    Role.LENDER: lender_report,
    Role.INSURER: insurer_report,
    Role.ADMIN: admin_report,
}
ROLE_NAMES = {
    Role.FARMER: L("Farmers", "Wakulima"),
    Role.BUYER: L("Buyers", "Wanunuzi"),
    Role.WAREHOUSE_OPERATOR: L("Ghala operators", "Waendeshaji wa ghala"),
    Role.LENDER: L("Lenders", "Wakopeshaji"),
    Role.INSURER: L("Insurers", "Kampuni za bima"),
    Role.ADMIN: L("Admins", "Wasimamizi"),
}
TITLES = {
    Role.FARMER: L("Farmer report", "Ripoti ya mkulima"),
    Role.BUYER: L("Buyer report", "Ripoti ya mnunuzi"),
    Role.WAREHOUSE_OPERATOR: L("Ghala report", "Ripoti ya ghala"),
    Role.LENDER: L("Lender report", "Ripoti ya mkopeshaji"),
    Role.INSURER: L("Insurer report", "Ripoti ya bima"),
    Role.ADMIN: L("Platform report", "Ripoti ya jukwaa"),
}

# The user's own recorded actions, in words (anything else is left out of the change log).
ACTIONS = {
    ("CREATE", "LOAN"): L("You applied for a loan", "Uliomba mkopo"),
    ("CONTRACT_OFFERED", "CONTRACT"): L("You offered a contract", "Ulitoa ofa ya mkataba"),
    ("CONTRACT_ACCEPTED", "CONTRACT"): L("You accepted a contract", "Ulikubali mkataba"),
    ("CROP_PHOTO_ADDED", "CROP"): L("You added a crop photo", "Uliongeza picha ya zao"),
    ("LOAN_DOCUMENT_ADDED", "LOAN_DOCUMENT"): L("You uploaded a loan document", "Ulipakia nyaraka ya mkopo"),
    ("FACE_ENROLLED", "USER"): L("You turned on Face ID", "Uliwasha Face ID"),
    ("NEW_DEVICE_LOGIN", "USER"): L("Sign-in from a new device", "Kuingia kutoka kifaa kipya"),
    ("REVOKE", "CONSENT"): L("You stopped sharing data with a partner", "Uliacha kushiriki data na mshirika"),
}


def changes(session: Session, user: User) -> list[dict]:
    since = utcnow() - timedelta(days=CHANGE_DAYS)
    out = [
        {"at": a.created_at.isoformat(), "kind": a.kind, "severity": a.severity, "text": a.message}
        for a in session.exec(select(Alert).where(Alert.user_id == user.id, Alert.created_at >= since).order_by(Alert.created_at.desc()).limit(40))  # type: ignore[attr-defined]
    ]
    for e in session.exec(select(AuditLog).where(AuditLog.actor_user_id == user.id, AuditLog.ts >= since).order_by(AuditLog.ts.desc()).limit(80)):  # type: ignore[attr-defined]
        text = ACTIONS.get((e.action, e.resource_type))
        if text:
            out.append({"at": e.ts.isoformat(), "kind": "ACTIVITY", "severity": "INFO", "text": text})
    # Identical entries on the same day are shown once with a count ("x5").
    grouped: list[dict] = []
    for c in sorted(out, key=lambda c: c["at"], reverse=True):
        last = grouped[-1] if grouped else None
        if last and last["text"] == c["text"] and last["at"][:10] == c["at"][:10]:
            last["count"] += 1
        else:
            grouped.append({**c, "count": 1})
    return grouped[:50]


def build(session: Session, user: User) -> dict[str, Any]:
    sections = BUILDERS[user.role](session, user)
    log = changes(session, user)
    # The stamp changes whenever any number, row or change-log entry changes: the page uses
    # it to tell the user the report was just updated.
    stamp = hashlib.sha1(json.dumps([sections, [c["at"] for c in log]], sort_keys=True, default=str).encode()).hexdigest()[:16]
    return {
        "role": user.role.value,
        "title": TITLES[user.role],
        "subject": user.full_name,
        "generated_at": utcnow().isoformat(),
        "stamp": stamp,
        "sections": sections,
        "changes": log,
        "change_days": CHANGE_DAYS,
    }


@router.get("/reports/me")
def my_report(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return build(session, user)


# ---------------------------------------------------------------- PDF

MONTHS = {
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
    "sw": ["Jan", "Feb", "Mac", "Apr", "Mei", "Jun", "Jul", "Ago", "Sep", "Okt", "Nov", "Des"],
}


def fmt(value: Any, kind: str, lang: str) -> str:
    if value is None:
        return "—"
    if isinstance(value, dict):
        return value.get(lang) or value.get("en", "")
    if kind == "tzs":
        return f"TZS {value:,.0f}"
    if kind == "kg":
        return f"{value:,.0f} kg" if value >= 10 else f"{value:g} kg"
    if kind == "acres":
        return f"{value:g} " + ("acres" if lang == "en" else "ekari")
    if kind == "pct":
        return f"{value}%"
    if kind == "date":
        d = date.fromisoformat(str(value)[:10])
        return f"{d.day} {MONTHS[lang][d.month - 1]} {d.year}"
    if kind == "count" and isinstance(value, (int, float)):
        return f"{value:,.0f}"
    return str(value)


def render_pdf(report: dict, lang: str) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    green, line = colors.HexColor("#1f4d2e"), colors.HexColor("#d8d2c4")
    styles = getSampleStyleSheet()
    h1, h2, body, small = styles["Title"], styles["Heading2"], styles["BodyText"], styles["Italic"]
    h1.textColor = h2.textColor = green
    h1.alignment = 0
    t = lambda d: d.get(lang) or d.get("en", "")  # noqa: E731
    when = datetime.fromisoformat(report["generated_at"])
    story = [
        Paragraph(f"AgriTrust · {t(report['title'])}", h1),
        Paragraph(f"{report['subject']} · {fmt(when.date().isoformat(), 'date', lang)} {when:%H:%M} UTC", body),
        Spacer(1, 4 * mm),
    ]
    grid = TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, line), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("FONTSIZE", (0, 0), (-1, -1), 9.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)])
    for s in report["sections"]:
        story.append(Paragraph(t(s["title"]), h2))
        rows = [[Paragraph(t(i["label"]), body), fmt(i["value"], i["format"], lang)] for i in s["items"]]
        story.append(Table(rows, colWidths=[110 * mm, 60 * mm], style=grid))
        tbl = s.get("table")
        if tbl and tbl["rows"]:
            head = [t(c) for c in tbl["columns"]]
            data = [[fmt(v, f, lang) for v, f in zip(r, tbl["formats"])] for r in tbl["rows"]]
            story += [Spacer(1, 3 * mm), Table([head] + data, repeatRows=1, style=TableStyle([*grid.getCommands(), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3ea")), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]))]
        story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(("What changed (last %d days)" if lang == "en" else "Mabadiliko (siku %d zilizopita)") % report["change_days"], h2))
    if report["changes"]:
        rows = [[fmt(c["at"], "date", lang), Paragraph(t(c["text"]) + (f" (x{c['count']})" if c.get("count", 1) > 1 else ""), body)] for c in report["changes"][:30]]
        story.append(Table(rows, colWidths=[28 * mm, 142 * mm], style=grid))
    else:
        story.append(Paragraph("No changes." if lang == "en" else "Hakuna mabadiliko.", body))
    story += [Spacer(1, 6 * mm), Paragraph("Generated automatically from live platform data." if lang == "en" else "Imetengenezwa kiotomatiki kutoka data hai ya jukwaa.", small)]
    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm, title=t(report["title"]), author="AgriTrust").build(story)
    return buf.getvalue()


@router.get("/reports/me.pdf")
def my_report_pdf(lang: Literal["en", "sw"] = Query("en"), user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    report = build(session, user)
    name = f"agritrust-report-{user.role.value.lower()}-{date.today().isoformat()}.pdf"
    return StreamingResponse(io.BytesIO(render_pdf(report, lang)), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"})
