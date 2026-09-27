"""Seed the demo scenario (README §24). All people and companies are fictional.

    python -m app.seed          # reset the database and load demo data

Every demo account uses PIN 1234."""

import math
from datetime import date, datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, select

from .chain.hashing import new_salt
from .chain.records import anchor_entity
from .db import engine
from .models import (
    Buyer,
    Crop,
    CropBatch,
    Farm,
    Farmer,
    Harvest,
    IrrigationAdvice,
    Language,
    OffTakeContract,
    Order,
    Role,
    Sale,
    Sensor,
    SensorReading,
    User,
    Warehouse,
    WarehouseReceipt,
    utcnow,
)
from .security.auth import hash_secret
from .storage import close_storage_window

DEMO_PIN = "1234"

ACCOUNTS = [
    # phone, name, role, language
    ("+255700000001", "Mama Neema", Role.FARMER, Language.SW),
    ("+255700000002", "Tanzanite Foods Ltd", Role.BUYER, Language.EN),
    ("+255700000003", "Ghala la Chamwino", Role.WAREHOUSE_OPERATOR, Language.SW),
    ("+255700000004", "Kilimo Microfinance (SIMULATED)", Role.LENDER, Language.EN),
    ("+255700000005", "Shamba Insurance (SIMULATED)", Role.INSURER, Language.EN),
    ("+255700000006", "Dodoma Grain Traders", Role.BUYER, Language.SW),
    ("+255700000007", "Ghala la Ushirika Mbeya", Role.WAREHOUSE_OPERATOR, Language.SW),
    ("+255700000008", "Juma Mwakalinga", Role.FARMER, Language.SW),
    ("+255700000010", "Upendo Kisanga", Role.FARMER, Language.SW),
    ("+255700000009", "Platform Admin", Role.ADMIN, Language.EN),
]


def _readings(session: Session, sensor: Sensor, hours: int, every_min: int, fn) -> None:
    now = utcnow().replace(microsecond=0, second=0)
    n = hours * 60 // every_min
    for i in range(n):
        ts = now - timedelta(minutes=every_min * (n - i))
        for metric, value in fn(i, n).items():
            session.add(SensorReading(sensor_id=sensor.id, ts=ts, metric=metric, value=round(value, 1), seq=i))
    sensor.last_seq = n
    sensor.last_seen_at = now - timedelta(minutes=every_min)
    session.add(sensor)


def _at(d: date) -> datetime:
    """Historical records get their real dates, not the time the seed ran."""
    return datetime(d.year, d.month, d.day, 9, 0, tzinfo=timezone.utc)


