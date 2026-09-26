"""The exact fields of each record that get hashed. Anything not listed here can change
without breaking verification (for example, listing price or receipt status)."""

from typing import Any

from sqlmodel import Session, select

from ..models import BlockchainProof, CropBatch, Farmer, Sale, StorageRecord, Warehouse, WarehouseReceipt
from .anchor import anchor, read_proof
from .hashing import record_hash


def batch_record(session: Session, b: CropBatch) -> dict[str, Any]:
    farmer = session.get(Farmer, b.farmer_id)
    return {
        "id": b.id,
        "farmer": farmer.public_id if farmer else None,  # pseudonymous
        "crop_type": b.crop_type,
        "harvest_date": b.harvest_date,
        "quantity_kg": b.quantity_kg,
    }


def receipt_record(session: Session, r: WarehouseReceipt) -> dict[str, Any]:
    farmer = session.get(Farmer, r.owner_farmer_id)
    wh = session.get(Warehouse, r.warehouse_id)
    return {
        "id": r.id,
        "batch_id": r.batch_id,
        "warehouse": wh.public_id if wh else None,
        "owner": farmer.public_id if farmer else None,
        "quantity_kg": r.quantity_kg,
        "grade": r.grade,
        "date_in": r.date_in,
        "bay": r.bay,
    }


def storage_record(_: Session, s: StorageRecord) -> dict[str, Any]:
    return {
        "id": s.id,
        "batch_id": s.batch_id,
        "window_start": s.window_start,
        "window_end": s.window_end,
        "reading_count": s.reading_count,
        "temp_avg": s.temp_avg,
        "temp_max": s.temp_max,
        "rh_avg": s.rh_avg,
        "rh_max": s.rh_max,
        "risk_level": s.risk_level,
        "merkle_root": s.merkle_root,
    }


def sale_record(_: Session, s: Sale) -> dict[str, Any]:
    return {
        "id": s.id,
        "order_id": s.order_id,
        "batch_id": s.batch_id,
        "quantity_kg": s.quantity_kg,
        "amount": s.amount,
        "currency": s.currency,
        "confirmed_by_farmer_at": s.confirmed_by_farmer_at,
        "confirmed_by_buyer_at": s.confirmed_by_buyer_at,
    }


BUILDERS = {
    "BATCH": batch_record,
    "RECEIPT": receipt_record,
    "STORAGE": storage_record,
    "SALE": sale_record,
}


def anchor_entity(session: Session, entity_type: str, entity: Any) -> BlockchainProof:
    session.flush()
    data_hash = record_hash(BUILDERS[entity_type](session, entity), entity.salt)
    return anchor(session, entity_type, str(entity.id), data_hash)


def verify_entity(session: Session, entity_type: str, entity: Any) -> dict[str, Any]:
    """Recompute the salted hash from the database and compare with the anchored one."""
    proof = session.exec(
        select(BlockchainProof).where(
            BlockchainProof.entity_type == entity_type, BlockchainProof.entity_id == str(entity.id)
        )
    ).first()
    result: dict[str, Any] = {"entity_type": entity_type, "entity_id": str(entity.id)}
    if not proof:
        return {**result, "status": "NOT_ANCHORED"}
    onchain = read_proof(session, proof)
    recomputed = record_hash(BUILDERS[entity_type](session, entity), entity.salt)
    result.update(
        {
            "mode": proof.mode,
            "tx_hash": proof.tx_hash,
            "block_number": proof.block_number,
            "chain_id": proof.chain_id,
            "recomputed_hash": recomputed,
            "onchain_hash": onchain.data_hash if onchain else None,
            "issuer": onchain.issuer if onchain else proof.issuer,
            "anchored_at": onchain.timestamp if onchain else None,
        }
    )
    if not onchain:
        result["status"] = "NOT_ANCHORED"
    elif onchain.data_hash.lower() == recomputed.lower():
        result["status"] = "VERIFIED"
    else:
        result["status"] = "MISMATCH"
    return result
