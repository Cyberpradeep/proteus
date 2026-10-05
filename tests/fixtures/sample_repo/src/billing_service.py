"""Sample billing service making direct HTTP calls."""

import httpx


def create_charge(amount: int) -> dict[str, str | int]:
    # Direct HTTP call candidate for discovery testing
    endpoint = "https://api.stripe.com/v1/payment_intents"
    headers = {"Authorization": "Bearer MOCK_KEY"}
    payload = {"amount": amount}
    with httpx.Client() as client:
        resp = client.post(endpoint, json=payload, headers=headers)
        return resp.json()  # type: ignore[no-any-return]
