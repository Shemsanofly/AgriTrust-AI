from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..ai import irrigation, planting
from ..db import get_session
from ..integrations.open_meteo import get_forecast
from ..models import Crop, Farm, Farmer, IrrigationAdvice, Role, Sensor, SensorReading, User, utcnow
from ..security.audit import audit
from ..security.auth import farmer_for, get_current_user, require_roles

router = APIRouter(tags=["shambani"])
EAT = timezone(timedelta(hours=3))  # Africa/Dar_es_Salaam


class CropIn(BaseModel):
    crop_type: str = "maize"
    variety: Optional[str] = None
    planting_date: date
    expected_harvest_date: Optional[date] = None
    growth_stage: str = "vegetative"


class FarmIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    region: str
    lat: float = Field(ge=-12.5, le=1.5)  # Tanzania bounding box (roughly)
    lon: float = Field(ge=29.0, le=41.0)
    acreage: float = Field(gt=0, le=10_000)
    soil_type: str = "loam"
    irrigation_type: str = "drip"
    soil_ph: Optional[float] = Field(default=None, ge=3, le=10)
    soil_nitrogen: Optional[str] = Field(default=None, pattern=r"^(low|medium|high)$")
    soil_phosphorus: Optional[str] = Field(default=None, pattern=r"^(low|medium|high)$")
    soil_potassium: Optional[str] = Field(default=None, pattern=r"^(low|medium|high)$")
    organic_matter_pct: Optional[float] = Field(default=None, ge=0, le=20)
    soil_source: Optional[str] = Field(default=None, pattern=r"^(lab|soil_map|farmer)$")
    crop: Optional[CropIn] = None


class CropUpdate(BaseModel):
    growth_stage: Optional[str] = None
    expected_harvest_date: Optional[date] = None


class FeedbackIn(BaseModel):
    followed: bool


def load_farm(session: Session, farm_id: int, user: User) -> Farm:
    farm = session.get(Farm, farm_id)
    if not farm:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    if user.role == Role.ADMIN:
        audit(session, user.id, "READ", "FARM", farm_id, reason="admin_access")
        return farm
    if user.role != Role.FARMER or farmer_for(session, user).id != farm.farmer_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
    return farm


def _latest(session: Session, sensor_ids: list[int], metric: str) -> Optional[SensorReading]:
    if not sensor_ids:
        return None
    return session.exec(
        select(SensorReading)
        .where(SensorReading.sensor_id.in_(sensor_ids), SensorReading.metric == metric)  # type: ignore[union-attr]
        .order_by(SensorReading.ts.desc())  # type: ignore[attr-defined]
    ).first()


def farm_json(session: Session, farm: Farm) -> dict:
    crops = list(session.exec(select(Crop).where(Crop.farm_id == farm.id)))
    sensors = list(session.exec(select(Sensor).where(Sensor.farm_id == farm.id)))
    ids = [s.id for s in sensors]
    latest = {}
    for metric in ("soil_moisture_pct", "soil_temperature_c"):
        r = _latest(session, ids, metric)
        if r:
            latest[metric] = {"value": r.value, "ts": r.ts.isoformat(), "quality_flag": r.quality_flag}
    return {
        **farm.model_dump(),
        "crops": [c.model_dump() for c in crops],
        "sensors": [
            {
                "device_id": s.device_id,
                "type": s.type,
                "simulated": s.simulated,
                "last_seen_at": s.last_seen_at.isoformat() if s.last_seen_at else None,
            }
            for s in sensors
        ],
        "latest": latest,
    }


@router.post("/farms", status_code=201)
def create_farm(body: FarmIn, user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    farmer = farmer_for(session, user)
    farm = Farm(farmer_id=farmer.id, **body.model_dump(exclude={"crop"}))
    session.add(farm)
    session.flush()
    if body.crop:
        session.add(Crop(farm_id=farm.id, **body.crop.model_dump()))
    session.commit()
    return farm_json(session, farm)


@router.get("/farms")
def list_farms(user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)):
    farmer = farmer_for(session, user)
    return [farm_json(session, f) for f in session.exec(select(Farm).where(Farm.farmer_id == farmer.id))]


