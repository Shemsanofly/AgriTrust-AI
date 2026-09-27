import json
import logging
import math
import secrets
from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..ai.profile import build_profile
from ..chain.hashing import new_salt
from ..chain.records import anchor_entity, verify_entity
from ..config import get_settings, public_web_url
from ..db import get_session
from ..i18n import bi
from ..integrations import snippe
from ..integrations.payments_mock import simulate_payment
from ..models import (
    Buyer,
    CropBatch,
    Farmer,
    Order,
    OrderMessage,
    PaymentIntent,
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

log = logging.getLogger(__name__)
router = APIRouter(tags=["sokoni"])

RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "UNKNOWN": 2, "HIGH": 3}
MIN_MARKET_KG = 5


class OrderIn(BaseModel):
    batch_id: str
    quantity_kg: float = Field(gt=0)
    confirm_pin: Optional[str] = None


class OrderAction(BaseModel):
    action: Literal["accept", "decline", "cancel", "pay", "release", "deliver"]
    confirm_pin: Optional[str] = None
    # Live payments: the mobile-money number that gets the USSD prompt (default: the buyer's).
    phone: Optional[str] = Field(default=None, pattern=r"^\+?[0-9]{9,15}$")
    # Snippe requires the payer's email; saved to the profile when the user has none yet.
    email: Optional[str] = Field(default=None, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
    # Leftovers under MIN_MARKET_KG stay with the farmer and don't clutter the marketplace.
    query = select(CropBatch).where(CropBatch.listed == True, CropBatch.available_kg >= MIN_MARKET_KG)  # noqa: E712
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
        "payment": intent_json(latest_intent(session, order.id)),
        "payment_mode": get_settings().payments_provider,
    }


# ---------------------------------------------------------------- payments


def latest_intent(session: Session, order_id: int) -> Optional[PaymentIntent]:
    return session.exec(select(PaymentIntent).where(PaymentIntent.order_id == order_id).order_by(PaymentIntent.id.desc())).first()  # type: ignore[union-attr]


def intent_json(intent: Optional[PaymentIntent]) -> Optional[dict]:
    if not intent:
        return None
    return {
        "id": intent.id,
        "provider": intent.provider,
        "reference": intent.reference,
        "amount": intent.amount,
        "phone": intent.phone,
        "status": intent.status,
        "failure_reason": intent.failure_reason,
        "created_at": intent.created_at.isoformat(),
    }


def mark_paid(session: Session, order: Order, reference: str) -> None:
    """Money confirmed: the order moves to PAID and everyone involved is told."""
    batch, farmer, buyer, wh = order_parties(session, order)
    order.payment_ref = reference
    order.status = "PAID"
    order.updated_at = utcnow()
    session.add(order)
    for uid in {farmer.user_id, buyer.user_id} | ({wh.operator_user_id} if wh else set()):
        notify(session, session.get(User, uid), "ORDER", bi("alert.order_status", order=order.id, status="PAID"), entity_type="ORDER", entity_id=str(order.id))


SNIPPE_STATUS = {"completed": "COMPLETED", "failed": "FAILED", "expired": "EXPIRED", "voided": "VOIDED", "pending": "PENDING"}


def apply_payment_status(session: Session, intent: PaymentIntent, provider_status: str, data: dict) -> None:
    """Apply Snippe's verdict once. Final states never change again (webhooks can repeat)."""
    new = SNIPPE_STATUS.get((provider_status or "").lower())
    if not new or intent.status != "PENDING" or new == "PENDING":
        return
    amount = data.get("amount")
    paid = amount.get("value") if isinstance(amount, dict) else amount
    if new == "COMPLETED" and paid is not None and int(paid) < intent.amount:
        new, data = "FAILED", {**data, "failure_reason": f"amount_mismatch: paid {paid}, expected {intent.amount}"}
    intent.status = new
    session.add(intent)
    order = session.get(Order, intent.order_id)
    if new == "COMPLETED":
        intent.completed_at = utcnow()
        if order and order.status == "ACCEPTED":
            mark_paid(session, order, intent.reference or f"SNIPPE-{intent.id}")
    else:
        intent.failure_reason = data.get("failure_reason") or new.lower()
        if order:
            _, _, buyer, _ = order_parties(session, order)
            notify(session, session.get(User, buyer.user_id), "ORDER", bi("alert.payment_failed", order=order.id, reason=intent.failure_reason), severity="WARNING", entity_type="ORDER", entity_id=str(order.id))


