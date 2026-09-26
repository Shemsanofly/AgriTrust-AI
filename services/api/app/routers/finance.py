from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..ai.profile import DROUGHT_PRONE_REGIONS, build_profile, profile_json
from ..db import get_session
from ..i18n import bi, crop_name
from ..integrations.open_meteo import get_rainfall_total
from ..models import (
    AuditLog,
    ConsentRecord,
    Crop,
    CropBatch,
    Farm,
    Farmer,
    InsuranceClaim,
    InsurancePolicy,
    LoanApplication,
    Role,
    Sale,
    SavingsGoal,
    User,
    WarehouseReceipt,
    utcnow,
)
from ..notify import notify
from ..security.audit import audit
from ..security.auth import farmer_for, get_current_user, require_pin, require_roles
from ..security.consent import DATA_CATEGORIES, require_consent

router = APIRouter(tags=["kifedha"])


# ---------------------------------------------------------------- schemas


class ConsentIn(BaseModel):
    grantee_user_id: int
    data_categories: list[str] = Field(min_length=1)
    purpose: str = Field(min_length=3, max_length=200)
    days: int = Field(default=90, ge=1, le=365)
    confirm_pin: str


class LoanIn(BaseModel):
    lender_user_id: int
    amount: float = Field(gt=0)
    purpose: str = Field(min_length=3, max_length=200)
    repayment_month: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    confirm_pin: str


class LoanDecisionIn(BaseModel):
    status: Literal["UNDER_REVIEW", "APPROVED", "DECLINED", "DISBURSED", "REPAYING", "CLOSED"]
    reason: Optional[str] = Field(default=None, max_length=500)
    interest_rate_pct: Optional[float] = None
    tenor_months: Optional[int] = None


class PolicyIn(BaseModel):
    insurer_user_id: int
    product: Literal["weather_index", "storage_cover"]
    coverage_tzs: float = Field(gt=0)
    farm_id: Optional[int] = None
    confirm_pin: str


class PolicyDecisionIn(BaseModel):
    status: Literal["ACTIVE", "DECLINED", "EXPIRED"]
    premium_tzs: Optional[float] = None
    reason: Optional[str] = None


class ClaimIn(BaseModel):
    policy_id: int
    trigger_type: Literal["STORAGE_LOSS", "MANUAL"] = "MANUAL"
    description: str = Field(min_length=3, max_length=1000)


class ClaimDecisionIn(BaseModel):
    status: Literal["UNDER_REVIEW", "APPROVED", "REJECTED", "PAID"]
    reason: Optional[str] = Field(default=None, max_length=500)


class GoalIn(BaseModel):
    bucket: Literal["inputs", "emergency", "household", "goal"]
    name: str = Field(min_length=2, max_length=80)
    target_amount: float = Field(gt=0)
    saved_amount: float = Field(default=0, ge=0)
    due_date: Optional[date] = None


class GoalUpdate(BaseModel):
    saved_amount: Optional[float] = Field(default=None, ge=0)
    target_amount: Optional[float] = Field(default=None, gt=0)
    name: Optional[str] = None


class ContestIn(BaseModel):
    description: str = Field(min_length=5, max_length=1000)


# ---------------------------------------------------------------- partners


