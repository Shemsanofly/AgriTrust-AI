import secrets
from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..ai.profile import build_profile
from ..chain.hashing import new_salt
from ..chain.records import anchor_entity, verify_entity
from ..config import get_settings, public_web_url
from ..db import get_session
from ..i18n import bi
from ..integrations.payments_mock import simulate_payment
from ..models import (
    Buyer,
    CropBatch,
    Farmer,
    Order,
    OrderMessage,
    Role,
    Sale,
    StorageRecord,
    User,
    Warehouse,
    WarehouseReceipt,
    utcnow,
)
from ..notify import notify
from ..security.auth import buyer_for, farmer_for, get_current_user, require_pin, require_roles, warehouses_for
from ..storage import batch_risk, ghala_series
from .batches import release_stock

router = APIRouter(tags=["sokoni"])

RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "UNKNOWN": 2, "HIGH": 3}


class OrderIn(BaseModel):
    batch_id: str
    quantity_kg: float = Field(gt=0)
    confirm_pin: Optional[str] = None


class OrderAction(BaseModel):
    action: Literal["accept", "decline", "cancel", "pay", "release", "deliver"]
    confirm_pin: Optional[str] = None


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=1000)


def verification_summary(session: Session, batch: CropBatch) -> dict:
    checks = [verify_entity(session, "BATCH", batch)]
    receipt = session.exec(select(WarehouseReceipt).where(WarehouseReceipt.batch_id == batch.id)).first()
    if receipt:
        checks.append(verify_entity(session, "RECEIPT", receipt))
    for rec in session.exec(select(StorageRecord).where(StorageRecord.batch_id == batch.id)):
        checks.append(verify_entity(session, "STORAGE", rec))
    statuses = {c["status"] for c in checks}
    overall = "MISMATCH" if "MISMATCH" in statuses else "VERIFIED" if statuses == {"VERIFIED"} else "PARTIAL"
    return {"status": overall, "checks": checks}


def listing_json(session: Session, batch: CropBatch, detail: bool = False) -> dict:
    farmer = session.get(Farmer, batch.farmer_id)
    wh = session.get(Warehouse, batch.warehouse_id) if batch.warehouse_id else None
    risk = batch_risk(session, batch)
    verification = verification_summary(session, batch)
    receipt = session.exec(select(WarehouseReceipt).where(WarehouseReceipt.batch_id == batch.id)).first()
    data = {
        "batch_id": batch.id,
        "crop_type": batch.crop_type,
        "grade": batch.grade,
        "available_kg": batch.available_kg,
        "price_per_kg": batch.price_per_kg,
        "currency": batch.currency,
        "harvest_date": batch.harvest_date.isoformat(),
        # No personal contact details until an order is accepted.
        "farmer": {
            "public_id": farmer.public_id,
            "display_name": farmer.display_name,
            "region": farmer.region,
            "district": farmer.district,
            "cooperative": farmer.cooperative,
        }
        if farmer
        else None,
        "warehouse": {"public_id": wh.public_id, "name": wh.name, "region": wh.region, "lat": wh.lat, "lon": wh.lon} if wh else None,
        "receipt_id": receipt.id if receipt else None,
        "date_in": receipt.date_in.isoformat() if receipt else None,
        "days_in_storage": (date.today() - receipt.date_in).days if receipt else None,
        "risk": {"level": risk.level, "headline": risk.headline, "drivers": risk.drivers, "stats": risk.stats},
        "verification_status": verification["status"],
        "qr_url": f"{public_web_url()}/verify/{batch.id}",
    }
    if detail:
        data["verification"] = verification
        data["storage_history"] = [
            {"ts": ts.isoformat(), "temperature_c": t, "humidity_pct": h}
            for ts, t, h in ghala_series(session, batch.warehouse_id, utcnow() - timedelta(hours=72))
        ] if batch.warehouse_id else []
        # Digital ghala: the farmer's other listed stock in the same warehouse.
        data["digital_ghala"] = [
            {
                "batch_id": b.id,
                "crop_type": b.crop_type,
                "grade": b.grade,
                "available_kg": b.available_kg,
                "risk": batch_risk(session, b).level,
            }
            for b in session.exec(
                select(CropBatch).where(
                    CropBatch.farmer_id == batch.farmer_id,
                    CropBatch.warehouse_id == batch.warehouse_id,
                    CropBatch.status == "IN_STORAGE",
                )
            )
        ]
        data["simulated_sensors"] = True
    return data


