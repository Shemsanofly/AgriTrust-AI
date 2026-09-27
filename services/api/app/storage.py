"""Ghala monitoring: current spoilage risk per batch, alerts, and storage-record windows
(summaries whose Merkle root is anchored on chain)."""

from datetime import datetime, timedelta

from sqlmodel import Session, select

from .ai import ghala, spoilage
from .chain.hashing import canonical_json, merkle_root, new_salt
from .chain.records import anchor_entity
from .i18n import bi
from .integrations.open_meteo import get_current_conditions
from .models import Alert, CropBatch, Farmer, Sensor, SensorReading, StorageRecord, User, Warehouse, WarehouseReceipt, utcnow
from .notify import notify


def ghala_series(session: Session, warehouse_id: int, since: datetime, until: datetime | None = None) -> list[tuple[datetime, float, float]]:
    """(ts, temperature_c, humidity_pct) pairs from the warehouse's ghala sensors."""
    sensor_ids = [s.id for s in session.exec(select(Sensor).where(Sensor.warehouse_id == warehouse_id))]
    if not sensor_ids:
        return []
    query = select(SensorReading).where(
        SensorReading.sensor_id.in_(sensor_ids),  # type: ignore[union-attr]
        SensorReading.ts >= since,
        SensorReading.quality_flag == "OK",
    )
    if until:
        query = query.where(SensorReading.ts <= until)
    rows = session.exec(query.order_by(SensorReading.ts))  # type: ignore[arg-type]
    by_ts: dict[datetime, dict[str, float]] = {}
    for r in rows:
        by_ts.setdefault(r.ts, {})[r.metric] = r.value
    return [(ts, v["temperature_c"], v["humidity_pct"]) for ts, v in sorted(by_ts.items()) if "temperature_c" in v and "humidity_pct" in v]


def batch_risk(session: Session, batch: CropBatch, now: datetime | None = None) -> spoilage.SpoilageAssessment:
    if not batch.warehouse_id:
        return spoilage.assess([], batch.crop_type)
    now = now or utcnow()
    receipt = session.exec(select(WarehouseReceipt).where(WarehouseReceipt.batch_id == batch.id)).first()
    days = (now.date() - receipt.date_in).days if receipt else 0
    series = ghala_series(session, batch.warehouse_id, now - timedelta(hours=24))
    return spoilage.assess(series, batch.crop_type, days)


def batch_outlook(session: Session, batch: CropBatch, now: datetime | None = None) -> ghala.GhalaOutlook:
    """Room forecast + quick actions for the ghala holding this batch."""
    if not batch.warehouse_id:
        return ghala.outlook([], None, batch.crop_type)
    now = now or utcnow()
    series = ghala_series(session, batch.warehouse_id, now - timedelta(hours=24))
    wh = session.get(Warehouse, batch.warehouse_id)
    outside = get_current_conditions(wh.lat, wh.lon) if wh and wh.lat is not None and wh.lon is not None else None
    return ghala.outlook(series, outside, batch.crop_type)


def evaluate_warehouse(session: Session, warehouse: Warehouse) -> None:
    """Called after new ghala readings: alert farmer + operator on HIGH risk (deduplicated)."""
    batches = session.exec(
        select(CropBatch).where(CropBatch.warehouse_id == warehouse.id, CropBatch.status == "IN_STORAGE")
    )
    operator = session.get(User, warehouse.operator_user_id)
    for batch in batches:
        result = batch_risk(session, batch)
        if result.level != "HIGH":
            continue
        farmer = session.get(Farmer, batch.farmer_id)
        farmer_user = session.get(User, farmer.user_id) if farmer else None
        recent = session.exec(
            select(Alert).where(
                Alert.kind == "SPOILAGE_RISK",
                Alert.entity_id == batch.id,
                Alert.created_at >= utcnow() - timedelta(hours=6),
            )
        ).first()
        if recent:
            continue
        message = bi(
            "alert.spoilage",
            level=bi("risk.HIGH"),
            batch=batch.id,
            warehouse=warehouse.name,
            action=result.action,
        )
        for user in (farmer_user, operator):
            if user:
                notify(session, user, "SPOILAGE_RISK", message, severity="CRITICAL", entity_type="BATCH", entity_id=batch.id, sms=True)


def close_storage_window(session: Session, batch: CropBatch, window_end: datetime | None = None) -> StorageRecord | None:
    """Summarise readings since the last window and anchor the summary + Merkle root."""
    if not batch.warehouse_id:
        return None
    window_end = window_end or utcnow()
    last = session.exec(
        select(StorageRecord).where(StorageRecord.batch_id == batch.id).order_by(StorageRecord.window_end.desc())  # type: ignore[attr-defined]
    ).first()
    receipt = session.exec(select(WarehouseReceipt).where(WarehouseReceipt.batch_id == batch.id)).first()
    if last:
        window_start = last.window_end + timedelta(seconds=1)
    elif receipt:
        window_start = min(receipt.created_at, window_end - timedelta(hours=24))
    else:
        window_start = window_end - timedelta(hours=24)
    series = ghala_series(session, batch.warehouse_id, window_start, window_end)
    if not series:
        return None
    days = (window_end.date() - receipt.date_in).days if receipt else 0
    result = spoilage.assess(series, batch.crop_type, days)
    leaves = [canonical_json({"ts": ts, "temperature_c": t, "humidity_pct": h}) for ts, t, h in series]
    record = StorageRecord(
        batch_id=batch.id,
        warehouse_id=batch.warehouse_id,
        window_start=series[0][0],
        window_end=series[-1][0],
        reading_count=len(series),
        temp_avg=result.stats["temp_avg"],
        temp_max=result.stats["temp_max"],
        rh_avg=result.stats["rh_avg"],
        rh_max=result.stats["rh_max"],
        risk_level=result.level,
        merkle_root=merkle_root(leaves),
        salt=new_salt(),
    )
    session.add(record)
    session.flush()
    anchor_entity(session, "STORAGE", record)
    return record
