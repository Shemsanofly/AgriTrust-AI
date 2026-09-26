"""Rule-based anomaly / fraud detection (ML is FUTURE)."""

from sqlmodel import Session, select

from ..i18n import bi
from ..models import CropBatch, Role, SensorReading, User, WarehouseReceipt
from ..notify import notify

PHYSICAL_RANGES = {
    "soil_moisture_pct": (0.0, 100.0),
    "soil_temperature_c": (-5.0, 70.0),
    "temperature_c": (-10.0, 60.0),
    "humidity_pct": (0.0, 100.0),
}
MAX_JUMP = {"soil_moisture_pct": 25.0, "soil_temperature_c": 15.0, "temperature_c": 12.0, "humidity_pct": 30.0}
FLATLINE_COUNT = 12


def check_reading(metric: str, value: float, previous: list[SensorReading]) -> dict[str, str] | None:
    """Return a bilingual reason if the new reading looks wrong. previous: newest first."""
    low, high = PHYSICAL_RANGES.get(metric, (float("-inf"), float("inf")))
    if not low <= value <= high:
        return bi("fraud.impossible", value=value)
    if previous and abs(value - previous[0].value) > MAX_JUMP.get(metric, float("inf")):
        return bi("fraud.jump", delta=round(abs(value - previous[0].value), 1))
    if len(previous) >= FLATLINE_COUNT - 1 and all(p.value == value for p in previous[: FLATLINE_COUNT - 1]):
        return bi("fraud.flatline")
    return None


def admins(session: Session) -> list[User]:
    return list(session.exec(select(User).where(User.role == Role.ADMIN)))


def check_duplicate_batch(session: Session, batch: CropBatch) -> None:
    others = session.exec(
        select(CropBatch).where(
            CropBatch.farmer_id == batch.farmer_id,
            CropBatch.crop_type == batch.crop_type,
            CropBatch.harvest_date == batch.harvest_date,
            CropBatch.quantity_kg == batch.quantity_kg,
            CropBatch.id != batch.id,
        )
    ).first()
    if others:
        for admin in admins(session):
            notify(
                session,
                admin,
                "FRAUD",
                bi("fraud.duplicate_batch", batch=batch.id, other=others.id),
                severity="WARNING",
                entity_type="BATCH",
                entity_id=batch.id,
            )


def check_receipt_quantity(session: Session, receipt: WarehouseReceipt, batch: CropBatch) -> None:
    # A receipt for more than was harvested is suspicious (small drying/cleaning losses are normal).
    if receipt.quantity_kg > batch.quantity_kg * 1.02:
        for admin in admins(session):
            notify(
                session,
                admin,
                "FRAUD",
                bi("fraud.qty_mismatch", batch=batch.id, receipt_qty=receipt.quantity_kg, batch_qty=batch.quantity_kg),
                severity="WARNING",
                entity_type="RECEIPT",
                entity_id=receipt.id,
            )
