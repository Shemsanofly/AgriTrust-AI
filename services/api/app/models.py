"""Database entities (see README §20). Human-readable texts that the platform generates
(alerts, advice reasons, profile factors) are stored as bilingual objects
{"en": "...", "sw": "..."} so the UI can switch language without refetching."""

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, Enum):
    FARMER = "FARMER"
    BUYER = "BUYER"
    WAREHOUSE_OPERATOR = "WAREHOUSE_OPERATOR"
    LENDER = "LENDER"
    INSURER = "INSURER"
    ADMIN = "ADMIN"


class Language(str, Enum):
    SW = "sw"
    EN = "en"


# ---------------------------------------------------------------- identity


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    phone: str = Field(index=True, unique=True)
    email: Optional[str] = None
    full_name: str = ""
    role: Role
    pin_hash: str
    language: Language = Language.SW
    status: str = "ACTIVE"  # PENDING_OTP | ACTIVE | LOCKED
    otp_code_hash: Optional[str] = None
    otp_expires_at: Optional[datetime] = None
    failed_logins: int = 0
    locked_until: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)


class RefreshToken(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    token_hash: str = Field(index=True)
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    # Session / device recognition (a random id the app keeps on the device).
    device_id: Optional[str] = None
    user_agent: Optional[str] = None
    login_method: str = "pin"  # pin | otp | biometric
    session_started_at: datetime = Field(default_factory=utcnow)
    created_at: datetime = Field(default_factory=utcnow)


class WebAuthnCredential(SQLModel, table=True):
    """A passkey / device biometric. Only the public key is stored: the fingerprint or
    face never leaves the device and nothing biometric is ever put on chain."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    credential_id: str = Field(index=True, unique=True)  # base64url
    public_key: str  # base64url COSE key
    sign_count: int = 0
    label: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    last_used_at: Optional[datetime] = None


class Farmer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    public_id: str = Field(index=True, unique=True)  # pseudonymous, e.g. FMR-0042
    user_id: int = Field(foreign_key="user.id", unique=True)
    display_name: str
    region: str
    district: str = ""
    cooperative: Optional[str] = None
    kyc_level: int = 1


class Buyer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True)
    business_name: str
    country: str = "TZ"
    verified: bool = False


class Warehouse(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    public_id: str = Field(index=True, unique=True)  # e.g. WH-DOD-01
    name: str
    operator_user_id: int = Field(foreign_key="user.id")
    region: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    capacity_kg: float = 0
    verified: bool = True


# ---------------------------------------------------------------- shambani


class Farm(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    farmer_id: int = Field(foreign_key="farmer.id", index=True)
    name: str
    region: str
    lat: float
    lon: float
    acreage: float
    soil_type: str = "loam"
    irrigation_type: str = "drip"
    # Soil profile (optional): from a lab test, the TARI soil map or the farmer.
    soil_ph: Optional[float] = None
    soil_nitrogen: Optional[str] = None  # low | medium | high
    soil_phosphorus: Optional[str] = None
    soil_potassium: Optional[str] = None
    organic_matter_pct: Optional[float] = None
    soil_source: Optional[str] = None  # lab | soil_map | farmer
    created_at: datetime = Field(default_factory=utcnow)


class Crop(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    farm_id: int = Field(foreign_key="farm.id", index=True)
    crop_type: str = "maize"
    variety: Optional[str] = None
    planting_date: date
    expected_harvest_date: Optional[date] = None
    growth_stage: str = "vegetative"  # initial | vegetative | flowering | maturity | harvested


class Sensor(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str = Field(index=True, unique=True)
    type: str  # soil | ghala
    farm_id: Optional[int] = Field(default=None, foreign_key="farm.id")
    warehouse_id: Optional[int] = Field(default=None, foreign_key="warehouse.id")
    # Shared HMAC secret. Kept server-side only; in production it lives in a secrets manager.
    secret: str
    calibration: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    last_seen_at: Optional[datetime] = None
    last_seq: int = -1
    simulated: bool = False


class SensorReading(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sensor_id: int = Field(foreign_key="sensor.id", index=True)
    ts: datetime = Field(index=True)
    metric: str  # soil_moisture_pct | soil_temperature_c | temperature_c | humidity_pct
    value: float
    seq: int
    quality_flag: str = "OK"  # OK | SUSPECT


class IrrigationAdvice(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    farm_id: int = Field(foreign_key="farm.id", index=True)
    crop_id: int = Field(foreign_key="crop.id")
    created_at: datetime = Field(default_factory=utcnow)
    action: str  # IRRIGATE | SKIP_RAIN | NO_ACTION | CHECK_SENSOR
    amount_mm: float = 0
    when: dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON))
    headline: dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON))
    reasons: list[dict[str, str]] = Field(default_factory=list, sa_column=Column(JSON))
    inputs: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    followed: Optional[bool] = None
    model_version: str = "irrigation-rules-v0.1"


class Harvest(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    crop_id: int = Field(foreign_key="crop.id", index=True)
    harvest_date: date
    quantity_kg: float
    notes: str = ""


# ---------------------------------------------------------------- ghalani


class CropBatch(SQLModel, table=True):
    id: str = Field(primary_key=True)  # BATCH-7F3A
    harvest_id: int = Field(foreign_key="harvest.id")
    farmer_id: int = Field(foreign_key="farmer.id", index=True)
    crop_type: str
    harvest_date: date
    quantity_kg: float
    available_kg: float
    grade: Optional[str] = None
    status: str = "HARVESTED"  # HARVESTED | IN_STORAGE | SOLD_OUT
    warehouse_id: Optional[int] = Field(default=None, foreign_key="warehouse.id")
    listed: bool = False
    price_per_kg: Optional[float] = None
    currency: str = "TZS"
    salt: str
    created_at: datetime = Field(default_factory=utcnow)


class StorageRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: str = Field(foreign_key="cropbatch.id", index=True)
    warehouse_id: int = Field(foreign_key="warehouse.id")
    window_start: datetime
    window_end: datetime
    reading_count: int = 0
    temp_avg: float
    temp_max: float
    rh_avg: float
    rh_max: float
    risk_level: str
    merkle_root: str
    salt: str


class WarehouseReceipt(SQLModel, table=True):
    id: str = Field(primary_key=True)  # WR-2026-000123
    batch_id: str = Field(foreign_key="cropbatch.id", unique=True)
    warehouse_id: int = Field(foreign_key="warehouse.id")
    owner_farmer_id: int = Field(foreign_key="farmer.id")
    quantity_kg: float
    released_kg: float = 0
    grade: str
    date_in: date
    bay: str = ""
    initial_temp_c: Optional[float] = None
    initial_rh_pct: Optional[float] = None
    status: str = "ACTIVE"  # ACTIVE | PARTIALLY_RELEASED | RELEASED | PLEDGED
    pledged_to: Optional[int] = None
    salt: str
    created_at: datetime = Field(default_factory=utcnow)


# ---------------------------------------------------------------- sokoni


class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    buyer_id: int = Field(foreign_key="buyer.id", index=True)
    batch_id: str = Field(foreign_key="cropbatch.id", index=True)
    quantity_kg: float
    price_per_kg: float
    currency: str = "TZS"
    # REQUESTED | ACCEPTED | DECLINED | CANCELLED | PAID | RELEASED | DELIVERED | SALE_CONFIRMED
    status: str = "REQUESTED"
    payment_ref: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class OrderMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id", index=True)
    sender_user_id: int = Field(foreign_key="user.id")
    body: str
    created_at: datetime = Field(default_factory=utcnow)


class Sale(SQLModel, table=True):
    id: str = Field(primary_key=True)  # SALE-xxxx
    order_id: int = Field(foreign_key="order.id", unique=True)
    farmer_id: int = Field(foreign_key="farmer.id", index=True)
    buyer_id: int = Field(foreign_key="buyer.id")
    batch_id: str = Field(foreign_key="cropbatch.id")
    quantity_kg: float
    amount: float
    currency: str = "TZS"
    confirmed_by_farmer_at: Optional[datetime] = None
    confirmed_by_buyer_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    payment_ref: Optional[str] = None
    salt: str


# ---------------------------------------------------------------- trust layer


class BlockchainProof(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    entity_type: str = Field(index=True)  # BATCH | RECEIPT | STORAGE | SALE | RECEIPT_STATUS
    entity_id: str = Field(index=True)
    record_key: str = Field(index=True)  # bytes32 hex used on chain
    data_hash: str
    chain_id: int
    tx_hash: str
    block_number: int
    issuer: str
    mode: str  # SIMULATED | ONCHAIN
    anchored_at: datetime = Field(default_factory=utcnow)


class LedgerEntry(SQLModel, table=True):
    """Local append-only ledger used when no EVM chain is configured (SIMULATED)."""

    id: Optional[int] = Field(default=None, primary_key=True)
    record_key: str = Field(index=True, unique=True)
    record_type: int
    data_hash: str
    issuer: str
    timestamp: int
    block_number: int
    tx_hash: str
    prev_tx_hash: str


# ---------------------------------------------------------------- kifedha


class FarmerRiskProfile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    farmer_id: int = Field(foreign_key="farmer.id", index=True)
    model_version: str
    risk_band: str
    score: float
    positive_factors: list[dict[str, str]] = Field(default_factory=list, sa_column=Column(JSON))
    risk_factors: list[dict[str, str]] = Field(default_factory=list, sa_column=Column(JSON))
    cash_flow: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    suggested_products: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    inputs: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    generated_at: datetime = Field(default_factory=utcnow)


class ConsentRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    farmer_id: int = Field(foreign_key="farmer.id", index=True)
    grantee_user_id: int = Field(foreign_key="user.id", index=True)
    data_categories: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    purpose: str
    granted_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    revoked_at: Optional[datetime] = None


class LoanApplication(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    farmer_id: int = Field(foreign_key="farmer.id", index=True)
    lender_user_id: int = Field(foreign_key="user.id", index=True)
    amount: float
    purpose: str
    repayment_month: Optional[str] = None
    # SUBMITTED | UNDER_REVIEW | APPROVED | DECLINED | DISBURSED | REPAYING | CLOSED
    status: str = "SUBMITTED"
    consent_id: Optional[int] = Field(default=None, foreign_key="consentrecord.id")
    decision_by: Optional[int] = None
    decision_reason: Optional[str] = None
    decided_at: Optional[datetime] = None
    terms: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class InsurancePolicy(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    farmer_id: int = Field(foreign_key="farmer.id", index=True)
    insurer_user_id: int = Field(foreign_key="user.id", index=True)
    product: str  # weather_index | storage_cover
    coverage_tzs: float
    premium_tzs: float
    status: str = "REQUESTED"  # REQUESTED | ACTIVE | DECLINED | EXPIRED
    rainfall_threshold_mm: Optional[float] = None
    window_start: Optional[date] = None
    window_end: Optional[date] = None
    farm_id: Optional[int] = Field(default=None, foreign_key="farm.id")
    created_at: datetime = Field(default_factory=utcnow)


class InsuranceClaim(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    policy_id: int = Field(foreign_key="insurancepolicy.id", index=True)
    trigger_type: str  # PARAMETRIC_RAINFALL | STORAGE_LOSS | MANUAL
    # FILED | EVIDENCE_ATTACHED | UNDER_REVIEW | APPROVED | REJECTED | PAID
    status: str = "FILED"
    evidence: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    decided_by: Optional[int] = None
    decision_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class SavingsGoal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    farmer_id: int = Field(foreign_key="farmer.id", index=True)
    bucket: str  # inputs | emergency | household | goal
    name: str
    target_amount: float
    saved_amount: float = 0
    due_date: Optional[date] = None


# ---------------------------------------------------------------- operations


class Alert(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    kind: str  # DRY_SOIL | HEAT | SENSOR_OFFLINE | SPOILAGE_RISK | FRAUD | SECURITY | ORDER | LOAN | ...
    severity: str = "INFO"  # INFO | WARNING | CRITICAL
    message: dict[str, str] = Field(default_factory=dict, sa_column=Column(JSON))
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    read: bool = False
    resolved_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)


class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    actor_user_id: Optional[int] = Field(default=None, index=True)
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    subject_farmer_id: Optional[int] = Field(default=None, index=True)
    reason: Optional[str] = None
    ts: datetime = Field(default_factory=utcnow)


class SmsLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    phone: str
    language: str
    body: str
    status: str  # SENT | LOGGED | FAILED
    created_at: datetime = Field(default_factory=utcnow)
