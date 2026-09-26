import io
import secrets
from datetime import date, timedelta
from typing import Optional

import qrcode
from qrcode.image.svg import SvgPathImage
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..ai import anomalies
from ..chain.anchor import anchor
from ..chain.hashing import new_salt, record_hash
from ..chain.records import anchor_entity, verify_entity
from ..config import get_settings
from ..db import get_session
from ..i18n import bi
from ..models import (
    BlockchainProof,
    Crop,
    CropBatch,
    Farm,
    Farmer,
    Harvest,
    Role,
    StorageRecord,
    User,
    Warehouse,
    WarehouseReceipt,
    utcnow,
)
from ..notify import notify
from ..security.audit import audit
from ..security.auth import farmer_for, get_current_user, require_roles, warehouses_for
from ..security.consent import require_consent
from ..storage import batch_risk, close_storage_window, ghala_series

router = APIRouter(tags=["ghalani"])


class HarvestIn(BaseModel):
    crop_id: int
    harvest_date: date
    quantity_kg: float = Field(gt=0, le=1_000_000)
    notes: str = ""


class ListingIn(BaseModel):
    listed: bool
    price_per_kg: Optional[float] = Field(default=None, gt=0)


class IntakeIn(BaseModel):
    batch_id: str
    quantity_kg: float = Field(gt=0)
    grade: str = Field(pattern=r"^(A|B|C)$")
    bay: str = ""


class ReleaseIn(BaseModel):
    quantity_kg: float = Field(gt=0)


def new_batch_id(session: Session) -> str:
    while True:
        candidate = f"BATCH-{secrets.token_hex(2).upper()}"
        if not session.get(CropBatch, candidate):
            return candidate


def new_receipt_id(session: Session) -> str:
    year = date.today().year
    count = len(list(session.exec(select(WarehouseReceipt.id))))
    while True:
        count += 1
        candidate = f"WR-{year}-{count:06d}"
        if not session.get(WarehouseReceipt, candidate):
            return candidate


def can_view_batch(session: Session, user: User, batch: CropBatch) -> bool:
    if user.role == Role.ADMIN:
        return True
    if user.role == Role.FARMER:
        return farmer_for(session, user).id == batch.farmer_id
    if user.role == Role.WAREHOUSE_OPERATOR:
        return batch.warehouse_id in {w.id for w in warehouses_for(session, user)} or batch.status == "HARVESTED"
    if user.role == Role.BUYER:
        return batch.listed
    return False