def seed() -> None:
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    pin_hash = hash_secret(DEMO_PIN)
    with Session(engine) as s:
        users = {}
        for phone, name, role, lang in ACCOUNTS:
            u = User(phone=phone, full_name=name, role=role, pin_hash=pin_hash, language=lang)
            s.add(u)
            users[phone] = u
        s.flush()

        neema = Farmer(
            public_id="FMR-0042",
            user_id=users["+255700000001"].id,
            display_name="Mama Neema",
            region="Dodoma",
            district="Chamwino",
            cooperative="Chamwino AMCOS",
        )
        buyer1 = Buyer(user_id=users["+255700000002"].id, business_name="Tanzanite Foods Ltd", country="TZ", verified=True)
        buyer2 = Buyer(user_id=users["+255700000006"].id, business_name="Dodoma Grain Traders", country="TZ", verified=True)
        s.add_all([neema, buyer1, buyer2])
        wh = Warehouse(
            public_id="WH-DOD-01",
            name="Ghala la Chamwino",
            operator_user_id=users["+255700000003"].id,
            region="Dodoma",
            lat=-6.20,
            lon=35.80,
            capacity_kg=200_000,
            verified=True,
        )
        s.add(wh)
        s.flush()

        today = date.today()
        farm = Farm(
            farmer_id=neema.id, name="Shamba", region="Dodoma", lat=-6.17, lon=35.75, acreage=5,
            soil_type="sandy loam", irrigation_type="drip",
            soil_ph=6.2, soil_nitrogen="medium", soil_phosphorus="low", soil_potassium="medium",
            organic_matter_pct=1.6, soil_source="lab",
        )
        s.add(farm)
        s.flush()
        growing = Crop(
            farm_id=farm.id, crop_type="maize", variety="SC 403", acreage=3, planting_date=today - timedelta(days=40),
            expected_harvest_date=today + timedelta(days=160), growth_stage="vegetative",
        )
        ready = Crop(
            farm_id=farm.id, crop_type="maize", variety="Staha", acreage=2, planting_date=today - timedelta(days=115),
            expected_harvest_date=today, growth_stage="maturity",
        )
        s.add_all([growing, ready])
        s.flush()

        soil = Sensor(device_id="ESP32-SOIL-01", type="soil", farm_id=farm.id, secret="dev-soil-secret", simulated=True)
        ghala = Sensor(device_id="ESP32-GHALA-01", type="ghala", warehouse_id=wh.id, secret="dev-ghala-secret", simulated=True)
        s.add_all([soil, ghala])
        s.flush()
        _readings(s, soil, 48, 30, lambda i, n: {"soil_moisture_pct": 33 - 2 * i / n + 0.5 * math.sin(i / 3), "soil_temperature_c": 24 + 3 * math.sin(i / 8)})
        _readings(s, ghala, 72, 60, lambda i, n: {"temperature_c": 24.5 + 1.2 * math.sin(i / 4), "humidity_pct": 59 + 2 * math.sin(i / 5)})

        # Off-take: one buyer has contracted part of the coming maize harvest; another offer waits.
        delivery = growing.expected_harvest_date.strftime("%Y-%m")
        s.add_all(
            [
                OffTakeContract(
                    buyer_id=buyer1.id, farmer_id=neema.id, crop_type="maize", quantity_kg=1500, price_per_kg=800,
                    delivery_month=delivery, status="ACCEPTED", note="Grade A, delivered to Ghala la Chamwino",
                    decided_at=utcnow() - timedelta(days=10),
                ),
                OffTakeContract(
                    buyer_id=buyer2.id, farmer_id=neema.id, crop_type="maize", quantity_kg=800, price_per_kg=780,
                    delivery_month=delivery, note="Price fixed now; we collect from the farm",
                ),
            ]
        )

        # Season history: 20 irrigation recommendations, 18 followed.
        for i in range(20):
            s.add(
                IrrigationAdvice(
                    farm_id=farm.id, crop_id=growing.id, created_at=utcnow() - timedelta(days=40 - 2 * i),
                    action="IRRIGATE" if i % 3 else "SKIP_RAIN", amount_mm=15 if i % 3 else 0,
                    when={"en": "tomorrow morning", "sw": "kesho asubuhi"},
                    headline={"en": "Seeded history", "sw": "Historia ya mfano"},
                    followed=i not in (4, 13),
                )
            )

        # Earlier harvest this year: stored, receipted and sold to two buyers.
        early_crop = Crop(
            farm_id=farm.id, crop_type="maize", variety="Staha", planting_date=today - timedelta(days=300),
            expected_harvest_date=today - timedelta(days=180), growth_stage="harvested",
        )
        s.add(early_crop)
        s.flush()
        h = Harvest(crop_id=early_crop.id, harvest_date=today - timedelta(days=180), quantity_kg=1800)
        s.add(h)
        s.flush()
        old = CropBatch(
            id="BATCH-1A2B", harvest_id=h.id, farmer_id=neema.id, crop_type="maize", harvest_date=h.harvest_date,
            quantity_kg=1800, available_kg=300, grade="A", status="IN_STORAGE", warehouse_id=wh.id,
            listed=True, price_per_kg=780, salt=new_salt(), created_at=_at(h.harvest_date),
        )
        s.add(old)
        anchor_entity(s, "BATCH", old)
        receipt = WarehouseReceipt(
            id=f"WR-{today.year}-000001", batch_id=old.id, warehouse_id=wh.id, owner_farmer_id=neema.id,
            quantity_kg=1800, released_kg=1500, grade="A", date_in=today - timedelta(days=178), bay="B-2",
            status="PARTIALLY_RELEASED", salt=new_salt(), created_at=_at(today - timedelta(days=178)),
        )
        s.add(receipt)
        anchor_entity(s, "RECEIPT", receipt)
        close_storage_window(s, old)

        for qty, price, buyer, days_ago in ((600, 720, buyer1, 150), (500, 740, buyer2, 120), (400, 760, buyer1, 60)):
            done = (utcnow() - timedelta(days=days_ago)).replace(microsecond=0)
            order = Order(buyer_id=buyer.id, batch_id=old.id, quantity_kg=qty, price_per_kg=price, status="SALE_CONFIRMED", created_at=done, updated_at=done)
            s.add(order)
            s.flush()
            sale = Sale(
                id=f"SALE-{order.id:04d}", order_id=order.id, farmer_id=neema.id, buyer_id=buyer.id, batch_id=old.id,
                quantity_kg=qty, amount=qty * price, confirmed_by_farmer_at=done, confirmed_by_buyer_at=done,
                completed_at=done, payment_ref=f"SIM-MM-SEED{order.id}", salt=new_salt(),
            )
            s.add(sale)
            anchor_entity(s, "SALE", sale)

        # Savings Neema already keeps (VICOBA / mobile wallet), recorded by hand.
        from .models import SavingsGoal

        s.add_all(
            [
                SavingsGoal(farmer_id=neema.id, bucket="inputs", name="Mbegu na mbolea 2027", target_amount=450_000, saved_amount=180_000, due_date=today + timedelta(days=150)),
                SavingsGoal(farmer_id=neema.id, bucket="emergency", name="Akiba ya dharura", target_amount=300_000, saved_amount=95_000),
                SavingsGoal(farmer_id=neema.id, bucket="goal", name="Tanki la maji", target_amount=800_000, saved_amount=120_000, due_date=today + timedelta(days=300)),
            ]
        )

        # A second ghala and two more farmers, so buyers see real choice.
        mbeya = Warehouse(
            public_id="WH-MBY-01", name="Ghala la Ushirika Mbeya", operator_user_id=users["+255700000007"].id,
            region="Mbeya", lat=-8.90, lon=33.46, capacity_kg=150_000, verified=True,
        )
        s.add(mbeya)
        s.flush()
        ghala2 = Sensor(device_id="ESP32-GHALA-02", type="ghala", warehouse_id=mbeya.id, secret="dev-ghala-secret-2", simulated=True)
        s.add(ghala2)
        s.flush()
        _readings(s, ghala2, 72, 60, lambda i, n: {"temperature_c": 21.5 + 1.5 * math.sin(i / 4), "humidity_pct": 57 + 2.5 * math.sin(i / 6)})

        def listed_batch(phone, public_id, name, region, district, coop, wh, crop_type, kg, grade, price, days_ago, bay, farm_name, lat, lon, soil):
            farmer = Farmer(public_id=public_id, user_id=users[phone].id, display_name=name, region=region, district=district, cooperative=coop)
            s.add(farmer)
            s.flush()
            farm = Farm(farmer_id=farmer.id, name=farm_name, region=region, lat=lat, lon=lon, acreage=4, soil_type=soil, irrigation_type="rainfed")
            s.add(farm)
            s.flush()
            crop = Crop(farm_id=farm.id, crop_type=crop_type, planting_date=today - timedelta(days=days_ago + 120), expected_harvest_date=today - timedelta(days=days_ago), growth_stage="harvested")
            s.add(crop)
            s.flush()
            harvest = Harvest(crop_id=crop.id, harvest_date=today - timedelta(days=days_ago), quantity_kg=kg + 60)
            s.add(harvest)
            s.flush()
            batch = CropBatch(
                id=f"BATCH-{public_id[-4:]}", harvest_id=harvest.id, farmer_id=farmer.id, crop_type=crop_type, harvest_date=harvest.harvest_date,
                quantity_kg=harvest.quantity_kg, available_kg=kg, grade=grade, status="IN_STORAGE", warehouse_id=wh.id,
                listed=True, price_per_kg=price, salt=new_salt(), created_at=_at(harvest.harvest_date),
            )
            s.add(batch)
            anchor_entity(s, "BATCH", batch)
            n = len(s.exec(select(WarehouseReceipt)).all()) + 1
            receipt = WarehouseReceipt(
                id=f"WR-{today.year}-{n:06d}", batch_id=batch.id, warehouse_id=wh.id, owner_farmer_id=farmer.id,
                quantity_kg=kg, grade=grade, date_in=today - timedelta(days=days_ago - 3), bay=bay, salt=new_salt(),
                created_at=_at(today - timedelta(days=days_ago - 3)),
            )
            s.add(receipt)
            anchor_entity(s, "RECEIPT", receipt)
            close_storage_window(s, batch)

        listed_batch("+255700000008", "FMR-0107", "Juma Mwakalinga", "Mbeya", "Mbarali", "Mbarali Rice Growers AMCOS", mbeya,
                     "rice", 3200, "A", 1850, 40, "C-1", "Shamba la Mpunga", -8.68, 34.12, "clay")
        listed_batch("+255700000010", "FMR-0215", "Upendo Kisanga", "Dodoma", "Chamwino", "Chamwino AMCOS", wh,
                     "beans", 900, "B", 2300, 55, "A-4", "Shamba la Upendo", -6.25, 35.84, "loam")
        s.commit()
    print("Seeded demo data. Accounts (PIN 1234):")
    for phone, name, role, lang in ACCOUNTS:
        print(f"  {role.value:<20} {phone}  {name}  [{lang.value}]")


if __name__ == "__main__":
    seed()
