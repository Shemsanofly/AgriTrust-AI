"""AI loan-eligibility model: predicts how likely a farmer is to repay an input loan from
what they actually do on the platform (sales, savings, harvests, storage, advice followed,
contracts, farm and soil data, activity).

Model: logistic regression (scikit-learn), the usual choice for credit scoring because every
prediction can be explained exactly: each feature's contribution to the log-odds is shown to
the farmer and the lender.

Training data: the platform has no repayment history yet, so the model is trained on a
SIMULATED history of farmers generated from agronomic and credit assumptions (see
`_simulated_history`). Loans that are repaid on the platform (status CLOSED) are added as real
outcomes each time the model is trained, so it learns from reality as it arrives. The model
card (samples, real outcomes, AUC) is returned with every prediction and shown in the UI."""

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

MODEL_VERSION = "credit-lr-v1"
THRESHOLD = 0.5  # probability of repaying needed to be eligible
SIMULATED_SAMPLES = 5000

# Feature order is the model's input order. Each has a bilingual label ("ai.f.<name>") and a
# tip ("ai.tip.<name>") for when it holds a farmer back.
FEATURES = [
    "sales_count",
    "sales_income",
    "distinct_buyers",
    "selling_months",
    "savings",
    "loans_repaid",
    "loans_open",
    "seasons",
    "harvest_kg",
    "harvest_consistency",
    "ghala_receipts",
    "storage_alerts",
    "advice_follow_rate",
    "acres",
    "drought_rainfed",
    "offtake_coverage",
    "soil_condition",
    "account_age",
    "activity_90d",
    "coming_harvest",
]


def to_vector(raw: dict[str, float]) -> list[float]:
    """Raw facts -> model inputs (log scales for money, kg, days and counts that grow large)."""
    return [
        min(raw["sales_count"], 12),
        math.log1p(raw["sales_income"] / 1000),
        min(raw["distinct_buyers"], 6),
        min(raw["selling_months"], 12),
        math.log1p(raw["savings"] / 1000),
        min(raw["loans_repaid"], 5),
        min(raw["loans_open"], 3),
        min(raw["seasons"], 8),
        math.log1p(raw["harvest_kg"]),
        raw["harvest_consistency"],
        min(raw["ghala_receipts"], 8),
        min(raw["storage_alerts"], 4),
        raw["advice_follow_rate"],
        math.log1p(raw["acres"]),
        raw["drought_rainfed"],
        raw["offtake_coverage"],
        raw["soil_condition"],
        math.log1p(raw["account_age"]),
        math.log1p(raw["activity_90d"]),
        raw["coming_harvest"],
    ]