def load_batch(session: Session, batch_id: str, user: User) -> CropBatch:
    batch = session.get(CropBatch, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if not can_view_batch(session, user, batch):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    return batch


def proofs_for(session: Session, entity_type: str, entity_id: str) -> list[dict]:
    return [
        p.model_dump(mode="json")
        for p in session.exec(
            select(BlockchainProof).where(BlockchainProof.entity_type == entity_type, BlockchainProof.entity_id == entity_id)
        )
    ]


def batch_json(session: Session, batch: CropBatch, detail: bool = False) -> dict:
    data = batch.model_dump(mode="json", exclude={"salt"})
    data["qr_url"] = f"{get_settings().public_web_url}/verify/{batch.id}"
    wh = session.get(Warehouse, batch.warehouse_id) if batch.warehouse_id else None
    data["warehouse"] = {"id": wh.id, "public_id": wh.public_id, "name": wh.name, "region": wh.region} if wh else None
    receipt = session.exec(select(WarehouseReceipt).where(WarehouseReceipt.batch_id == batch.id)).first()
    data["receipt"] = receipt.model_dump(mode="json", exclude={"salt"}) if receipt else None
    risk = batch_risk(session, batch) if wh else None
    data["risk"] = (
        {"level": risk.level, "drivers": risk.drivers, "action": risk.action, "stats": risk.stats, "model_version": risk.model_version}
        if risk
        else None
    )
    if detail:
        data["proofs"] = proofs_for(session, "BATCH", batch.id) + (proofs_for(session, "RECEIPT", receipt.id) if receipt else [])
        data["storage_records"] = [
            r.model_dump(mode="json", exclude={"salt"})
            for r in session.exec(select(StorageRecord).where(StorageRecord.batch_id == batch.id).order_by(StorageRecord.window_end))  # type: ignore[arg-type]
        ]
    return data


# ---------------------------------------------------------------- harvest / batches


@router.post("/harvests", status_code=201)
def record_harvest(body: HarvestIn, user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    farmer = farmer_for(session, user)
    crop = session.get(Crop, body.crop_id)
    farm = session.get(Farm, crop.farm_id) if crop else None
    if not crop or not farm or farm.farmer_id != farmer.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    harvest = Harvest(crop_id=crop.id, harvest_date=body.harvest_date, quantity_kg=body.quantity_kg, notes=body.notes)
    session.add(harvest)
    session.flush()
    batch = CropBatch(
        id=new_batch_id(session),
        harvest_id=harvest.id,
        farmer_id=farmer.id,
        crop_type=crop.crop_type,
        harvest_date=body.harvest_date,
        quantity_kg=body.quantity_kg,
        available_kg=body.quantity_kg,
        salt=new_salt(),
    )
    session.add(batch)
    crop.growth_stage = "harvested"
    session.add(crop)
    anchor_entity(session, "BATCH", batch)
    anomalies.check_duplicate_batch(session, batch)
    session.commit()
    return batch_json(session, batch, detail=True)


@router.get("/batches")
def list_batches(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    query = select(CropBatch).order_by(CropBatch.created_at.desc())  # type: ignore[attr-defined]
    if user.role == Role.FARMER:
        query = query.where(CropBatch.farmer_id == farmer_for(session, user).id)
    elif user.role == Role.WAREHOUSE_OPERATOR:
        ids = [w.id for w in warehouses_for(session, user)]
        query = query.where(CropBatch.warehouse_id.in_(ids))  # type: ignore[union-attr]
    elif user.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden_role")
    return [batch_json(session, b) for b in session.exec(query)]


@router.get("/batches/{batch_id}")
def get_batch(batch_id: str, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return batch_json(session, load_batch(session, batch_id, user), detail=True)


@router.patch("/batches/{batch_id}/listing")
def set_listing(batch_id: str, body: ListingIn, user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    batch = load_batch(session, batch_id, user)
    if body.listed:
        # Listings only come from stock with a warehouse receipt (fraud control).
        if batch.status != "IN_STORAGE" or batch.available_kg <= 0:
            raise HTTPException(status.HTTP_409_CONFLICT, "needs_warehouse_receipt")
        if not (body.price_per_kg or batch.price_per_kg):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "price_required")
    batch.listed = body.listed
    if body.price_per_kg:
        batch.price_per_kg = body.price_per_kg
    session.add(batch)
    session.commit()
    return batch_json(session, batch)


@router.get("/batches/{batch_id}/storage-risk")
def storage_risk(batch_id: str, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    batch = load_batch(session, batch_id, user)
    r = batch_risk(session, batch)
    return {"batch_id": batch.id, "level": r.level, "drivers": r.drivers, "action": r.action, "stats": r.stats, "model_version": r.model_version}


@router.get("/batches/{batch_id}/storage-history")
def storage_history(batch_id: str, hours: int = 72, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    batch = load_batch(session, batch_id, user)
    if not batch.warehouse_id:
        return []
    since = utcnow() - timedelta(hours=min(hours, 24 * 30))
    return [
        {"ts": ts.isoformat(), "temperature_c": t, "humidity_pct": h}
        for ts, t, h in ghala_series(session, batch.warehouse_id, since)
    ]


@router.post("/batches/{batch_id}/storage-records", status_code=201)
def anchor_storage_window(
    batch_id: str,
    user: User = Depends(require_roles(Role.WAREHOUSE_OPERATOR, Role.ADMIN)),
    session: Session = Depends(get_session),
):
    batch = load_batch(session, batch_id, user)
    record = close_storage_window(session, batch)
    if not record:
        raise HTTPException(status.HTTP_409_CONFLICT, "no_new_readings")
    session.commit()
    return {**record.model_dump(mode="json", exclude={"salt"}), "verification": verify_entity(session, "STORAGE", record)}


@router.get("/qr/{record_id}.svg")
def qr_svg(record_id: str):
    """QR code pointing to the public verify page (printable on bags and receipts)."""
    img = qrcode.make(f"{get_settings().public_web_url}/verify/{record_id}", image_factory=SvgPathImage, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400"})


# ---------------------------------------------------------------- warehouses


@router.get("/warehouses")
def list_warehouses(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return [
        {"id": w.id, "public_id": w.public_id, "name": w.name, "region": w.region, "verified": w.verified}
        for w in session.exec(select(Warehouse))
    ]


def own_warehouse(session: Session, user: User, warehouse_id: int) -> Warehouse:
    wh = session.get(Warehouse, warehouse_id)
    if not wh:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if user.role != Role.ADMIN and wh.operator_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    return wh


@router.get("/warehouses/{warehouse_id}/dashboard")
def warehouse_dashboard(
    warehouse_id: int,
    user: User = Depends(require_roles(Role.WAREHOUSE_OPERATOR, Role.ADMIN)),
    session: Session = Depends(get_session),
):
    wh = own_warehouse(session, user, warehouse_id)
    batches = list(session.exec(select(CropBatch).where(CropBatch.warehouse_id == wh.id)))
    series = ghala_series(session, wh.id, utcnow() - timedelta(hours=72))
    stored_kg = sum(b.available_kg for b in batches if b.status == "IN_STORAGE")
    return {
        "warehouse": wh.model_dump(),
        "stored_kg": stored_kg,
        "batches": [batch_json(session, b) for b in batches],
        "latest": {"ts": series[-1][0].isoformat(), "temperature_c": series[-1][1], "humidity_pct": series[-1][2]}
        if series
        else None,
        "history": [{"ts": ts.isoformat(), "temperature_c": t, "humidity_pct": h} for ts, t, h in series],
    }


@router.get("/warehouses/pending-batches")
def pending_batches(user: User = Depends(require_roles(Role.WAREHOUSE_OPERATOR)), session: Session = Depends(get_session)):
    """Harvested batches not yet taken into any ghala (for the intake form)."""
    rows = session.exec(select(CropBatch).where(CropBatch.status == "HARVESTED"))
    out = []
    for b in rows:
        farmer = session.get(Farmer, b.farmer_id)
        out.append(
            {
                "id": b.id,
                "crop_type": b.crop_type,
                "quantity_kg": b.quantity_kg,
                "harvest_date": b.harvest_date.isoformat(),
                "farmer": {"public_id": farmer.public_id, "display_name": farmer.display_name, "region": farmer.region} if farmer else None,
            }
        )
    return out


@router.post("/warehouses/{warehouse_id}/intake", status_code=201)
def intake(
    warehouse_id: int,
    body: IntakeIn,
    user: User = Depends(require_roles(Role.WAREHOUSE_OPERATOR)),
    session: Session = Depends(get_session),
):
    wh = own_warehouse(session, user, warehouse_id)
    if not wh.verified:
        raise HTTPException(status.HTTP_409_CONFLICT, "warehouse_not_verified")
    batch = session.get(CropBatch, body.batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if batch.status != "HARVESTED":
        raise HTTPException(status.HTTP_409_CONFLICT, "batch_already_stored")
    series = ghala_series(session, wh.id, utcnow() - timedelta(hours=6))
    receipt = WarehouseReceipt(
        id=new_receipt_id(session),
        batch_id=batch.id,
        warehouse_id=wh.id,
        owner_farmer_id=batch.farmer_id,
        quantity_kg=body.quantity_kg,
        grade=body.grade,
        date_in=date.today(),
        bay=body.bay,
        initial_temp_c=series[-1][1] if series else None,
        initial_rh_pct=series[-1][2] if series else None,
        salt=new_salt(),
    )
    session.add(receipt)
    batch.status = "IN_STORAGE"
    batch.warehouse_id = wh.id
    batch.grade = body.grade
    # Weighed at intake: this is the quantity that can be sold.
    batch.available_kg = body.quantity_kg
    session.add(batch)
    anchor_entity(session, "RECEIPT", receipt)
    anomalies.check_receipt_quantity(session, receipt, batch)
    farmer = session.get(Farmer, batch.farmer_id)
    farmer_user = session.get(User, farmer.user_id) if farmer else None
    if farmer_user:
        notify(
            session,
            farmer_user,
            "RECEIPT",
            bi("alert.receipt_issued", receipt=receipt.id, batch=batch.id, qty=receipt.quantity_kg, grade=receipt.grade),
            entity_type="RECEIPT",
            entity_id=receipt.id,
            sms=True,
        )
    session.commit()
    return receipt_json(session, receipt)


def receipt_json(session: Session, r: WarehouseReceipt) -> dict:
    wh = session.get(Warehouse, r.warehouse_id)
    farmer = session.get(Farmer, r.owner_farmer_id)
    return {
        **r.model_dump(mode="json", exclude={"salt"}),
        "warehouse": {"public_id": wh.public_id, "name": wh.name, "region": wh.region} if wh else None,
        "owner": {"public_id": farmer.public_id, "display_name": farmer.display_name} if farmer else None,
        "qr_url": f"{get_settings().public_web_url}/verify/{r.id}",
        "legal_notice": {
            "en": "Platform record only. Not a legal warehouse receipt under the regulated warehouse receipt system.",
            "sw": "Ni kumbukumbu ya jukwaa tu. Si stakabadhi rasmi ya ghala chini ya mfumo unaodhibitiwa wa stakabadhi za ghala.",
        },
        "proofs": proofs_for(session, "RECEIPT", r.id),
    }


@router.get("/receipts/{receipt_id}")
def get_receipt(receipt_id: str, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    r = session.get(WarehouseReceipt, receipt_id)
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    batch = session.get(CropBatch, r.batch_id)
    if user.role in (Role.LENDER, Role.INSURER):
        require_consent(session, r.owner_farmer_id, user.id, "receipts")
        audit(session, user.id, "READ", "RECEIPT", r.id, subject_farmer_id=r.owner_farmer_id, reason="consented_access")
        session.commit()
    elif not can_view_batch(session, user, batch):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    return receipt_json(session, r)


def release_stock(session: Session, receipt: WarehouseReceipt, quantity_kg: float) -> WarehouseReceipt:
    remaining = receipt.quantity_kg - receipt.released_kg
    if quantity_kg > remaining + 1e-6:
        raise HTTPException(status.HTTP_409_CONFLICT, "exceeds_receipt_balance")
    receipt.released_kg = round(receipt.released_kg + quantity_kg, 3)
    receipt.status = "RELEASED" if receipt.released_kg >= receipt.quantity_kg - 1e-6 else "PARTIALLY_RELEASED"
    session.add(receipt)
    # Status changes are append-only events: RECEIPT_STATUS "WR-...#1", "#2", ...
    n = len(
        list(
            session.exec(
                select(BlockchainProof).where(
                    BlockchainProof.entity_type == "RECEIPT_STATUS",
                    BlockchainProof.entity_id.startswith(f"{receipt.id}#"),  # type: ignore[attr-defined]
                )
            )
        )
    )
    event = {"receipt": receipt.id, "status": receipt.status, "released_kg": receipt.released_kg, "n": n + 1}
    anchor(session, "RECEIPT_STATUS", f"{receipt.id}#{n + 1}", record_hash(event, receipt.salt))
    batch = session.get(CropBatch, receipt.batch_id)
    if batch and receipt.status == "RELEASED" and batch.available_kg <= 0:
        batch.status = "SOLD_OUT"
        batch.listed = False
        session.add(batch)
    return receipt


@router.post("/receipts/{receipt_id}/release")
def release(
    receipt_id: str,
    body: ReleaseIn,
    user: User = Depends(require_roles(Role.WAREHOUSE_OPERATOR)),
    session: Session = Depends(get_session),
):
    r = session.get(WarehouseReceipt, receipt_id)
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    own_warehouse(session, user, r.warehouse_id)
    release_stock(session, r, body.quantity_kg)
    session.commit()
    return receipt_json(session, r)