@router.get("/partners")
def partners(role: Literal["LENDER", "INSURER"], user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return [{"id": u.id, "name": u.full_name} for u in session.exec(select(User).where(User.role == Role(role), User.status == "ACTIVE"))]


# ---------------------------------------------------------------- profile


@router.get("/farmers/me/profile")
def my_profile(user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    farmer = farmer_for(session, user)
    profile = build_profile(session, farmer)
    session.commit()
    return profile_json(profile, farmer)


@router.get("/farmers/{public_id}/profile")
def farmer_profile(public_id: str, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    farmer = session.exec(select(Farmer).where(Farmer.public_id == public_id)).first()
    if not farmer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if user.role == Role.FARMER:
        if farmer.user_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    elif user.role in (Role.LENDER, Role.INSURER):
        consent = require_consent(session, farmer.id, user.id, "profile")
        audit(session, user.id, "READ", "PROFILE", farmer.public_id, subject_farmer_id=farmer.id, reason=f"consent#{consent.id}: {consent.purpose}")
    else:
        # Admins and buyers never see risk profiles (RBAC matrix, README §15).
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden_role")
    profile = build_profile(session, farmer)
    session.commit()
    return profile_json(profile, farmer)


@router.post("/farmers/me/profile/contest", status_code=201)
def contest_profile(body: ContestIn, user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    """Farmers can flag wrong data (for example a missing sale); an admin reviews it."""
    farmer = farmer_for(session, user)
    for admin in session.exec(select(User).where(User.role == Role.ADMIN)):
        notify(
            session,
            admin,
            "CONTEST",
            {"en": f"{farmer.public_id} contests their profile: {body.description}", "sw": f"{farmer.public_id} anapinga wasifu wake: {body.description}"},
            severity="WARNING",
            entity_type="FARMER",
            entity_id=farmer.public_id,
        )
    audit(session, user.id, "CONTEST", "PROFILE", farmer.public_id, subject_farmer_id=farmer.id, reason=body.description[:200])
    session.commit()
    return {"status": "SUBMITTED"}


@router.get("/farmers/me/access-history")
def access_history(user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    """Who looked at my data, when and why."""
    farmer = farmer_for(session, user)
    rows = session.exec(
        select(AuditLog).where(AuditLog.subject_farmer_id == farmer.id, AuditLog.actor_user_id != user.id).order_by(AuditLog.ts.desc())  # type: ignore[attr-defined]
    )
    out = []
    for r in rows:
        actor = session.get(User, r.actor_user_id) if r.actor_user_id else None
        out.append({**r.model_dump(mode="json"), "actor_name": actor.full_name if actor else None, "actor_role": actor.role.value if actor else None})
    return out


# ---------------------------------------------------------------- consent


def consent_json(session: Session, c: ConsentRecord) -> dict:
    grantee = session.get(User, c.grantee_user_id)
    farmer = session.get(Farmer, c.farmer_id)
    now = utcnow()
    state = "REVOKED" if c.revoked_at else "EXPIRED" if c.expires_at <= now else "ACTIVE"
    return {
        **c.model_dump(mode="json"),
        "state": state,
        "grantee": {"id": grantee.id, "name": grantee.full_name, "role": grantee.role.value} if grantee else None,
        "farmer": {"public_id": farmer.public_id, "display_name": farmer.display_name} if farmer else None,
    }


def grant_consent(session: Session, user: User, farmer: Farmer, grantee_user_id: int, categories: list[str], purpose: str, days: int) -> ConsentRecord:
    grantee = session.get(User, grantee_user_id)
    if not grantee or grantee.role not in (Role.LENDER, Role.INSURER):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_grantee")
    bad = [c for c in categories if c not in DATA_CATEGORIES]
    if bad:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_category")
    consent = ConsentRecord(
        farmer_id=farmer.id,
        grantee_user_id=grantee.id,
        data_categories=categories,
        purpose=purpose,
        expires_at=utcnow() + timedelta(days=days),
    )
    session.add(consent)
    session.flush()
    audit(session, user.id, "GRANT", "CONSENT", consent.id, subject_farmer_id=farmer.id, reason=purpose)
    notify(
        session,
        grantee,
        "CONSENT",
        bi("alert.consent_granted", farmer=farmer.display_name, purpose=purpose),
        entity_type="FARMER",
        entity_id=farmer.public_id,
    )
    return consent


@router.post("/consents", status_code=201)
def create_consent(body: ConsentIn, user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    require_pin(user, body.confirm_pin)
    farmer = farmer_for(session, user)
    consent = grant_consent(session, user, farmer, body.grantee_user_id, body.data_categories, body.purpose, body.days)
    session.commit()
    return consent_json(session, consent)


@router.get("/consents")
def list_consents(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    query = select(ConsentRecord).order_by(ConsentRecord.granted_at.desc())  # type: ignore[attr-defined]
    if user.role == Role.FARMER:
        query = query.where(ConsentRecord.farmer_id == farmer_for(session, user).id)
    elif user.role in (Role.LENDER, Role.INSURER):
        query = query.where(ConsentRecord.grantee_user_id == user.id)
    elif user.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden_role")
    return [consent_json(session, c) for c in session.exec(query)]


@router.delete("/consents/{consent_id}")
def revoke_consent(consent_id: int, user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    consent = session.get(ConsentRecord, consent_id)
    farmer = farmer_for(session, user)
    if not consent or consent.farmer_id != farmer.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if not consent.revoked_at:
        consent.revoked_at = utcnow()
        session.add(consent)
        audit(session, user.id, "REVOKE", "CONSENT", consent.id, subject_farmer_id=farmer.id)
        session.commit()
    return consent_json(session, consent)


# ---------------------------------------------------------------- loans


def loan_json(session: Session, loan: LoanApplication, viewer: User) -> dict:
    farmer = session.get(Farmer, loan.farmer_id)
    lender = session.get(User, loan.lender_user_id)
    decider = session.get(User, loan.decision_by) if loan.decision_by else None
    consent = session.get(ConsentRecord, loan.consent_id) if loan.consent_id else None
    return {
        **loan.model_dump(mode="json"),
        "farmer": {"public_id": farmer.public_id, "display_name": farmer.display_name, "region": farmer.region} if farmer else None,
        "lender": {"id": lender.id, "name": lender.full_name} if lender else None,
        "decided_by_name": decider.full_name if decider else None,
        "consent": consent_json(session, consent) if consent else None,
    }


@router.post("/loans", status_code=201)
def apply_loan(body: LoanIn, user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    require_pin(user, body.confirm_pin)
    farmer = farmer_for(session, user)
    lender = session.get(User, body.lender_user_id)
    if not lender or lender.role != Role.LENDER:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_grantee")
    consent = grant_consent(
        session, user, farmer, lender.id, ["profile", "production", "storage", "sales", "receipts"], f"Loan application: {body.purpose}", 90
    )
    loan = LoanApplication(
        farmer_id=farmer.id,
        lender_user_id=lender.id,
        amount=body.amount,
        purpose=body.purpose,
        repayment_month=body.repayment_month,
        consent_id=consent.id,
    )
    session.add(loan)
    session.flush()
    notify(session, lender, "LOAN", bi("alert.loan_submitted", loan=loan.id, amount=loan.amount), entity_type="LOAN", entity_id=str(loan.id))
    audit(session, user.id, "CREATE", "LOAN", loan.id, subject_farmer_id=farmer.id)
    session.commit()
    return loan_json(session, loan, user)


@router.get("/loans")
def list_loans(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    query = select(LoanApplication).order_by(LoanApplication.created_at.desc())  # type: ignore[attr-defined]
    if user.role == Role.FARMER:
        query = query.where(LoanApplication.farmer_id == farmer_for(session, user).id)
    elif user.role == Role.LENDER:
        query = query.where(LoanApplication.lender_user_id == user.id)
    elif user.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden_role")
    return [loan_json(session, loan, user) for loan in session.exec(query)]


@router.get("/loans/{loan_id}")
def get_loan(loan_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    loan = session.get(LoanApplication, loan_id)
    if not loan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    farmer = session.get(Farmer, loan.farmer_id)
    data = None
    if user.role == Role.LENDER and loan.lender_user_id == user.id:
        data = loan_json(session, loan, user)
        try:
            consent = require_consent(session, farmer.id, user.id, "profile")
            audit(session, user.id, "READ", "PROFILE", farmer.public_id, subject_farmer_id=farmer.id, reason=f"loan#{loan.id} consent#{consent.id}")
            data["profile"] = profile_json(build_profile(session, farmer), farmer)
        except HTTPException:
            data["profile"] = None  # consent revoked or expired
        session.commit()
    elif (user.role == Role.FARMER and farmer.user_id == user.id) or user.role == Role.ADMIN:
        data = loan_json(session, loan, user)
    if data is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    return data


@router.patch("/loans/{loan_id}/decision")
def decide_loan(loan_id: int, body: LoanDecisionIn, user: User = Depends(require_roles(Role.LENDER)), session: Session = Depends(get_session)):
    """The lender records a HUMAN decision. The platform never approves or declines."""
    loan = session.get(LoanApplication, loan_id)
    if not loan or loan.lender_user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if body.status in ("APPROVED", "DECLINED") and not (body.reason and body.reason.strip()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "reason_required")
    loan.status = body.status
    if body.status in ("APPROVED", "DECLINED"):
        loan.decision_by = user.id
        loan.decision_reason = body.reason
        loan.decided_at = utcnow()
        if body.status == "APPROVED":
            loan.terms = {"interest_rate_pct": body.interest_rate_pct, "tenor_months": body.tenor_months, "repayment_month": loan.repayment_month}
    session.add(loan)
    farmer = session.get(Farmer, loan.farmer_id)
    notify(
        session,
        session.get(User, farmer.user_id),
        "LOAN",
        bi("alert.loan_decided", loan=loan.id, status=loan.status, reason=body.reason or "-"),
        entity_type="LOAN",
        entity_id=str(loan.id),
        sms=body.status in ("APPROVED", "DECLINED", "DISBURSED"),
    )
    audit(session, user.id, f"DECISION_{body.status}", "LOAN", loan.id, subject_farmer_id=farmer.id, reason=body.reason)
    session.commit()
    return loan_json(session, loan, user)


# ---------------------------------------------------------------- insurance


@router.get("/insurance/recommendations")
def insurance_recommendations(user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    farmer = farmer_for(session, user)
    recs = []
    farms = list(session.exec(select(Farm).where(Farm.farmer_id == farmer.id)))
    for farm in farms:
        crop = session.exec(select(Crop).where(Crop.farm_id == farm.id, Crop.growth_stage != "harvested")).first()
        if crop:
            threshold = 200.0 if farmer.region.lower() in DROUGHT_PRONE_REGIONS else 300.0
            coverage = round(farm.acreage * 700 * 750 * 0.5, -3)
            recs.append(
                {
                    "product": "weather_index",
                    "farm_id": farm.id,
                    "suggested_coverage_tzs": coverage,
                    "indicative_premium_tzs": round(coverage * 0.06, -2),
                    "rainfall_threshold_mm": threshold,
                    "reason": bi("insurance.rec.weather_index", crop=crop_name(crop.crop_type), mm=threshold),
                    "priority": "HIGH" if farmer.region.lower() in DROUGHT_PRONE_REGIONS else "MEDIUM",
                }
            )
    stored = sum(
        r.quantity_kg - r.released_kg
        for r in session.exec(select(WarehouseReceipt).where(WarehouseReceipt.owner_farmer_id == farmer.id))
        if r.status in ("ACTIVE", "PARTIALLY_RELEASED")
    )
    if stored > 0:
        coverage = round(stored * 750, -3)
        recs.append(
            {
                "product": "storage_cover",
                "suggested_coverage_tzs": coverage,
                "indicative_premium_tzs": round(coverage * 0.02, -2),
                "reason": bi("insurance.rec.storage_cover", kg=round(stored)),
                "priority": "MEDIUM",
            }
        )
    return {"simulated_insurer": True, "recommendations": recs}


def policy_json(session: Session, p: InsurancePolicy) -> dict:
    farmer = session.get(Farmer, p.farmer_id)
    insurer = session.get(User, p.insurer_user_id)
    claims = session.exec(select(InsuranceClaim).where(InsuranceClaim.policy_id == p.id))
    return {
        **p.model_dump(mode="json"),
        "farmer": {"public_id": farmer.public_id, "display_name": farmer.display_name, "region": farmer.region} if farmer else None,
        "insurer": {"id": insurer.id, "name": insurer.full_name} if insurer else None,
        "claims": [c.model_dump(mode="json") for c in claims],
    }


def load_policy(session: Session, policy_id: int, user: User) -> InsurancePolicy:
    p = session.get(InsurancePolicy, policy_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if user.role == Role.FARMER and farmer_for(session, user).id == p.farmer_id:
        return p
    if user.role == Role.INSURER and p.insurer_user_id == user.id:
        return p
    if user.role == Role.ADMIN:
        return p
    raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")


@router.post("/insurance/policies", status_code=201)
def request_policy(body: PolicyIn, user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    require_pin(user, body.confirm_pin)
    farmer = farmer_for(session, user)
    insurer = session.get(User, body.insurer_user_id)
    if not insurer or insurer.role != Role.INSURER:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_grantee")
    farm = session.get(Farm, body.farm_id) if body.farm_id else None
    if body.product == "weather_index":
        if not farm or farm.farmer_id != farmer.id:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "farm_required")
    grant_consent(session, user, farmer, insurer.id, ["profile", "production", "storage"], f"Insurance: {body.product}", 180)
    today = date.today()
    policy = InsurancePolicy(
        farmer_id=farmer.id,
        insurer_user_id=insurer.id,
        product=body.product,
        coverage_tzs=body.coverage_tzs,
        premium_tzs=round(body.coverage_tzs * (0.06 if body.product == "weather_index" else 0.02), -2),
        farm_id=farm.id if farm else None,
        rainfall_threshold_mm=(200.0 if farmer.region.lower() in DROUGHT_PRONE_REGIONS else 300.0) if body.product == "weather_index" else None,
        window_start=today - timedelta(days=60) if body.product == "weather_index" else None,
        window_end=today + timedelta(days=60) if body.product == "weather_index" else None,
    )
    session.add(policy)
    session.commit()
    return policy_json(session, policy)


@router.get("/insurance/policies")
def list_policies(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    query = select(InsurancePolicy).order_by(InsurancePolicy.created_at.desc())  # type: ignore[attr-defined]
    if user.role == Role.FARMER:
        query = query.where(InsurancePolicy.farmer_id == farmer_for(session, user).id)
    elif user.role == Role.INSURER:
        query = query.where(InsurancePolicy.insurer_user_id == user.id)
    elif user.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden_role")
    return [policy_json(session, p) for p in session.exec(query)]


@router.patch("/insurance/policies/{policy_id}")
def decide_policy(policy_id: int, body: PolicyDecisionIn, user: User = Depends(require_roles(Role.INSURER)), session: Session = Depends(get_session)):
    p = load_policy(session, policy_id, user)
    p.status = body.status
    if body.premium_tzs:
        p.premium_tzs = body.premium_tzs
    session.add(p)
    farmer = session.get(Farmer, p.farmer_id)
    notify(session, session.get(User, farmer.user_id), "INSURANCE", bi("alert.policy_status", policy=p.id, product=p.product, status=p.status), entity_type="POLICY", entity_id=str(p.id))
    audit(session, user.id, f"POLICY_{body.status}", "POLICY", p.id, subject_farmer_id=p.farmer_id, reason=body.reason)
    session.commit()
    return policy_json(session, p)


@router.post("/insurance/policies/{policy_id}/check-trigger")
def check_parametric_trigger(policy_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """SIMULATED parametric demo: if cumulative rainfall in the window is below the
    threshold, a claim is *proposed*. The insurer still reviews and decides."""
    p = load_policy(session, policy_id, user)
    if p.product != "weather_index" or not p.farm_id or not p.window_start or not p.window_end:
        raise HTTPException(status.HTTP_409_CONFLICT, "not_parametric")
    if p.status != "ACTIVE":
        raise HTTPException(status.HTTP_409_CONFLICT, "policy_not_active")
    farm = session.get(Farm, p.farm_id)
    end = min(p.window_end, date.today())
    rainfall, simulated, source = get_rainfall_total(farm.lat, farm.lon, p.window_start, end)
    triggered = rainfall < (p.rainfall_threshold_mm or 0)
    result = {
        "policy_id": p.id,
        "window_start": p.window_start.isoformat(),
        "window_end": end.isoformat(),
        "rainfall_mm": rainfall,
        "threshold_mm": p.rainfall_threshold_mm,
        "triggered": triggered,
        "simulated": simulated,
        "source": source,
        "claim": None,
    }
    if triggered:
        existing = session.exec(
            select(InsuranceClaim).where(InsuranceClaim.policy_id == p.id, InsuranceClaim.trigger_type == "PARAMETRIC_RAINFALL")
        ).first()
        claim = existing or InsuranceClaim(
            policy_id=p.id,
            trigger_type="PARAMETRIC_RAINFALL",
            status="EVIDENCE_ATTACHED",
            evidence={k: v for k, v in result.items() if k != "claim"},
        )
        if not existing:
            session.add(claim)
            session.flush()
            farmer = session.get(Farmer, p.farmer_id)
            for recipient in (session.get(User, farmer.user_id), session.get(User, p.insurer_user_id)):
                notify(session, recipient, "CLAIM", bi("alert.claim_proposed", policy=p.id), severity="WARNING", entity_type="CLAIM", entity_id=str(claim.id), sms=recipient.role == Role.FARMER)
        session.commit()
        result["claim"] = claim.model_dump(mode="json")
    return result


@router.post("/insurance/claims", status_code=201)
def file_claim(body: ClaimIn, user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    p = load_policy(session, body.policy_id, user)
    if p.status != "ACTIVE":
        raise HTTPException(status.HTTP_409_CONFLICT, "policy_not_active")
    evidence: dict = {"description": body.description}
    if body.trigger_type == "STORAGE_LOSS":
        farmer = farmer_for(session, user)
        evidence["batches"] = [b.id for b in session.exec(select(CropBatch).where(CropBatch.farmer_id == farmer.id, CropBatch.status == "IN_STORAGE"))]
    claim = InsuranceClaim(policy_id=p.id, trigger_type=body.trigger_type, status="FILED", evidence=evidence)
    session.add(claim)
    session.flush()
    notify(session, session.get(User, p.insurer_user_id), "CLAIM", bi("alert.claim_filed", claim=claim.id, policy=p.id), entity_type="CLAIM", entity_id=str(claim.id))
    session.commit()
    return claim.model_dump(mode="json")


@router.get("/insurance/claims")
def list_claims(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    policies = list_policies(user, session)
    return [{**c, "policy_id": p["id"], "product": p["product"], "farmer": p["farmer"]} for p in policies for c in p["claims"]]


@router.patch("/insurance/claims/{claim_id}/decision")
def decide_claim(claim_id: int, body: ClaimDecisionIn, user: User = Depends(require_roles(Role.INSURER)), session: Session = Depends(get_session)):
    """The insurer records a HUMAN decision on the claim."""
    claim = session.get(InsuranceClaim, claim_id)
    if not claim:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    p = load_policy(session, claim.policy_id, user)
    if body.status in ("APPROVED", "REJECTED") and not (body.reason and body.reason.strip()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "reason_required")
    claim.status = body.status
    if body.status in ("APPROVED", "REJECTED"):
        claim.decided_by = user.id
        claim.decision_reason = body.reason
    session.add(claim)
    farmer = session.get(Farmer, p.farmer_id)
    notify(
        session,
        session.get(User, farmer.user_id),
        "CLAIM",
        bi("alert.claim_decided", claim=claim.id, status=claim.status, reason=body.reason or "-"),
        entity_type="CLAIM",
        entity_id=str(claim.id),
        sms=body.status in ("APPROVED", "REJECTED", "PAID"),
    )
    audit(session, user.id, f"CLAIM_{body.status}", "CLAIM", claim.id, subject_farmer_id=p.farmer_id, reason=body.reason)
    session.commit()
    return claim.model_dump(mode="json")


# ---------------------------------------------------------------- savings

SPLIT = {"inputs": 0.40, "emergency": 0.20, "household": 0.30, "goal": 0.10}


@router.get("/savings/plan")
def savings_plan(user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    """Rule-based split of the latest verified income. The farmer can always change it."""
    farmer = farmer_for(session, user)
    last_sale = session.exec(
        select(Sale).where(Sale.farmer_id == farmer.id, Sale.completed_at.is_not(None)).order_by(Sale.completed_at.desc())  # type: ignore[union-attr]
    ).first()
    if last_sale:
        amount, source = last_sale.amount, "latest_verified_sale"
    else:
        flow = build_profile(session, farmer).cash_flow
        rng = flow.get("expected_income_range_tzs")
        amount, source = (rng[0], "cash_flow_estimate_low") if rng else (0.0, "none")
        session.rollback()  # planning only; do not store a new profile snapshot
    return {
        "income_tzs": amount,
        "source": source,
        "reason": bi("savings.reason", amount=round(amount)),
        "buckets": [{"bucket": b, "label": bi(f"savings.{b}"), "share": s, "amount_tzs": round(amount * s, -2)} for b, s in SPLIT.items()],
        "method": "rules",
    }


def _own_goal(session: Session, user: User, goal_id: int) -> SavingsGoal:
    goal = session.get(SavingsGoal, goal_id)
    if not goal or goal.farmer_id != farmer_for(session, user).id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return goal


@router.get("/savings/goals")
def list_goals(user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    return list(session.exec(select(SavingsGoal).where(SavingsGoal.farmer_id == farmer_for(session, user).id)))


@router.post("/savings/goals", status_code=201)
def create_goal(body: GoalIn, user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    goal = SavingsGoal(farmer_id=farmer_for(session, user).id, **body.model_dump())
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


@router.patch("/savings/goals/{goal_id}")
def update_goal(goal_id: int, body: GoalUpdate, user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    goal = _own_goal(session, user, goal_id)
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(goal, key, value)
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


@router.delete("/savings/goals/{goal_id}", status_code=204)
def delete_goal(goal_id: int, user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    session.delete(_own_goal(session, user, goal_id))
    session.commit()