@router.get("/farms/{farm_id}")
def get_farm(farm_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    farm = load_farm(session, farm_id, user)
    data = farm_json(session, farm)
    session.commit()
    return data


@router.post("/farms/{farm_id}/crops", status_code=201)
def add_crop(farm_id: int, body: CropIn, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    farm = load_farm(session, farm_id, user)
    crop = Crop(farm_id=farm.id, **body.model_dump())
    session.add(crop)
    session.commit()
    session.refresh(crop)
    return crop


@router.patch("/crops/{crop_id}")
def update_crop(crop_id: int, body: CropUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    crop = session.get(Crop, crop_id)
    if not crop:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    load_farm(session, crop.farm_id, user)
    if body.growth_stage:
        if body.growth_stage not in ("initial", "vegetative", "flowering", "maturity", "harvested"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid_stage")
        crop.growth_stage = body.growth_stage
    if body.expected_harvest_date:
        crop.expected_harvest_date = body.expected_harvest_date
    session.add(crop)
    session.commit()
    session.refresh(crop)
    return crop


@router.get("/farms/{farm_id}/readings")
def farm_readings(farm_id: int, hours: int = 48, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    farm = load_farm(session, farm_id, user)
    ids = [s.id for s in session.exec(select(Sensor).where(Sensor.farm_id == farm.id))]
    if not ids:
        return []
    since = utcnow() - timedelta(hours=min(hours, 24 * 30))
    rows = session.exec(
        select(SensorReading)
        .where(SensorReading.sensor_id.in_(ids), SensorReading.ts >= since)  # type: ignore[union-attr]
        .order_by(SensorReading.ts)  # type: ignore[arg-type]
    )
    return [{"ts": r.ts.isoformat(), "metric": r.metric, "value": r.value, "quality_flag": r.quality_flag} for r in rows]


@router.get("/farms/{farm_id}/weather")
def farm_weather(farm_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    farm = load_farm(session, farm_id, user)
    fc = get_forecast(farm.lat, farm.lon)
    return {
        "source": fc.source,
        "simulated": fc.simulated,
        "days": [{"date": d.day.isoformat(), "rain_mm": d.rain_mm, "et0_mm": d.et0_mm, "tmax_c": d.tmax_c} for d in fc.days],
    }


def advice_json(a: IrrigationAdvice) -> dict:
    data = a.model_dump()
    data["created_at"] = a.created_at.isoformat()
    return data


def compute_advice(session: Session, farm: Farm, now: Optional[datetime] = None) -> Optional[IrrigationAdvice]:
    crop = session.exec(
        select(Crop).where(Crop.farm_id == farm.id, Crop.growth_stage != "harvested").order_by(Crop.planting_date.desc())  # type: ignore[attr-defined]
    ).first()
    if not crop:
        return None
    now = now or utcnow()
    ids = [s.id for s in session.exec(select(Sensor).where(Sensor.farm_id == farm.id))]
    reading = _latest(session, ids, "soil_moisture_pct")
    if reading and reading.quality_flag != "OK":
        # Do not act on suspicious data; fall back to the most recent good reading.
        reading = session.exec(
            select(SensorReading)
            .where(
                SensorReading.sensor_id.in_(ids),  # type: ignore[union-attr]
                SensorReading.metric == "soil_moisture_pct",
                SensorReading.quality_flag == "OK",
            )
            .order_by(SensorReading.ts.desc())  # type: ignore[attr-defined]
        ).first()
    age = (now - reading.ts).total_seconds() / 3600 if reading else None
    forecast = get_forecast(farm.lat, farm.lon)
    local_now = now.astimezone(EAT)
    result = irrigation.recommend(crop.crop_type, crop.growth_stage, reading.value if reading else None, age, forecast, local_now)

    last = session.exec(
        select(IrrigationAdvice).where(IrrigationAdvice.farm_id == farm.id).order_by(IrrigationAdvice.created_at.desc())  # type: ignore[attr-defined]
    ).first()
    # Keep one record per decision: a new record when the action changes or after 12 hours.
    if last and last.action == result.action and (now - last.created_at) < timedelta(hours=12):
        last.amount_mm = result.amount_mm
        last.when = result.when
        last.headline = result.headline
        last.reasons = result.reasons
        last.inputs = result.inputs
        session.add(last)
        return last
    advice = IrrigationAdvice(
        farm_id=farm.id,
        crop_id=crop.id,
        created_at=now,
        action=result.action,
        amount_mm=result.amount_mm,
        when=result.when,
        headline=result.headline,
        reasons=result.reasons,
        inputs=result.inputs,
        model_version=result.model_version,
    )
    session.add(advice)
    session.flush()
    return advice


@router.get("/farms/{farm_id}/irrigation-advice")
def irrigation_advice(farm_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    farm = load_farm(session, farm_id, user)
    advice = compute_advice(session, farm)
    session.commit()
    if not advice:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no_active_crop")
    session.refresh(advice)
    return advice_json(advice)


@router.get("/farms/{farm_id}/planting-advice")
def planting_advice(farm_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    """Recommend crops to plant based on the farm's registered soil type."""
    farm = load_farm(session, farm_id, user)
    current = session.exec(
        select(Crop).where(Crop.farm_id == farm.id, Crop.growth_stage != "harvested").order_by(Crop.planting_date.desc())  # type: ignore[attr-defined]
    ).first()
    result = planting.recommend(farm.soil_type, current.crop_type if current else None, farm.irrigation_type)
    return {
        "headline": result.headline,
        "soil_summary": result.soil_summary,
        "tips": result.tips,
        "recommendations": result.recommendations,
        "current_crop": result.current_crop,
        "soil_profile": {
            **planting.soil_profile_notes(
                farm.soil_ph,
                {"N": farm.soil_nitrogen, "P": farm.soil_phosphorus, "K": farm.soil_potassium},
            ),
            "organic_matter_pct": farm.organic_matter_pct,
            "source": farm.soil_source,
        },
        "inputs": result.inputs,
        "model_version": result.model_version,
    }


@router.get("/farms/{farm_id}/advice-history")
def advice_history(farm_id: int, user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    farm = load_farm(session, farm_id, user)
    rows = session.exec(
        select(IrrigationAdvice).where(IrrigationAdvice.farm_id == farm.id).order_by(IrrigationAdvice.created_at.desc())  # type: ignore[attr-defined]
    )
    return [advice_json(a) for a in rows]


@router.post("/advice/{advice_id}/feedback")
def advice_feedback(
    advice_id: int, body: FeedbackIn, user: User = Depends(require_roles(Role.FARMER)), session: Session = Depends(get_session)
):
    advice = session.get(IrrigationAdvice, advice_id)
    if not advice:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not_found")
    load_farm(session, advice.farm_id, user)
    advice.followed = body.followed
    session.add(advice)
    session.commit()
    session.refresh(advice)
    return advice_json(advice)


def farmer_of_farm(session: Session, farm: Farm) -> Farmer:
    return session.get(Farmer, farm.farmer_id)  # type: ignore[return-value]