class PaymentRefused(Exception):
    """Snippe refused to start the payment; the message is Snippe's own reason."""


def start_live_payment(session: Session, order: Order, user: User, phone: Optional[str], email: Optional[str] = None) -> PaymentIntent:
    """Snippe USSD push to the payer. The order stays ACCEPTED until Snippe confirms."""
    pending = latest_intent(session, order.id)
    if pending and pending.status == "PENDING":
        raise HTTPException(status.HTTP_409_CONFLICT, "payment_pending")
    amount = math.ceil(order.quantity_kg * order.price_per_kg)
    if amount < snippe.MIN_AMOUNT_TZS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "amount_too_small")
    email = (email or user.email or "").strip()
    if not email:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "email_required")
    base = public_web_url()
    if not base.startswith("https://"):
        # Snippe requires a public https webhook address (PUBLIC_WEB_URL, e.g. the ngrok link).
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "payment_setup_incomplete")
    if not user.email:
        user.email = email
        session.add(user)
    intent = PaymentIntent(order_id=order.id, provider="snippe", amount=amount, phone=phone or user.phone)
    session.add(intent)
    session.flush()
    names = (user.full_name or "Buyer").split()
    try:
        data = snippe.create_mobile_payment(
            amount_tzs=amount,
            phone=intent.phone,
            firstname=names[0],
            lastname=" ".join(names[1:]) or names[0],
            email=email,
            # Through the web server, /api/... reaches this API (see vite proxy).
            webhook_url=f"{base}/api/payments/snippe/webhook",
            metadata={"order_id": str(order.id), "batch_id": order.batch_id},
            idempotency_key=f"agt-o{order.id}-p{intent.id}",
        )
    except snippe.SnippeError as err:
        log.warning("Snippe payment for order %s failed: %s (%s)", order.id, err.message, err.error_code)
        intent.status, intent.failure_reason = "FAILED", err.message
        session.add(intent)
        session.commit()
        raise PaymentRefused(err.message) from err
    intent.reference = data.get("reference")
    session.add(intent)
    apply_payment_status(session, intent, data.get("status", "pending"), data)
    session.commit()
    return intent


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
        if get_settings().payments_provider == "snippe":
            try:
                start_live_payment(session, order, user, body.phone, body.email)
            except PaymentRefused as err:
                # Keep the usual error code, and pass Snippe's reason on so the payer sees it.
                return JSONResponse({"detail": "payment_provider_error", "reason": str(err)}, status_code=status.HTTP_502_BAD_GATEWAY)
            return order_json(session, order, user)
        order.payment_ref = simulate_payment(total, order.currency)["reference"]
        session.add(PaymentIntent(order_id=order.id, provider="simulated", reference=order.payment_ref, amount=math.ceil(total), phone=user.phone, status="COMPLETED", completed_at=utcnow()))
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


@router.get("/orders/{order_id}/payment")
def payment_status(order_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """Latest payment attempt. A pending Snippe payment is re-checked with Snippe, so the
    order still updates if the webhook cannot reach this server."""
    order = load_order(session, order_id, user)
    intent = latest_intent(session, order.id)
    if intent and intent.provider == "snippe" and intent.status == "PENDING" and intent.reference:
        try:
            data = snippe.get_payment(intent.reference)
            apply_payment_status(session, intent, data.get("status", ""), data)
            session.commit()
        except snippe.SnippeError as err:
            log.warning("Snippe status check for %s failed: %s", intent.reference, err.message)
    return {"payment": intent_json(intent), "order": order_json(session, order, user)}


@router.post("/payments/snippe/webhook")
async def snippe_webhook(request: Request, session: Session = Depends(get_session)):
    """Snippe's signed payment events. Unsigned, forged or stale calls are refused."""
    raw = await request.body()
    if not snippe.verify_webhook(raw, request.headers.get("x-webhook-signature"), request.headers.get("x-webhook-timestamp")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_signature")
    try:
        event = json.loads(raw)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_json")
    data = event.get("data") or {}
    intent = session.exec(select(PaymentIntent).where(PaymentIntent.reference == data.get("reference"))).first() if data.get("reference") else None
    if not intent:
        return {"received": True, "matched": False}  # not ours (e.g. another integration): acknowledge
    status_value = data.get("status") or str(event.get("type", "")).removeprefix("payment.")
    apply_payment_status(session, intent, status_value, data)
    session.commit()
    return {"received": True, "matched": True}


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
