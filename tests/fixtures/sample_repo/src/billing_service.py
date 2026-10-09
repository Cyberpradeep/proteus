"""Sample billing service making direct HTTP calls to Stripe API."""

import httpx
import requests

STRIPE_BASE = "https://api.stripe.com/v1"


def create_payment_intent(amount: int) -> dict:
    """Create a payment intent using direct httpx client."""
    headers = {"Authorization": "Bearer sk-test_98765432101234567890"}
    payload = {"amount": amount, "currency": "usd"}
    with httpx.Client() as client:
        resp = client.post(
            f"{STRIPE_BASE}/payment_intents",
            json=payload,
            headers=headers,
        )
        return resp.json()


def list_customers() -> list:
    """List Stripe customers using direct requests call."""
    headers = {"Authorization": "Bearer sk-test_98765432101234567890"}
    resp = requests.get(
        "https://api.stripe.com/v1/customers",
        headers=headers,
    )
    return resp.json()
