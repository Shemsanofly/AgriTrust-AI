"""Public QR verification: /verify/<BATCH-… | WR-… | SALE-…>. Returns only public,
non-personal information plus a status for every anchored record."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..chain.anchor import chain_mode
from ..chain.records import verify_entity
from ..db import get_session
from ..models import CropBatch, Farmer, Sale, StorageRecord, Warehouse, WarehouseReceipt

router = APIRouter(tags=["verify"])


def _overall(checks: list[dict]) -> str:
    statuses = {c["status"] for c in checks}
    if "MISMATCH" in statuses:
        return "MISMATCH"
    if statuses == {"VERIFIED"}:
        return "VERIFIED"
    if "VERIFIED" in statuses:
        return "PARTIAL"
    return "NOT_ANCHORED"


@router.get("/verify/{record_id}")
def verify(record_id: str, session: Session = Depends(get_session)):
    batch = None
    if record_id.startswith("BATCH-"):
        batch = session.get(CropBatch, record_id)
    elif record_id.startswith("WR-"):
        receipt = session.get(WarehouseReceipt, record_id)
        batch = session.get(CropBatch, receipt.batch_id) if receipt else None
    elif record_id.startswith("SALE-"):
        sale = session.get(Sale, record_id)
        batch = session.get(CropBatch, sale.batch_id) if sale else None
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")

    farmer = session.get(Farmer, batch.farmer_id)
    shambani = {
        "stage": "SHAMBANI",
        "facts": {
            "batch_id": batch.id,
            "crop_type": batch.crop_type,
            "harvest_date": batch.harvest_date.isoformat(),
            "quantity_kg": batch.quantity_kg,
            "farmer": farmer.public_id if farmer else None,  # pseudonymous
            "region": farmer.region if farmer else None,
        },
        "checks": [verify_entity(session, "BATCH", batch)],
    }

    receipt = session.exec(select(WarehouseReceipt).where(WarehouseReceipt.batch_id == batch.id)).first()
    ghalani = None
    if receipt:
        wh = session.get(Warehouse, receipt.warehouse_id)
        storage = list(session.exec(select(StorageRecord).where(StorageRecord.batch_id == batch.id).order_by(StorageRecord.window_end)))  # type: ignore[arg-type]
        ghalani = {
            "stage": "GHALANI",
            "facts": {
                "receipt_id": receipt.id,
                "warehouse": wh.name if wh else None,
                "warehouse_region": wh.region if wh else None,
                "date_in": receipt.date_in.isoformat(),
                "quantity_kg": receipt.quantity_kg,
                "grade": receipt.grade,
                "receipt_status": receipt.status,
                "storage_windows": [
                    {
                        "window_start": s.window_start.isoformat(),
                        "window_end": s.window_end.isoformat(),
                        "risk_level": s.risk_level,
                        "temp_avg": s.temp_avg,
                        "rh_avg": s.rh_avg,
                        "reading_count": s.reading_count,
                    }
                    for s in storage
                ],
            },
            "checks": [verify_entity(session, "RECEIPT", receipt)] + [verify_entity(session, "STORAGE", s) for s in storage],
        }

    sales = list(session.exec(select(Sale).where(Sale.batch_id == batch.id, Sale.completed_at.is_not(None))))  # type: ignore[union-attr]
    sokoni = None
    if sales:
        sokoni = {
            "stage": "SOKONI",
            "facts": {
                "verified_sales": [
                    {"sale_id": s.id, "quantity_kg": s.quantity_kg, "completed_at": s.completed_at.isoformat()} for s in sales
                ]
            },
            "checks": [verify_entity(session, "SALE", s) for s in sales],
        }

    stages = [s for s in (shambani, ghalani, sokoni) if s]
    all_checks = [c for s in stages for c in s["checks"]]
    return {
        "record_id": record_id,
        "batch_id": batch.id,
        "status": _overall(all_checks),
        "chain_mode": chain_mode(),
        "stages": stages,
        "note": {
            "en": "Verified means the record has not changed since it was anchored. It does not prove the original data was true.",
            "sw": "Imethibitishwa maana yake kumbukumbu haijabadilika tangu ilipohifadhiwa kwenye blockchain. Haithibitishi kwamba data ya awali ilikuwa sahihi.",
        },
    }
