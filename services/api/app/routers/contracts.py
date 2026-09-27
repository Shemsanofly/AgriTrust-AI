"""Off-take contracts: a buyer agrees to buy part of a farmer's future harvest.

Buyer offers -> farmer accepts or declines. The buyer can withdraw an offer before it is
answered, and marks an accepted contract delivered once the harvest arrives. Accepted
contracts feed criterion 4 (market certainty) of the farmer's credit assessment."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..db import get_session
from ..i18n import bi, crop_name
from ..models import Buyer, Crop, Farm, Farmer, OffTakeContract, Role, User, utcnow
from ..notify import notify
from ..security.audit import audit
from ..security.auth import buyer_for, farmer_for, get_current_user, require_roles

router = APIRouter(tags=["contracts"])


class ContractIn(BaseModel):
    farmer_id: str = Field(min_length=3, max_length=20)  # the farmer's public id, e.g. FMR-0042
    crop_type: Literal["maize", "beans", "rice", "sorghum", "sunflower"]
    quantity_kg: float = Field(gt=0, le=1_000_000)
    price_per_kg: float = Field(gt=0, le=1_000_000)
    delivery_month: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    note: str = Field(default="", max_length=300)


class ContractAction(BaseModel):
    action: Literal["accept", "decline", "cancel", "fulfil"]


# action -> (who may do it, allowed from, new status)
TRANSITIONS = {
    "accept": ("farmer", "OFFERED", "ACCEPTED"),
    "decline": ("farmer", "OFFERED", "DECLINED"),
    "cancel": ("buyer", "OFFERED", "CANCELLED"),
    "fulfil": ("buyer", "ACCEPTED", "FULFILLED"),
}


def contract_json(session: Session, c: OffTakeContract) -> dict:
    buyer = session.get(Buyer, c.buyer_id)
    farmer = session.get(Farmer, c.farmer_id)
    return {
        **c.model_dump(mode="json"),
        "total_tzs": round(c.quantity_kg * c.price_per_kg),
        "buyer": {"name": buyer.business_name, "verified": buyer.verified} if buyer else None,
        "farmer": {"public_id": farmer.public_id, "display_name": farmer.display_name, "region": farmer.region} if farmer else None,
    }


@router.get("/contracts/farmers")
def farmer_directory(user: User = Depends(require_roles(Role.BUYER)), session: Session = Depends(get_session)):
    """Farmers a buyer can offer a contract to: public id, name, region and what they grow.
    No phone numbers or finances."""
    out = []
    for farmer in session.exec(select(Farmer).order_by(Farmer.display_name)):
        farms = list(session.exec(select(Farm).where(Farm.farmer_id == farmer.id)))
        if not farms:
            continue
        crops = session.exec(select(Crop).where(Crop.farm_id.in_([f.id for f in farms]), Crop.growth_stage != "harvested")).all()  # type: ignore[union-attr]
        out.append(
            {
                "public_id": farmer.public_id,
                "display_name": farmer.display_name,
                "region": farmer.region,
                "cooperative": farmer.cooperative,
                "acres": round(sum(f.acreage for f in farms), 1),
                "growing": sorted({c.crop_type for c in crops}),
                "next_harvest": min((c.expected_harvest_date for c in crops if c.expected_harvest_date and c.expected_harvest_date >= date.today()), default=None),
            }
        )
    return out


@router.post("/contracts", status_code=201)
def offer_contract(body: ContractIn, user: User = Depends(require_roles(Role.BUYER)), session: Session = Depends(get_session)):
    buyer = buyer_for(session, user)
    farmer = session.exec(select(Farmer).where(Farmer.public_id == body.farmer_id.upper())).first()
    if not farmer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if body.delivery_month < date.today().strftime("%Y-%m"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "delivery_in_past")
    contract = OffTakeContract(buyer_id=buyer.id, farmer_id=farmer.id, **body.model_dump(exclude={"farmer_id"}))
    session.add(contract)
    session.flush()
    notify(
        session,
        session.get(User, farmer.user_id),
        "CONTRACT",
        bi("alert.contract_offered", buyer=buyer.business_name, qty=round(contract.quantity_kg), crop=crop_name(contract.crop_type), price=round(contract.price_per_kg), month=contract.delivery_month),
        entity_type="CONTRACT",
        entity_id=str(contract.id),
        sms=True,
    )
    audit(session, user.id, "CONTRACT_OFFERED", "CONTRACT", contract.id, subject_farmer_id=farmer.id)
    session.commit()
    return contract_json(session, contract)


@router.get("/contracts")
def list_contracts(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    if user.role == Role.FARMER:
        query = select(OffTakeContract).where(OffTakeContract.farmer_id == farmer_for(session, user).id)
    elif user.role == Role.BUYER:
        query = select(OffTakeContract).where(OffTakeContract.buyer_id == buyer_for(session, user).id)
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    return [contract_json(session, c) for c in session.exec(query.order_by(OffTakeContract.created_at.desc()))]  # type: ignore[attr-defined]


@router.patch("/contracts/{contract_id}")
def update_contract(contract_id: int, body: ContractAction, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    contract = session.get(OffTakeContract, contract_id)
    if not contract:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    buyer = session.get(Buyer, contract.buyer_id)
    farmer = session.get(Farmer, contract.farmer_id)
    role = "farmer" if farmer and farmer.user_id == user.id else "buyer" if buyer and buyer.user_id == user.id else None
    if role is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    who, from_status, to_status = TRANSITIONS[body.action]
    if role != who:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    if contract.status != from_status:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    contract.status = to_status
    contract.decided_at = utcnow()
    session.add(contract)
    params = {"contract": contract.id, "qty": round(contract.quantity_kg), "crop": crop_name(contract.crop_type), "buyer": buyer.business_name, "farmer": farmer.display_name}
    if role == "farmer":
        notify(session, session.get(User, buyer.user_id), "CONTRACT", bi(f"alert.contract_{to_status.lower()}", **params), entity_type="CONTRACT", entity_id=str(contract.id))
    else:
        notify(session, session.get(User, farmer.user_id), "CONTRACT", bi(f"alert.contract_{to_status.lower()}", **params), entity_type="CONTRACT", entity_id=str(contract.id))
    audit(session, user.id, f"CONTRACT_{to_status}", "CONTRACT", contract.id, subject_farmer_id=farmer.id)
    session.commit()
    return contract_json(session, contract)
