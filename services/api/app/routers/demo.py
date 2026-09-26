"""Demo helpers (DEV_MODE only). Readings go through the same ingestion path as real
devices; the UI labels them SIMULATED. The tamper endpoint edits the database directly
to show that verification detects silent changes."""

import math
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..config import get_settings
from ..db import get_session
from ..models import AuditLog, CropBatch, Farm, Role, Sensor, SensorReading, User, Warehouse, utcnow
from ..security.audit import audit
from ..security.auth import farmer_for, get_current_user, require_roles
from .iot import ingest

router = APIRouter(prefix="/demo", tags=["demo"])


def _require_dev() -> None:
    if not get_settings().dev_mode:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")


def _curve(start: float, end: float, n: int, wobble: float = 0.4) -> list[float]:
    return [round(start + (end - start) * i / (n - 1) + wobble * math.sin(i * 1.3), 1) for i in range(n)]


def _inject(session: Session, sensor: Sensor, series: list[dict[str, float]], hours: float) -> int:
    """Replay a scenario over the last `hours`. The replay replaces that sensor's readings
    in the same span so the curve is clean (demo only)."""
    now = utcnow().replace(microsecond=0)
    n = len(series)
    for old in session.exec(
        select(SensorReading).where(SensorReading.sensor_id == sensor.id, SensorReading.ts >= now - timedelta(hours=hours))
    ):
        session.delete(old)
    session.flush()
    for i, readings in enumerate(series):
        ts = now - timedelta(hours=hours * (n - 1 - i) / max(1, n - 1))
        ingest(session, sensor, ts, readings, sensor.last_seq + 1)
    sensor.simulated = True
    session.add(sensor)
    return n


SCENARIOS = {
    # name: (sensor type, builder)
    "soil-drying": ("soil", lambda n: [{"soil_moisture_pct": m, "soil_temperature_c": t} for m, t in zip(_curve(31, 21, n), _curve(24, 29, n))]),
    "soil-wet": ("soil", lambda n: [{"soil_moisture_pct": m, "soil_temperature_c": t} for m, t in zip(_curve(27, 36, n), _curve(24, 23, n))]),
    "ghala-humid": ("ghala", lambda n: [{"temperature_c": t, "humidity_pct": h} for t, h in zip(_curve(26, 31, n), _curve(62, 83, n))]),
    "ghala-normal": ("ghala", lambda n: [{"temperature_c": t, "humidity_pct": h} for t, h in zip(_curve(24, 25, n), _curve(58, 60, n))]),
}


@router.post("/scenario/{name}")
def run_scenario(name: str, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    _require_dev()
    if name not in SCENARIOS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_scenario")
    sensor_type, builder = SCENARIOS[name]
    query = select(Sensor).where(Sensor.type == sensor_type)
    if user.role == Role.FARMER and sensor_type == "soil":
        farm_ids = [f.id for f in session.exec(select(Farm).where(Farm.farmer_id == farmer_for(session, user).id))]
        query = query.where(Sensor.farm_id.in_(farm_ids))  # type: ignore[union-attr]
    elif user.role == Role.WAREHOUSE_OPERATOR and sensor_type == "ghala":
        wh_ids = [w.id for w in session.exec(select(Warehouse).where(Warehouse.operator_user_id == user.id))]
        query = query.where(Sensor.warehouse_id.in_(wh_ids))  # type: ignore[union-attr]
    elif user.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden_role")
    sensors = list(session.exec(query))
    total = sum(_inject(session, s, builder(24), hours=12 if sensor_type == "soil" else 24) for s in sensors)
    session.commit()
    return {"scenario": name, "sensors": [s.device_id for s in sensors], "readings": total, "simulated": True}


@router.post("/tamper/{batch_id}")
def tamper(batch_id: str, user: User = Depends(require_roles(Role.ADMIN)), session: Session = Depends(get_session)):
    """Silently change a batch quantity in the database (the tamper demo)."""
    _require_dev()
    batch = session.get(CropBatch, batch_id)
    if not batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    audit(session, user.id, "DEMO_TAMPER", "BATCH", batch.id, reason=f"original_quantity_kg={batch.quantity_kg}")
    batch.quantity_kg = batch.quantity_kg + 500
    session.add(batch)
    session.commit()
    return {"batch_id": batch.id, "quantity_kg": batch.quantity_kg}


@router.post("/restore/{batch_id}")
def restore(batch_id: str, user: User = Depends(require_roles(Role.ADMIN)), session: Session = Depends(get_session)):
    _require_dev()
    batch = session.get(CropBatch, batch_id)
    entry = session.exec(
        select(AuditLog)
        .where(AuditLog.action == "DEMO_TAMPER", AuditLog.resource_id == batch_id)
        .order_by(AuditLog.ts.asc())  # type: ignore[attr-defined]
    ).first()
    if not batch or not entry or not entry.reason:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "nothing_to_restore")
    batch.quantity_kg = float(entry.reason.split("=")[1])
    session.add(batch)
    audit(session, user.id, "DEMO_RESTORE", "BATCH", batch.id)
    session.commit()
    return {"batch_id": batch.id, "quantity_kg": batch.quantity_kg}


@router.post("/weather/{mode}")
def demo_weather(mode: str, user: User = Depends(get_current_user)):
    """Demo: 'rain' forces a rainy forecast, 'dry' a dry one, 'live' returns to normal."""
    _require_dev()
    from ..integrations import open_meteo

    if mode not in ("rain", "dry", "live"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown_scenario")
    open_meteo.DEMO_OVERRIDE["weather"] = None if mode == "live" else mode
    open_meteo._cache.clear()
    return {"weather": mode, "simulated": mode != "live"}
