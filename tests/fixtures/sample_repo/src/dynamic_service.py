"""Sample service with ambiguous dynamic URLs without known provider mapping."""

import requests


def call_dynamic_endpoint(endpoint_path: str, query: str) -> dict:
    """Dynamic URL construction that cannot be statically resolved."""
    dynamic_url = f"https://internal-gateway.corp/{endpoint_path}?q={query}"
    response = requests.get(dynamic_url)
    return response.json()
