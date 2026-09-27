"""The AI loan-eligibility model: trained, sensible, explained, and learning from real repayments."""

from sqlmodel import Session, select

from app.ai import credit_model
from app.db import engine
from app.models import Farmer, LoanApplication, Role, User

AVERAGE = dict(
    sales_count=2, sales_income=800_000, distinct_buyers=1, selling_months=2, savings=0, loans_repaid=0, loans_open=0,
    seasons=1, harvest_kg=1500, harvest_consistency=0.5, ghala_receipts=1, storage_alerts=0, advice_follow_rate=0.5,
    acres=2, drought_rainfed=0, offtake_coverage=0, soil_condition=0.7, account_age=200, activity_90d=10, coming_harvest=1,
)


def test_model_trains_reproducibly_and_predicts_well():
    a, b = credit_model.train(), credit_model.train()
    assert a.card == b.card  # same simulated history, same model
    assert a.card["auc"] >= 0.85 and a.card["trained_on"] == credit_model.SIMULATED_SAMPLES
    assert a.card["simulated"] is True and a.card["name"] == "logistic regression"


def test_behaviour_moves_the_prediction_the_right_way():
    model = credit_model.train()
    base = credit_model.predict(model, AVERAGE)["probability"]
    better = {**AVERAGE, "sales_count": 6, "distinct_buyers": 3, "selling_months": 5, "loans_repaid": 2, "advice_follow_rate": 0.9, "offtake_coverage": 0.6}
    worse = {**AVERAGE, "storage_alerts": 3, "drought_rainfed": 1, "coming_harvest": 0, "activity_90d": 0, "loans_open": 2}
    assert credit_model.predict(model, better)["probability"] > base > credit_model.predict(model, worse)["probability"]


def test_profile_uses_the_ai_verdict_and_explains_it(client, login):
    neema = client.get("/farmers/me/profile", headers=login("farmer")).json()
    e = neema["eligibility"]
    assert e["eligible"] and e["probability"] >= e["threshold"] == 0.5
    assert e["helped"] and all(h["label"]["en"] and h["label"]["sw"] and h["impact"] > 0 for h in e["helped"])
    assert all(h["impact"] < 0 and h["tip"]["sw"] for h in e["held_back"])
    assert e["model"]["auc"] >= 0.85 and e["model"]["simulated"]
    offer = next(x for x in neema["suggested_products"] if x["type"] == "input_loan")
    assert offer["max_amount_tzs"] > 0 and offer["probability"] == e["probability"]
    assert neema["risk_band"] in ("LOW", "MEDIUM")

    juma = {"Authorization": "Bearer " + client.post("/auth/login", json={"phone": "+255700000008", "pin": "1234"}).json()["access_token"]}
    p = client.get("/farmers/me/profile", headers=juma).json()
    assert p["eligibility"]["probability"] < e["probability"]
    if not p["eligibility"]["eligible"]:
        assert not any(x["type"] == "input_loan" for x in p["suggested_products"])
        assert p["eligibility"]["held_back"]  # told what held them back, with tips


def test_repaid_loans_become_real_training_examples(client, login):
    before = client.get("/farmers/me/profile", headers=login("farmer")).json()["eligibility"]["model"]
    with Session(engine) as s:
        neema = s.exec(select(Farmer).where(Farmer.public_id == "FMR-0042")).one()
        lender = s.exec(select(User).where(User.role == Role.LENDER)).first()
        s.add(LoanApplication(farmer_id=neema.id, lender_user_id=lender.id, amount=100_000, purpose="Seeds", status="CLOSED"))
        s.commit()
    after = client.get("/farmers/me/profile", headers=login("farmer")).json()["eligibility"]["model"]
    assert after["real_outcomes"] == before["real_outcomes"] + 1
    assert after["trained_on"] == before["trained_on"] + 1
