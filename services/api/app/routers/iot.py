"""IoT ingestion. Devices sign payloads with HMAC-SHA256 using a per-device secret:

    sig = "hmac-sha256:" + hex(HMAC(secret, canonical_json({device_id, ts, readings, seq})))

Stale/replayed messages (seq not increasing, ts too far in the past or future) and
physically impossible values are rejected or flagged."""

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from ..ai import anomalies, irrigation
from ..db import get_session
from ..i18n import bi
from ..models import Alert, Farm, Farmer, Sensor, SensorReading, User, Warehouse, utcnow
from ..notify import notify
from ..storage import evaluate_warehouse

router = APIRouter(prefix="/iot", tags=["iot"])

ALLOWED_METRICS = {
    "soil": {"soil_moisture_pct", "soil_temperature_c"},
    "ghala": {"temperature_c", "humidity_pct"},
}
MAX_BACKFILL = timedelta(days=7)  # store-and-forward: devices may upload buffered readings
MAX_CLOCK_SKEW = timedelta(minutes=5)


class ReadingsIn(BaseModel):
    device_id: str
    ts: str  # ISO-8601, kept as the exact string the device signed
    readings: dict[str, float]
    seq: int
    sig: str


def signing_payload(device_id: str, ts: str, readings: dict[str, float], seq: int) -> bytes:
    return json.dumps(
        {"device_id": device_id, "ts": ts, "readings": readings, "seq": seq}, sort_keys=True, separators=(",", ":")
    ).encode()


def sign(secret: str, device_id: str, ts: str, readings: dict[str, float], seq: int) -> str:
    mac = hmac.new(secret.encode(), signing_payload(device_id, ts, readings, seq), hashlib.sha256).hexdigest()
    return f"hmac-sha256:{mac}"


def _as_utc(ts: datetime) -> datetime:
    return ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _owner_users(session: Session, sensor: Sensor) -> list[User]:
    if sensor.farm_id:
        farm = session.get(Farm, sensor.farm_id)
        farmer = session.get(Farmer, farm.farmer_id) if farm else None
        return [u for u in [session.get(User, farmer.user_id) if farmer else None] if u]
    if sensor.warehouse_id:
        wh = session.get(Warehouse, sensor.warehouse_id)
        return [u for u in [session.get(User, wh.operator_user_id) if wh else None] if u]
    return []


def _recent_alert(session: Session, user_id: int, kind: str, entity_id: str, hours: int = 6) -> bool:
    return (
        session.exec(
            select(Alert).where(
                Alert.user_id == user_id,
                Alert.kind == kind,
                Alert.entity_id == entity_id,
                Alert.created_at >= utcnow() - timedelta(hours=hours),
            )
        ).first()
        is not None
    )


def ingest(session: Session, sensor: Sensor, ts: datetime, readings: dict[str, float], seq: int) -> list[SensorReading]:
    """Store readings after validation; raise alerts. Shared by the HTTP endpoint and the demo simulator."""
    allowed = ALLOWED_METRICS.get(sensor.type, set())
    unknown = set(readings) - allowed
    if unknown:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"unknown_metric:{sorted(unknown)[0]}")
    stored: list[SensorReading] = []
    owners = _owner_users(session, sensor)
    for metric, value in readings.items():
        previous = list(
            session.exec(
                select(SensorReading)
                .where(SensorReading.sensor_id == sensor.id, SensorReading.metric == metric)
                .order_by(SensorReading.ts.desc())  # type: ignore[attr-defined]
                .limit(anomalies.FLATLINE_COUNT)
            )
        )
        problem = anomalies.check_reading(metric, value, previous)
        reading = SensorReading(
            sensor_id=sensor.id, ts=ts, metric=metric, value=value, seq=seq, quality_flag="SUSPECT" if problem else "OK"
        )
        session.add(reading)
        stored.append(reading)
        if problem:
            for user in owners + anomalies.admins(session):
                if not _recent_alert(session, user.id, "SENSOR_SUSPECT", sensor.device_id):
                    notify(
                        session,
                        user,
                        "SENSOR_SUSPECT",
                        bi("alert.sensor_suspect", device=sensor.device_id, detail=problem),
                        severity="WARNING",
                        entity_type="SENSOR",
                        entity_id=sensor.device_id,
                    )
    sensor.last_seq = seq
    if not sensor.last_seen_at or ts > sensor.last_seen_at:
        sensor.last_seen_at = ts
    session.add(sensor)
    session.flush()

    if sensor.type == "soil" and sensor.farm_id:
        farm = session.get(Farm, sensor.farm_id)
        moisture = readings.get("soil_moisture_pct")
        temp = readings.get("soil_temperature_c")
        good = {r.metric for r in stored if r.quality_flag == "OK"}
        for user in owners:
            if moisture is not None and "soil_moisture_pct" in good and moisture < irrigation.DRY_ALERT_PCT:
                if not _recent_alert(session, user.id, "DRY_SOIL", str(farm.id)):
                    notify(
                        session, user, "DRY_SOIL", bi("alert.dry_soil", farm=farm.name, moisture=round(moisture, 1)),
                        severity="WARNING", entity_type="FARM", entity_id=str(farm.id), sms=True,
                    )
            if temp is not None and "soil_temperature_c" in good and temp >= irrigation.HEAT_ALERT_C:
                if not _recent_alert(session, user.id, "HEAT", str(farm.id)):
                    notify(
                        session, user, "HEAT", bi("alert.heat", farm=farm.name, temp=round(temp, 1)),
                        severity="WARNING", entity_type="FARM", entity_id=str(farm.id),
                    )
    elif sensor.type == "ghala" and sensor.warehouse_id:
        evaluate_warehouse(session, session.get(Warehouse, sensor.warehouse_id))
    return stored


@router.post("/readings", status_code=201)
def post_readings(body: ReadingsIn, session: Session = Depends(get_session)):
    sensor = session.exec(select(Sensor).where(Sensor.device_id == body.device_id)).first()
    if not sensor:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown_device")
    expected = sign(sensor.secret, body.device_id, body.ts, body.readings, body.seq)
    if not hmac.compare_digest(expected, body.sig):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad_signature")
    try:
        parsed = datetime.fromisoformat(body.ts.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_timestamp")
    if body.seq <= sensor.last_seq:
        raise HTTPException(status.HTTP_409_CONFLICT, "replayed_or_stale_seq")
    ts = _as_utc(parsed)
    now = utcnow()
    if ts > now + MAX_CLOCK_SKEW or ts < now - MAX_BACKFILL:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "timestamp_out_of_range")
    stored = ingest(session, sensor, ts, body.readings, body.seq)
    session.commit()
    return {"stored": len(stored), "flags": {r.metric: r.quality_flag for r in stored}}
