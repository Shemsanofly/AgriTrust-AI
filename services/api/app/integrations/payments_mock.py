"""SIMULATED mobile-money payment. No money moves; returns a fake reference."""

import secrets


def simulate_payment(amount: float, currency: str = "TZS") -> dict:
    return {
        "reference": f"SIM-MM-{secrets.token_hex(4).upper()}",
        "amount": amount,
        "currency": currency,
        "status": "SUCCESS",
        "simulated": True,
    }