def _simulated_history(n: int, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """Simulated farmers and whether they repaid. A hidden 'diligence' trait drives both what
    a farmer does (sales, records, advice followed...) and repayment, plus noise, so the model
    has to learn repayment from observable behaviour, as it would from real data."""
    rng = np.random.default_rng(seed)
    X, y = [], []
    for _ in range(n):
        d = rng.beta(2, 2)  # hidden diligence, never given to the model
        acres = float(np.clip(rng.lognormal(math.log(2.5), 0.7), 0.25, 50))
        seasons = int(np.clip(rng.poisson(0.5 + 3 * d), 0, 8))
        harvest_kg = acres * 600 * seasons * rng.lognormal(0, 0.3) if seasons else 0.0
        consistency = float(rng.beta(1 + 4 * d, 2)) if seasons >= 2 else 0.5
        sales = int(rng.poisson(seasons * (0.4 + 2.2 * d)))
        income = sum(rng.lognormal(math.log(400_000), 0.6) for _ in range(sales))
        buyers = min(sales, int(rng.poisson(0.5 + 2 * d)) + (1 if sales else 0))
        months = min(sales, 12)
        savings = 0.0 if rng.random() < 0.6 - 0.4 * d else float(rng.lognormal(math.log(150_000), 0.9))
        repaid = int(rng.poisson(1.5 * d * seasons / 3))
        open_loans = int(rng.random() < 0.25)
        receipts = int(rng.poisson(seasons * d))
        alerts = int(rng.poisson(0.8 * (1 - d)))
        follow = float(rng.beta(1 + 5 * d, 1 + 3 * (1 - d)))
        drought_rainfed = int(rng.random() < 0.3)
        offtake = 0.0 if rng.random() < 0.7 - 0.2 * d else float(rng.beta(2, 3))
        soil = float(rng.beta(3, 1.5))
        age = float(rng.uniform(15, 1500))
        activity = int(rng.poisson(3 + 40 * d))
        coming = int(rng.random() < 0.55 + 0.35 * d)
        raw = dict(
            sales_count=sales, sales_income=income, distinct_buyers=buyers, selling_months=months, savings=savings,
            loans_repaid=repaid, loans_open=open_loans, seasons=seasons, harvest_kg=harvest_kg, harvest_consistency=consistency,
            ghala_receipts=receipts, storage_alerts=alerts, advice_follow_rate=follow, acres=acres, drought_rainfed=drought_rainfed,
            offtake_coverage=offtake, soil_condition=soil, account_age=age, activity_90d=activity, coming_harvest=coming,
        )
        # Assumed ground truth: repayment rises with verified income, savings, repaid loans,
        # steady harvests, following advice, contracts, good soil and a coming harvest; falls
        # with open loans, spoilage and rain-fed farming in drought areas.
        z = (
            -2.2
            + 0.30 * min(sales, 8)
            + 0.20 * math.log1p(income / 100_000)
            + 0.25 * min(buyers, 4)
            + 0.25 * math.log1p(savings / 100_000)
            + 0.60 * min(repaid, 3)
            - 0.60 * open_loans
            + 0.15 * min(seasons, 5)
            + 0.90 * (consistency - 0.5)
            + 0.15 * min(receipts, 5)
            - 0.50 * min(alerts, 3)
            + 1.40 * (follow - 0.5)
            + 0.15 * math.log1p(acres)
            - 0.80 * drought_rainfed
            + 1.20 * offtake
            + 0.90 * (soil - 0.6)
            + 0.15 * math.log1p(age / 30)
            + 0.20 * math.log1p(activity)
            + 1.00 * coming
            + 1.50 * (d - 0.5)
            + rng.normal(0, 0.7)
        )
        X.append(to_vector(raw))
        y.append(int(rng.random() < 1 / (1 + math.exp(-z))))
    return np.array(X, dtype=float), np.array(y, dtype=int)


@dataclass
class CreditModel:
    pipeline: Any
    card: dict[str, Any]


def train(real: list[tuple[list[float], int]] | None = None) -> CreditModel:
    X, y = _simulated_history(SIMULATED_SAMPLES)
    if real:
        X = np.vstack([X, np.array([r[0] for r in real], dtype=float)])
        y = np.concatenate([y, np.array([r[1] for r in real], dtype=int)])
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=7, stratify=y)
    pipeline = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
    pipeline.fit(X_train, y_train)
    proba = pipeline.predict_proba(X_test)[:, 1]
    card = {
        "name": "logistic regression",
        "version": MODEL_VERSION,
        "trained_on": int(len(y)),
        "real_outcomes": len(real or []),
        "simulated": True,
        "auc": round(float(roc_auc_score(y_test, proba)), 3),
        "accuracy": round(float(accuracy_score(y_test, proba >= THRESHOLD)), 3),
        "repaid_share": round(float(y.mean()), 3),
        "threshold": THRESHOLD,
    }
    return CreditModel(pipeline, card)


@lru_cache(maxsize=1)
def _cached(real_key: tuple) -> CreditModel:
    return train([(list(v), label) for v, label in real_key])


def get_model(real: list[tuple[list[float], int]]) -> CreditModel:
    """Trained once per set of real outcomes (retrains automatically when a loan is repaid)."""
    return _cached(tuple((tuple(v), label) for v, label in real))


def predict(model: CreditModel, raw: dict[str, float]) -> dict[str, Any]:
    """Probability of repaying plus each feature's push on the log-odds (vs an average farmer)."""
    x = np.array([to_vector(raw)], dtype=float)
    scaler, clf = model.pipeline.named_steps["standardscaler"], model.pipeline.named_steps["logisticregression"]
    z = scaler.transform(x)[0]
    contributions = clf.coef_[0] * z
    probability = float(model.pipeline.predict_proba(x)[0, 1])
    return {
        "probability": round(probability, 3),
        "eligible": probability >= THRESHOLD,
        "contributions": {name: round(float(c), 3) for name, c in zip(FEATURES, contributions)},
    }