@router.get("/marketplace/listings")
def listings(
    crop: Optional[str] = None,
    grade: Optional[str] = None,
    region: Optional[str] = None,
    max_price: Optional[float] = None,
    min_qty: Optional[float] = None,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    query = select(CropBatch).where(CropBatch.listed == True, CropBatch.available_kg > 0)  # noqa: E712
    if crop:
        query = query.where(CropBatch.crop_type == crop)
    if grade:
        query = query.where(CropBatch.grade == grade)
    if max_price:
        query = query.where(CropBatch.price_per_kg <= max_price)  # type: ignore[operator]
    if min_qty:
        query = query.where(CropBatch.available_kg >= min_qty)
    items = [listing_json(session, b) for b in session.exec(query)]
    if region:
        items = [i for i in items if i["warehouse"] and i["warehouse"]["region"].lower() == region.lower()]
    # Buyer matching (rules): verified first, then lower storage risk, then price.
    items.sort(key=lambda i: (i["verification_status"] != "VERIFIED", RISK_ORDER.get(i["risk"]["level"], 2), i["price_per_kg"] or 0))
    return items


@router.get("/marketplace/listings/{batch_id}")
def listing_detail(batch_id: str, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    batch = session.get(CropBatch, batch_id)
    if not batch or not batch.listed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    return listing_json(session, batch, detail=True)


# ---------------------------------------------------------------- orders


def order_parties(session: Session, order: Order) -> tuple[CropBatch, Farmer, Buyer, Optional[Warehouse]]:
    batch = session.get(CropBatch, order.batch_id)
    farmer = session.get(Farmer, batch.farmer_id)
    buyer = session.get(Buyer, order.buyer_id)
    wh = session.get(Warehouse, batch.warehouse_id) if batch.warehouse_id else None
    return batch, farmer, buyer, wh


def user_role_in_order(session: Session, user: User, order: Order) -> Optional[str]:
    batch, farmer, buyer, wh = order_parties(session, order)
    if user.role == Role.BUYER and buyer.user_id == user.id:
        return "buyer"
    if user.role == Role.FARMER and farmer.user_id == user.id:
        return "farmer"
    if user.role == Role.WAREHOUSE_OPERATOR and wh and wh.operator_user_id == user.id:
        return "warehouse"
    if user.role == Role.ADMIN:
        return "admin"
    return None


def order_json(session: Session, order: Order, viewer: User) -> dict:
    batch, farmer, buyer, wh = order_parties(session, order)
    sale = session.exec(select(Sale).where(Sale.order_id == order.id)).first()
    accepted = order.status not in ("REQUESTED", "DECLINED", "CANCELLED")
    farmer_user = session.get(User, farmer.user_id)
    buyer_user = session.get(User, buyer.user_id)
    return {
        **order.model_dump(mode="json"),
        "total": round(order.quantity_kg * order.price_per_kg, 2),
        "crop_type": batch.crop_type,
        "grade": batch.grade,
        "farmer": {
            "public_id": farmer.public_id,
            "display_name": farmer.display_name,
            "region": farmer.region,
            # Contact details are shared only once the order is accepted.
            "phone": farmer_user.phone if accepted and farmer_user else None,
        },
        "buyer": {
            "business_name": buyer.business_name,
            "country": buyer.country,
            "phone": buyer_user.phone if accepted and buyer_user else None,
        },
        "warehouse": {"name": wh.name, "region": wh.region} if wh else None,
        "sale": sale.model_dump(mode="json", exclude={"salt"}) if sale else None,
        "my_role": user_role_in_order(session, viewer, order),
    }


def load_order(session: Session, order_id: int, user: User) -> Order:
    order = session.get(Order, order_id)
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if not user_role_in_order(session, user, order):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    return order


@router.post("/orders", status_code=201)
def place_order(body: OrderIn, user: User = Depends(require_roles(Role.BUYER)), session: Session = Depends(get_session)):
    buyer = buyer_for(session, user)
    batch = session.get(CropBatch, body.batch_id)
    if not batch or not batch.listed or not batch.price_per_kg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if body.quantity_kg > batch.available_kg:
        raise HTTPException(status.HTTP_409_CONFLICT, "insufficient_quantity")
    total = body.quantity_kg * batch.price_per_kg
    if total > get_settings().step_up_threshold_tzs:
        require_pin(user, body.confirm_pin)
    order = Order(buyer_id=buyer.id, batch_id=batch.id, quantity_kg=body.quantity_kg, price_per_kg=batch.price_per_kg, currency=batch.currency)
    session.add(order)
    session.flush()
    farmer = session.get(Farmer, batch.farmer_id)
    notify(
        session,
        session.get(User, farmer.user_id),
        "ORDER",
        bi("alert.order_new", buyer=buyer.business_name, qty=order.quantity_kg, batch=batch.id, price=order.price_per_kg),
        entity_type="ORDER",
        entity_id=str(order.id),
        sms=True,
    )
    session.commit()
    return order_json(session, order, user)


@router.get("/orders")
def list_orders(user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    query = select(Order).order_by(Order.created_at.desc())  # type: ignore[attr-defined]
    if user.role == Role.BUYER:
        query = query.where(Order.buyer_id == buyer_for(session, user).id)
    elif user.role == Role.FARMER:
        batch_ids = [b.id for b in session.exec(select(CropBatch).where(CropBatch.farmer_id == farmer_for(session, user).id))]
        query = query.where(Order.batch_id.in_(batch_ids))  # type: ignore[attr-defined]
    elif user.role == Role.WAREHOUSE_OPERATOR:
        wh_ids = [w.id for w in warehouses_for(session, user)]
        batch_ids = [b.id for b in session.exec(select(CropBatch).where(CropBatch.warehouse_id.in_(wh_ids)))]  # type: ignore[union-attr]
        query = query.where(Order.batch_id.in_(batch_ids))  # type: ignore[attr-defined]
    elif user.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden_role")
    return [order_json(session, o, user) for o in session.exec(query)]


@router.get("/orders/{order_id}")
def get_order(order_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    return order_json(session, load_order(session, order_id, user), user)


TRANSITIONS = {
    # action: (who, from statuses, to status)
    "accept": ("farmer", {"REQUESTED"}, "ACCEPTED"),
    "decline": ("farmer", {"REQUESTED"}, "DECLINED"),
    "cancel": ("either", {"REQUESTED", "ACCEPTED"}, "CANCELLED"),
    "pay": ("buyer", {"ACCEPTED"}, "PAID"),
    "release": ("warehouse", {"PAID"}, "RELEASED"),
    "deliver": ("buyer", {"RELEASED"}, "DELIVERED"),
}


@router.patch("/orders/{order_id}")
def update_order(order_id: int, body: OrderAction, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    order = load_order(session, order_id, user)
    role = user_role_in_order(session, user, order)
    who, allowed_from, to_status = TRANSITIONS[body.action]
    if not (who == role or (who == "either" and role in ("buyer", "farmer"))):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    if order.status not in allowed_from:
        raise HTTPException(status.HTTP_409_CONFLICT, "invalid_transition")
    batch, farmer, buyer, wh = order_parties(session, order)

    if body.action == "accept":
        if order.quantity_kg > batch.available_kg:
            raise HTTPException(status.HTTP_409_CONFLICT, "insufficient_quantity")
        batch.available_kg = round(batch.available_kg - order.quantity_kg, 3)  # reserve stock
        if batch.available_kg <= 0:
            batch.listed = False
        session.add(batch)
    elif body.action == "cancel" and order.status == "ACCEPTED":
        batch.available_kg = round(batch.available_kg + order.quantity_kg, 3)
        session.add(batch)
    elif body.action == "pay":
        total = order.quantity_kg * order.price_per_kg
        if total > get_settings().step_up_threshold_tzs:
            require_pin(user, body.confirm_pin)
        order.payment_ref = simulate_payment(total, order.currency)["reference"]
    elif body.action == "release":
        receipt = session.exec(select(WarehouseReceipt).where(WarehouseReceipt.batch_id == batch.id)).first()
        if not receipt:
            raise HTTPException(status.HTTP_409_CONFLICT, "no_receipt")
        release_stock(session, receipt, order.quantity_kg)
    elif body.action == "deliver":
        session.add(
            Sale(
                id=f"SALE-{secrets.token_hex(3).upper()}",
                order_id=order.id,
                farmer_id=farmer.id,
                buyer_id=buyer.id,
                batch_id=batch.id,
                quantity_kg=order.quantity_kg,
                amount=round(order.quantity_kg * order.price_per_kg, 2),
                currency=order.currency,
                payment_ref=order.payment_ref,
                salt=new_salt(),
            )
        )

    order.status = to_status
    order.updated_at = utcnow()
    session.add(order)
    for party_user_id in {farmer.user_id, buyer.user_id} - {user.id}:
        notify(
            session,
            session.get(User, party_user_id),
            "ORDER",
            bi("alert.order_status", order=order.id, status=to_status),
            entity_type="ORDER",
            entity_id=str(order.id),
        )
    if body.action == "pay" and wh:
        notify(session, session.get(User, wh.operator_user_id), "ORDER", bi("alert.order_status", order=order.id, status=to_status), entity_type="ORDER", entity_id=str(order.id))
    session.commit()
    return order_json(session, order, user)


@router.post("/sales/{sale_id}/confirm")
def confirm_sale(sale_id: str, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """Two-party confirmation. When both farmer and buyer confirm, the sale is anchored
    and the farmer's explainable profile is refreshed."""
    sale = session.get(Sale, sale_id)
    if not sale:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    order = load_order(session, sale.order_id, user)
    role = user_role_in_order(session, user, order)
    now = utcnow().replace(microsecond=0)
    if role == "farmer" and not sale.confirmed_by_farmer_at:
        sale.confirmed_by_farmer_at = now
    elif role == "buyer" and not sale.confirmed_by_buyer_at:
        sale.confirmed_by_buyer_at = now
    elif role not in ("farmer", "buyer"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    if sale.confirmed_by_farmer_at and sale.confirmed_by_buyer_at and not sale.completed_at:
        sale.completed_at = now
        order.status = "SALE_CONFIRMED"
        order.updated_at = now
        session.add(order)
        session.add(sale)
        anchor_entity(session, "SALE", sale)
        farmer = session.get(Farmer, sale.farmer_id)
        notify(
            session,
            session.get(User, farmer.user_id),
            "SALE",
            bi("alert.sale_confirmed", qty=sale.quantity_kg, amount=sale.amount),
            entity_type="SALE",
            entity_id=sale.id,
            sms=True,
        )
        build_profile(session, farmer)
    session.add(sale)
    session.commit()
    return order_json(session, order, user)


@router.get("/orders/{order_id}/messages")
def list_messages(order_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    order = load_order(session, order_id, user)
    rows = session.exec(select(OrderMessage).where(OrderMessage.order_id == order.id).order_by(OrderMessage.created_at))  # type: ignore[arg-type]
    return [
        {**m.model_dump(mode="json"), "mine": m.sender_user_id == user.id, "sender_name": session.get(User, m.sender_user_id).full_name}
        for m in rows
    ]


@router.post("/orders/{order_id}/messages", status_code=201)
def post_message(order_id: int, body: MessageIn, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    order = load_order(session, order_id, user)
    if user_role_in_order(session, user, order) not in ("buyer", "farmer"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    msg = OrderMessage(order_id=order.id, sender_user_id=user.id, body=body.body)
    session.add(msg)
    session.commit()
    session.refresh(msg)
    return {**msg.model_dump(mode="json"), "mine": True, "sender_name": user.full_name}
